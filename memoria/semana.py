#!/usr/bin/env python3
"""Relatório da semana: a memória está ajudando ou não? Gera semana-AAAA-MM-DD.md nesta pasta.

Junta:
 1. uso real do comando memoria (uso.jsonl): quantas vezes, quem chamou, tempo, notas útil/inútil;
 2. adoção nas sessões dos agentes: chamadas ao memoria × grep nas fontes de sempre
    (as pastas de sessão ficam em "sessoes" no fontes.json; opcional);
 3. custo da carga (carga.jsonl): documentos e tokens aproximados enviados ao LLM;
 4. memória RAM do serviço do servidor;
 5. com --avaliar, refaz as perguntas do avalia.py para ver se a qualidade se manteve
    (gasta a cota da assinatura: 1 chamada de LLM por pergunta).

  python3 semana.py [--dias 7] [--avaliar]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(os.path.realpath(__file__)).parent
sys.path.insert(0, str(AQUI))
from hs import BANCO, SERVICO, caminho  # noqa: E402

RE_MEM = re.compile(r'(^|[\s;&|(\\"])memoria\s+(-r\s+|--recall\s+)?(\\"|\'|")')


def config_fontes():
    arq = Path(os.environ.get("MEMORIA_FONTES") or AQUI / "fontes.json")
    try:
        return json.loads(arq.read_text())
    except (OSError, ValueError):
        return {"fontes": []}


def re_grep(fontes):
    """grep em qualquer uma das fontes (pelo nome do arquivo ou da pasta)."""
    nomes = sorted({Path(os.path.expanduser(f["caminho"])).name for f in fontes if f.get("caminho")})
    if not nomes:
        return None
    return re.compile(r"grep[^\n]{0,200}(" + "|".join(re.escape(n) for n in nomes) + ")")


def le(arq, desde):
    if not arq.exists():
        return []
    out = []
    for l in arq.read_text().splitlines():
        try:
            r = json.loads(l)
            if datetime.fromisoformat(r["ts"]).timestamp() >= desde:
                out.append(r)
        except (ValueError, KeyError):
            continue
    return out


def sessoes(desde, pastas, rx_grep):
    """Conta, por fonte, sessões e comandos de ferramenta com memoria × grep nas fontes antigas."""
    cont = {}
    for s in pastas:
        raiz = caminho(s["pasta"])
        if not raiz.is_dir():
            continue
        n = m = g = 0
        for f in raiz.rglob("*.jsonl"):
            try:
                if f.stat().st_mtime < desde:
                    continue
                txt = f.read_text(errors="ignore")
            except OSError:
                continue
            n += 1
            for l in txt.splitlines():
                if '"tool_use"' not in l and '"function_call"' not in l and '"exec_command' not in l:
                    continue
                m += bool(RE_MEM.search(l))
                g += bool(rx_grep and rx_grep.search(l))
        cont[s["nome"]] = (n, m, g)
    return cont


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dias", type=int, default=7)
    ap.add_argument("--avaliar", action="store_true", help="refaz as perguntas do avalia.py (gasta cota)")
    a = ap.parse_args()
    cfg = config_fontes()
    desde = time.time() - a.dias * 86400
    ini = datetime.fromtimestamp(desde).strftime("%d/%m")
    uso = le(AQUI / "uso.jsonl", desde)
    carga = le(AQUI / "carga.jsonl", desde)
    perg = [u for u in uso if u.get("modo") in ("reflect", "recall")]
    notas = [u for u in uso if u.get("modo") == "nota"]
    erros = [u for u in uso if u.get("modo") == "erro"]
    md = [f"# Memória (Hindsight, banco {BANCO}) — semana {ini} a {datetime.now():%d/%m/%Y}", ""]

    md += ["## 1. Uso do comando memoria", ""]
    if perg:
        por = {}
        for u in perg:
            por[u["quem"]] = por.get(u["quem"], 0) + 1
        ts = sorted(u["s"] for u in perg)
        md += [f"- **{len(perg)} perguntas** ({', '.join(f'{k}: {v}' for k, v in por.items())}); "
               f"reflect {sum(u['modo'] == 'reflect' for u in perg)}, recall {sum(u['modo'] == 'recall' for u in perg)}",
               f"- Tempo: mediana {ts[len(ts) // 2]} s, máximo {ts[-1]} s · texto devolvido: {sum(u.get('tokens', 0) for u in perg):,} tokens no total",
               f"- Sem resposta: {sum(u.get('vazio', False) for u in perg)} · servidor fora: {len(erros)}",
               f"- Notas: {sum(n['nota'] == 'util' for n in notas)} útil, {sum(n['nota'] == 'inutil' for n in notas)} inútil"]
        md += [f"  - {n['nota']}: {n['motivo']}" for n in notas if n.get("motivo")]
        md += ["", "Perguntas feitas:"] + [f"- {u['ts'][5:16]} ({u['quem']}, {u['s']} s) {u['pergunta']}" for u in perg[-25:]]
    else:
        md += ["- **Nenhuma pergunta na semana.** Se o agente não usou, a regra não pegou ou o comando não ajuda."]
    if erros:
        md += ["- Erros: " + "; ".join(e["erro"][:80] for e in erros[-3:])]

    md += ["", "## 2. Adoção nas sessões (memoria × grep nas fontes)", ""]
    pastas = cfg.get("sessoes", [])
    s = sessoes(desde, pastas, re_grep(cfg.get("fontes", []))) if pastas else {}
    if s:
        for k, (n, m, g) in s.items():
            md.append(f"- {k}: {n} sessões · `memoria` {m} vezes · grep nas fontes {g} vezes")
        md.append("- Contagem aproximada (procura o texto do comando nas chamadas de ferramenta). Agente que não grava "
                  "sessão em arquivo não aparece aqui: para ele vale o campo `quem` da seção 1.")
    else:
        md.append("- Nenhuma pasta de sessão configurada ou encontrada (\"sessoes\" no fontes.json).")

    md += ["", "## 3. Custo da carga", ""]
    if carga:
        md += [f"- {len(carga)} execuções, {sum(c['docs'] for c in carga)} documentos gravados, "
               f"~{sum(c['tokens_aprox'] for c in carga):,} tokens de texto enviados (o servidor soma o prompt de "
               f"extração; no piloto foram ~5,6 mil tokens de entrada por documento)",
               f"- Pendentes/erros na última: {carga[-1]['pendentes']} " + "; ".join(carga[-1]["erros"][:2])]
    else:
        md += ["- Nenhuma carga registrada."]

    md += ["", "## 4. Máquina", ""]
    try:
        r = subprocess.run(["systemctl", "--user", "show", SERVICO, "-p", "ActiveState,MemoryCurrent,MemoryPeak,NRestarts"],
                           capture_output=True, text=True, timeout=20).stdout.split()
    except (OSError, subprocess.TimeoutExpired):
        r = []
    val = dict(x.split("=", 1) for x in r if "=" in x)
    gb = lambda v: f"{int(v) / 2**30:.1f} GB" if v.isdigit() else v  # noqa: E731
    md += [f"- Serviço {SERVICO}: {val.get('ActiveState', '?')} · RAM agora {gb(val.get('MemoryCurrent', '?'))} · "
           f"pico {gb(val.get('MemoryPeak', '?'))} · reinícios {val.get('NRestarts', '?')}"]

    if a.avaliar:
        md += ["", "## 5. Perguntas de avaliação, de novo", ""]
        p = subprocess.run([sys.executable, str(AQUI / "avalia.py")], capture_output=True, text=True, timeout=3600)
        md += [(AQUI / "resultado.md").read_text() if p.returncode == 0 else f"falhou: {p.stderr[-300:]}"]

    md += ["", "## Para decidir", "",
           "- Ajudou se: o agente usou (seções 1 e 2), as notas são mais úteis que inúteis, a qualidade se manteve "
           "(seção 5) e o custo da carga é pequeno.",
           "- Não ajudou se: quase ninguém chamou, as respostas vieram vazias ou erradas, ou o tempo atrapalhou. "
           f"Aí: mudar a regra do agente ou desligar (`systemctl --user disable --now {SERVICO} memoria-carga.timer "
           "memoria-semana.timer`)."]
    saida = AQUI / f"semana-{datetime.now():%Y-%m-%d}.md"
    saida.write_text("\n".join(md) + "\n")
    print(saida)


if __name__ == "__main__":
    main()
