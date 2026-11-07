# memoria-projetos — ache qualquer projeto e pergunte o que já foi decidido

[![Memória de Projetos](guia/assets/banner.jpg)](https://inematds.github.io/memoria-projetos/guia/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## O que é

O memoria-projetos é um kit para quem tem muitos projetos e trabalha com agentes de IA, como o Claude Code e o Codex. Ele resolve dois problemas: o agente não sabe onde está cada projeto e esquece o que já foi decidido. O comando `projeto` procura pelo que o projeto faz, nas suas pastas e no GitHub. O comando `memoria` responde perguntas como "pode fazer X?" lendo suas lições e anotações, com data e fonte. Para usar, você precisa de um computador com Linux, Python, o Ollama e, para a memória, a assinatura do Claude (sem chave de API). O índice fica todo na sua máquina; a memória manda o texto das anotações ao Claude para extrair os fatos. As duas metades são independentes: dá para instalar só uma.

## 📖 Guia de uso

Guia completo (landing + passo a passo): **https://inematds.github.io/memoria-projetos/guia/**

## As duas metades

| Metade | Pasta | Comando | Precisa de |
|---|---|---|---|
| Índice de projetos | `indice/` | `projeto` | Python 3, Ollama com `bge-m3`, `gh` (opcional) |
| Memória que responde | `memoria/` | `memoria` | Python 3, servidor Hindsight, Claude Code CLI logado, Ollama com `bge-m3` |

## Pré-requisitos

Instale e confira antes (o `instalar.sh` só confere, não instala nada do sistema):

1. **Python 3.11 ou mais novo** (`python3 --version`). Os comandos do kit usam só a biblioteca padrão.
2. **Ollama** (https://ollama.com) rodando em `127.0.0.1:11434`, com o modelo de vetores multilíngue:
   ```bash
   ollama pull bge-m3
   ```
3. **Só para o índice — GitHub CLI** (`gh`), logado em cada conta que você quer indexar:
   ```bash
   gh auth login            # repita para cada conta; o kit usa "gh auth token -u <conta>"
   gh auth status
   ```
   Sem `gh` (ou com `"contas": []`), o índice fica só com as pastas locais.
4. **Só para a memória — Claude Code CLI** instalado e logado na sua assinatura (`claude` no PATH; o kit põe `~/.npm-global/bin` e `~/.local/bin` na frente). O servidor usa o provedor `claude-code` do Hindsight, que a documentação dele indica para **uso pessoal/local**.
5. **Só para a memória — internet uma vez** na primeira subida do servidor: o PostgreSQL embutido (pg0) e o modelo de reordenação são baixados nessa hora. Depois, tudo roda local.
6. **systemd de usuário** (Linux) para os horários automáticos. Para os timers rodarem mesmo sem você logado:
   ```bash
   loginctl enable-linger "$USER"
   ```
   Sem systemd, use `--sem-systemd` e rode os comandos à mão (ou pelo cron).

## Instalação

```bash
git clone https://github.com/inematds/memoria-projetos.git
cd memoria-projetos
./instalar.sh --dry-run                 # mostra tudo o que faria, sem gravar nada
./instalar.sh --instalar-hindsight      # instala as duas metades + o servidor Hindsight
```

Opções do `instalar.sh` (pode rodar quantas vezes quiser: só grava o que mudou):

| Opção | O que faz |
|---|---|
| `--so-indice` / `--so-memoria` | instala só uma metade |
| `--sem-systemd` | não cria serviços nem timers |
| `--dry-run` | só mostra o que faria |
| `--instalar-hindsight` | cria `memoria/.venv` e instala o Hindsight (≈2 GB) |
| `--forcar` | substitui atalho ou unidade que já existe e não é deste kit |

O que ele faz:

- copia `config.exemplo.json` → `config.json`, `sinonimos.exemplo.json` → `sinonimos.json`, `.env.exemplo` → `.env` e `fontes.exemplo.json` → `fontes.json` **só se ainda não existirem** (nunca apaga config sua);
- cria os atalhos `~/.local/bin/projeto` e `~/.local/bin/memoria` apontando para esta pasta;
- escreve as unidades do systemd de usuário com o caminho real desta pasta, com teto de memória (`MemoryMax`) e de tempo (`TimeoutStartSec`), `PATH` com `~/.npm-global/bin` e `~/.local/bin` na frente e timers `Persistent=true` (se a máquina estava desligada no horário, roda quando ligar):

| Unidade | Quando | O que roda | Teto |
|---|---|---|---|
| `memoria-indice.timer` | todo dia 05:40 | `projeto --atualizar` | 1 GB · 20 min |
| `memoria-hindsight.service` | sempre ligado | servidor Hindsight em `127.0.0.1:8891` | 8 GB |
| `memoria-carga.timer` | todo dia 06:10 | `carga.py --max 25` | 512 MB · 60 min |
| `memoria-semana.timer` | segunda 08:00 | `semana.py --dias 7` | 512 MB · 30 min |

### O Hindsight, se preferir instalar à mão

O `--instalar-hindsight` faz exatamente isto (versão 1.0.0, a que foi testada; a 1.2.0 já existe no PyPI):

```bash
python3 -m venv memoria/.venv
memoria/.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu   # torch só CPU (bem menor)
memoria/.venv/bin/pip install hindsight-api==1.0.0
```

Se o `hindsight-api` já estiver instalado em outro lugar: `HINDSIGHT_BIN=/caminho/hindsight-api ./instalar.sh`.
Também funciona a partir do código-fonte: `pip install -e "<pasta-do-clone>/hindsight-api-slim[all]"` (clone de https://github.com/vectorize-io/hindsight).
Os dados do banco ficam em `~/.pg0` (PostgreSQL embutido).

## Configuração

### Índice — `indice/config.json`

| Campo | Para que serve |
|---|---|
| `raiz` | pasta onde ficam seus projetos (ex.: `~/projetos`); cada subpasta com git ou README vira um projeto |
| `contas` | contas do GitHub a indexar (`[]` = só local). A ordem conta: em pasta com vários remotos, a 1ª conta ganha |
| `subpastas_com_readme` | pastas (relativas à raiz) cujas subpastas com README também contam como projeto (ex.: uma pasta de ferramentas) |
| `pular` / `pular_subpastas` | nomes de pasta que nunca entram |
| `saida_md` / `saida_jsonl` | onde gravar o índice (padrão: dentro de `indice/`) |
| `ollama_url` / `ollama_modelo` | onde estão os vetores (padrão `bge-m3` local) |
| `peso_palavra` | quanto a busca por palavra soma à busca por sentido (padrão 0,35) |

`sinonimos.json`: abreviações que valem como a palavra inteira (`yt` → `youtube`, `ops` → `operacao`…). Acrescente as suas.

### Memória — `memoria/.env` e `memoria/fontes.json`

No `.env`: `HINDSIGHT_URL`, `HINDSIGHT_BANCO` (um banco por projeto ou pessoa) e a configuração do servidor (LLM `claude-code` com `claude-haiku-5-5`, vetores `bge-m3` no Ollama, reordenação local). A linha da chave do Ollama é um texto qualquer: o Ollama não usa chave.

No `fontes.json`, a lista do que vai para a memória. Três tipos:

| Tipo | Lê | Vira |
|---|---|---|
| `linhas` | itens `- ` de uma lista markdown (ex.: `LESSONS.md`) | as linhas novas do dia, em blocos de até `bloco` linhas (padrão 15) |
| `tabela` | linhas de dados de tabelas markdown (ex.: `FALHAS.md`), sem cabeçalho | idem |
| `pasta-md` | cada arquivo `.md` de uma pasta (ex.: a memória do agente) | um documento por arquivo; se o arquivo mudar, substitui o anterior |

Cada fonte tem `nome` (não troque depois da 1ª carga), `caminho`, `contexto` (uma frase dizendo o que é aquilo) e `tag`. Em `pasta-md`, `ignorar` lista arquivos que ficam de fora (ex.: o índice `MEMORY.md`).

**Custo da carga.** A carga só envia o que é novo ou mudou; conteúdo idêntico nem sai da máquina. Mas cada documento enviado é uma chamada ao LLM pela sua assinatura. Medido no piloto: **~5,6 mil tokens de entrada do Haiku por documento; 100 documentos ≈ 8 min ≈ 566 mil tokens**. Por isso o teto `--max` (padrão 25 por execução; o que sobrar vai no dia seguinte). A 1ª execução é a carga inicial: veja antes com `--simular` e, se quiser fazer tudo de uma vez, use `--max 200`.
Atenção: editar uma linha antiga (em `linhas` ou `tabela`) custa duas chamadas: o bloco antigo é reenviado sem ela e a versão nova entra no bloco do dia. Acrescentar linhas novas não mexe nos blocos antigos.

## Uso

```bash
# índice
projeto --atualizar                      # refaz o índice e os vetores (≈1–2 min para mil projetos)
projeto "separa operação do desenvolvimento"
projeto "publica vídeo no youtube" -n 5  # * na nota = todas as palavras casaram

# memória
python3 memoria/carga.py --simular       # o que seria gravado (não envia nada)
python3 memoria/carga.py --max 200       # 1ª carga
memoria "posso rodar processo longo sem teto de memória?"   # resposta pronta (30–75 s)
memoria -r "systemd PATH"                # só os trechos (7–17 s, sem LLM na resposta)
memoria --nota util "achou a regra certa"                   # avalia a última resposta
python3 memoria/semana.py                # relatório da semana → memoria/semana-AAAA-MM-DD.md
python3 memoria/avalia.py                # grep × recall × reflect nas suas perguntas (gasta cota)
```

Se o Ollama estiver fora, o `projeto` cai só na busca por palavra e avisa. Se o servidor da memória estiver fora, o `memoria` avisa e sai com código 2: use o grep de sempre.

`avalia.py` usa `perguntas.jsonl` (copie de `perguntas.exemplo.jsonl` e escreva perguntas reais suas), uma por linha: `{"pergunta": "...", "palavra_grep": "palavra que você usaria no grep", "gabarito": ["regex que a resposta certa precisa ter"]}`.

## O processo, do início ao fim

🧠 sessão (você, com ou sem o agente) · ⚙️ script/timer · 🤖 agente

1. 🧠 Instalar os pré-requisitos (Ollama + `ollama pull bge-m3`, `gh auth login`, Claude Code logado, `loginctl enable-linger`).
2. 🧠 `./instalar.sh --dry-run` e depois `./instalar.sh --instalar-hindsight`.
3. 🧠 Ajustar `indice/config.json` (raiz e contas), `memoria/fontes.json` (suas fontes) e `memoria/.env` (nome do banco).
4. 🧠 Primeiro índice: `projeto --atualizar`; conferir com `projeto "algo que você sabe onde está"`.
5. 🧠 Primeira carga da memória: `python3 memoria/carga.py --simular`, depois `python3 memoria/carga.py --max 200`.
6. 🧠 Colar a regra do agente (abaixo) no `CLAUDE.md` / `AGENTS.md` dos seus projetos.
7. ⚙️ Todo dia 05:40: `memoria-indice.timer` refaz o índice e calcula vetores só do que mudou.
8. ⚙️ Todo dia 06:10: `memoria-carga.timer` grava na memória só o que é novo (no máximo 25 documentos).
9. 🤖 Na sessão, pergunta "qual projeto faz X / onde está Y" → `projeto "X"` antes de varrer pastas.
10. 🤖 Na sessão, pergunta de regra ou decisão ("pode X?", "o que decidimos sobre Y?") → `memoria "…"` antes do grep; depois `memoria --nota util|inutil "motivo"`.
11. ⚙️ Toda segunda 08:00: `memoria-semana.timer` gera `memoria/semana-AAAA-MM-DD.md` (uso, adoção pelo agente, custo, RAM).
12. 🧠 Ler o relatório: ficou útil, muda a regra do agente ou desliga. De vez em quando, `python3 memoria/avalia.py` para medir a qualidade.

Desligar tudo: `systemctl --user disable --now memoria-hindsight.service memoria-carga.timer memoria-semana.timer memoria-indice.timer`.

## Fazendo o agente usar

O agente só usa o que está na regra dele. Cole isto no `CLAUDE.md` (Claude Code) ou no `AGENTS.md` (Codex) dos seus projetos, ou no arquivo global de instruções:

```markdown
## Achar projeto e consultar a memória

- Pergunta do tipo "qual projeto faz X" ou "onde está Y": rode `projeto "X"` ANTES de varrer pastas
  ou o histórico. Não leia o projetos.md inteiro; use o comando ou `grep -i`.
- Pergunta de regra, decisão ou erro já visto ("pode X?", "o que decidimos sobre Y?",
  "que erro já deu com Z?"): rode `memoria "pergunta"` (resposta pronta) ou `memoria -r "palavras"`
  (só trechos, mais rápido) ANTES do grep nas lições e falhas.
- Depois de usar a resposta, avalie: `memoria --nota util "motivo"` ou `memoria --nota inutil "motivo"`.
- Se `memoria` sair com código 2 (servidor fora), siga com o grep de sempre e avise.
```

Não coloque a resposta da memória no início de toda sessão: o agente pergunta quando precisa. Assim o começo da sessão fica sempre igual (o cache funciona) e a cota só é gasta quando há pergunta.

## Créditos

- A memória usa o **Hindsight**, da vectorize-io, licença MIT: https://github.com/vectorize-io/hindsight
- Espelho e guia em português: https://github.com/inematds/hindsight · https://inematds.github.io/hindsight/guia/
- Vetores: modelo `bge-m3` (BAAI) servido pelo Ollama.

## Licença

MIT — veja [LICENSE](LICENSE). © 2026 INEMA.
