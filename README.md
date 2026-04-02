# 📑 Organizador de XML Fiscais v3

O **Organizador de XML Fiscais** é uma ferramenta de alta performance para automação de triagem contábil. Ele resolve o problema de grandes volumes de documentos, organizando milhares de XMLs em segundos com base na data de emissão real, agora com suporte total a arquivos compactados aninhados.

---

## 🚀 Como baixar e usar (Executável)

Se você deseja apenas utilizar a ferramenta sem configurar um ambiente de programação, siga estes passos simples:

1. Acesse a aba **[Releases](https://github.com/gmveratti/organizadorXML/releases)** deste repositório.
2. Baixe o executável `OrganizadorXML.exe` da versão mais recente.
3. Certifique-se de que o arquivo não esteja bloqueado pelo Windows (Botão direito > Propriedades > Desbloquear, se necessário).
4. Basta executar o programa (não requer instalação).

---

## ✨ Funcionalidades v3

| Recurso | Descrição |
| :--- | :--- |
| **Extração Recursiva** | Motor estilo "cebola": extrai ZIPs dentro de ZIPs infinitamente (limitado a 5 camadas). |
| **Híbrido de Origem** | Botões dedicados para selecionar uma **Pasta** inteira ou um unico **Ficheiro** (.zip/.rar). |
| **RAM Ultra-Low** | Lê apenas os primeiros 8 KB (Header) de cada XML para extrair a data, poupando gigabytes de RAM. |
| **Segurança Ativa** | Proteção contra *Zip Slip* (Path Traversal) e *Zip Bombs* integradas no motor. |
| **Log de Erros Real** | Gera um arquivo físico `log_erros.txt` na pasta de erros detalhando cada falha. |
| **Limpeza Automática** | Remove pastas vazias de origem e arquivos temporários de extração ao concluir. |

### 📂 Modos de Organização

* **Mês e Ano:** Cria estrutura `Ano/Ano.Mês` (Ex: `2024/2024.05`).
* **Somente Ano:** Todos os arquivos do ano em uma pasta única (Ex: `2024/`).
* **Somente Mês:** Organiza por mês e ano na raiz (Ex: `05.2024/`).

---

## 🛠️ Requisitos de Sistema

### Suporte a RAR
Para suporte completo a arquivos `.rar` no Windows, o motor tenta localizar automaticamente o `UnRAR.exe` (nativamente incluído na instalação do WinRAR em `C:\Program Files\WinRAR\UnRAR.exe`). Se não for encontrado, o suporte RAR será desativado, mantendo apenas o suporte nativo a ZIP.

### Desenvolvimento
Se deseja rodar o código-fonte via [uv](https://docs.astral.sh/uv/):
```powershell
# Executar a aplicação
uv run main.py

# Compilar localmente (Windows)
uv run pyinstaller --noconsole --onefile --icon=assets/icon.ico --add-data "assets;assets" --add-data "bin;bin" --name "OrganizadorXML" main.py
```

---

## 💻 Arquitetura de Performance

O projeto utiliza um padrão de **Fila (Deque)** para o motor de extração, garantindo que o processamento de arquivos compactados seja linear e não cause estouro de pilha (*Stack Overflow*). A movimentação de arquivos é protegida por verificações de duplicidade, renomeando automaticamente conflitos para evitar sobrescrita de dados fiscais importantes.
