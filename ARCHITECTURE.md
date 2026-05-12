# 🏗️ ARCHITECTURE.md — Organizador de XML Fiscais v3

> Documento de arquitetura e code review técnico.
> Gerado em: 2026-05-12

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Estrutura de Diretórios](#2-estrutura-de-diretórios)
3. [Diagrama de Arquitetura](#3-diagrama-de-arquitetura)
4. [Fluxo de Dados (Pipeline)](#4-fluxo-de-dados-pipeline)
5. [Módulos — Análise Detalhada](#5-módulos--análise-detalhada)
6. [Padrões de Design](#6-padrões-de-design)
7. [Segurança](#7-segurança)
8. [CI/CD e Distribuição](#8-cicd-e-distribuição)
9. [Code Review — Problemas Identificados](#9-code-review--problemas-identificados)
10. [Recomendações de Melhoria](#10-recomendações-de-melhoria)

---

## 1. Visão Geral

O **Organizador de XML Fiscais** é uma aplicação desktop (Tkinter) que automatiza a triagem contábil de documentos fiscais XML (NF-e, CT-e, etc.). Recebe uma pasta ou arquivo compactado como entrada, extrai recursivamente arquivos aninhados (ZIP dentro de ZIP), lê a data de emissão de cada XML e organiza-os em pastas estruturadas por data.

| Atributo         | Valor                                   |
| :--------------- | :-------------------------------------- |
| **Linguagem**    | Python 3.14                             |
| **UI Framework** | Tkinter (stdlib)                        |
| **Dependências** | `rarfile` (runtime), `pyinstaller` (dev)|
| **Gerenciador**  | `uv`                                    |
| **Distribuição** | Executável standalone (PyInstaller)     |

---

## 2. Estrutura de Diretórios

```
organizadorXML-main/
├── main.py                  # Ponto de entrada da aplicação
├── pyproject.toml            # Metadados e dependências (uv)
├── uv.lock                  # Lockfile de dependências
├── .python-version           # Python 3.14
│
├── core/                    # 🧠 Lógica de negócio
│   ├── __init__.py
│   ├── archive_handler.py    # Motor de extração recursiva (ZIP/RAR)
│   ├── organizer.py          # Parser de XML + movimentação de arquivos
│   └── worker.py             # Thread de processamento + orquestração
│
├── ui/                      # 🖥️ Interface gráfica
│   ├── __init__.py
│   └── main_window.py        # Janela principal Tkinter
│
├── assets/                  # 🎨 Recursos visuais
│   └── icon.ico              # Ícone do executável
│
├── bin/                     # 🔧 Binários de terceiros
│   └── UnRAR.exe             # Ferramenta de extração RAR (Windows)
│
└── .github/workflows/       # ⚙️ CI/CD
    └── build-windows.yml     # Pipeline de compilação automática
```

---

## 3. Diagrama de Arquitetura

```
┌────────────────────────────────────────────────────┐
│                  UI (Tkinter)                      │
│              main_window.py                        │
│          XMLOrganizerApp                           │
│                                                    │
│  ┌─────────────┐    ┌────────────────────────┐     │
│  │  Inputs      │    │  Feedback Visual       │     │
│  │  (src, dst)  │    │  (ProgressBar, Labels) │     │
│  └──────┬───────┘    └──────────▲─────────────┘     │
└─────────┼───────────────────────┼──────────────────┘
          │ start()               │ Queue messages
          ▼                       │
┌─────────────────────────────────┼──────────────────┐
│              core/worker.py     │                   │
│           ProcessingWorker      │                   │
│                                 │                   │
│  ┌──────────┐   ┌──────────────┐│   ┌────────────┐ │
│  │ArchiveH. │──>│ xml_files[]  ││──>│ThreadPool  │ │
│  │(generator)│  │              ││   │Executor    │ │
│  └──────────┘   └──────────────┘│   └─────┬──────┘ │
└─────────────────────────────────┼─────────┼────────┘
                                  │         │
                                  │         ▼
                    ┌─────────────┘  ┌──────────────┐
                    │                │organizer.py   │
                    │                │organize_file()│
                    │                └──────┬───────┘
                    │                       │
                    │                       ▼
                    │              ┌─────────────────┐
                    │              │ Sistema de       │
                    │              │ Arquivos         │
                    │              │ (Ano/Mês/Erro)   │
                    │              └─────────────────┘
```

### Comunicação entre Camadas

| De → Para       | Mecanismo               | Dados Trafegados                    |
| :-------------- | :---------------------- | :---------------------------------- |
| UI → Worker     | `threading.Thread`      | Paths de origem/destino + modo      |
| Worker → UI     | `queue.Queue`           | Tuplas de status (PROGRESS, DONE…)  |
| Worker → Handler| Chamada direta (gerador)| Paths de XMLs via `yield`           |
| Worker → Org.   | `ThreadPoolExecutor`    | Path de cada XML + destino + modo   |

---

## 4. Fluxo de Dados (Pipeline)

O processamento segue um pipeline de **3 fases sequenciais**:

```
  ENTRADA                EXTRAÇÃO                  ORGANIZAÇÃO              SAÍDA
 ┌────────┐   ┌──────────────────────────┐   ┌──────────────────┐   ┌──────────────┐
 │Pasta ou│──>│ FASE 1: Extração superf. │──>│                  │──>│ Ano/Mês dirs │
 │ZIP/RAR │   │ FASE 2: BFS c/ deque     │   │  ThreadPool      │   │ xmls_eventos │
 │        │   │ FASE 3: Yield XMLs       │   │  organize_file() │   │ xmls_com_erro│
 └────────┘   └──────────────────────────┘   └──────────────────┘   │ log_erros.txt│
                                                                     └──────────────┘
```

### Fase 1 — Extração Superficial (`archive_handler.py`)
- Se a entrada é um **arquivo único** `.xml`, retorna diretamente via `yield`.
- Se é um **arquivo compactado**, extrai para um `TemporaryDirectory`.
- Se é um **diretório**, varre recursivamente com `rglob("*")` e extrai todos os compactados encontrados.

### Fase 2 — Fila BFS com Limite de Profundidade
- Utiliza um `collections.deque` para processar arquivos compactados aninhados (ZIP dentro de ZIP).
- Limite de profundidade: **5 camadas** (`MAX_DEPTH = 5`) — proteção contra Zip Bombs.
- Cada arquivo extraído é deletado após processamento (`delete_after=True`).

### Fase 3 — Yield de XMLs
- Todos os `.xml` encontrados no diretório temporário são retornados via gerador.
- Se a entrada era um diretório, também varre XMLs soltos na origem.

### Organização (`worker.py` + `organizer.py`)
- O worker consome o gerador, materializa em lista (necessário para barra de progresso).
- Distribui a organização via `ThreadPoolExecutor` com cap de `min(8, cpu_count + 4)` workers.
- Cada XML é lido nos primeiros **8 KB** (header) para extrair a tag `<dhEmi>` ou `<dEmi>`.

### Modos de Organização

| Modo         | Estrutura Gerada       | Exemplo           |
| :----------- | :--------------------- | :---------------- |
| `year_month` | `dest/Ano/Ano.Mês/`   | `2024/2024.05/`   |
| `year`       | `dest/Ano/`            | `2024/`           |
| `month`      | `dest/Mês.Ano/`        | `05.2024/`        |

---

## 5. Módulos — Análise Detalhada

### 5.1 `main.py` (7 linhas)

Ponto de entrada minimalista. Instancia o `Tk` root e delega tudo ao `XMLOrganizerApp`.

> ✅ **Ponto positivo:** Separação clara — o entry point não contém lógica.

---

### 5.2 `core/archive_handler.py` (125 linhas)

**Responsabilidade:** Extrair recursivamente arquivos compactados e localizar XMLs.

| Aspecto           | Avaliação |
| :---------------- | :-------- |
| Segurança (Zip Slip) | ✅ Implementada via `_is_safe_path()` |
| Proteção Zip Bomb | ✅ `MAX_DEPTH = 5` limita profundidade |
| Gestão de recursos | ✅ `TemporaryDirectory` com cleanup explícito |
| Suporte RAR       | ✅ Detecção dinâmica, graceful fallback |
| Compatibilidade PyInstaller | ✅ Detecção de `sys._MEIPASS` |

**Pontos de atenção:**
- Exceções de `rarfile` e `BadZipFile` são silenciadas (linhas 70-76). O usuário não recebe feedback sobre arquivos corrompidos na fase de extração.
- O método `extract_and_find_xmls` mistura extração e busca — poderia ser separado para testabilidade.

---

### 5.3 `core/organizer.py` (64 linhas)

**Responsabilidade:** Ler a data de emissão de um XML e movê-lo para a pasta correta.

| Aspecto           | Avaliação |
| :---------------- | :-------- |
| Performance       | ✅ Lê apenas 8 KB por arquivo (header) |
| Regex binário     | ✅ `rb` mode evita problemas de encoding |
| Detecção de eventos | ✅ Separa XMLs de eventos fiscais |
| Duplicatas        | ✅ Renomeação automática com sufixo `_N` |
| Tratamento de erros | ✅ Duplo try/except com fallback |

**Pontos de atenção:**
- O regex `PATTERN_DATE` captura apenas `<dhEmi>` e `<dEmi>`. Documentos com namespace XML (ex: `<nfe:dhEmi>`) não serão capturados.
- A leitura de 8 KB pode ser insuficiente para XMLs com headers muito grandes ou encoding declarations extensas.

---

### 5.4 `core/worker.py` (94 linhas)

**Responsabilidade:** Orquestrar o pipeline completo em uma thread separada.

| Aspecto           | Avaliação |
| :---------------- | :-------- |
| Thread safety     | ✅ Comunicação via `queue.Queue` |
| Cancelamento      | ✅ Flag `is_cancelled` + `cancel_futures` |
| I/O throttling    | ✅ Cap conservador de workers |
| Log de erros      | ✅ Arquivo físico `log_erros.txt` |
| Limpeza de origem | ✅ Remove pastas vazias com `rglob` reverso |
| Cleanup de temp   | ✅ `finally` block garante limpeza |

**Pontos de atenção:**
- `future.result()` na linha 52 não tem `try/except` — uma exceção não tratada em `organize_file` pode matar o loop inteiro.
- A materialização do gerador em lista (`list()` na linha 29) anula parcialmente o benefício de memória do gerador.

---

### 5.5 `ui/main_window.py` (224 linhas)

**Responsabilidade:** Interface gráfica completa — inputs, progress bar, controle de estado.

| Aspecto           | Avaliação |
| :---------------- | :-------- |
| UX                | ✅ Progress bar indeterminate → determinate |
| Proteção de estado | ✅ Desabilita campos durante processamento |
| Fechamento seguro | ✅ `WM_DELETE_WINDOW` interceptado |
| Compatibilidade paths | ✅ `format_path()` lida com WSL e Windows |
| Polling de queue  | ✅ `root.after(100ms)` não bloqueia a UI |

**Pontos de atenção:**
- `format_path()` está no módulo de UI mas é lógica de negócio — deveria estar em `core/`.
- Strings de escape duplo na mensagem de `on_closing` (linha 157): `\\n` ao invés de `\n`.
- O timer de `check_queue` roda eternamente (mesmo sem processamento ativo), consumindo ciclos desnecessários.

---

## 6. Padrões de Design

| Padrão                   | Onde é Usado                    | Finalidade                                    |
| :----------------------- | :------------------------------ | :-------------------------------------------- |
| **Producer-Consumer**    | `worker.py` ↔ `main_window.py` | Desacopla processamento da UI via `Queue`     |
| **BFS com Deque**        | `archive_handler.py`            | Extração iterativa (evita stack overflow)      |
| **Generator (Lazy)**     | `extract_and_find_xmls()`       | Reduz pico de memória no discovery de XMLs    |
| **ThreadPool**           | `worker.py`                     | Paralelismo I/O-bound na organização          |
| **Graceful Degradation** | `archive_handler.py`            | RAR support opcional sem quebrar a aplicação  |
| **Safe Move**            | `organizer.py`                  | Renomeação automática para evitar sobrescrita |

---

## 7. Segurança

### 7.1 Proteções Implementadas

| Ameaça              | Proteção                                                 | Localização           |
| :------------------ | :------------------------------------------------------- | :-------------------- |
| **Zip Slip**        | Validação com `resolve().relative_to()`                  | `_is_safe_path()`     |
| **Zip Bomb**        | Limite de profundidade de extração (`MAX_DEPTH = 5`)     | `extract_and_find_xmls()` |
| **Path Traversal**  | `Path.resolve()` canonicaliza caminhos                   | `_is_safe_path()`     |
| **Vazamento de temp** | `TemporaryDirectory` + cleanup no `finally`             | `ArchiveHandler`      |
| **Sobrescrita**     | Renomeação automática de duplicatas                      | `safe_move()`         |

### 7.2 Lacunas de Segurança

- **Zip Bomb por tamanho:** Não há verificação do tamanho descompactado total. Um arquivo com ratio de compressão extremo pode encher o disco.
- **Symlink attacks:** `_is_safe_path` não verifica se os caminhos extraídos são symlinks.
- **Race condition em `safe_move`:** Entre o `exists()` e o `shutil.move()`, outro thread pode criar o arquivo (TOCTOU).

---

## 8. CI/CD e Distribuição

### Pipeline GitHub Actions (`build-windows.yml`)

```
Push main/master → checkout → setup-python 3.13 → pip install → PyInstaller → upload-artifact
```

**Observações:**

- ⚠️ **Inconsistência de versão:** O projeto usa Python **3.14** localmente (`.python-version`), mas o CI compila com Python **3.13**. Isso pode causar incompatibilidades de bytecode ou features.
- ⚠️ **Sem releases automáticos:** O workflow gera um artifact no GitHub Actions, mas não cria uma Release. A publicação é manual.
- ⚠️ **Sem testes no CI:** O pipeline compila diretamente sem rodar nenhum teste antes.

---

## 9. Code Review — Problemas Identificados

### 🔴 Severidade Alta

| #  | Problema | Localização | Impacto |
| :- | :------- | :---------- | :------ |
| 1  | `future.result()` sem `try/except` | `worker.py:52` | Exceção não tratada em qualquer XML mata o loop inteiro e trava a UI no estado "processando" |
| 2  | Escape duplo em string de diálogo | `main_window.py:157` | A mensagem de confirmação mostra `\n` literal ao invés de quebra de linha |

### 🟡 Severidade Média

| #  | Problema | Localização | Impacto |
| :- | :------- | :---------- | :------ |
| 3  | Exceções silenciadas na extração | `archive_handler.py:70-76` | Arquivos corrompidos são ignorados sem feedback ao usuário |
| 4  | Sem limite de tamanho descompactado | `archive_handler.py` | Vulnerável a Zip Bombs por consumo de disco |
| 5  | `format_path()` na camada de UI | `main_window.py:20-28` | Lógica de negócio vazando para a camada de apresentação |
| 6  | Versão de Python inconsistente no CI | `build-windows.yml:19` | CI usa 3.13, local usa 3.14 |
| 7  | Gerador materializado em lista | `worker.py:29` | Anula benefício de memória para volumes muito grandes |

### 🟢 Severidade Baixa

| #  | Problema | Localização | Impacto |
| :- | :------- | :---------- | :------ |
| 8  | `check_queue` roda eternamente | `main_window.py:212` | Consumo desnecessário de CPU quando idle |
| 9  | Regex não suporta namespaces XML | `organizer.py:5` | XMLs com prefixo de namespace não terão data extraída |
| 10 | Race condition em `safe_move` (TOCTOU) | `organizer.py:13-18` | Possível colisão entre threads concorrentes |
| 11 | `description` placeholder no `pyproject.toml` | `pyproject.toml:4` | Metadado incompleto |

---

## 10. Recomendações de Melhoria

### Prioridade Alta

1. **Proteger `future.result()` com try/except** — Evita que uma exceção isolada trave todo o processamento:
   ```python
   try:
       status, log_msg = future.result()
   except Exception as e:
       status, log_msg = 'ERROR', f"{futures[future]}: {str(e)}"
   ```

2. **Corrigir escape da mensagem de diálogo** — Trocar `\\n` por `\n` na linha 157 de `main_window.py`.

3. **Alinhar versão do Python no CI** — Atualizar `build-windows.yml` para usar Python 3.14 (ou a versão mais recente suportada pelo PyInstaller).

### Prioridade Média

4. **Registrar arquivos corrompidos no log** — Ao invés de silenciar exceções em `_extract_archive`, coletar os erros e incluí-los no `log_erros.txt`.

5. **Mover `format_path()` para `core/`** — Criar um módulo `core/utils.py` para funções utilitárias compartilhadas.

6. **Adicionar limite de tamanho total extraído** — Implementar um contador cumulativo de bytes extraídos com threshold configurável.

### Prioridade Baixa

7. **Otimizar polling da queue** — Iniciar o `check_queue` apenas durante processamento e pará-lo no `reset_ui()`.

8. **Expandir regex para namespaces** — Alterar para `rb'<(?:\w+:)?(?:dh|d)Emi>(\d{4})-(\d{2})'`.

9. **Adicionar testes unitários** — O projeto não possui nenhum teste. Módulos `organizer.py` e `archive_handler.py` são bons candidatos iniciais.

10. **Preencher metadados do `pyproject.toml`** — Adicionar `description`, `authors`, `license`, e `keywords`.

---

> **Conclusão Geral:** O projeto é bem estruturado para seu escopo, com separação clara de camadas (UI / Core), bom uso de padrões de concorrência, e mecanismos de segurança sólidos. Os problemas identificados são majoritariamente de robustez (tratamento de exceções) e higiene de código, sem falhas arquiteturais fundamentais. Com as correções de prioridade alta aplicadas, a aplicação estará significativamente mais resiliente.
