import os
import re
import queue
import time
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core.worker import ProcessingWorker

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def format_path(input_path):
    clean_path = input_path.strip('"\'')
    if os.name == 'nt':
        return os.path.normpath(clean_path)
    if re.match(r'^[a-zA-Z]:[\\/]', clean_path):
        drive_letter = clean_path[0].lower()
        rest_of_path = clean_path[2:].replace('\\', '/')
        return f"/mnt/{drive_letter}{rest_of_path}"
    return clean_path.replace('\\', '/')

class XMLOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Organizador de XML Fiscais")
        self.root.geometry("600x350") # Janela menor novamente
        self.root.resizable(False, False)
        
        # Define o ícone da janela
        try:
            icon_path = resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass # Ignora se não conseguir carregar o ícone
        
        self.queue = queue.Queue()
        self.is_processing = False
        self.start_time = 0
        
        self.setup_ui()
        self.check_queue() 

    def setup_ui(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Configuração de Pastas", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 10))
        
        # Origem (Agora com dois botões)
        ttk.Label(main_frame, text="Pasta Origem ou Arquivo ZIP/RAR:").pack(anchor=tk.W)
        src_frame = ttk.Frame(main_frame)
        src_frame.pack(fill=tk.X, pady=(0, 10))
        self.src_entry = ttk.Entry(src_frame)
        self.src_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        # Botões divididos
        ttk.Button(src_frame, text="Pasta...", width=8, command=self.browse_src_dir).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(src_frame, text="Ficheiro...", width=10, command=self.browse_src_file).pack(side=tk.LEFT)

        # Destino
        ttk.Label(main_frame, text="Pasta Destino (onde serão organizados):").pack(anchor=tk.W)
        dst_frame = ttk.Frame(main_frame)
        dst_frame.pack(fill=tk.X, pady=(0, 15))
        self.dst_entry = ttk.Entry(dst_frame)
        self.dst_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(dst_frame, text="Procurar...", width=10, command=self.browse_dst).pack(side=tk.RIGHT)

        ttk.Label(main_frame, text="Organizar por:", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 5))
        
        self.mode_var = tk.StringVar(value="year_month")
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Radiobutton(options_frame, text="Mês e Ano", variable=self.mode_var, value="year_month").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(options_frame, text="Somente Ano", variable=self.mode_var, value="year").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(options_frame, text="Somente Mês", variable=self.mode_var, value="month").pack(side=tk.LEFT)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 20))
        self.lbl_count = ttk.Label(status_frame, text="A aguardar ficheiros...")
        self.lbl_count.pack(side=tk.LEFT)
        self.lbl_time = ttk.Label(status_frame, text="Tempo: 00:00")
        self.lbl_time.pack(side=tk.RIGHT)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        self.btn_cancel = ttk.Button(btn_frame, text="Cancelar / Fechar", command=self.root.destroy)
        self.btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.btn_start = ttk.Button(btn_frame, text="Iniciar Organização", command=self.start_processing)
        self.btn_start.pack(side=tk.RIGHT)

    def browse_src_dir(self):
        folder = filedialog.askdirectory(title="Selecione a pasta de Origem")
        if folder:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, folder)

    def browse_src_file(self):
        filetypes = (("Arquivos Compactados", "*.zip *.rar"), ("Todos", "*.*"))
        filepath = filedialog.askopenfilename(title="Selecione o ficheiro ZIP/RAR", filetypes=filetypes)
        if filepath:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, filepath)

    def browse_dst(self):
        folder = filedialog.askdirectory(title="Selecione a pasta de Destino")
        if folder:
            self.dst_entry.delete(0, tk.END)
            self.dst_entry.insert(0, folder)

    def start_processing(self):
        if self.is_processing:
            return

        src_dir = format_path(self.src_entry.get())
        dst_dir = format_path(self.dst_entry.get())
        mode = self.mode_var.get()

        if not src_dir or not dst_dir:
            messagebox.showwarning("Atenção", "Por favor, preencha as origens e destinos.")
            return

        self.is_processing = True
        self.start_time = time.time()
        self.btn_start.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.DISABLED)
        self.src_entry.config(state=tk.DISABLED)
        self.dst_entry.config(state=tk.DISABLED)

        threading.Thread(target=ProcessingWorker(src_dir, dst_dir, mode, self.queue).run, daemon=True).start()

    def check_queue(self):
        if self.is_processing:
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            self.lbl_time.config(text=f"Tempo: {mins:02d}:{secs:02d}")

        while True:
            try:
                msg = self.queue.get_nowait()
                msg_type = msg[0]

                if msg_type == "START_EXTRACTION":
                    self.start_time = time.time()
                    self.progress_bar.config(mode='indeterminate')
                    self.progress_bar.start(15) # Inicia o vai e vem!
                    self.lbl_count.config(text="A extrair e varrer diretórios...")

                elif msg_type == "START_PROCESSING":
                    total = msg[1]
                    self.progress_bar.stop()
                    self.progress_bar.config(mode='determinate', maximum=total)
                    self.progress_var.set(0)
                    self.lbl_count.config(text=f"Ficheiros: 0 / {total} (0.0%)")

                elif msg_type == "PROGRESS":
                    current, total = msg[1], msg[2]
                    self.progress_var.set(current)
                    percent = (current / total) * 100
                    self.lbl_count.config(text=f"Ficheiros: {current} / {total} ({percent:.1f}%)")

                elif msg_type == "NO_FILES":
                    messagebox.showinfo("Aviso", "Nenhum ficheiro XML encontrado.")
                    self.reset_ui()

                elif msg_type == "DONE":
                    total, sucesso, eventos, erros = msg[1], msg[2], msg[3], msg[4]
                    msg_final = f"Organização Concluída!\n\nTotal de Ficheiros: {total}\nSucesso: {sucesso}\nEventos: {eventos}\nErros: {erros}"
                    messagebox.showinfo("Sucesso", msg_final)
                    self.reset_ui()

                elif msg_type == "FATAL_ERROR":
                    erro = msg[1]
                    messagebox.showerror("Erro Inesperado", f"Ocorreu um erro crítico:\n{erro}")
                    self.reset_ui()

            except queue.Empty:
                break

        self.root.after(100, self.check_queue)

    def reset_ui(self):
        self.is_processing = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_cancel.config(state=tk.NORMAL)
        self.src_entry.config(state=tk.NORMAL)
        self.dst_entry.config(state=tk.NORMAL)
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
        self.progress_var.set(0)
        self.lbl_count.config(text="A aguardar ficheiros...")
