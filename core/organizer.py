import os
import shutil
import re

# Regex para extrair Ano (grupo 1) e Mês (grupo 2)
PATTERN_DATE = re.compile(rb'<(?:dh|d)Emi>(\d{4})-(\d{2})')
# Regex para identificar se é um evento (Carta de correção, cancelamento, etc.)
PATTERN_EVENT = re.compile(rb'<(?:evento|procEvento)')

def safe_move(src_path, dest_dir, file_name):
    """Move o ficheiro e previne sobrescrita caso existam nomes duplicados."""
    os.makedirs(dest_dir, exist_ok=True)
    target_path = os.path.join(dest_dir, file_name)
    
    if os.path.exists(target_path):
        base, ext = os.path.splitext(file_name)
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
            counter += 1
            
    shutil.move(src_path, target_path)

def organize_file(file_path, dest_dir, mode):
    """
    Processa um ficheiro XML e move para a pasta correta (Evento, Erro ou Data).
    """
    file_name = os.path.basename(file_path)
    error_dir = os.path.join(dest_dir, 'xmls_com_erro')
    event_dir = os.path.join(dest_dir, 'xmls_eventos')

    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            
        # 1. REGRA: É um Evento?
        if PATTERN_EVENT.search(content):
            safe_move(file_path, event_dir, file_name)
            return 'EVENT', f"{file_name}: Movido para eventos."

        # 2. REGRA: É nota válida com Data?
        match_date = PATTERN_DATE.search(content)
        if match_date:
            year = match_date.group(1).decode('ascii')
            month = match_date.group(2).decode('ascii')
            
            if mode == 'year_month':
                target_dir = os.path.join(dest_dir, year, f"{year}.{month}")
            elif mode == 'year':
                target_dir = os.path.join(dest_dir, year)
            elif mode == 'month':
                target_dir = os.path.join(dest_dir, f"{month}.{year}")
                
            safe_move(file_path, target_dir, file_name)
            return 'SUCCESS', None
            
        # 3. REGRA: Não é evento e não tem data (Inválido/Corrompido)
        safe_move(file_path, error_dir, file_name)
        return 'NOT_FOUND', f"{file_name}: Tag de data de emissão não encontrada."
            
    except Exception as e:
        # Se o ficheiro estiver bloqueado pelo Windows ou realmente corrompido
        try:
            safe_move(file_path, error_dir, file_name)
        except Exception as move_error:
            return 'ERROR', f"{file_name}: Erro de leitura ({str(e)}) e falha ao mover ({str(move_error)})."
        return 'ERROR', f"{file_name}: Erro de leitura/ficheiro corrompido - {str(e)}"
