import os
import shutil
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Regex otimizada para buscar a tag de emissão (ex: <dhEmi> ou <dEmi>)
PATTERN = re.compile(rb'<(?:dh|d)Emi>(\d{4}-\d{2})')

def print_progress_bar(iteration, total, prefix='', suffix='', length=50, fill='█'):
    """Gera uma barra de progresso visual no terminal."""
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix} ({iteration}/{total})')
    sys.stdout.flush()
    if iteration == total:
        print()

def process_file(file_name, base_dir, error_dir):
    file_path = os.path.join(base_dir, file_name)
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            
        match = PATTERN.search(content)

        if match:
            # Sucesso: formata a pasta e move o arquivo
            folder_name = match.group(1).decode('ascii').replace('-', '.')
            target_dir = os.path.join(base_dir, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            
            target_path = os.path.join(target_dir, file_name)
            shutil.move(file_path, target_path)
            return 'SUCCESS', None
            
        else:
            # Falha: Tag não encontrada
            target_path = os.path.join(error_dir, file_name)
            shutil.move(file_path, target_path)
            return 'NOT_FOUND', f"{file_name}: Tag de data de emissão não encontrada."
            
    except Exception as e:
        # Falha: Arquivo corrompido ou erro de permissão
        try:
            target_path = os.path.join(error_dir, file_name)
            shutil.move(file_path, target_path)
        except Exception as move_error:
            return 'ERROR', f"{file_name}: Erro ao ler ({str(e)}) e falha ao mover ({str(move_error)})."
            
        return 'ERROR', f"{file_name}: Erro de leitura/arquivo corrompido - {str(e)}"

def format_wsl_path(input_path):
    """Converte caminhos do Windows para o formato do WSL, se necessário."""
    # Remove aspas caso o usuário tenha usado "Copiar como caminho" no Windows
    clean_path = input_path.strip('"\'')
    
    # Verifica se começa com letra de unidade (ex: C:\ ou D:\)
    if re.match(r'^[a-zA-Z]:[\\/]', clean_path):
        drive_letter = clean_path[0].lower()
        # Pega o restante do caminho e troca barras invertidas por barras normais
        rest_of_path = clean_path[2:].replace('\\', '/')
        return f"/mnt/{drive_letter}{rest_of_path}"
    
    # Se já for um caminho Linux/WSL, apenas garante que as barras estão corretas
    return clean_path.replace('\\', '/')

def main():
    # Solicita o caminho da pasta
    raw_path = input("Digite ou cole o caminho da pasta com os XMLs: ")
    base_dir = format_wsl_path(raw_path)
    
    if not os.path.isdir(base_dir):
        print(f"\nErro: O diretório '{base_dir}' não foi encontrado.")
        print("Verifique se o caminho está correto e tente novamente.")
        return

    error_dir = os.path.join(base_dir, 'xmls_com_erro')
    
    print(f"\nMapeando arquivos no diretório: {base_dir}")
    xml_files = [f.name for f in os.scandir(base_dir) if f.is_file() and f.name.lower().endswith('.xml')]
    total_files = len(xml_files)

    if total_files == 0:
        print("Nenhum arquivo XML encontrado no diretório especificado.")
        return

    # Cria a pasta de erros antecipadamente
    os.makedirs(error_dir, exist_ok=True)

    print(f"Iniciando o processamento de {total_files} arquivos XML...\n")

    moved_count = 0
    error_logs = []
    processed_count = 0

    workers = os.cpu_count() * 2

    print_progress_bar(0, total_files, prefix='Progresso:', suffix='Concluído')

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_file, name, base_dir, error_dir): name for name in xml_files}

        for future in as_completed(futures):
            status, log_msg = future.result()
            
            if status == 'SUCCESS':
                moved_count += 1
            else:
                error_logs.append(log_msg)
                
            processed_count += 1
            print_progress_bar(processed_count, total_files, prefix='Progresso:', suffix='Concluído')

    # Grava o log de erros se houver algum
    if error_logs:
        log_file_path = os.path.join(error_dir, 'log_erros.txt')
        with open(log_file_path, 'w', encoding='utf-8') as log_file:
            log_file.write(f"Total de erros: {len(error_logs)}\n")
            log_file.write("-" * 40 + "\n")
            for log in error_logs:
                log_file.write(log + '\n')

    # Resumo final
    print("\n--- Resumo da Execução ---")
    print(f"Total processado: {total_files}")
    print(f"Movidos com sucesso: {moved_count}")
    print(f"Com erro/movidos para log: {len(error_logs)}")
    
    if error_logs:
        print(f"Verifique a pasta '{error_dir}' e o arquivo 'log_erros.txt' para detalhes.")

if __name__ == '__main__':
    main()
