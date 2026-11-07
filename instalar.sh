#!/usr/bin/env bash
# instalar.sh — instala o kit memoria-projetos (índice de projetos + memória que responde).
#
#   ./instalar.sh                      # instala as duas metades
#   ./instalar.sh --so-indice          # só o índice de projetos (precisa de Ollama + gh)
#   ./instalar.sh --so-memoria         # só a memória (precisa de Hindsight + Claude Code + Ollama)
#   ./instalar.sh --sem-systemd        # não cria serviços/timers (você roda à mão)
#   ./instalar.sh --dry-run            # só mostra o que faria; não grava nada
#   ./instalar.sh --instalar-hindsight # cria memoria/.venv e instala o hindsight-api 1.0.0 (PyPI)
#   ./instalar.sh --forcar             # substitui unidade/atalho que existe mas não é deste kit
#
# Pode rodar quantas vezes quiser: só grava o que mudou e nunca apaga config sua.
# Tudo é escrito a partir do caminho real desta pasta (nada de caminho fixo de outra máquina).
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
MARCA="# gerado por memoria-projetos/instalar.sh"
UNID="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
BIN="$HOME/.local/bin"
PY="$(command -v python3 || echo /usr/bin/python3)"
CAMINHO_PATH='%h/.npm-global/bin:%h/.local/bin:/usr/local/bin:/usr/bin:/bin'

INDICE=1; MEMORIA=1; SYSTEMD=1; DRY=0; FORCAR=0; HS_INSTALAR=0
for a in "$@"; do
  case "$a" in
    --so-indice) MEMORIA=0 ;;
    --so-memoria) INDICE=0 ;;
    --sem-systemd) SYSTEMD=0 ;;
    --dry-run) DRY=1 ;;
    --forcar) FORCAR=1 ;;
    --instalar-hindsight) HS_INSTALAR=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $a (veja --help)" >&2; exit 1 ;;
  esac
done

MUDOU_UNID=0
PULADAS=" "
diz() { echo "$@"; }
aviso() { echo "  ! $*"; }
faz() { if [ "$DRY" = 1 ]; then echo "  [dry-run] $*"; else eval "$@"; fi; }

# copia o arquivo de exemplo para o arquivo real, só se o real ainda não existir
copia_exemplo() {
  local de="$1" para="$2"
  if [ -e "$para" ]; then diz "  ok: $para já existe (mantido)"; return; fi
  faz "cp '$de' '$para'"
  [ "$DRY" = 1 ] || diz "  criado: $para (ajuste antes de usar)"
}

# grava uma unidade systemd se o conteúdo mudou; não mexe em unidade que não é do kit
grava_unidade() {
  local nome="$1" conteudo="$2" alvo="$UNID/$1"
  conteudo="$MARCA
$conteudo"
  if [ -e "$alvo" ] && ! grep -qF "$MARCA" "$alvo" && [ "$FORCAR" = 0 ]; then
    aviso "$alvo existe e não é deste kit: pulado (use --forcar para substituir)"; PULADAS+="$nome "; return
  fi
  if [ -e "$alvo" ] && [ "$(cat "$alvo")" = "$conteudo" ]; then
    diz "  ok: $nome sem mudança"; return
  fi
  if [ "$DRY" = 1 ]; then
    echo "  [dry-run] escreveria $alvo:"; echo "$conteudo" | sed 's/^/      | /'
  else
    mkdir -p "$UNID"; printf '%s\n' "$conteudo" > "$alvo"; diz "  gravado: $alvo"
  fi
  MUDOU_UNID=1
}

# atalho em ~/.local/bin; não troca atalho que aponta para outro lugar sem --forcar
atalho() {
  local nome="$1" destino="$2" alvo="$BIN/$1"
  if [ -L "$alvo" ] && [ "$(readlink -f "$alvo")" = "$(readlink -f "$destino")" ]; then
    diz "  ok: $alvo → $destino"; return
  fi
  if [ -e "$alvo" ] || [ -L "$alvo" ]; then
    if [ "$FORCAR" = 0 ]; then
      aviso "$alvo já existe e aponta para $(readlink -f "$alvo" 2>/dev/null || echo '?'): pulado (use --forcar)"; return
    fi
  fi
  faz "mkdir -p '$BIN' && chmod +x '$destino' && ln -sfn '$destino' '$alvo'"
  [ "$DRY" = 1 ] || diz "  atalho: $alvo → $destino"
}

le_env() {  # le_env CHAVE PADRAO  (do memoria/.env, ou do exemplo)
  local arq="$KIT/memoria/.env"; [ -e "$arq" ] || arq="$KIT/memoria/.env.exemplo"
  local v; v="$(grep -E "^$1=" "$arq" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
  echo "${v:-$2}"
}

diz "Kit em: $KIT"
[ "$DRY" = 1 ] && diz "(dry-run: nada será gravado)"

# ---------------- pré-requisitos (só conferência, não instala nada do sistema) ----------------
diz ""; diz "Pré-requisitos:"
command -v python3 >/dev/null && diz "  ok: python3 ($PY)" || aviso "falta python3"
if command -v ollama >/dev/null; then
  if timeout 15 ollama list 2>/dev/null | grep '^bge-m3' >/dev/null; then diz "  ok: ollama com bge-m3"
  else aviso "Ollama sem o modelo bge-m3 (ou parado): rode  ollama pull bge-m3"; fi
else aviso "falta o Ollama (https://ollama.com) + ollama pull bge-m3"; fi
if [ "$INDICE" = 1 ]; then
  command -v gh >/dev/null && diz "  ok: gh" || aviso "falta o gh (GitHub CLI): sem ele o índice fica só com as pastas locais"
fi
if [ "$MEMORIA" = 1 ]; then
  command -v claude >/dev/null || [ -x "$HOME/.npm-global/bin/claude" ] && diz "  ok: Claude Code CLI" \
    || aviso "falta o Claude Code CLI logado na sua assinatura (o servidor usa o provedor claude-code)"
fi
if [ "$SYSTEMD" = 1 ]; then
  if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || echo no)" != "yes" ]; then
    aviso "linger desligado: os timers só rodam com você logado. Para rodar sempre: loginctl enable-linger $USER"
  else diz "  ok: linger ligado"; fi
fi

# ---------------- índice ----------------
if [ "$INDICE" = 1 ]; then
  diz ""; diz "Índice de projetos (indice/):"
  copia_exemplo "$KIT/indice/config.exemplo.json" "$KIT/indice/config.json"
  copia_exemplo "$KIT/indice/sinonimos.exemplo.json" "$KIT/indice/sinonimos.json"
  atalho projeto "$KIT/indice/projeto"
  if [ "$SYSTEMD" = 1 ]; then
    grava_unidade memoria-indice.service "[Unit]
Description=memoria-projetos: refaz o índice de projetos e os vetores de busca ($KIT/indice)

[Service]
Type=oneshot
WorkingDirectory=$KIT/indice
Environment=PATH=$CAMINHO_PATH
ExecStart=$PY $KIT/indice/projeto --atualizar
TimeoutStartSec=20min
MemoryMax=1G"
    grava_unidade memoria-indice.timer "[Unit]
Description=memoria-projetos: índice de projetos todo dia às 05:40

[Timer]
OnCalendar=*-*-* 05:40:00
Persistent=true

[Install]
WantedBy=timers.target"
  fi
fi

# ---------------- memória ----------------
if [ "$MEMORIA" = 1 ]; then
  diz ""; diz "Memória (memoria/):"
  copia_exemplo "$KIT/memoria/.env.exemplo" "$KIT/memoria/.env"
  copia_exemplo "$KIT/memoria/fontes.exemplo.json" "$KIT/memoria/fontes.json"
  atalho memoria "$KIT/memoria/memoria"
  SERVICO="$(le_env HINDSIGHT_SERVICO memoria-hindsight)"
  HS_BIN="${HINDSIGHT_BIN:-$KIT/memoria/.venv/bin/hindsight-api}"

  if [ "$HS_INSTALAR" = 1 ]; then
    if [ -x "$KIT/memoria/.venv/bin/hindsight-api" ]; then diz "  ok: hindsight-api já instalado em memoria/.venv"
    else
      diz "  instalando o Hindsight em memoria/.venv (≈2 GB; torch só CPU):"
      faz "python3 -m venv '$KIT/memoria/.venv'"
      faz "'$KIT/memoria/.venv/bin/pip' install -q --upgrade pip"
      faz "'$KIT/memoria/.venv/bin/pip' install torch --index-url https://download.pytorch.org/whl/cpu"
      faz "'$KIT/memoria/.venv/bin/pip' install hindsight-api==1.0.0"
    fi
  elif [ ! -x "$HS_BIN" ]; then
    aviso "hindsight-api não encontrado em $HS_BIN: rode ./instalar.sh --instalar-hindsight (ou defina HINDSIGHT_BIN)"
  else diz "  ok: hindsight-api em $HS_BIN"; fi

  if [ "$SYSTEMD" = 1 ]; then
    grava_unidade "$SERVICO.service" "[Unit]
Description=memoria-projetos: servidor Hindsight local (LLM pela assinatura do Claude, vetores no Ollama)
After=network.target

[Service]
WorkingDirectory=$KIT/memoria
EnvironmentFile=$KIT/memoria/.env
Environment=PATH=$CAMINHO_PATH
ExecStart=$HS_BIN --log-level info
StandardOutput=append:$KIT/memoria/servidor.log
StandardError=append:$KIT/memoria/servidor.log
MemoryMax=8G
TimeoutStartSec=10min
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target"
    grava_unidade memoria-carga.service "[Unit]
Description=memoria-projetos: carga diária do que mudou nas fontes ($KIT/memoria/fontes.json)
Wants=$SERVICO.service
After=$SERVICO.service

[Service]
Type=oneshot
WorkingDirectory=$KIT/memoria
Environment=PATH=$CAMINHO_PATH
ExecStart=$PY $KIT/memoria/carga.py --max 25
TimeoutStartSec=60min
MemoryMax=512M"
    grava_unidade memoria-carga.timer "[Unit]
Description=memoria-projetos: carga da memória todo dia às 06:10

[Timer]
OnCalendar=*-*-* 06:10:00
Persistent=true

[Install]
WantedBy=timers.target"
    grava_unidade memoria-semana.service "[Unit]
Description=memoria-projetos: relatório da semana ($KIT/memoria/semana-AAAA-MM-DD.md)

[Service]
Type=oneshot
WorkingDirectory=$KIT/memoria
Environment=PATH=$CAMINHO_PATH
ExecStart=$PY $KIT/memoria/semana.py --dias 7
TimeoutStartSec=30min
MemoryMax=512M"
    grava_unidade memoria-semana.timer "[Unit]
Description=memoria-projetos: relatório da memória toda segunda às 08:00

[Timer]
OnCalendar=Mon *-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target"
  fi
fi

# ---------------- ligar ----------------
if [ "$SYSTEMD" = 1 ]; then
  diz ""; diz "systemd --user:"
  LIGAR=()
  [ "$INDICE" = 1 ] && LIGAR+=(memoria-indice.timer)
  if [ "$MEMORIA" = 1 ]; then
    LIGAR+=(memoria-carga.timer memoria-semana.timer)
    if [ -x "$HS_BIN" ] || [ "$DRY" = 1 ]; then LIGAR+=("$SERVICO.service")
    else aviso "servidor não ligado (falta o hindsight-api)"; fi
  fi
  FINAL=()
  for u in "${LIGAR[@]}"; do
    base="${u%.timer}"; base="${base%.service}"
    case "$PULADAS" in *" $u "*|*" $base.service "*) aviso "$u não será ligado (unidade não é deste kit)" ;; *) FINAL+=("$u") ;; esac
  done
  [ "$MUDOU_UNID" = 1 ] && faz "systemctl --user daemon-reload"
  [ "${#FINAL[@]}" -gt 0 ] && faz "systemctl --user enable --now ${FINAL[*]}"
fi

diz ""
diz "Próximos passos:"
[ "$INDICE" = 1 ] && diz "  1. Edite indice/config.json (raiz e contas) e rode: projeto --atualizar"
[ "$MEMORIA" = 1 ] && diz "  2. Edite memoria/fontes.json e memoria/.env; teste: python3 $KIT/memoria/carga.py --simular"
[ "$MEMORIA" = 1 ] && diz "  3. 1ª carga (gasta cota da assinatura): python3 $KIT/memoria/carga.py --max 200"
case ":$PATH:" in *":$BIN:"*) ;; *) aviso "$BIN não está no PATH: acrescente no ~/.bashrc  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;; esac
