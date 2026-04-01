# 📑 Organizador de XML Fiscais

O **Organizador de XML Fiscais** é uma ferramenta de alta performance desenvolvida para automação de processos contábeis e fiscais. Ele resolve o problema de triagem de grandes volumes de arquivos, organizando milhares de XMLs em segundos com base na data de emissão real contida no documento.

---

## 🚀 Como baixar e usar (Executável)

Se você deseja apenas utilizar a ferramenta sem configurar um ambiente de programação:

1. Acesse a aba **[Releases]([https://github.com/gmveratti/organizadorXML/releases/tag/Execut%C3%A1vel])** deste repositório.
2. Baixe o arquivo `OrganizadorXML.exe`.
3. Execute o programa (não requer instalação).
4. Selecione a **Pasta Origem** (onde estão seus XMLs bagunçados) e a **Pasta Destino**.
5. Escolha o modo de organização e clique em **Iniciar**.

---

## ✨ Funcionalidades Principais

| Recurso | Descrição |
| :--- | :--- |
| **Interface Gráfica** | GUI amigável com barra de progresso, contador de arquivos e cronômetro. |
| **Alta Performance** | Processamento paralelo (*Multithreading*) para lidar com 50.000+ arquivos rapidamente. |
| **Busca Recursiva** | Varre automaticamente todas as subpastas dentro do diretório selecionado. |
| **Limpeza Inteligente** | Após mover os arquivos, o script remove as pastas antigas (apenas se estiverem vazias). |
| **Prevenção de Perda** | Caso existam arquivos com nomes iguais em pastas diferentes, o script renomeia automaticamente (ex: `nota_1.xml`) para evitar sobrescrita. |

### 📂 Modos de Organização

Você pode escolher entre três estruturas de pastas no destino:
* **Mês e Ano:** Cria uma pasta para o Ano e subpastas para o Mês (Ex: `2022/2022.06`).
* **Somente Ano:** Coloca todos os arquivos do ano em uma única pasta (Ex: `2022/`).
* **Somente Mês:** Organiza por mês e ano na raiz (Ex: `06.2022/`).

---

## 🛠️ Tratamento de Erros e Logs

Segurança é prioridade em documentos fiscais. O script gerencia falhas de forma isolada:

1.  **Pasta de Erros:** Qualquer XML corrompido ou sem a tag de emissão (`<dhEmi>` ou `<dEmi>`) é movido para a pasta `xmls_com_erro/`.
2.  **Relatório Detalhado:** Dentro dessa pasta, um arquivo `log_erros.txt` é gerado explicando o motivo exato da falha de cada arquivo.
3.  **Ambiente Híbrido:** O script detecta automaticamente se você está rodando no **Windows nativo** ou no **WSL**, tratando os caminhos de diretório corretamente em ambos.

---

## 💻 Desenvolvimento e Compilação

Para rodar o código-fonte ou gerar seu próprio executável:

### Requisitos
* [uv](https://docs.astral.sh/uv/) (Gerenciador de pacotes e projetos Python ultra-rápido)
* Python 3.13+ (Instalado automaticamente pelo `uv` se necessário)
* Biblioteca `tkinter` (Nativa no Windows. No Linux/WSL use: `sudo apt install python3-tk`)

### Executar o Código-Fonte
Para rodar o script diretamente usando o `uv`, utilize o comando:
```powershell
uv run main.py
```

### Gerar Executável com Ícone
As dependências de build (como o `pyinstaller`) já estão configuradas no `pyproject.toml`. Para compilar preservando o ícone, utilize o comando abaixo no PowerShell (na raiz do projeto):
```powershell
uv run pyinstaller --noconsole --onefile --icon=assets/icon.ico main.py
```
