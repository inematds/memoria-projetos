#!/usr/bin/env python3
"""Cliente mínimo do Hindsight (servidor e banco vêm do .env desta pasta).

  hs.py retain <arquivo.jsonl>     # cada linha: {"content","context","timestamp","document_id","tags"}
  hs.py recall "pergunta" [-n 8]
  hs.py reflect "pergunta"
  hs.py stats

Variáveis (no .env ou no ambiente): HINDSIGHT_URL (padrão http://127.0.0.1:8891)
e HINDSIGHT_BANCO (padrão "projeto"). Só biblioteca padrão do Python: roda com o python3 do sistema.
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(os.path.realpath(__file__)).parent


def le_env(arq=AQUI / ".env"):
    """Lê um .env simples (CHAVE=valor, # comentário). O ambiente tem prioridade."""
    vals = {}
    if arq.exists():
        for linha in arq.read_text().splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    vals.update({k: v for k, v in os.environ.items() if k.startswith("HINDSIGHT_")})
    return vals


ENV = le_env()
URL = ENV.get("HINDSIGHT_URL") or f"http://127.0.0.1:{ENV.get('HINDSIGHT_API_PORT', '8891')}"
BANCO = ENV.get("HINDSIGHT_BANCO", "projeto")
BASE = f"{URL.rstrip('/')}/v1/default/banks/{BANCO}"
SERVICO = ENV.get("HINDSIGHT_SERVICO", "memoria-hindsight")


def caminho(valor):
    """Expande ~ e variáveis; caminho relativo fica relativo à pasta memoria/."""
    p = Path(os.path.expandvars(os.path.expanduser(str(valor))))
    return p if p.is_absolute() else AQUI / p


def carregar_fontes(arq=None):
    """Lista de fontes do fontes.json (ou do arquivo em MEMORIA_FONTES / do argumento)."""
    arq = Path(arq or os.environ.get("MEMORIA_FONTES") or AQUI / "fontes.json")
    if not arq.exists():
        sys.exit(f"falta {arq}: copie fontes.exemplo.json para fontes.json e ajuste os caminhos")
    fontes = json.loads(arq.read_text())["fontes"]
    for f in fontes:
        f["_caminho"] = caminho(f["caminho"])
        f.setdefault("nome", f.get("tag", f["_caminho"].stem))
        f.setdefault("tag", f["nome"])
        f.setdefault("contexto", f"{f['tipo']} de {f['_caminho'].name}")
    return fontes


def call(metodo, rota, corpo=None, timeout=900):
    req = urllib.request.Request(BASE + rota, method=metodo,
                                 data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["retain", "recall", "reflect", "stats"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("-n", type=int, default=8)
    ap.add_argument("--lote", type=int, default=10)
    ap.add_argument("--async", dest="assinc", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    if a.cmd == "retain":
        itens = [json.loads(l) for l in open(a.arg)]
        for n in range(0, len(itens), a.lote):
            lote = itens[n:n + a.lote]
            r = call("POST", "/memories", {"items": lote, "async": a.assinc})
            print(f"{n + len(lote)}/{len(itens)} {time.time() - t0:.0f}s {str(r)[:160]}", flush=True)
    elif a.cmd == "recall":
        r = call("POST", "/memories/recall", {"query": a.arg, "budget": "mid", "max_tokens": 2500})
        for x in r.get("results", [])[:a.n]:
            print(f"- [{x.get('type', '')}] {x.get('text', '')[:260]}")
    elif a.cmd == "reflect":
        r = call("POST", "/reflect", {"query": a.arg, "budget": "mid"})
        print(r.get("text") or json.dumps(r, ensure_ascii=False)[:3000])
    elif a.cmd == "stats":
        print(json.dumps(call("GET", "/memories/list?limit=1"), ensure_ascii=False)[:600])
    print(f"({time.time() - t0:.1f}s · banco {BANCO} em {URL})", file=sys.stderr)


if __name__ == "__main__":
    main()
