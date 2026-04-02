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
        self.daemon = True

    def run(self):
        try:
            self.queue.put(("START_EXTRACTION",))
            
            archive_handler = ArchiveHandler()
            xml_files = archive_handler.extract_and_find_xmls(self.source_dir)
            
            total_files = len(xml_files)
            if total_files == 0:
                self.queue.put(("NO_FILES",))
                archive_handler.cleanup()
                return
                
            self.queue.put(("START_PROCESSING", total_files))
            
            moved_count = 0
            event_count = 0
            error_count = 0
            processed = 0
            
            workers = os.cpu_count() * 2
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(organize_file, path, self.dest_dir, self.mode): path for path in xml_files}
                
                for future in as_completed(futures):
                    status, _ = future.result() # Ignoramos as mensagens de log
                    
                    if status == 'SUCCESS':
                        moved_count += 1
                    elif status == 'EVENT':
                        event_count += 1
                    else:
                        error_count += 1
                            
                    processed += 1
                    # Otimização: atualiza a GUI a cada 50 arquivos
                    if processed % 50 == 0 or processed == total_files:
                        self.queue.put(("PROGRESS", processed, total_files))
            
            archive_handler.cleanup()
            
            # Limpa pastas antigas APENAS se a origem for uma pasta (e não um ZIP solto)
            if os.path.isdir(self.source_dir):
                for root, dirs, files in os.walk(self.source_dir, topdown=False):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        try:
                            os.rmdir(dir_path)
                        except OSError:
                            pass
            
            self.queue.put(("DONE", total_files, moved_count, event_count, error_count))
            
        except Exception as e:
            self.queue.put(("FATAL_ERROR", str(e)))
