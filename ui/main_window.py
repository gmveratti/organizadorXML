import os
import re
import queue
import sys
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
    """Formata o caminho dependendo se está no Windows ou no WSL."""
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
        self.root.title("Organizador de XML Fiscais v3")
        self.root.geometry("650x550")
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
        
        self.setup_ui()
        self.check_queue()

    def setup_ui(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Arial", 11, "bold"))

        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Pastas
        ttk.Label(main_frame, text="Pasta Origem (XMLs soltos ou em ZIP/RAR):", style="Header.TLabel").pack(anchor=tk.W)
        src_frame = ttk.Frame(main_frame)
        src_frame.pack(fill=tk.X, pady=(0, 10))
        self.src_entry = ttk.Entry(src_frame)
        self.src_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(src_frame, text="Procurar...", command=self.browse_src).pack(side=tk.RIGHT)

        ttk.Label(main_frame, text="Pasta Destino (Organização final):", style="Header.TLabel").pack(anchor=tk.W)
        dst_frame = ttk.Frame(main_frame)
        dst_frame.pack(fill=tk.X, pady=(0, 15))
        self.dst_entry = ttk.Entry(dst_frame)
        self.dst_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(dst_frame, text="Procurar...", command=self.browse_dst).pack(side=tk.RIGHT)

        # Opções
        ttk.Label(main_frame, text="Organizar por:", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 5))
        self.mode_var = tk.StringVar(value="year_month")
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Radiobutton(options_frame, text="Mês e Ano", variable=self.mode_var, value="year_month").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(options_frame, text="Somente Ano", variable=self.mode_var, value="year").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(options_frame, text="Somente Mês", variable=self.mode_var, value="month").pack(side=tk.LEFT)

        # Caixa de Logs (estilo terminal escuro)
        ttk.Label(main_frame, text="Estado do Processamento:", style="Header.TLabel").pack(anchor=tk.W)
        self.log_text = tk.Text(main_frame, height=10, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.X, pady=(0, 10))

        # Progresso
        self.status_lbl = ttk.Label(main_frame, text="A aguardar início...")
        self.status_lbl.pack(anchor=tk.W)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(5, 15))

        # Botões
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        self.btn_cancel = ttk.Button(btn_frame, text="Sair", command=self.root.destroy)
        self.btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
        self.btn_start = ttk.Button(btn_frame, text="Iniciar Organização", command=self.start_processing)
        self.btn_start.pack(side=tk.RIGHT)

    def browse_src(self):
        folder = filedialog.askdirectory()
        if folder:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, folder)

    def browse_dst(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dst_entry.delete(0, tk.END)
            self.dst_entry.insert(0, folder)

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_processing(self):
        if self.is_processing: return
        
        src_dir = format_path(self.src_entry.get())
        dst_dir = format_path(self.dst_entry.get())
        
        if not src_dir or not dst_dir:
            messagebox.showwarning("Aviso", "Preencha as pastas de origem e destino.")
            return

        self.is_processing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.DISABLED)
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.progress_var.set(0)

        worker = ProcessingWorker(src_dir, dst_dir, self.mode_var.get(), self.queue)
        worker.start()

    def check_queue(self):
        while True:
            try:
                msg = self.queue.get_nowait()
                msg_type = msg[0]

                if msg_type == "LOG":
                    self.log(msg[1])
                elif msg_type == "PHASE":
                    if msg[1] == "EXTRACTION":
                        self.status_lbl.config(text="A descompactar e procurar ficheiros...")
                        self.progress_bar.config(mode='indeterminate')
                        self.progress_bar.start(10)
                    elif msg[1] == "PROCESSING":
                        self.progress_bar.stop()
                        self.progress_bar.config(mode='determinate', maximum=msg[2])
                        self.progress_var.set(0)
                        self.status_lbl.config(text=f"A organizar 0 / {msg[2]} ficheiros...")
                elif msg_type == "PROGRESS":
                    self.progress_var.set(msg[1])
                    total = self.progress_bar['maximum']
                    self.status_lbl.config(text=f"A organizar {msg[1]} / {int(total)} ficheiros...")
                elif msg_type == "ERROR":
                    messagebox.showerror("Erro Fatal", msg[1])
                    self.reset_ui()
                elif msg_type == "DONE":
                    total, sucesso, eventos, erros, tempo = msg[1], msg[2], msg[3], msg[4], msg[5]
                    self.progress_bar.stop()
                    self.progress_var.set(self.progress_bar['maximum'] if total > 0 else 0)
                    self.status_lbl.config(text="Operação Finalizada.")
                    
                    resumo = f"Resumo da Operação:\n\nTempo: {tempo:.1f}s\nTotal de Ficheiros: {total}\nSucesso (Notas): {sucesso}\nEventos/Cancelamentos: {eventos}\nErros/Corrompidos: {erros}"
                    messagebox.showinfo("Concluído", resumo)
                    self.reset_ui()
            except queue.Empty:
                break
        self.root.after(100, self.check_queue)

    def reset_ui(self):
        self.is_processing = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_cancel.config(state=tk.NORMAL)
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
        self.progress_var.set(0)
        self.status_lbl.config(text="A aguardar início...")
