"""Leitura da configuração do índice (config.json; se não existir, config.exemplo.json)."""
import json
import os
from pathlib import Path

AQUI = Path(os.path.realpath(__file__)).parent

PADRAO = {
    "raiz": "~/projetos",
    "contas": [],
    "subpastas_com_readme": [],
    "pular": ["output", "node_modules", "__pycache__", "lost+found"],
    "pular_subpastas": ["longrun", "handoffs"],
    "saida_md": "projetos.md",
    "saida_jsonl": "projetos.jsonl",
    "ollama_url": "http://127.0.0.1:11434/api/embed",
    "ollama_modelo": "bge-m3",
    "peso_palavra": 0.35,
}


def caminho(valor):
    """Expande ~ e variáveis; caminho relativo fica relativo à pasta indice/."""
    p = Path(os.path.expandvars(os.path.expanduser(str(valor))))
    return p if p.is_absolute() else AQUI / p


def carregar_config():
    arq = os.environ.get("INDICE_CONFIG")
    candidatos = [Path(arq)] if arq else [AQUI / "config.json", AQUI / "config.exemplo.json"]
    cfg = dict(PADRAO)
    for c in candidatos:
        if c.exists():
            cfg.update({k: v for k, v in json.loads(c.read_text()).items() if not k.startswith("_")})
            cfg["_arquivo"] = str(c)
            break
    return cfg


def carregar_sinonimos():
    for nome in ("sinonimos.json", "sinonimos.exemplo.json"):
        p = AQUI / nome
        if p.exists():
            d = json.loads(p.read_text())
            return {k: v for k, v in d.items() if not k.startswith("_")}
    return {}
