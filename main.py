import os
import shutil
import re
import time
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed

# Regex para extrair Ano (grupo 1) e Mês (grupo 2)
PATTERN = re.compile(rb'<(?:dh|d)Emi>(\d{4})-(\d{2})')

def format_path(input_path):
    """Formata o caminho dependendo se está no Windows ou no WSL."""
    clean_path = input_path.strip('"\'')
    
    # Se estiver rodando nativamente no Windows, mantém o caminho do Windows
    if os.name == 'nt':
        return os.path.normpath(clean_path)
        
    # Se estiver no Linux (WSL) e receber um caminho com letra de unidade (ex: C:\)
    if re.match(r'^[a-zA-Z]:[\\/]', clean_path):
        drive_letter = clean_path[0].lower()
        rest_of_path = clean_path[2:].replace('\\', '/')
        return f"/mnt/{drive_letter}{rest_of_path}"
        
    return clean_path.replace('\\', '/')

def safe_move(src_path, dest_dir, file_name):
    """Move o ficheiro e previne sobrescrita caso existam nomes duplicados em subpastas diferentes."""
    os.makedirs(dest_dir, exist_ok=True)
    target_path = os.path.join(dest_dir, file_name)
    
    if os.path.exists(target_path):
        base, ext = os.path.splitext(file_name)
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
            counter += 1
            
    shutil.move(src_path, target_path)

def process_single_file(file_path, dest_dir, error_dir, mode):
    """Função worker para processar um único ficheiro."""
    file_name = os.path.basename(file_path)
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            
        match = PATTERN.search(content)

        if match:
            year = match.group(1).decode('ascii')
            month = match.group(2).decode('ascii')
            
            # Lógica de criação de pastas
            if mode == 'year_month':
                # Cria a pasta do ano, e dentro dela a pasta ano.mês
                target_dir = os.path.join(dest_dir, year, f"{year}.{month}")
            elif mode == 'year':
                # Cria apenas a pasta do ano
                target_dir = os.path.join(dest_dir, year)
            elif mode == 'month':
                # Cria a pasta mês.ano diretamente na raiz de destino
                target_dir = os.path.join(dest_dir, f"{month}.{year}")
                
            safe_move(file_path, target_dir, file_name)
            return 'SUCCESS', None
            
        else:
            safe_move(file_path, error_dir, file_name)
            return 'NOT_FOUND', f"{file_name}: Tag de data de emissão não encontrada."
            
    except Exception as e:
        try:
            safe_move(file_path, error_dir, file_name)
        except Exception as move_error:
            return 'ERROR', f"{file_name}: Erro leitura ({str(e)}) e falha ao mover ({str(move_error)})."
        return 'ERROR', f"{file_name}: Erro de leitura/ficheiro corrompido - {str(e)}"

class XMLOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Organizador de XML Fiscais")
        self.root.geometry("600x420")
        self.root.resizable(False, False)
        
        self.queue = queue.Queue()
        self.is_processing = False
        self.start_time = 0
        
        self.setup_ui()
        self.check_queue() 

    def setup_ui(self):
        style = ttk.Style()
        style.configure("TLabel", font=("Arial", 10))
        style.configure("TButton", font=("Arial", 10))
        style.configure("TRadiobutton", font=("Arial", 10))
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Seção de Diretórios ---
        ttk.Label(main_frame, text="Configuração de Pastas", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(main_frame, text="Pasta Origem (onde estão os XMLs):").pack(anchor=tk.W)
        src_frame = ttk.Frame(main_frame)
        src_frame.pack(fill=tk.X, pady=(0, 10))
        self.src_entry = ttk.Entry(src_frame)
        self.src_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(src_frame, text="Procurar...", command=self.browse_src).pack(side=tk.RIGHT)

        ttk.Label(main_frame, text="Pasta Destino (onde serão organizados):").pack(anchor=tk.W)
        dst_frame = ttk.Frame(main_frame)
        dst_frame.pack(fill=tk.X, pady=(0, 15))
        self.dst_entry = ttk.Entry(dst_frame)
        self.dst_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(dst_frame, text="Procurar...", command=self.browse_dst).pack(side=tk.RIGHT)

        # --- Seção de Opções ---
        ttk.Label(main_frame, text="Organizar por:", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 5))
        
        self.mode_var = tk.StringVar(value="year_month")
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Radiobutton(options_frame, text="Mês e Ano (Ex: 2022/2022.06)", variable=self.mode_var, value="year_month").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(options_frame, text="Somente Ano (Ex: 2022)", variable=self.mode_var, value="year").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(options_frame, text="Somente Mês (Ex: 06.2022)", variable=self.mode_var, value="month").pack(side=tk.LEFT)

        # --- Progresso ---
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 20))
        self.lbl_count = ttk.Label(status_frame, text="Ficheiros: 0 / 0 (0%)")
        self.lbl_count.pack(side=tk.LEFT)
        self.lbl_time = ttk.Label(status_frame, text="Tempo: 00:00")
        self.lbl_time.pack(side=tk.RIGHT)

        # --- Botões de Ação ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        self.btn_cancel = ttk.Button(btn_frame, text="Cancelar / Fechar", command=self.root.destroy)
        self.btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.btn_start = ttk.Button(btn_frame, text="Iniciar Organização", command=self.start_processing)
        self.btn_start.pack(side=tk.RIGHT)

    def browse_src(self):
        folder = filedialog.askdirectory(title="Selecione a pasta de Origem")
        if folder:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, folder)

    def browse_dst(self):
        folder = filedialog.askdirectory(title="Selecione a pasta de Destino")
        if folder:
            self.dst_entry.delete(0, tk.END)
            self.dst_entry.insert(0, folder)

    def start_processing(self):
        if self.is_processing:
            return

        # Agora usando a função corrigida que entende o ambiente atual
        src_dir = format_path(self.src_entry.get())
        dst_dir = format_path(self.dst_entry.get())
        mode = self.mode_var.get()

        if not src_dir or not dst_dir:
            messagebox.showwarning("Atenção", "Por favor, preencha as pastas de origem e destino.")
            return
        if not os.path.isdir(src_dir):
            messagebox.showerror("Erro", f"A pasta de origem não existe ou é inválida:\n{src_dir}")
            return

        confirm = messagebox.askyesno("Confirmar", "Deseja iniciar a organização dos ficheiros?\nEsta ação moverá os XMLs de lugar.")
        if not confirm:
            return

        self.is_processing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.DISABLED)
        self.src_entry.config(state=tk.DISABLED)
        self.dst_entry.config(state=tk.DISABLED)

        threading.Thread(target=self.process_files_thread, args=(src_dir, dst_dir, mode), daemon=True).start()

    def process_files_thread(self, src_dir, dst_dir, mode):
        try:
            error_dir = os.path.join(dst_dir, 'xmls_com_erro')
            xml_files = []

            for root, dirs, files in os.walk(src_dir):
                for file in files:
                    if file.lower().endswith('.xml'):
                        xml_files.append(os.path.join(root, file))

            total_files = len(xml_files)
            if total_files == 0:
                self.queue.put(("NO_FILES",))
                return

            self.queue.put(("START", total_files))
            
            moved_count = 0
            error_logs = []
            processed_count = 0

            workers = os.cpu_count() * 2

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(process_single_file, path, dst_dir, error_dir, mode): path for path in xml_files}

                for future in as_completed(futures):
                    status, log_msg = future.result()
                    
                    if status == 'SUCCESS':
                        moved_count += 1
                    else:
                        error_logs.append(log_msg)
                        
                    processed_count += 1
                    
                    if processed_count % 50 == 0 or processed_count == total_files:
                        self.queue.put(("PROGRESS", processed_count, total_files))

            if error_logs:
                os.makedirs(error_dir, exist_ok=True)
                with open(os.path.join(error_dir, 'log_erros.txt'), 'w', encoding='utf-8') as log_file:
                    log_file.write(f"Total de erros: {len(error_logs)}\n" + "-"*40 + "\n")
                    for log in error_logs:
                        log_file.write(log + '\n')

            for root, dirs, files in os.walk(src_dir, topdown=False):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        os.rmdir(dir_path) 
                    except OSError:
                        pass 

            self.queue.put(("DONE", total_files, moved_count, len(error_logs)))
            
        except Exception as e:
            self.queue.put(("FATAL_ERROR", str(e)))

    def check_queue(self):
        if self.is_processing:
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            self.lbl_time.config(text=f"Tempo: {mins:02d}:{secs:02d}")

        while True:
            try:
                msg = self.queue.get_nowait()
                msg_type = msg[0]

                if msg_type == "START":
                    self.start_time = time.time()
                    total = msg[1]
                    self.progress_bar['maximum'] = total
                    self.lbl_count.config(text=f"Ficheiros: 0 / {total} (0.0%)")

                elif msg_type == "PROGRESS":
                    current, total = msg[1], msg[2]
                    self.progress_var.set(current)
                    percent = (current / total) * 100
                    self.lbl_count.config(text=f"Ficheiros: {current} / {total} ({percent:.1f}%)")

                elif msg_type == "NO_FILES":
                    messagebox.showinfo("Aviso", "Nenhum ficheiro XML encontrado nas pastas selecionadas.")
                    self.reset_ui()

                elif msg_type == "DONE":
                    total, sucesso, erros = msg[1], msg[2], msg[3]
                    msg_final = f"Organização Concluída!\n\nTotal de Ficheiros: {total}\nProcessados com Sucesso: {sucesso}\nErros / Ignorados: {erros}"
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
        self.progress_var.set(0)
        self.lbl_count.config(text="Ficheiros: 0 / 0 (0%)")

if __name__ == "__main__":
    root = tk.Tk()
    app = XMLOrganizerApp(root)
    root.mainloop()