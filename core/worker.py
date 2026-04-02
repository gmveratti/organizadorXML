import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.archive_handler import ArchiveHandler
from core.organizer import organize_file
from pathlib import Path

class ProcessingWorker(threading.Thread):
    def __init__(self, source_dir, dest_dir, mode, msg_queue):
        super().__init__()
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.mode = mode
        self.queue = msg_queue
        self.daemon = True
        self.is_cancelled = False  # Flag para parada segura

    def stop(self):
        self.is_cancelled = True

    def run(self):
        archive_handler = None
        try:
            self.queue.put(("START_EXTRACTION",))
            archive_handler = ArchiveHandler()
            
            # Consome o gerador (Obrigatório para desenhar a barra de progresso Tkinter)
            xml_files = list(archive_handler.extract_and_find_xmls(self.source_dir))
            
            total_files = len(xml_files)
            if total_files == 0:
                self.queue.put(("NO_FILES",))
                return
                
            self.queue.put(("START_PROCESSING", total_files))
            
            moved_count = event_count = error_count = processed = 0
            error_logs = []
            
            # PREVENÇÃO I/O THRASHING: Capping conservador para manipulação de disco
            workers = min(8, (os.cpu_count() or 1) + 4)
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(organize_file, path, self.dest_dir, self.mode): path for path in xml_files}
                
                for future in as_completed(futures):
                    if self.is_cancelled:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    status, log_msg = future.result() 
                    
                    if status == 'SUCCESS':
                        moved_count += 1
                    elif status == 'EVENT':
                        event_count += 1
                    else:
                        error_count += 1
                        if log_msg:
                            error_logs.append(log_msg)
                            
                    processed += 1
                    if processed % 50 == 0 or processed == total_files:
                        self.queue.put(("PROGRESS", processed, total_files))

            if self.is_cancelled:
                return

            # GERAÇÃO DO ARQUIVO FÍSICO DE LOG DE ERROS E ALERTAS
            if error_logs:
                error_dir = Path(self.dest_dir) / 'xmls_com_erro'
                error_dir.mkdir(exist_ok=True)
                with open(error_dir / 'log_erros.txt', 'w', encoding='utf-8') as log_file:
                    log_file.write(f"Total de erros: {len(error_logs)}\n" + "-"*40 + "\n")
                    for log in error_logs:
                        log_file.write(log + '\n')
            
            # Limpeza moderna com pathlib (remove pastas vazias na origem)
            src_path = Path(self.source_dir)
            if src_path.is_dir():
                for dir_path in sorted(src_path.rglob('*'), reverse=True):
                    if dir_path.is_dir() and not any(dir_path.iterdir()):
                        try: dir_path.rmdir()
                        except OSError: pass
            
            self.queue.put(("DONE", total_files, moved_count, event_count, error_count))
            
        except Exception as e:
            self.queue.put(("FATAL_ERROR", str(e)))
        finally:
            if archive_handler:
                archive_handler.cleanup()  # Garantia de eliminação do vazamento
