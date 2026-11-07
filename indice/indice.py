#!/usr/bin/env python3
"""Gera o índice de projetos: projetos.md (uma linha por projeto) + projetos.jsonl.

Fontes (tudo vem do config.json; sem ele, do config.exemplo.json):
  - as pastas da "raiz" (ex.: ~/projetos);
  - as subpastas com README das pastas listadas em "subpastas_com_readme";
  - os repositórios das "contas" do GitHub (pelo gh; cada conta usa o próprio token).
Cada projeto sai como: local + GitHub, só local ou só GitHub.
Só leitura: não mexe em repositório nenhum. O README de quem só está no GitHub vem do gh
e fica em cache até o próximo push.

  python3 indice.py
"""
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(os.path.realpath(__file__)).parent
sys.path.insert(0, str(AQUI))
from comum import caminho, carregar_config  # noqa: E402

CFG = carregar_config()
HOME = Path.home()
RAIZ = caminho(CFG["raiz"])
CONTAS = list(CFG["contas"])
SUBPASTAS = [caminho(x) if os.path.isabs(os.path.expanduser(x)) else RAIZ / x for x in CFG["subpastas_com_readme"]]
PULAR = set(CFG["pular"])
PULAR_SUB = set(CFG["pular_subpastas"])
SAIDA_MD = caminho(CFG["saida_md"])
SAIDA_JSONL = caminho(CFG["saida_jsonl"])
CACHE = AQUI / "cache-readme.json"
MAX_DESC = 220
IDIOMAS = re.compile(r"Portugu[eê]s|English|Espa[nñ]ol|Ingl[eê]s", re.I)


def sh(cmd, cwd=None, env=None, timeout=60):
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def limpa(t):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)          # imagens
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)     # links → texto
    t = re.sub(r"[*_`]+", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmlmod.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:MAX_DESC].rstrip() + ("…" if len(t) > MAX_DESC else "")


def primeiro_paragrafo(texto):
    """Primeira prosa útil de um markdown (pula título, selos, troca de idioma, citações)."""
    if not texto:
        return ""
    bloco, em_codigo = [], False
    for linha in texto.splitlines():
        s = linha.strip()
        if s.startswith("```"):
            em_codigo = not em_codigo
            continue
        if em_codigo or s.startswith("<!--"):
            continue
        ruim = (not s or s.startswith(("#", "[![", "![", ">", "|", "---", "<", "**[", "[English", "[Português"))
                or re.fullmatch(r"[\W_]+", s) or len(re.sub(r"[^\w]", "", s)) < 12)
        if ruim:
            if bloco:
                break
            continue
        if IDIOMAS.search(s) and len(IDIOMAS.findall(s)) >= 2:
            if bloco:
                break
            continue
        bloco.append(s.lstrip("-* "))
        if sum(len(b) for b in bloco) > MAX_DESC:
            break
    return limpa(" ".join(bloco))


def limpa_longo(t):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"<[^>]+>|[*_`|>]+", " ", t)
    return re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()


def texto_busca(md, n=1500):
    """Títulos + prosa do começo do markdown, para a busca (não aparece no projetos.md)."""
    if not md:
        return ""
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    titulos = " · ".join(t.strip("# ").strip() for t in re.findall(r"^#{1,3} .+$", md, re.M)[:25])
    prosa = limpa_longo(re.sub(r"^#.*$", " ", md, flags=re.M))
    return (titulos + " | " + prosa)[:n]


def le(p, n=20000):
    try:
        return p.read_text(errors="ignore")[:n]
    except Exception:
        return ""


def busca_local(pasta):
    partes = []
    for nome in ("README.md", "readme.md", "CLAUDE.md", "AGENTS.md"):
        t = le(pasta / nome)
        if t:
            partes.append(texto_busca(t, 1200))
        if sum(len(x) for x in partes) > 1500:
            break
    return " ".join(partes)[:2000]


def desc_local(pasta):
    for nome in ("README.md", "readme.md", "README.MD", "README.pt.md", "README"):
        d = primeiro_paragrafo(le(pasta / nome))
        if d:
            return d
    for nome in ("CLAUDE.md", "AGENTS.md"):
        d = primeiro_paragrafo(le(pasta / nome))
        if d:
            return d
    for html in ("index.html", "guia/index.html", "curso/index.html"):
        m = re.search(r"<title[^>]*>(.*?)</title>", le(pasta / html), re.S | re.I)
        if m and limpa(m.group(1)):
            return limpa(m.group(1))
    try:
        d = json.loads(le(pasta / "package.json")).get("description", "")
        if d:
            return limpa(d)
    except Exception:
        pass
    return ""


def ordem_conta(repo):
    dono = repo.split("/")[0].lower()
    contas = [c.lower() for c in CONTAS]
    return (contas.index(dono) if dono in contas else len(contas), repo.lower())


def remotos(pasta):
    """Lista de (remoto, 'dono/repo') do GitHub; contas do config primeiro, na ordem do config."""
    out = sh(["git", "remote", "-v"], cwd=pasta)
    achados = {}
    for m in re.finditer(r"^(\S+)\s+\S*github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?\s", out + " ", re.M):
        r = f"{m.group(2)}/{m.group(3)}"
        achados.setdefault(r, m.group(1))
    return sorted(achados, key=ordem_conta), achados


def coleta_locais():
    if not RAIZ.is_dir():
        print(f"aviso: raiz {RAIZ} não existe", file=sys.stderr)
        return []
    pastas = [p for p in RAIZ.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in PULAR]
    # pastas cujas subpastas com README próprio também contam como projeto
    for sp in SUBPASTAS:
        if sp.is_dir():
            pastas += [p for p in sp.iterdir() if p.is_dir() and not p.name.startswith(".")
                       and p.name not in PULAR | PULAR_SUB and (p / "README.md").exists()]
    itens = []
    for p in sorted(set(pastas)):
        eh_git = (p / ".git").exists()
        tem_doc = any((p / n).exists() for n in ("README.md", "CLAUDE.md", "AGENTS.md", "package.json"))
        if not eh_git and not tem_doc:
            continue
        data = sh(["git", "log", "-1", "--format=%cs"], cwd=p) if eh_git else ""
        if not data:
            data = time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime))
        repos, nomes_remoto = remotos(p) if eh_git else ([], {})
        itens.append({
            "nome": p.name if p.parent == RAIZ else f"{p.parent.name}/{p.name}",
            "pasta": str(p).replace(str(HOME), "~", 1),
            "repos": repos,
            "remotos": nomes_remoto,
            "git": eh_git,
            "data_local": data,
            "desc_local": desc_local(p),
            "busca": busca_local(p),
            "guia": (p / "guia" / "index.html").exists(),
        })
    return itens


def env_conta(conta):
    """Ambiente com o token da conta (gh auth token -u). Sem ele, usa a conta ativa do gh."""
    env = dict(os.environ)
    tok = sh(["gh", "auth", "token", "-u", conta]) or ""
    if tok:
        env["GH_TOKEN"] = tok
    return env


def coleta_github():
    repos = {}
    if not CONTAS:
        print("  github: nenhuma conta no config (só pastas locais)", file=sys.stderr)
        return repos
    for conta in CONTAS:
        env = env_conta(conta)
        out = sh(["gh", "repo", "list", conta, "--limit", "3000", "--json",
                  "nameWithOwner,description,isPrivate,isFork,pushedAt,homepageUrl"], env=env, timeout=180)
        try:
            lista = json.loads(out or "[]")
        except Exception:
            lista = []
        print(f"  github {conta}: {len(lista)} repos", file=sys.stderr)
        for r in lista:
            r["_env_conta"] = conta
            repos[r["nameWithOwner"].lower()] = r
    return repos


def readme_remoto(r, cache, envs):
    chave = r["nameWithOwner"].lower()
    c = cache.get(chave)
    if c and c.get("pushedAt") == r.get("pushedAt") and "busca" in c:
        return c.get("desc", ""), c.get("busca", "")
    conta = r["_env_conta"]
    if conta not in envs:
        envs[conta] = env_conta(conta)
    texto = sh(["gh", "api", f"repos/{r['nameWithOwner']}/readme", "-H", "Accept: application/vnd.github.raw"],
               env=envs[conta], timeout=30)
    d = primeiro_paragrafo(texto[:20000])
    b = texto_busca(texto[:20000], 2000)
    cache[chave] = {"pushedAt": r.get("pushedAt"), "desc": d, "busca": b}
    return d, b


def confere_atras(lista):
    """A data só levanta suspeita; aqui confere o commit do GitHub (git ls-remote) contra a pasta.
    Usa o próprio remoto da pasta, então vale a autenticação que a pessoa já tem (SSH ou HTTPS)."""
    from concurrent.futures import ThreadPoolExecutor

    def um(i):
        p = os.path.expanduser(i["pasta"])
        remoto = i.get("_remoto") or f"https://github.com/{i['repo']}.git"
        o = sh(["git", "ls-remote", remoto, "HEAD"], cwd=p, timeout=40).split()
        if not o:
            return "?"
        if subprocess.run(["git", "cat-file", "-e", o[0] + "^{commit}"], cwd=p, capture_output=True).returncode:
            return "atrás"
        ok = subprocess.run(["git", "merge-base", "--is-ancestor", o[0], "HEAD"], cwd=p, capture_output=True)
        return "" if ok.returncode == 0 else "divergiu"

    with ThreadPoolExecutor(12) as ex:
        for i, e in zip(lista, ex.map(um, lista)):
            i["atras"] = bool(e and e != "?")
            i["estado_git"] = e


def main():
    t0 = time.time()
    locais = coleta_locais()
    gh = coleta_github()
    try:
        cache = json.loads(CACHE.read_text())
    except Exception:
        cache = {}

    itens, usados = [], set()
    for l in locais:
        r = next((gh[x.lower()] for x in l["repos"] if x.lower() in gh), None)
        if r:
            usados.add(r["nameWithOwner"].lower())
        repo = r["nameWithOwner"] if r else (l["repos"][0] if l["repos"] else "")
        desc_gh = (r or {}).get("description") or ""
        if len(IDIOMAS.findall(desc_gh)) >= 2:
            desc_gh = ""
        desc = desc_gh or l["desc_local"]
        data_gh = ((r or {}).get("pushedAt") or "")[:10]
        onde = "local + GitHub" if repo else "só local"
        remoto = next((v for k, v in l["remotos"].items() if k.lower() == repo.lower()), "") if repo else ""
        itens.append({
            "nome": l["nome"], "onde": onde, "pasta": l["pasta"], "repo": repo, "_remoto": remoto,
            "privado": (r or {}).get("isPrivate"), "fork": (r or {}).get("isFork", False),
            "desc": limpa(desc) if desc else "",
            "busca": l["busca"],
            "ultimo": max(l["data_local"], data_gh),
            "atras": bool(data_gh and l["git"] and data_gh > l["data_local"]),
            "outros_remotos": [x for x in l["repos"] if x.lower() != repo.lower()],
            "guia": (f"https://{repo.split('/')[0].lower()}.github.io/{repo.split('/')[1]}/guia/"
                     if l["guia"] and repo and not (r or {}).get("isPrivate") else ""),
            "site": (r or {}).get("homepageUrl") or "",
        })
    envs = {}
    for chave, r in gh.items():
        if chave in usados:
            continue
        d_readme, busca = readme_remoto(r, cache, envs)
        desc = r.get("description") or d_readme
        itens.append({
            "nome": r["nameWithOwner"].split("/")[1], "onde": "só GitHub", "pasta": "", "repo": r["nameWithOwner"],
            "privado": r.get("isPrivate"), "fork": r.get("isFork", False), "desc": limpa(desc) if desc else "",
            "busca": busca,
            "ultimo": (r.get("pushedAt") or "")[:10], "atras": False, "outros_remotos": [],
            "guia": "", "site": r.get("homepageUrl") or "",
        })
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
    confere_atras([i for i in itens if i["atras"]])
    itens.sort(key=lambda i: i["ultimo"], reverse=True)

    SAIDA_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA_JSONL.open("w") as f:
        for i in itens:
            f.write(json.dumps({k: v for k, v in i.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    cont = {k: sum(1 for i in itens if i["onde"] == k) for k in ("local + GitHub", "só local", "só GitHub")}
    sem = sum(1 for i in itens if not i["desc"])
    atras = sum(1 for i in itens if i["atras"])
    linhas = [
        "# Projetos — índice (gerado, não editar à mão)",
        "",
        f"Gerado em {time.strftime('%d/%m/%Y %H:%M')} pelo `indice/indice.py` do kit memoria-projetos. "
        f"{len(itens)} projetos: {cont['local + GitHub']} local + GitHub · {cont['só local']} só local · "
        f"{cont['só GitHub']} só GitHub · {sem} sem descrição · {atras} com a pasta local atrás ou divergente do GitHub (conferido por commit).",
        "",
        "**Buscar:** `projeto \"o que faz\"` (palavra + sentido, local). Não ler este arquivo inteiro; usar o comando ou `grep -i`.",
        "",
        "Formato: `nome — descrição · onde · pasta · repo · último commit/push · guia/site`",
        "",
    ]
    for i in itens:
        partes = [f"- **{i['nome']}** — {i['desc'] or '(sem descrição)'}", i["onde"]]
        if i["pasta"]:
            partes.append(i["pasta"])
        if i["repo"]:
            extra = " privado" if i["privado"] else ""
            extra += " fork" if i["fork"] else ""
            partes.append(f"{i['repo']}{(' (' + extra.strip() + ')') if extra else ''}")
        if i["outros_remotos"]:
            partes.append("também " + ", ".join(i["outros_remotos"]))
        partes.append(i["ultimo"] + (f" (pasta {i.get('estado_git', 'atrás')} do GitHub)" if i["atras"] else ""))
        if i["guia"]:
            partes.append(i["guia"])
        elif i["site"]:
            partes.append(i["site"])
        linhas.append(" · ".join(partes))
    SAIDA_MD.parent.mkdir(parents=True, exist_ok=True)
    SAIDA_MD.write_text("\n".join(linhas) + "\n")
    print(f"ok: {len(itens)} projetos ({cont}) sem_desc={sem} atras={atras} em {time.time()-t0:.0f}s → {SAIDA_MD}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
