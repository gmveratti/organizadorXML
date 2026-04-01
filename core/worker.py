import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.archive_handler import ArchiveHandler
from core.organizer import organize_file

class ProcessingWorker(threading.Thread):
    def __init__(self, source_dir, dest_dir, mode, msg_queue):
        super().__init__()
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.mode = mode
        self.queue = msg_queue
        self.daemon = True # A thread morre se o programa for fechado

    def run(self):
        try:
            self.queue.put(("LOG", "A iniciar o motor de extração e varredura..."))
            start_time = time.time()
            
            archive_handler = ArchiveHandler()
            
            # Função para enviar os logs da extração para a interface
            def log_callback(msg):
                self.queue.put(("LOG", msg))
                
            # --- FASE 1: Extração e Busca ---
            self.queue.put(("PHASE", "EXTRACTION"))
            xml_files = archive_handler.extract_and_find_xmls(self.source_dir, log_callback)
            
            total_files = len(xml_files)
            if total_files == 0:
                self.queue.put(("LOG", "Nenhum ficheiro XML encontrado. A encerrar operação."))
                self.queue.put(("DONE", 0, 0, 0, 0, 0))
                archive_handler.cleanup()
                return
                
            self.queue.put(("LOG", f"> Encontrados {total_files} ficheiros XML no total."))
            self.queue.put(("LOG", "A iniciar a organização das notas..."))
            self.queue.put(("PHASE", "PROCESSING", total_files))
            
            # --- FASE 2: Organização ---
            moved_count = 0
            event_count = 0
            error_count = 0
            processed = 0
            
            workers = os.cpu_count() * 2
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(organize_file, path, self.dest_dir, self.mode): path for path in xml_files}
                
                for future in as_completed(futures):
                    status, log_msg = future.result()
                    
                    if status == 'SUCCESS':
                        moved_count += 1
                    elif status == 'EVENT':
                        event_count += 1
                    else:
                        error_count += 1
                        if log_msg:
                            self.queue.put(("LOG", f"[ERRO/AVISO] {log_msg}"))
                            
                    processed += 1
                    # Atualiza a barra de progresso
                    if processed % 10 == 0 or processed == total_files:
                        self.queue.put(("PROGRESS", processed))
            
            # --- FASE 3: Limpeza ---
            self.queue.put(("LOG", "A limpar ficheiros temporários da extração..."))
            archive_handler.cleanup()
            
            # Limpeza de pastas vazias na origem
            for root, dirs, files in os.walk(self.source_dir, topdown=False):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        os.rmdir(dir_path)
                    except OSError:
                        pass
            
            elapsed = time.time() - start_time
            self.queue.put(("LOG", f"Operação concluída com sucesso em {elapsed:.2f} segundos!"))
            self.queue.put(("DONE", total_files, moved_count, event_count, error_count, elapsed))
            
        except Exception as e:
            self.queue.put(("ERROR", str(e)))
