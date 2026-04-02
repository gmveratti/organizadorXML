import shutil
import re
from pathlib import Path

PATTERN_DATE = re.compile(rb'<(?:dh|d)Emi>(\d{4})-(\d{2})')
PATTERN_EVENT = re.compile(rb'<(?:evento|procEvento)')

def safe_move(src_path: Path, dest_dir: Path, file_name: str):
    """Move usando pathlib e lidando com arquivos duplicados."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = dest_dir / file_name
    
    if target_path.exists():
        base, ext = target_path.stem, target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = dest_dir / f"{base}_{counter}{ext}"
            counter += 1
            
    shutil.move(str(src_path), str(target_path))

def organize_file(file_path_str, dest_dir_str, mode):
    file_path = Path(file_path_str)
    dest_dir = Path(dest_dir_str)
    file_name = file_path.name
    error_dir = dest_dir / 'xmls_com_erro'
    event_dir = dest_dir / 'xmls_eventos'

    try:
        # OPTIMIZAÇÃO: Lê apenas o cabeçalho do XML (8 KB), evitando RAM Spikes!
        with open(file_path, 'rb') as f:
            content = f.read(8192)
            
        if PATTERN_EVENT.search(content):
            safe_move(file_path, event_dir, file_name)
            return 'EVENT', f"{file_name}: Movido para eventos."

        match_date = PATTERN_DATE.search(content)
        if match_date:
            year = match_date.group(1).decode('ascii')
            month = match_date.group(2).decode('ascii')
            
            if mode == 'year_month':
                target_dir = dest_dir / year / f"{year}.{month}"
            elif mode == 'year':
                target_dir = dest_dir / year
            elif mode == 'month':
                target_dir = dest_dir / f"{month}.{year}"
            else:
                target_dir = dest_dir / year / f"{year}.{month}" # default fallback
                
            safe_move(file_path, target_dir, file_name)
            return 'SUCCESS', None
            
        safe_move(file_path, error_dir, file_name)
        return 'NOT_FOUND', f"{file_name}: Tag de data de emissão não encontrada no cabeçalho."
            
    except Exception as e:
        try:
            safe_move(file_path, error_dir, file_name)
        except Exception as move_error:
            return 'ERROR', f"{file_name}: Erro de leitura ({str(e)}) e de mover ({str(move_error)})."
        return 'ERROR', f"{file_name}: Arquivo bloqueado ou corrompido - {str(e)}"
