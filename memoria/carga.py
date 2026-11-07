#!/usr/bin/env python3
"""Carga incremental do Hindsight: grava só o que é novo ou mudou desde a última vez.

As fontes ficam no fontes.json (veja fontes.exemplo.json). Três tipos:
- linhas   : itens "- " de uma lista markdown (ex.: LESSONS.md). As linhas vistas pela 1ª vez no
             mesmo dia viram documentos de até "bloco" linhas (<nome>-AAAAMMDD-<n>).
- tabela   : linhas de dados de tabelas markdown (sem cabeçalho e sem a linha ---). Mesmo esquema.
- pasta-md : cada arquivo .md da pasta vira o documento <nome>-<arquivo>; se o arquivo mudar,
             o documento é substituído (mesmo document_id).
Se o mesmo document_id voltar com outro conteúdo, o servidor substitui o anterior; conteúdo
idêntico nem é enviado (o estado guarda um hash de cada documento).

A 1ª execução É a carga inicial: tudo é novo. Cada documento = 1 chamada ao LLM do servidor
(no piloto, ~5,6 mil tokens de entrada do Haiku por documento; 100 documentos ≈ 8 min ≈ 566 mil
tokens, pela assinatura). Por isso o teto --max (padrão 25 por execução); o que sobrar vai na próxima.
Para a 1ª carga, rode antes com --simular e depois, se quiser, com --max 200.

Estado em estado-carga.json; cada execução vira uma linha em carga.jsonl (base do relatório da semana).

  python3 carga.py --simular          # só mostra o que seria gravado
  python3 carga.py [--max 25]
"""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import os

AQUI = Path(os.path.realpath(__file__)).parent
sys.path.insert(0, str(AQUI))
from hs import BANCO, call, carregar_fontes  # noqa: E402

ESTADO = AQUI / "estado-carga.json"
LOG = AQUI / "carga.jsonl"
SEPARADOR = re.compile(r"^\|[\s:|-]+\|?$")


def h(t):
    return hashlib.sha1(t.encode()).hexdigest()[:16]


def linhas_uteis(fonte):
    arq = fonte["_caminho"]
    if not arq.exists():
        print(f"aviso: {arq} não existe (fonte {fonte['nome']})", file=sys.stderr)
        return []
    brutas = [l.strip() for l in arq.read_text(errors="ignore").splitlines()]
    out = []
    if fonte["tipo"] == "linhas":
        out = [l for l in brutas if l.startswith("- ") and len(l) > 3]
    elif fonte["tipo"] == "tabela":
        for n, l in enumerate(brutas):
            if not l.startswith("|") or SEPARADOR.match(l):
                continue
            if n + 1 < len(brutas) and SEPARADOR.match(brutas[n + 1]):
                continue  # cabeçalho da tabela
            if re.sub(r"[|\s]", "", l):
                out.append(l)
    seen, unicas = set(), []
    for l in out:
        if l not in seen:
            seen.add(l)
            unicas.append(l)
    return unicas


def docs_de_linhas(fonte, est, hoje, agora):
    nome, bloco = fonte["nome"], int(fonte.get("bloco", 15))
    vistas = est["linhas"].setdefault(nome, {})
    linhas = linhas_uteis(fonte)
    for l in linhas:
        vistas.setdefault(h(l), hoje)
    por_dia = {}
    for l in linhas:  # agrupa pela data em que a linha apareceu pela 1ª vez, na ordem do arquivo
        por_dia.setdefault(vistas[h(l)], []).append(l)
    docs = []
    for dia in sorted(por_dia):
        grupo = por_dia[dia]
        for k in range(0, len(grupo), bloco):
            corpo = "\n".join(grupo[k:k + bloco])
            did = f"{nome}-{dia}-{k // bloco + 1}"
            if est["docs"].get(did) != h(corpo):
                docs.append({"item": {"content": corpo, "context": fonte["contexto"], "timestamp": agora,
                                      "document_id": did, "tags": [fonte["tag"]]}, "did": did, "hash": h(corpo)})
    return docs


def tipo_mem(texto):
    m = re.search(r"^\s*type:\s*(\w+)", texto, re.M)
    return m.group(1) if m else ""


def docs_de_pasta(fonte, est):
    pasta = fonte["_caminho"]
    if not pasta.is_dir():
        print(f"aviso: pasta {pasta} não existe (fonte {fonte['nome']})", file=sys.stderr)
        return []
    ignorar = set(fonte.get("ignorar", []))
    padrao = "**/*.md" if fonte.get("recursivo") else "*.md"
    docs = []
    for f in sorted(pasta.glob(padrao)):
        if f.name in ignorar or not f.is_file():
            continue
        txt = f.read_text(errors="ignore")
        if not txt.strip():
            continue
        rel = f.relative_to(pasta).with_suffix("").as_posix().replace("/", "--")
        did = f"{fonte['nome']}-{rel}"
        if est["docs"].get(did) != h(txt):
            ts = datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(timespec="seconds")
            t = tipo_mem(txt)
            docs.append({"item": {"content": txt, "context": f"{fonte['contexto']} (arquivo {f.name})", "timestamp": ts,
                                  "document_id": did, "tags": [fonte["tag"] + (f"-{t}" if t else "")]},
                         "did": did, "hash": h(txt)})
    return docs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=25, help="teto de documentos por execução (padrão 25)")
    ap.add_argument("--simular", action="store_true", help="só mostra o que seria gravado (não envia nada)")
    ap.add_argument("--fontes", help="outro arquivo de fontes (padrão: fontes.json)")
    a = ap.parse_args()
    fontes = carregar_fontes(a.fontes)
    est = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    primeira = not est
    est.setdefault("linhas", {})
    est.setdefault("docs", {})
    hoje = datetime.now().strftime("%Y%m%d")
    agora = datetime.now().astimezone().isoformat(timespec="seconds")

    docs = []
    for f in fontes:
        if f["tipo"] in ("linhas", "tabela"):
            docs += docs_de_linhas(f, est, hoje, agora)
        elif f["tipo"] == "pasta-md":
            docs += docs_de_pasta(f, est)
        else:
            print(f"aviso: tipo desconhecido '{f['tipo']}' na fonte {f['nome']}", file=sys.stderr)

    fila, sobra = docs[:a.max], len(docs) - min(len(docs), a.max)
    print(("1ª carga (sem estado ainda). " if primeira else "")
          + f"{len(docs)} documento(s) novo(s)/alterado(s); {'seriam gravados' if a.simular else 'gravando'} {len(fila)}"
          + (f", {sobra} ficam para a próxima execução" if sobra else "") + f" · banco {BANCO}")
    if a.simular:
        for d in fila:
            print(f" - {d['did']}  ({len(d['item']['content'])} car., tag {d['item']['tags'][0]})")
        print(f"estimativa: ~{len(fila) * 5600:,} tokens de entrada do LLM (≈5,6 mil por documento, medido no piloto)")
        return  # não grava estado nenhum
    t0, ok, erros, chars = time.time(), 0, [], 0
    for d in fila:
        try:
            call("POST", "/memories", {"items": [d["item"]], "async": False}, timeout=900)
            ok += 1
            chars += len(d["item"]["content"])
            est["docs"][d["did"]] = d["hash"]
            ESTADO.write_text(json.dumps(est, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            erros.append(f"{d['did']}: {str(e)[:120]}")
    ESTADO.write_text(json.dumps(est, ensure_ascii=False))
    reg = {"ts": agora, "docs": ok, "pendentes": sobra + len(erros), "caracteres": chars,
           "tokens_aprox": chars // 4, "s": round(time.time() - t0), "erros": erros}
    with LOG.open("a") as fh:
        fh.write(json.dumps(reg, ensure_ascii=False) + "\n")
    print(json.dumps(reg, ensure_ascii=False))
    if erros:
        sys.exit(1)


if __name__ == "__main__":
    main()
