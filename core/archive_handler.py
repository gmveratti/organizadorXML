import os
import tempfile
import zipfile
import shutil

class ArchiveHandler:
    def __init__(self):
        # Cria uma diretoria temporária no sistema para extrair os ficheiros
        self.temp_dir = tempfile.mkdtemp(prefix="organizador_xml_")

    def extract_and_find_xmls(self, source_dir, callback_msg=None):
        """
        Extrai ficheiros compactados e devolve uma lista com todos os caminhos de ficheiros XML encontrados.
        """
        xml_files = []
        
        # 1. Procurar e extrair ficheiros ZIP
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith('.zip'):
                    file_path = os.path.join(root, file)
                    if callback_msg: 
                        callback_msg(f"A extrair ficheiro compactado: {file}")
                    try:
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            # Extrai para uma subpasta dentro do temp_dir
                            extract_path = os.path.join(self.temp_dir, file[:-4])
                            zip_ref.extractall(extract_path)
                    except Exception as e:
                        if callback_msg: 
                            callback_msg(f"Aviso: Erro ao extrair {file}: {e}")

        # 2. Varrer a pasta de origem e a pasta temporária à procura de XMLs
        if callback_msg: 
            callback_msg("A procurar ficheiros XML nas diretorias...")
            
        dirs_to_scan = [source_dir, self.temp_dir]
        for d in dirs_to_scan:
            for root, _, files in os.walk(d):
                for file in files:
                    if file.lower().endswith('.xml'):
                        xml_files.append(os.path.join(root, file))
                        
        return xml_files

    def cleanup(self):
        """Remove a diretoria temporária de extração ao finalizar."""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass
