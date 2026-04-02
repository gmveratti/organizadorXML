import os
import tempfile
import zipfile
import shutil
import uuid

try:
    import rarfile
    RAR_SUPPORT = True
except ImportError:
    rarfile = None
    RAR_SUPPORT = False

class ArchiveHandler:
    def __init__(self):
        # Cria pasta temporária
        self.temp_dir = tempfile.mkdtemp(prefix="organizador_xml_")

    def _extract_archive(self, file_path):
        """Lógica interna para extrair um arquivo específico e retorna a pasta de destino."""
        unique_id = str(uuid.uuid4())[:8]
        extract_path = os.path.join(self.temp_dir, f"{os.path.basename(file_path)[:-4]}_{unique_id}")
        try:
            if file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
            elif file_path.lower().endswith('.rar') and RAR_SUPPORT:
                with rarfile.RarFile(file_path, 'r') as rar_ref: # type: ignore
                    rar_ref.extractall(extract_path)
            return extract_path
        except Exception:
            return None # Ignora silenciosamente arquivos corrompidos na extração

    def extract_and_find_xmls(self, source_path):
        """Extrai e busca XMLs recursivamente, aceitando tanto arquivo único quanto pasta inteira."""
        xml_files = []
        archives_to_process = []
        extracted_archives = set()
        
        # 1. População Inicial da Fila de Arquivos
        if os.path.isfile(source_path):
            if source_path.lower().endswith(('.zip', '.rar')):
                archives_to_process.append(os.path.abspath(source_path))
        elif os.path.isdir(source_path):
            for root, _, files in os.walk(source_path):
                for file in files:
                    if file.lower().endswith(('.zip', '.rar')):
                        archives_to_process.append(os.path.abspath(os.path.join(root, file)))

        # 2. Processamento Recursivo de Extração
        while archives_to_process:
            current_archive = archives_to_process.pop(0)
            
            if current_archive in extracted_archives:
                continue
                
            extract_path = self._extract_archive(current_archive)
            extracted_archives.add(current_archive)
            
            if extract_path and os.path.exists(extract_path):
                # Verifica a pasta extraída procurando por novos zips/rars aninhados
                for root, _, files in os.walk(extract_path):
                    for file in files:
                        if file.lower().endswith(('.zip', '.rar')):
                            new_archive = os.path.abspath(os.path.join(root, file))
                            if new_archive not in extracted_archives and new_archive not in archives_to_process:
                                archives_to_process.append(new_archive)

        # 3. Varredura final pelos arquivos XML extraídos
        dirs_to_scan = [self.temp_dir]
        if os.path.isdir(source_path):
            dirs_to_scan.append(source_path)
            
        for d in dirs_to_scan:
            for root, _, files in os.walk(d):
                for file in files:
                    if file.lower().endswith('.xml'):
                        xml_files.append(os.path.join(root, file))
                        
        # Adiciona suporte se o usuário escolher sem querer apenas 1 XML solto
        if os.path.isfile(source_path) and source_path.lower().endswith('.xml'):
            if source_path not in xml_files:
                xml_files.append(source_path)
            
        return xml_files

    def cleanup(self):
        """Remove a diretoria temporária."""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass
