# memoria-projetos — encuentra cualquier proyecto y consulta lo que ya se decidió

[![Memoria de Proyectos](guia/assets/banner-es.jpg)](https://inematds.github.io/memoria-projetos/guia/es/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## Qué es

memoria-projetos es un kit para quienes tienen muchos proyectos y trabajan con agentes de IA, como Claude Code y Codex. Resuelve dos problemas: el agente no sabe dónde está cada proyecto y olvida lo que ya se decidió. El comando `projeto` busca por lo que hace el proyecto, en tus carpetas y en GitHub. El comando `memoria` responde preguntas como «¿se puede hacer X?» leyendo tus lecciones y notas, con fecha y fuente. Para usarlo, necesitas una computadora con Linux, Python, Ollama y, para la memoria, una suscripción a Claude (sin clave de API). Todo el índice queda en tu computadora; la memoria envía el texto de las notas a Claude para extraer los hechos. Las dos partes son independientes: puedes instalar solo una.

## 📖 Guía de uso

Guía completa (landing + paso a paso): **https://inematds.github.io/memoria-projetos/guia/es/**

## Las dos partes

| Parte | Carpeta | Comando | Requisitos |
|---|---|---|---|
| Índice de proyectos | `indice/` | `projeto` | Python 3, Ollama con `bge-m3`, `gh` (opcional) |
| Memoria que responde | `memoria/` | `memoria` | Python 3, servidor Hindsight, CLI de Claude Code con sesión iniciada, Ollama con `bge-m3` |

## Requisitos previos

Instala y verifica lo siguiente antes (el `instalar.sh` solo verifica; no instala nada en el sistema):

1. **Python 3.11 o posterior** (`python3 --version`). Los comandos del kit usan solo la biblioteca estándar.
2. **Ollama** (https://ollama.com) en ejecución en `127.0.0.1:11434`, con el modelo multilingüe de vectores:
   ```bash
   ollama pull bge-m3
   ```
3. **Solo para el índice — GitHub CLI** (`gh`), con sesión iniciada en cada cuenta que quieras indexar:
   ```bash
   gh auth login            # repite para cada cuenta; el kit usa "gh auth token -u <conta>"
   gh auth status
   ```
   Sin `gh` (o con `"contas": []`), el índice incluirá solo las carpetas locales.
4. **Solo para la memoria — CLI de Claude Code** instalado y con sesión iniciada en tu suscripción (`claude` en el PATH; el kit antepone `~/.npm-global/bin` y `~/.local/bin`). El servidor usa el proveedor `claude-code` de Hindsight, que su documentación indica para **uso personal/local**.
5. **Solo para la memoria — conexión a internet una vez** al iniciar el servidor por primera vez: PostgreSQL integrado (pg0) y el modelo de reordenamiento se descargan en ese momento. Después, todo se ejecuta localmente.
6. **systemd de usuario** (Linux) para los horarios automáticos. Para que los temporizadores se ejecuten aunque no hayas iniciado sesión:
   ```bash
   loginctl enable-linger "$USER"
   ```
   Sin systemd, usa `--sem-systemd` y ejecuta los comandos manualmente (o mediante cron).

## Instalación

```bash
git clone https://github.com/inematds/memoria-projetos.git
cd memoria-projetos
./instalar.sh --dry-run                 # muestra todo lo que haría, sin escribir nada
./instalar.sh --instalar-hindsight      # instala las dos partes y el servidor Hindsight
```

Opciones de `instalar.sh` (puedes ejecutarlo cuantas veces quieras: solo escribe lo que cambió):

| Opción | Qué hace |
|---|---|
| `--so-indice` / `--so-memoria` | instala solo una parte |
| `--sem-systemd` | no crea servicios ni temporizadores |
| `--dry-run` | solo muestra lo que haría |
| `--instalar-hindsight` | crea `memoria/.venv` e instala Hindsight (≈2 GB) |
| `--forcar` | reemplaza un acceso directo o una unidad existente que no pertenezca a este kit |

Esto es lo que hace:

- copia `config.exemplo.json` → `config.json`, `sinonimos.exemplo.json` → `sinonimos.json`, `.env.exemplo` → `.env` y `fontes.exemplo.json` → `fontes.json` **solo si aún no existen** (nunca borra tu configuración);
- crea los accesos directos `~/.local/bin/projeto` y `~/.local/bin/memoria` que apuntan a esta carpeta;
- escribe las unidades de systemd de usuario con la ruta real de esta carpeta, límites de memoria (`MemoryMax`) y tiempo (`TimeoutStartSec`), `PATH` con `~/.npm-global/bin` y `~/.local/bin` al principio, y temporizadores `Persistent=true` (si la computadora estaba apagada a la hora programada, se ejecutan al encenderla):

| Unidad | Cuándo | Qué ejecuta | Límite |
|---|---|---|---|
| `memoria-indice.timer` | todos los días a las 05:40 | `projeto --atualizar` | 1 GB · 20 min |
| `memoria-hindsight.service` | siempre activo | servidor Hindsight en `127.0.0.1:8891` | 8 GB |
| `memoria-carga.timer` | todos los días a las 06:10 | `carga.py --max 25` | 512 MB · 60 min |
| `memoria-semana.timer` | lunes a las 08:00 | `semana.py --dias 7` | 512 MB · 30 min |

### Hindsight, si prefieres instalarlo manualmente

`--instalar-hindsight` hace exactamente esto (versión 1.0.0, la que se probó; la 1.2.0 ya está disponible en PyPI):

```bash
python3 -m venv memoria/.venv
memoria/.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu   # torch solo para CPU (mucho más pequeño)
memoria/.venv/bin/pip install hindsight-api==1.0.0
```

Si `hindsight-api` ya está instalado en otro lugar: `HINDSIGHT_BIN=/caminho/hindsight-api ./instalar.sh`.
También funciona desde el código fuente: `pip install -e "<pasta-do-clone>/hindsight-api-slim[all]"` (clon de https://github.com/vectorize-io/hindsight).
Los datos de la base de datos quedan en `~/.pg0` (PostgreSQL integrado).

## Configuración

### Índice — `indice/config.json`

| Campo | Para qué sirve |
|---|---|
| `raiz` | carpeta donde están tus proyectos (p. ej., `~/projetos`); cada subcarpeta con git o README se convierte en un proyecto |
| `contas` | cuentas de GitHub que se indexarán (`[]` = solo local). El orden importa: en una carpeta con varios remotos, prevalece la primera cuenta |
| `subpastas_com_readme` | carpetas (relativas a la raíz) cuyas subcarpetas con README también cuentan como proyectos (p. ej., una carpeta de herramientas) |
| `pular` / `pular_subpastas` | nombres de carpetas que nunca se incluyen |
| `saida_md` / `saida_jsonl` | dónde guardar el índice (predeterminado: dentro de `indice/`) |
| `ollama_url` / `ollama_modelo` | dónde están los vectores (predeterminado: `bge-m3` local) |
| `peso_palavra` | cuánto se suma la búsqueda por palabra a la búsqueda por sentido (predeterminado: 0,35) |

`sinonimos.json`: abreviaturas que equivalen a la palabra completa (`yt` → `youtube`, `ops` → `operacao`…). Añade las tuyas.

### Memoria — `memoria/.env` y `memoria/fontes.json`

En `.env`: `HINDSIGHT_URL`, `HINDSIGHT_BANCO` (una base de datos por proyecto o persona) y la configuración del servidor (LLM `claude-code` con `claude-haiku-5-5`, vectores `bge-m3` en Ollama, reordenamiento local). La línea de la clave de Ollama puede contener cualquier texto: Ollama no usa una clave.

En `fontes.json`, la lista de lo que se enviará a la memoria. Hay tres tipos:

| Tipo | Lee | Se convierte en |
|---|---|---|
| `linhas` | elementos `- ` de una lista markdown (p. ej., `LESSONS.md`) | las líneas nuevas del día, en bloques de hasta `bloco` líneas (predeterminado: 15) |
| `tabela` | filas de datos de tablas markdown (p. ej., `FALHAS.md`), sin encabezado | igual |
| `pasta-md` | cada archivo `.md` de una carpeta (p. ej., la memoria del agente) | un documento por archivo; si el archivo cambia, reemplaza el anterior |

Cada fuente tiene `nome` (no lo cambies después de la primera carga), `caminho`, `contexto` (una frase que explique qué es) y `tag`. En `pasta-md`, `ignorar` enumera los archivos que se excluyen (p. ej., el índice `MEMORY.md`).

**Costo de la carga.** La carga solo envía lo nuevo o lo que cambió; el contenido idéntico ni siquiera sale de la computadora. Pero cada documento enviado implica una llamada al LLM mediante tu suscripción. Medido en la prueba piloto: **~5,6 mil tokens de entrada de Haiku por documento; 100 documentos ≈ 8 min ≈ 566 mil tokens**. Por eso existe el límite `--max` (predeterminado: 25 por ejecución; lo que quede se procesa al día siguiente). La primera ejecución es la carga inicial: compruébalo antes con `--simular` y, si quieres hacer todo de una vez, usa `--max 200`.
Atención: editar una línea antigua (en `linhas` o `tabela`) cuesta dos llamadas: se vuelve a enviar el bloque antiguo sin esa línea y la nueva versión se añade al bloque del día. Añadir líneas nuevas no modifica los bloques antiguos.

## Uso

```bash
# índice
projeto --atualizar                      # rehace el índice y los vectores (≈1–2 min para mil proyectos)
projeto "separa operação do desenvolvimento"
projeto "publica vídeo no youtube" -n 5  # * en la nota = coincidieron todas las palabras

# memoria
python3 memoria/carga.py --simular       # lo que se guardaría (no envía nada)
python3 memoria/carga.py --max 200       # carga inicial
memoria "posso rodar processo longo sem teto de memória?"   # respuesta lista (30–75 s)
memoria -r "systemd PATH"                # solo los fragmentos (7–17 s, sin LLM en la respuesta)
memoria --nota util "achou a regra certa"                   # evalúa la última respuesta
python3 memoria/semana.py                # informe semanal → memoria/semana-AAAA-MM-DD.md
python3 memoria/avalia.py                # grep × recall × reflect en tus preguntas (consume cuota)
```

Si Ollama no está disponible, `projeto` usa solo la búsqueda por palabra y avisa. Si el servidor de memoria no está disponible, `memoria` avisa y termina con código 2: usa el grep de siempre.

`avalia.py` usa `perguntas.jsonl` (copia `perguntas.exemplo.jsonl` y escribe preguntas reales tuyas), una por línea: `{"pergunta": "...", "palavra_grep": "palavra que você usaria no grep", "gabarito": ["regex que a resposta certa precisa ter"]}`.

## El proceso, de principio a fin

🧠 sesión (tú, con o sin el agente) · ⚙️ script/temporizador · 🤖 agente

1. 🧠 Instala los requisitos previos (Ollama + `ollama pull bge-m3`, `gh auth login`, Claude Code con sesión iniciada, `loginctl enable-linger`).
2. 🧠 Ejecuta `./instalar.sh --dry-run` y luego `./instalar.sh --instalar-hindsight`.
3. 🧠 Ajusta `indice/config.json` (raíz y cuentas), `memoria/fontes.json` (tus fuentes) y `memoria/.env` (nombre de la base de datos).
4. 🧠 Primer índice: `projeto --atualizar`; verifica con `projeto "algo que sabes dónde está"`.
5. 🧠 Primera carga de memoria: `python3 memoria/carga.py --simular`, luego `python3 memoria/carga.py --max 200`.
6. 🧠 Pega la regla del agente (más abajo) en el `CLAUDE.md` / `AGENTS.md` de tus proyectos.
7. ⚙️ Todos los días a las 05:40: `memoria-indice.timer` rehace el índice y calcula vectores solo para lo que cambió.
8. ⚙️ Todos los días a las 06:10: `memoria-carga.timer` guarda en la memoria solo lo nuevo (máximo 25 documentos).
9. 🤖 Durante la sesión, pregunta «¿qué proyecto hace X / dónde está Y?» → ejecuta `projeto "X"` antes de recorrer carpetas.
10. 🤖 Durante la sesión, pregunta de regla o decisión («¿se puede hacer X?», «¿qué decidimos sobre Y?») → ejecuta `memoria "…"` antes de grep; después, `memoria --nota util|inutil "motivo"`.
11. ⚙️ Todos los lunes a las 08:00: `memoria-semana.timer` genera `memoria/semana-AAAA-MM-DD.md` (uso, adopción por el agente, costo, RAM).
12. 🧠 Lee el informe: decide si te resultó útil, cambia la regla del agente o desactívalo. De vez en cuando, ejecuta `python3 memoria/avalia.py` para medir la calidad.

Desactivar todo: `systemctl --user disable --now memoria-hindsight.service memoria-carga.timer memoria-semana.timer memoria-indice.timer`.

## Cómo hacer que el agente lo use

El agente solo usa lo que dice su regla. Pega esto en el `CLAUDE.md` (Claude Code) o el `AGENTS.md` (Codex) de tus proyectos, o en el archivo global de instrucciones:

```markdown
## Encontrar proyectos y consultar la memoria

- Preguntas como «¿qué proyecto hace X?» o «¿dónde está Y?»: ejecuta `projeto "X"` ANTES de recorrer carpetas
  o revisar el historial. No leas el archivo proyectos.md completo; usa el comando o `grep -i`.
- Preguntas sobre reglas, decisiones o errores ya conocidos («¿se puede hacer X?», «¿qué decidimos sobre Y?»,
  «¿qué error ocurrió con Z?»): ejecuta `memoria "pregunta"` (respuesta lista) o `memoria -r "palavras"`
  (solo fragmentos, más rápido) ANTES de buscar con grep en las lecciones y fallas.
- Después de usar la respuesta, evalúala: `memoria --nota util "motivo"` o `memoria --nota inutil "motivo"`.
- Si `memoria` termina con código 2 (servidor no disponible), continúa con el grep de siempre e informa.
```

No pongas la respuesta de la memoria al comienzo de cada sesión: el agente consulta cuando lo necesita. Así el inicio de la sesión siempre es igual (la caché funciona) y solo se consume cuota cuando hay una pregunta.

## Créditos

- La memoria usa **Hindsight**, de vectorize-io, con licencia MIT: https://github.com/vectorize-io/hindsight
- Espejo y guía en portugués: https://github.com/inematds/hindsight · https://inematds.github.io/hindsight/guia/
- Vectores: modelo `bge-m3` (BAAI) servido por Ollama.

## Licencia

MIT — consulta [LICENSE](LICENSE). © 2026 INEMA.
