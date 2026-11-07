#!/usr/bin/env python3
"""Compara o jeito de sempre (grep na palavra óbvia) com o Hindsight (recall e reflect) em perguntas reais.

Perguntas em perguntas.jsonl (sem ele, perguntas.exemplo.jsonl), uma por linha:
  {"pergunta": "...", "palavra_grep": "...", "gabarito": ["regex", "regex|alternativa"]}
Todo item do gabarito precisa aparecer na resposta (sem acento e sem diferença de maiúscula).
O grep procura a palavra nos arquivos e pastas listados no fontes.json.

Mede: acertou? quanto texto o agente teria de ler (≈ tokens = caracteres/4)? quanto tempo?
Saída: tabela em resultado.md + bruto em resultado.json (os dois ficam fora do git).
Custo: cada pergunta faz 1 reflect = 1 chamada de LLM pela assinatura.

  python3 avalia.py [--perguntas arquivo.jsonl]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

AQUI = Path(os.path.realpath(__file__)).parent
sys.path.insert(0, str(AQUI))
from hs import carregar_fontes  # noqa: E402


def norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def acerta(texto, gabarito):
    n = norm(texto)
    return all(re.search(norm(g), n) for g in gabarito)


def grep(palavra, alvos):
    if not alvos:
        return ""
    r = subprocess.run(["grep", "-rhi", "--include=*.md", palavra] + alvos, capture_output=True, text=True,
                       timeout=120)
    return r.stdout


def hs(cmd, q):
    t0 = time.time()
    r = subprocess.run([sys.executable, str(AQUI / "hs.py"), cmd, q, "-n", "8"], capture_output=True, text=True,
                       timeout=600)
    return r.stdout, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perguntas", help="arquivo .jsonl (padrão: perguntas.jsonl ou perguntas.exemplo.jsonl)")
    a = ap.parse_args()
    arq = Path(a.perguntas) if a.perguntas else next(
        (p for p in (AQUI / "perguntas.jsonl", AQUI / "perguntas.exemplo.jsonl") if p.exists()), None)
    if not arq:
        sys.exit("falta perguntas.jsonl")
    perguntas = [json.loads(l) for l in arq.read_text().splitlines() if l.strip()]
    alvos = [str(f["_caminho"]) for f in carregar_fontes() if f["_caminho"].exists()]

    linhas, bruto = [], []
    tot = {"grep": [0, 0], "recall": [0, 0], "reflect": [0, 0]}
    for p in perguntas:
        q, palavra, gab = p["pergunta"], p["palavra_grep"], p["gabarito"]
        t0 = time.time()
        g = grep(palavra, alvos)
        tg = time.time() - t0
        rc, trc = hs("recall", q)
        rf, trf = hs("reflect", q)
        res = {}
        for nome, txt, t in (("grep", g, tg), ("recall", rc, trc), ("reflect", rf, trf)):
            ok = acerta(txt, gab)
            res[nome] = {"ok": ok, "tokens": len(txt) // 4, "s": round(t, 1)}
            tot[nome][0] += ok
            tot[nome][1] += len(txt) // 4
        bruto.append({"pergunta": q, "palavra": palavra, "gabarito": gab, "res": res,
                      "reflect": rf[:1500], "recall": rc[:1500]})
        linhas.append(f"| {q} | " + " | ".join(
            f"{'✅' if res[k]['ok'] else '❌'} {res[k]['tokens']:,} tk · {res[k]['s']}s" for k in ("grep", "recall", "reflect")) + " |")
        print(linhas[-1], flush=True)
    n = len(perguntas)
    linhas.append("| **Total** | " + " | ".join(f"**{tot[k][0]}/{n}** · {tot[k][1]:,} tk" for k in ("grep", "recall", "reflect")) + " |")
    md = ["| pergunta | grep (de sempre) | Hindsight recall | Hindsight reflect |", "|---|---|---|---|"] + linhas
    (AQUI / "resultado.md").write_text("\n".join(md) + "\n")
    (AQUI / "resultado.json").write_text(json.dumps(bruto, ensure_ascii=False, indent=1))
    print(linhas[-1])


if __name__ == "__main__":
    main()
