# memoria-projetos — find any project and ask what has already been decided

[![Project Memory](guia/assets/banner-en.jpg)](https://inematds.github.io/memoria-projetos/guia/en/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## What it is

memoria-projetos is a toolkit for people with many projects who work with AI agents such as Claude Code and Codex. It solves two problems: the agent does not know where each project is and forgets what has already been decided. The `projeto` command searches by what a project does, across your folders and GitHub. The `memoria` command answers questions like “can I do X?” by reading your lessons and notes, along with their dates and sources. To use it, you need a computer with Linux, Python, Ollama and, for memory, a Claude subscription (no API key). The index stays entirely on your machine; memory sends the text of your notes to Claude to extract facts. The two halves are independent: you can install either one on its own.

## 📖 User guide

Full guide (landing page + walkthrough): **https://inematds.github.io/memoria-projetos/guia/en/**

## The two halves

| Half | Folder | Command | Requires |
|---|---|---|---|
| Project index | `indice/` | `projeto` | Python 3, Ollama with `bge-m3`, `gh` (optional) |
| Memory that answers | `memoria/` | `memoria` | Python 3, Hindsight server, logged-in Claude Code CLI, Ollama with `bge-m3` |

## Prerequisites

Install and check these first (`instalar.sh` only checks; it does not install anything on your system):

1. **Python 3.11 or newer** (`python3 --version`). The kit’s commands use only the standard library.
2. **Ollama** (https://ollama.com) running at `127.0.0.1:11434`, with the multilingual embedding model:
   ```bash
   ollama pull bge-m3
   ```
3. **For the index only — GitHub CLI** (`gh`), logged in to each account you want to index:
   ```bash
   gh auth login            # repeat for each account; the kit uses "gh auth token -u <account>"
   gh auth status
   ```
   Without `gh` (or with `"contas": []`), the index includes only local folders.
4. **For memory only — Claude Code CLI** installed and logged in to your subscription (`claude` on PATH; the kit puts `~/.npm-global/bin` and `~/.local/bin` first). The server uses Hindsight’s `claude-code` provider, which its documentation recommends for **personal/local use**.
5. **For memory only — internet access once** when first starting the server: the embedded PostgreSQL (pg0) and reranking model are downloaded at that time. After that, everything runs locally.
6. **User systemd** (Linux) for scheduled runs. To have the timers run even when you are not logged in:
   ```bash
   loginctl enable-linger "$USER"
   ```
   Without systemd, use `--sem-systemd` and run the commands manually (or through cron).

## Installation

```bash
git clone https://github.com/inematds/memoria-projetos.git
cd memoria-projetos
./instalar.sh --dry-run                 # shows everything it would do without writing anything
./instalar.sh --instalar-hindsight      # installs both halves + the Hindsight server
```

`instalar.sh` options (you can run it as many times as you like: it only writes what has changed):

| Option | What it does |
|---|---|
| `--so-indice` / `--so-memoria` | installs just one half |
| `--sem-systemd` | does not create services or timers |
| `--dry-run` | only shows what it would do |
| `--instalar-hindsight` | creates `memoria/.venv` and installs Hindsight (≈2 GB) |
| `--forcar` | replaces an existing shortcut or unit that does not belong to this kit |

What it does:

- copies `config.exemplo.json` → `config.json`, `sinonimos.exemplo.json` → `sinonimos.json`, `.env.exemplo` → `.env` and `fontes.exemplo.json` → `fontes.json` **only if they do not already exist** (never deletes your configuration);
- creates the `~/.local/bin/projeto` and `~/.local/bin/memoria` shortcuts pointing to this folder;
- writes user systemd units with this folder’s actual path, memory (`MemoryMax`) and time (`TimeoutStartSec`) limits, `PATH` with `~/.npm-global/bin` and `~/.local/bin` first, and timers with `Persistent=true` (if the machine was off at the scheduled time, the task runs when it starts):

| Unit | When | What runs | Limit |
|---|---|---|---|
| `memoria-indice.timer` | every day at 05:40 | `projeto --atualizar` | 1 GB · 20 min |
| `memoria-hindsight.service` | always on | Hindsight server at `127.0.0.1:8891` | 8 GB |
| `memoria-carga.timer` | every day at 06:10 | `carga.py --max 25` | 512 MB · 60 min |
| `memoria-semana.timer` | Monday at 08:00 | `semana.py --dias 7` | 512 MB · 30 min |

### Hindsight, if you prefer to install it manually

`--instalar-hindsight` does exactly this (version 1.0.0, the one that was tested; 1.2.0 is already available on PyPI):

```bash
python3 -m venv memoria/.venv
memoria/.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only torch (much smaller)
memoria/.venv/bin/pip install hindsight-api==1.0.0
```

If `hindsight-api` is already installed somewhere else: `HINDSIGHT_BIN=/path/hindsight-api ./instalar.sh`.
It also works from source: `pip install -e "<path-to-clone>/hindsight-api-slim[all]"` (clone of https://github.com/vectorize-io/hindsight).
The database files are stored in `~/.pg0` (embedded PostgreSQL).

## Configuration

### Index — `indice/config.json`

| Field | What it does |
|---|---|
| `raiz` | folder containing your projects (e.g., `~/projetos`); each subfolder with git or a README becomes a project |
| `contas` | GitHub accounts to index (`[]` = local only). Order matters: in a folder with multiple remotes, the first account takes precedence |
| `subpastas_com_readme` | folders (relative to the root) whose subfolders with READMEs also count as projects (e.g., a tools folder) |
| `pular` / `pular_subpastas` | folder names that are always skipped |
| `saida_md` / `saida_jsonl` | where to write the index (default: inside `indice/`) |
| `ollama_url` / `ollama_modelo` | where the embeddings are (default: local `bge-m3`) |
| `peso_palavra` | how much the word search adds to the semantic search (default 0.35) |

`sinonimos.json`: abbreviations treated as the full word (`yt` → `youtube`, `ops` → `operacao`…). Add your own.

### Memory — `memoria/.env` and `memoria/fontes.json`

In `.env`: `HINDSIGHT_URL`, `HINDSIGHT_BANCO` (one database per project or person), and the server configuration (LLM `claude-code` with `claude-haiku-5-5`, `bge-m3` embeddings in Ollama, local reranking). The Ollama key line can contain any text: Ollama does not use a key.

In `fontes.json`, the list of what goes into memory. Three types:

| Type | Reads | Becomes |
|---|---|---|
| `linhas` | `- ` items in a Markdown list (e.g., `LESSONS.md`) | the new lines for the day, in blocks of up to `bloco` lines (default 15) |
| `tabela` | data rows in Markdown tables (e.g., `FALHAS.md`), without the header | same |
| `pasta-md` | each `.md` file in a folder (e.g., the agent’s memory) | one document per file; if the file changes, it replaces the previous one |

Each source has a `nome` (do not change it after the first load), `caminho`, `contexto` (a sentence describing what it is) and `tag`. For `pasta-md`, `ignorar` lists files to leave out (e.g., the `MEMORY.md` index).

**Load cost.** The loader sends only what is new or changed; identical content never leaves your machine. But each document sent is an LLM call through your subscription. In the pilot, the measured cost was **~5.6k Haiku input tokens per document; 100 documents ≈ 8 min ≈ 566k tokens**. That is why there is the `--max` limit (default 25 per run; anything left over goes the next day). The first run is the initial load: preview it with `--simular` first and, if you want to do everything at once, use `--max 200`.
Note: editing an old line (in `linhas` or `tabela`) costs two calls: the old block is resent without it, and the new version goes into the day’s block. Adding new lines does not affect old blocks.

## Usage

```bash
# index
projeto --atualizar                      # rebuilds the index and embeddings (≈1–2 min for a thousand projects)
projeto "separa operação do desenvolvimento"
projeto "publica vídeo no youtube" -n 5  # * in the note = all words matched

# memory
python3 memoria/carga.py --simular       # what would be saved (sends nothing)
python3 memoria/carga.py --max 200       # first load
memoria "posso rodar processo longo sem teto de memória?"   # ready-to-use answer (30–75 s)
memoria -r "systemd PATH"                # excerpts only (7–17 s, no LLM in the answer)
memoria --nota util "achou a regra certa"                   # rates the last answer
python3 memoria/semana.py                # weekly report → memoria/semana-AAAA-MM-DD.md
python3 memoria/avalia.py                # grep × recall × reflect on your questions (uses quota)
```

If Ollama is down, `projeto` falls back to word search only and displays a notice. If the memory server is down, `memoria` displays a notice and exits with code 2: use your usual grep.

`avalia.py` uses `perguntas.jsonl` (copy `perguntas.exemplo.jsonl` and write your actual questions), one per line: `{"pergunta": "...", "palavra_grep": "word you would use in grep", "gabarito": ["regex the correct answer must contain"]}`.

## The process, from start to finish

🧠 session (you, with or without the agent) · ⚙️ script/timer · 🤖 agent

1. 🧠 Install the prerequisites (Ollama + `ollama pull bge-m3`, `gh auth login`, logged-in Claude Code, `loginctl enable-linger`).
2. 🧠 Run `./instalar.sh --dry-run` and then `./instalar.sh --instalar-hindsight`.
3. 🧠 Adjust `indice/config.json` (root and accounts), `memoria/fontes.json` (your sources) and `memoria/.env` (database name).
4. 🧠 Build the first index: `projeto --atualizar`; check it with `projeto "something you know where to find"`.
5. 🧠 Load the initial memory: `python3 memoria/carga.py --simular`, then `python3 memoria/carga.py --max 200`.
6. 🧠 Add the agent rule (below) to the `CLAUDE.md` / `AGENTS.md` files in your projects.
7. ⚙️ Every day at 05:40: `memoria-indice.timer` rebuilds the index and calculates embeddings only for what changed.
8. ⚙️ Every day at 06:10: `memoria-carga.timer` saves only new items to memory (up to 25 documents).
9. 🤖 During a session, ask “which project does X / where is Y?” → run `projeto "X"` before searching folders.
10. 🤖 During a session, ask a rule or decision question (“can I do X?”, “what did we decide about Y?”) → run `memoria "…"` before grep; then `memoria --nota util|inutil "reason"`.
11. ⚙️ Every Monday at 08:00: `memoria-semana.timer` generates `memoria/semana-AAAA-MM-DD.md` (usage, agent adoption, cost, RAM).
12. 🧠 Read the report: if it was useful, update the agent rule or turn it off. Every so often, run `python3 memoria/avalia.py` to measure quality.

Turn everything off: `systemctl --user disable --now memoria-hindsight.service memoria-carga.timer memoria-semana.timer memoria-indice.timer`.

## Making the agent use it

The agent only uses what is in its instructions. Add this to `CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex) in your projects, or to your global instructions file:

```markdown
## Find projects and consult memory

- For questions like “which project does X” or “where is Y”: run `projeto "X"` BEFORE searching folders
  or history. Do not read all of `projetos.md`; use the command or `grep -i`.
- For questions about a rule, decision or previously seen error (“can I do X?”, “what did we decide about Y?”,
  “what error happened with Z?”): run `memoria "question"` (ready-to-use answer) or `memoria -r "words"`
  (excerpts only, faster) BEFORE grepping the lessons and failures.
- After using the answer, rate it: `memoria --nota util "reason"` or `memoria --nota inutil "reason"`.
- If `memoria` exits with code 2 (server down), continue with your usual grep and let the user know.
```

Do not put the memory answer at the start of every session: the agent asks when it needs it. This keeps the start of each session the same (the cache works) and uses quota only when there is a question.

## Credits

- Memory uses **Hindsight**, by vectorize-io, MIT license: https://github.com/vectorize-io/hindsight
- Portuguese mirror and guide: https://github.com/inematds/hindsight · https://inematds.github.io/hindsight/guia/
- Embeddings: `bge-m3` model (BAAI) served by Ollama.

## License

MIT — see [LICENSE](LICENSE). © 2026 INEMA.
