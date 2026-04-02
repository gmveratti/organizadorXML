# core/archive_handler.py
import os
import tempfile
import zipfile
import shutil
from collections import deque
from pathlib import Path

try:
    import rarfile
    # Tenta configurar o UnRAR no Windows nativo
    if os.name == 'nt':
        unrar_path = r"C:\Program Files\WinRAR\UnRAR.exe"
        if os.path.exists(unrar_path):
            rarfile.UNRAR_TOOL = unrar_path
    RAR_SUPPORT = True
except ImportError:
    RAR_SUPPORT = False

_ARCHIVE_EXTENSIONS = ('.rar', '.zip')

class ArchiveHandler:
    def __init__(self):
        # Cria a pasta temporária invisível para o trabalho pesado
        self.temp_dir = tempfile.mkdtemp(prefix="organizador_xml_")

    def _is_safe_path(self, extract_path: str, target_path: str) -> bool:
        """Evita ataques de Path Traversal (Zip Slip) e Zip Bombs."""
        abs_extract = os.path.abspath(extract_path)
        abs_target = os.path.abspath(target_path)
        return os.path.commonpath([abs_extract, abs_target]) == abs_extract

    def _extract_archive(self, file_path: str, extract_path: str, delete_after: bool = False) -> list:
        """Extrai um ficheiro e devolve uma lista de novos arquivos compactados encontrados dentro dele."""
        new_archives = []
        os.makedirs(extract_path, exist_ok=True)
        try:
            if file_path.lower().endswith(".rar") and RAR_SUPPORT:
                with rarfile.RarFile(file_path) as rf:
                    for member in rf.infolist():
                        if self._is_safe_path(extract_path, os.path.join(extract_path, member.filename)):
                            rf.extract(member, path=extract_path)
                            if member.filename.lower().endswith(_ARCHIVE_EXTENSIONS):
                                new_archives.append(os.path.join(extract_path, member.filename))
                                
            elif file_path.lower().endswith(".zip"):
                with zipfile.ZipFile(file_path) as zf:
                    for member in zf.infolist():
                        if self._is_safe_path(extract_path, os.path.join(extract_path, member.filename)):
                            zf.extract(member, path=extract_path)
                            if member.filename.lower().endswith(_ARCHIVE_EXTENSIONS):
                                new_archives.append(os.path.join(extract_path, member.filename))
            
            # Apaga o zip APENAS se for temporário, para não estourar o disco
            if delete_after:
                os.remove(file_path)
        except Exception:
            pass # Ficheiros corrompidos ou com senha são ignorados silenciosamente
            
        return new_archives

    def extract_and_find_xmls(self, source_path):
        """O cérebro: Extrai infinitamente e retorna a lista limpa de todos os XMLs."""
        xml_files = []
        
        # --- FASE 1: Extração Superficial ---
        if os.path.isfile(source_path):
            if source_path.lower().endswith('.xml'):
                return [source_path]
            
            if source_path.lower().endswith(_ARCHIVE_EXTENSIONS):
                # Extrai o arquivo raiz para a temp_dir (delete_after=False preserva o original!)
                self._extract_archive(source_path, self.temp_dir, delete_after=False)
                
        elif os.path.isdir(source_path):
            for root, _, files in os.walk(source_path):
                for file in files:
                    if file.lower().endswith(_ARCHIVE_EXTENSIONS):
                        file_path = os.path.join(root, file)
                        extract_path = os.path.join(self.temp_dir, file[:-4])
                        # Extrai (delete_after=False preserva o original!)
                        self._extract_archive(file_path, extract_path, delete_after=False)

        # --- FASE 2: Motor Recursivo (Descascando a cebola na pasta temporária) ---
        archive_queue = deque()

        # Alimenta a fila com os primeiros ZIPs/RARs que apareceram na extração inicial
        for root, _, files in os.walk(self.temp_dir):
            for f in files:
                if f.lower().endswith(_ARCHIVE_EXTENSIONS):
                    archive_queue.append(os.path.join(root, f))

        # Roda infinitamente até não sobrar nenhum arquivo compactado dentro de outro
        while archive_queue:
            file_path = archive_queue.popleft()
            if not os.path.exists(file_path):
                continue
            extract_path = os.path.dirname(file_path)
            
            # delete_after=True apaga o zip temporário após extraí-lo
            new_archives = self._extract_archive(file_path, extract_path, delete_after=True)
            archive_queue.extend(new_archives)

        # --- FASE 3: Captura de XMLs ---
        # 1. Usar o recurso moderno do Python (rglob) para varrer todos os subdiretórios da temp_dir
        for p in Path(self.temp_dir).rglob("*.xml"):
            xml_files.append(str(p))
            
        # 2. Resgatar XMLs que já estavam soltos e visíveis na origem, se for uma pasta
        if os.path.isdir(source_path):
            for p in Path(source_path).rglob("*.xml"):
                xml_files.append(str(p))
                
        return xml_files

    def cleanup(self):
        """Apaga os rastros temporários."""
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
