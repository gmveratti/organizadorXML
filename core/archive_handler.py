import os
import tempfile
import zipfile
from collections import deque
from pathlib import Path

try:
    import rarfile
    if os.name == 'nt':
        unrar_path = r"C:\Program Files\WinRAR\UnRAR.exe"
        if Path(unrar_path).exists():
            rarfile.UNRAR_TOOL = unrar_path
    RAR_SUPPORT = True
except ImportError:
    rarfile = None
    RAR_SUPPORT = False

_ARCHIVE_EXTENSIONS = ('.rar', '.zip')
MAX_DEPTH = 5  # Proteção contra Zip Bombs

class ArchiveHandler:
    def __init__(self):
        # Utiliza o gerenciador de contexto do Python para garantir a autolimpeza na memória
        self._temp_dir_obj = tempfile.TemporaryDirectory(prefix="organizador_xml_")
        self.temp_dir = Path(self._temp_dir_obj.name)

    def _is_safe_path(self, extract_path: Path, target_path: Path) -> bool:
        """Evita ataques de Path Traversal (Zip Slip) e Zip Bombs."""
        try:
            target_path.resolve().relative_to(extract_path.resolve())
            return True
        except ValueError:
            return False

    def _extract_archive(self, file_path: Path, extract_path: Path, delete_after: bool = False) -> list:
        new_archives = []
        extract_path.mkdir(parents=True, exist_ok=True)
        try:
            if file_path.suffix.lower() == ".rar" and RAR_SUPPORT:
                with rarfile.RarFile(file_path) as rf: # type: ignore
                    for member in rf.infolist():
                        target = extract_path / member.filename
                        if self._is_safe_path(extract_path, target):
                            rf.extract(member, path=extract_path)
                            if target.suffix.lower() in _ARCHIVE_EXTENSIONS:
                                new_archives.append(target)
                                
            elif file_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(file_path) as zf:
                    for member in zf.infolist():
                        target = extract_path / member.filename
                        if self._is_safe_path(extract_path, target):
                            zf.extract(member, path=extract_path)
                            if target.suffix.lower() in _ARCHIVE_EXTENSIONS:
                                new_archives.append(target)
            
            if delete_after:
                file_path.unlink(missing_ok=True)
                
        except (zipfile.BadZipFile, RuntimeError):
            pass  # Exceções silenciadas especificamente para arquivos corrompidos
        except Exception as e:
            if RAR_SUPPORT and isinstance(e, rarfile.Error): # type: ignore
                pass
            else:
                raise
            
        return new_archives

    def extract_and_find_xmls(self, source_path_str: str):
        """Usa geradores (yield) para reduzir o consumo de memória RAM na Thread."""
        source_path = Path(source_path_str)
        
        # FASE 1: Extração Superficial
        if source_path.is_file():
            if source_path.suffix.lower() == '.xml':
                yield str(source_path)
            elif source_path.suffix.lower() in _ARCHIVE_EXTENSIONS:
                self._extract_archive(source_path, self.temp_dir, delete_after=False)
                
        elif source_path.is_dir():
            for file in source_path.rglob("*"):
                if file.suffix.lower() in _ARCHIVE_EXTENSIONS:
                    extract_path = self.temp_dir / file.stem
                    self._extract_archive(file, extract_path, delete_after=False)

        # FASE 2: Fila com Limite de Profundidade
        archive_queue = deque()
        for file in self.temp_dir.rglob("*"):
            if file.suffix.lower() in _ARCHIVE_EXTENSIONS:
                archive_queue.append((file, 1))

        while archive_queue:
            file_path, depth = archive_queue.popleft()
            
            if not file_path.exists() or depth >= MAX_DEPTH:
                continue
                
            extract_path = file_path.parent
            new_archives = self._extract_archive(file_path, extract_path, delete_after=True)
            for na in new_archives:
                archive_queue.append((na, depth + 1))

        # FASE 3: Envio de Resultados (Generator)
        for p in self.temp_dir.rglob("*.xml"):
            yield str(p)
            
        if source_path.is_dir():
            for p in source_path.rglob("*.xml"):
                yield str(p)

    def cleanup(self):
        """Limpeza forçada invocada pelo final do worker."""
        self._temp_dir_obj.cleanup()
