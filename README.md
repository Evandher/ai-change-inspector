# AI Change Inspector

Auditor independiente de cambios de Git para la Meta AI Developer Hackathon 2026.
Conserva el explorador y parser determinista del Sprint 1. En Sprint 2, Muse Spark 1.3 propone
riesgos y el backend valida sus referencias de forma independiente. Los hallazgos siguen siendo
hipótesis, incluso cuando todas sus referencias coinciden con el diff.
Sprint 3 añade un MCP local por stdio para pedir auditorías explícitas de cambios Git.
No hay autenticación, base de datos, historial, hooks, Skills ni ejecución de código del diff.

## Requisitos

- Node.js 22.12 o superior (verificado con 22.14.0) y npm (verificado con 11.6.0).
- Python 3.12 (verificado con 3.12.1).
- Git para producir diffs; el parser no ejecuta Git.
- Para MCP: Git instalado en el PATH del operador y un cliente MCP (Codex o Claude Code).

## Instalación y ejecución local

Primero clona o descarga el repositorio completo y abre PowerShell en su carpeta raíz.
Se usa `npm.cmd` para evitar el bloqueo de `npm.ps1`
por la política de ejecución de Windows, sin modificar esa política.

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
cd frontend
npm.cmd ci
```

`requirements-lock.txt` contiene las versiones exactas de ejecución y desarrollo resueltas en
Python 3.12/Windows; `requirements.txt` y `requirements-dev.txt` declaran las dependencias directas.
`package-lock.json` fija la resolución del frontend. El parser no necesita secretos.
La revisión con Muse Spark requiere `MODEL_API_KEY` solo en el entorno del backend.

Abre dos terminales nuevas en la raíz del repositorio.

Terminal 1:

```powershell
cd backend
# Para la revisión con Meta: define MODEL_API_KEY en esta terminal antes de iniciar Uvicorn.
# Si está ausente, el parser sigue funcionando y la revisión devuelve un error de configuración.
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm.cmd run dev
```

Abrir <http://127.0.0.1:5173>. El puerto es fijo: si está ocupado, Vite falla en vez de cambiarlo.
Vite reenvía `/api` y `/health` al backend local. No se requiere CORS para este flujo.
FastAPI publica el contrato OpenAPI en <http://127.0.0.1:8000/docs>.

Para generar un diff compatible:

```powershell
git diff --no-ext-diff --no-color --src-prefix=a/ --dst-prefix=b/
```

Se puede añadir `--cached` para cambios staged. Los botones de ejemplo cargan fixtures incluidos
en el proyecto y no realizan llamadas al modelo. Cambiar el texto invalida los resultados anteriores.

## Sprint 2: revisión con Muse Spark

Configura `MODEL_API_KEY` en el mismo proceso PowerShell desde el que iniciarás el backend.
Puedes introducirla sin dejar su valor en el historial de comandos:

```powershell
$modelSecret = Read-Host 'MODEL_API_KEY' -AsSecureString
$env:MODEL_API_KEY = [System.Net.NetworkCredential]::new('', $modelSecret).Password
Remove-Variable modelSecret
```

Después inicia Uvicorn como se indica arriba. `backend/.env.example` documenta el nombre de la
variable; no se carga automáticamente. Nunca uses `VITE_MODEL_API_KEY` ni envíes la clave al frontend.
Si el backend ya estaba iniciado sin clave, reinícialo desde esa terminal.

1. Pega el diff o carga un ejemplo y pulsa **Analizar diff**: solo se invoca el parser local.
2. Pulsa **Revisar con Muse Spark**: se envía el diff parseado a Meta y puede consumir créditos.
3. El panel muestra el resumen y los riesgos como hipótesis del modelo. Las referencias inválidas
   se conservan y explican; solo las válidas enlazan al explorador existente.
4. Las pruebas sugeridas se muestran como texto y nunca se ejecutan.

El proveedor es fijo: `https://api.meta.ai/v1`, modelo `muse-spark-1.3`, SDK Python `openai`,
Responses API. No se usa OpenAI como proveedor ni se reutiliza `OPENAI_API_KEY`.
La solicitud usa `text.format={type: "json_schema", name: "diff_review", schema: ..., strict: true}`,
con objetos cerrados y todos los campos requeridos. La sintaxis está verificada en las referencias
oficiales de [Meta Responses](https://dev.meta.ai/docs/protocols/responses),
[esquemas de Responses](https://dev.meta.ai/docs/api-reference/responses/schemas) y
[Structured Outputs](https://dev.meta.ai/docs/structured-output).

Se envía una sola solicitud, sin herramientas, sin historial, con `store: false`, timeout de
60 segundos, máximo de 8192 tokens de salida y cero reintentos automáticos. No hay fallback a
texto libre. Se rechazan rechazos del modelo, respuestas parciales, salidas de herramientas,
JSON inválido y datos que no cumplen el contrato Pydantic estricto. Los errores del proveedor
se traducen sin exponer su cuerpo, el diff ni la clave. La clave no se registra explícitamente.
Los prompts tratan código, comentarios y metadatos como datos no confiables; el modelo no
recibe herramientas ni capacidad de ejecutar instrucciones incluidas en el diff.

**Alcance de la validación:** archivo por `file_id`, hunk perteneciente al archivo por `hunk_id`,
ruta exacta del lado `old`/`new`, rango inclusivo presente íntegramente en ese hunk y lado, y
fragmento literal unido con `\n`, incluidos sus espacios. No se corrigen referencias inventadas
ni se leen archivos del repositorio. Se preservan los IDs del parser. La validación acredita la
localización del fragmento, no la certeza del riesgo, su severidad, el resumen ni las pruebas sugeridas.

El límite del parser sigue siendo 1 MiB UTF-8. La revisión además limita el JSON del diff
parseado a **128 KiB**, antes de cualquier llamada al modelo; si lo supera, pide reducir el diff.
No se trunca ni se fragmenta silenciosamente. Este es un presupuesto local de entrada, no una
afirmación sobre la ventana de contexto del proveedor. Los cambios sin hunks textuales se
rechazan antes de gastar créditos. Los binarios en diffs mixtos solo aportan metadatos.

### POST /api/diff/analyze

Nuevo endpoint propio de la aplicación. Recibe el mismo `{"diff":"..."}` que el parser y
vuelve a parsearlo en el backend; no confía en IDs enviados por el navegador.
Devuelve `model`, `summary`, `parsed_diff` y `findings`. Cada hallazgo contiene:

- `hypothesis`: `title`, `severity` (`low`, `medium`, `high`, `critical`), `explanation`,
  `references` y `suggested_tests`. Como máximo 20 hallazgos, con 1–5 referencias y 1–5 pruebas cada uno.
- Cada referencia: `file_id`, `hunk_id`, `path`, `side`, `line_start`, `line_end`, `quote`.
- `reference_checks`: la referencia original, `status` (`valid`/`invalid`), `reason` y
  `diff_line` (solo no nulo cuando la referencia es válida).
- `all_references_valid`: resultado del validador determinista, nunca una afirmación de que
  se haya demostrado el riesgo. Los campos de validación no forman parte de la salida del modelo.

Razones estructurales: `matched`, `file_not_found`, `hunk_not_found`, `path_mismatch`,
`invalid_range`, `line_not_found`, `quote_mismatch`. Cero hallazgos no certifica ausencia de problemas.

Los errores usan el mismo sobre `error: {code, message, line}` del parser:

| HTTP | Códigos |
| --- | --- |
| 413 | `analysis_too_large` |
| 422 | Errores del parser/entrada y `no_text_changes` |
| 502 | `model_unavailable`, `model_request_failed`, `model_invalid_response`, `model_invalid_output`, `model_incomplete`, `model_refusal` |
| 503 | `model_not_configured`, `model_auth_error`, `model_rate_limited` |
| 504 | `model_timeout` |

Las pruebas automatizadas bloquean el transporte HTTP real del SDK y usan `MockTransport`,
incluyendo el recorrido endpoint → parser → SDK → JSON Schema → validador. No requieren clave ni
consumen créditos. Una prueba real con Meta se realiza manualmente con la variable configurada;
una prueba simulada no acredita disponibilidad del proveedor ni acceso de una cuenta concreta.

## Sprint 3: MCP local por stdio

El servidor ofrece una sola herramienta, **`inspect_changes`**. Comparte el servicio
`analysis.analyze_parsed` con HTTP: usa el mismo parser, adaptador Muse Spark y validador de
referencias. No necesita Uvicorn ni Vite; el agente inicia el proceso y comunica JSON-RPC por
stdin/stdout. Los diagnósticos van a stderr. No registra herramientas dentro de Meta.

### Instalación y autorización de repositorios

Desde la raíz del proyecto, actualiza el entorno con el lockfile:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
```

El SDK utilizado es `mcp==2.3.0`, con `MCPServer`, herramientas tipadas y transporte `stdio`.
`python-dotenv` permite cargar **solo** `MODEL_API_KEY` desde un archivo indicado al arrancar.
No se exploran archivos `.env` del repositorio auditado. El entorno ya definido tiene prioridad
y la expansión `${VARIABLE}` está desactivada. No pongas la clave en argumentos ni configuración
versionada del cliente. `backend/.env` debe permanecer ignorado por Git.

Ejemplo de arranque (las rutas corresponden a esta instalación; reemplázalas en otro equipo):

```powershell
& 'D:\Programacion\ai-change-inspector\backend\.venv\Scripts\python.exe' `
  'D:\Programacion\ai-change-inspector\backend\run_mcp.py' `
  --repo 'project=D:\Programacion\ai-change-inspector' `
  --env-file 'D:\Programacion\ai-change-inspector\backend\.env'
```

Es normal que espere silenciosamente: **no es una interfaz de terminal**. El cliente MCP debe
controlar stdin/stdout. `--env-file` es opcional si el proceso hereda `MODEL_API_KEY`.

Política de rutas:

- El operador autoriza **raíces concretas** con `--repo ID=RUTA_ABSOLUTA`; puede repetir la opción.
- La herramienta solo acepta ese ID y el alcance. No acepta rutas, comandos, variables de entorno,
  patrones de inclusión ni opciones para desactivar los filtros. Sin autorizaciones no arranca.
- Las rutas se canonicalizan al iniciar y se comprueban de nuevo durante la captura; no se aceptan
  subdirectorios como repositorios adicionales ni escapes mediante symlinks/junctions conocidos.
- Sprint 3 admite repositorios de trabajo con `.git` local. No admite bare repos, linked worktrees,
  submódulos como repositorios, almacenes alternativos de objetos, partial clones ni metadatos externos.
- El ejecutable Git debe ser confiable, fuera del repositorio inspeccionado; en Windows debe ser `.exe`.
- El operador debe confiar en la instalación del servidor, Git y los metadatos del repositorio.
  Estas comprobaciones no sustituyen un sandbox del sistema operativo ni protegen de un proceso
  hostil que reescriba simultáneamente el servidor o sus metadatos. No hay bloqueo de repositorio;
  las evidencias se refieren al diff capturado, no a ediciones posteriores.

### Selección del alcance y protección antes de Meta

Los dos argumentos son obligatorios:

```json
{"repository":"project","scope":"unstaged"}
```

- `staged`: diff del índice contra HEAD; en una rama sin commit, Git compara el índice con el vacío.
- `unstaged`: diff del árbol de trabajo contra el índice; no vuelve a incluir las modificaciones staged.
- No existe alcance `all`: no se concatenan dos diffs ni se cuentan dos veces sus modificaciones.
  Dos auditorías explícitas son independientes y pueden compartir líneas de contexto.
- **Untracked siempre excluidos**: no se listan ni leen sus contenidos y el MCP nunca ejecuta `git add`.
  Para revisar un archivo nuevo, el usuario debe incorporarlo al índice por su cuenta antes de elegir
  `staged`. El servidor no lo hace. Los ignored también quedan fuera salvo que ya estén rastreados.
- Se desactiva detección de renombrados: una operación puede aparecer como baja y alta, sin inferencias.
  Se ignoran submódulos. No se ejecutan pruebas, hooks, filtros, textconv ni diff externo.

Cada invocación Git usa una lista de argumentos fija, sin shell, con stdin cerrado, como máximo
10 segundos, 1 MiB de salida de diff y 64 KiB en consultas de configuración/estado. La lectura es
incremental y se mata el proceso si excede el presupuesto; no se acumula salida ilimitada.
`GIT_OPTIONAL_LOCKS=0` evita actualizaciones opcionales del índice; no se cambian Git config, HEAD,
índice ni archivos del repositorio. `safe.directory` se aplica solo al proceso y a la raíz autorizada.

No se heredan credenciales ni overrides `GIT_*` del agente. Se desactivan configuraciones globales y
de sistema, atributos externos, fsmonitor y hooks. Antes del diff, una consulta local con
`--no-includes` rechaza includes, filtros clean/process, fsmonitor y configuraciones de almacenamiento
no admitidas. Esto también evita ejecutar filtros del repositorio durante `git diff`.
No se ejecuta ningún comando de salida del modelo ni contenido del repositorio.

Antes de enviar a Meta se valida el diff entero y se bloquea **toda** la auditoría si aparece:

- Una ruta sensible: `.env*` (incluido `.env.example`), directorios de credenciales, archivos de claves,
  certificados privados o nombres como `credentials.*`, `secrets.*`, `tokens.*`.
- Una ruta no relativa/que escape del repositorio, symlinks o gitlinks no admitidos.
- Indicios de credenciales en cualquier línea agregada, eliminada o de contexto: claves privadas,
  patrones de tokens conocidos, asignaciones de claves/contraseñas, bearer tokens o URLs con credenciales.
  También se busca el valor de `MODEL_API_KEY` configurado, sin enviarlo ni mostrarlo.

Los filtros son heurísticos y conservadores: **pueden tener falsos positivos y falsos negativos**;
no detectan todos los formatos, secretos ofuscados ni información confidencial contextual.
No hay bypass por herramienta ni redacción silenciosa que altere las evidencias. Si hay bloqueo,
no se envía contenido parcial a Meta: revisa localmente el alcance antes de volver a invocar.
El límite adicional del JSON parseado sigue siendo 128 KiB; no se trunca el diff.
Sin cambios, sin texto, por límites o filtros bloqueantes, no se llama al proveedor.
El endpoint HTTP manual conserva el comportamiento del Sprint 2: estos filtros son del adaptador MCP.

### Resultado estructurado y errores recuperables

El SDK publica `inputSchema`/`outputSchema` y devuelve JSON en `structuredContent`, además de texto.
El resultado contiene:

- `status`: `completed`, `no_changes`, `blocked` o `error`.
- `repository`, `scope`, `untracked_policy: "excluded"`.
- `analysis`: `model`, `summary` y `findings`, o `null` cuando no se revisó.
- Cada hallazgo conserva `hypothesis` (riesgo, explicación y `suggested_tests`),
  `reference_checks` (citas y resultados estructurales) y `all_references_valid` del backend.
- `error`: `code`, mensaje sanitizado y `recoverable: true`, o `null`. Recuperable significa que
  el usuario puede corregir configuración/alcance o intentar más tarde, no que deba reintentarse
  automáticamente. Una respuesta completada sin hallazgos no certifica ausencia de riesgos.

El MCP no devuelve todo el diff parseado al agente: devuelve hipótesis y citas, evitando duplicar
código y contexto innecesariamente. No permite marcar hallazgos como verificados o resueltos;
solo el backend determina la validez estructural y eso no demuestra corrección semántica.
Un agente tampoco debe ejecutar las pruebas sugeridas como consecuencia automática de la auditoría.

Entre los errores están `unauthorized_repository`, `unauthorized_path`, `invalid_repository`,
`unsafe_git_layout`, `unsafe_git_config`, `unsafe_git_executable`, `git_unavailable`, `git_error`,
`git_timeout`, `git_output_too_large`, `unsupported_encoding`, `unsafe_diff_path`, `sensitive_path`,
`unsupported_change`, `possible_secret`, los errores del parser y los del proveedor documentados arriba.
Un argumento ausente o fuera del esquema produce error de herramienta MCP antes de ejecutar la captura.

### Codex: ejemplo verificado

Añade este bloque a tu `~/.codex/config.toml`, conservando las entradas existentes. No lo añadas
dos veces si ya registraste el mismo nombre. Son rutas Windows en strings literales TOML:

```toml
[mcp_servers.ai-change-inspector]
command = 'D:\Programacion\ai-change-inspector\backend\.venv\Scripts\python.exe'
args = ['D:\Programacion\ai-change-inspector\backend\run_mcp.py', '--repo', 'project=D:\Programacion\ai-change-inspector', '--env-file', 'D:\Programacion\ai-change-inspector\backend\.env']
startup_timeout_sec = 20
tool_timeout_sec = 120
enabled_tools = ["inspect_changes"]
default_tools_approval_mode = "prompt"
```

Comprueba la entrada y reinicia/conecta una sesión del cliente para descubrir la herramienta:

```powershell
codex.cmd mcp get ai-change-inspector
```

El timeout de herramienta se amplía para cubrir Git y los 60 segundos de Meta. La aprobación se
mantiene explícita; no se configura autoaprobación. La sintaxis fue contrastada con la
[documentación oficial de Codex MCP](https://developers.openai.com/codex/mcp) y la ayuda del CLI instalado.

### Claude Code: ejemplo verificado

Desde el proyecto en que usarás Claude Code, registra el servidor en scope local:

```powershell
claude mcp add --transport stdio --scope local ai-change-inspector -- `
  'D:\Programacion\ai-change-inspector\backend\.venv\Scripts\python.exe' `
  'D:\Programacion\ai-change-inspector\backend\run_mcp.py' `
  --repo 'project=D:\Programacion\ai-change-inspector' `
  --env-file 'D:\Programacion\ai-change-inspector\backend\.env'
claude mcp get ai-change-inspector
```

En la sesión Claude Code, `/mcp` permite comprobar la conexión. Conserva las aprobaciones de
herramientas. Puedes fijar `$env:MCP_TOOL_TIMEOUT = '120000'` antes de iniciar Claude si necesitas
un límite de dos minutos. El timeout del cliente no garantiza cancelar una solicitud a Meta ya enviada;
no repitas una auditoría automáticamente tras desconectar o cancelar.
La sintaxis y scope fueron contrastados con la
[documentación oficial de Claude Code](https://code.claude.com/docs/en/mcp) y `claude mcp add --help`.

### Invocación explícita desde el agente

Una vez conectado, pide por ejemplo:

> Invoca inspect_changes con repository="project" y scope="unstaged". Audita solo esos cambios.
> No ejecutes pruebas sugeridas, no modifiques archivos y distingue hipótesis de referencias válidas.

O cambia explícitamente a `scope="staged"`. El cliente invoca la herramienta; no se ejecuta el
comando de arranque repetidamente como un comando de revisión ni se pega el diff en el chat.
No hay hooks, watcher ni auditoría automática al iniciar el servidor. La descripción de la herramienta
pide intención explícita; la autorización humana y política de aprobación las controla el cliente.
Una revisión aceptada consume créditos Meta; descubrir herramientas y responder `no_changes` no.

Los ejemplos verifican sintaxis y contrato, no afirman que se hayan modificado las configuraciones
personales de Codex/Claude ni realizado una llamada real con tu cuenta. La prueba automatizada de stdio
arranca el servidor desde otro directorio, descubre la herramienta y comprueba errores seguros sin Meta.
Referencias del SDK: [ejecución](https://py.sdk.modelcontextprotocol.io/run/),
[herramientas](https://py.sdk.modelcontextprotocol.io/servers/tools/) y
[pruebas](https://py.sdk.modelcontextprotocol.io/get-started/testing/).

## Estructura

```text
backend/
  app/main.py                 # Adaptador HTTP y errores
  app/models.py               # Contrato del parser
  app/analysis_models.py      # Hipótesis y validaciones estructurales separadas
  app/services/diff_parser.py # Parser puro, dataclasses inmutables
  app/services/model_client.py # Adaptador de Meta Responses
  app/services/reference_validator.py # Validación sin I/O sobre el diff parseado
  app/services/analysis.py    # Orquestación compartida HTTP/MCP
  app/services/git_capture.py # Captura Git acotada, sin shell
  app/services/egress_guard.py # Filtros previos a Meta en MCP
  app/mcp_server.py           # Herramienta y configuración stdio
  run_mcp.py                 # Launcher por ruta absoluta
  tests/                     # Parser y contrato HTTP
frontend/
  src/components/            # DiffExplorer y FindingsPanel separados
  src/lib/                   # Cliente HTTP y ejemplos compartidos
  src/types/                 # Contrato TypeScript
examples/diffs/               # Fixtures válidos y un ejemplo inválido
AGENTS.md                     # Reglas para agentes que trabajen en el proyecto
```

## API del parser (Sprint 1, conservada)

### GET /health

Respuesta `200`:

```json
{"status":"ok"}
```

Comprueba que el proceso responde; no comprueba servicios externos.

### POST /api/diff/parse

Content-Type: `application/json`. Único campo permitido: `diff`, de tipo string.

```json
{"diff":"diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n"}
```

Respuesta `200`:

- `files`: archivos en orden de entrada.
- `additions`, `deletions`: totales de líneas textuales; una sustitución cuenta como eliminación y adición.
- Cada archivo incluye `file_id`, `old_path`, `new_path`, `change_type`, `is_binary`, `metadata`,
  `hunks`, `additions` y `deletions`. La ruta inexistente es `null`.
- Cada hunk incluye `hunk_id`, `header`, `old_start`, `old_count`, `new_start`, `new_count`, `lines`.
- Cada línea incluye `kind` (`context`, `addition`, `deletion`), `content` sin el prefijo,
  `old_line`, `new_line`, `diff_line` y `no_newline`. Los números son de base 1; un lado
  inexistente es `null`. `diff_line` es la posición en el diff pegado.
- `change_type`: `added`, `deleted`, `modified`, `renamed` o `copied`.
- Los binarios y cambios solo de metadatos no producen líneas ni estadísticas inventadas.

Errores de entrada o parser: `422`, con un único formato:

```json
{
  "error": {
    "code": "invalid_header",
    "message": "Expected a diff --git header at the start.",
    "line": 1
  }
}
```

`line` es `null` cuando el error no corresponde a una línea concreta. Códigos:
`invalid_request`, `empty_diff`, `diff_too_large`, `invalid_encoding`, `invalid_header`,
`invalid_path`, `invalid_hunk`, `invalid_range`, `hunk_count_mismatch`, `invalid_marker`,
`invalid_metadata`, `unexpected_line`, `empty_file`, `unsupported_format`.

El límite es **1.048.576 bytes UTF-8 del campo `diff`**, inclusive, antes de normalizar CRLF.
No es un límite de caracteres ni del sobre JSON. El backend es la autoridad y el frontend
anticipa el error. El cuerpo JSON se decodifica antes de validar el campo: esto no implementa
un límite de transporte HTTP ni configura un proxy de producción.

Ejemplo PowerShell desde la raíz, con ambos servidores iniciados:

```powershell
Invoke-RestMethod http://127.0.0.1:5173/health
$sampleDiff = [System.IO.File]::ReadAllText((Join-Path $PWD 'examples/diffs/multiple-files.diff'))
$requestJson = @{ diff = [string]$sampleDiff } | ConvertTo-Json -Compress
Invoke-RestMethod http://127.0.0.1:5173/api/diff/parse -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($requestJson))
```

## Parser e identificadores

El parser importa únicamente la biblioteca estándar de Python y devuelve dataclasses congeladas
con tuplas. No lee rutas del diff, ejecuta procesos, accede a red, usa reloj ni genera UUID.
La adaptación a Pydantic ocurre en la capa HTTP.

- `file_id = file_<sha256>`: hash de una representación JSON canónica del bloque de archivo
  normalizado y su número de aparición entre bloques idénticos.
- `hunk_id = hunk_<sha256>`: hash de `file_id`, índice del hunk y sus líneas originales normalizadas.
- CRLF se normaliza a LF y se ignora un terminador de línea final. Los IDs son iguales al repetir
  el mismo diff o cambiar exclusivamente esos terminadores.
- Agregar o reordenar archivos distintos no cambia los IDs de los bloques existentes. Los bloques
  idénticos repetidos tienen IDs distintos por su número de aparición.
- Editar cualquier parte de un bloque cambia su `file_id` y todos sus `hunk_id`. Estos IDs identifican
  una versión del cambio; no prometen continuidad entre revisiones ni commits diferentes.

Para vincular hallazgos, usar `file_id`, `hunk_id`, lado (`old`/`new`) y número de línea de ese lado.
`diff_line` sirve para localizar el texto de entrada, pero cambia si se anteponen otros archivos.
El explorador expone IDs de archivo/hunk en el DOM; el panel de hallazgos solo enlaza referencias validadas.

### Formato soportado y límites

- Parches con cabeceras `diff --git`, prefijos estándar `a/`, `b/`, pares `---`/`+++` y hunks `@@`.
- Varios archivos/hunks, contexto vacío, rangos de cantidad omitida o cero, altas y bajas con `/dev/null`.
- Rutas con espacios y comillas C de Git, incluyendo escapes octales UTF-8.
- Renombrados/copias explícitos y cambios de permisos; no se infieren por similitud de contenido.
- Marcador `\ No newline at end of file`, LF y CRLF.
- Binarios: se reconoce `Binary files … differ` y `GIT binary patch`; su payload es opaco y no se valida.
- Se validan cantidades de hunks, orden de rangos, metadatos reconocidos y marcadores mal ubicados.
- Los componentes numéricos de rangos admiten hasta 9 dígitos. Rangos mayores se rechazan como `invalid_hunk`.
- No se admiten combined diffs de merges, diffs sin cabecera Git, salida ANSI, envoltorios de correo,
  prefijos personalizados, formatos raw/word-diff ni rutas con bytes no UTF-8. No se aplica el parche
  ni se comprueba su contenido contra un repositorio real.

## Verificación

Desde `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest -q -W error
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pip check
```

Desde `frontend/`:

```powershell
npm.cmd run test -- --run
npm.cmd run lint
npm.cmd run build
```

Las pruebas del backend cubren conteos, números de línea, errores, IDs, CRLF, metadatos, rutas,
binarios y el límite UTF-8 inclusive. Las de frontend usan respuestas controladas para verificar
el envío, estados de carga/error, texto seguro, navegación y el panel de hipótesis con referencias
válidas e inválidas. Las pruebas del adaptador ejercitan el SDK con un transporte simulado y
comprueban el contrato HTTP enviado a Meta, sus errores y los límites antes de enviar.
No sustituyen una revisión visual en navegador. `npm.cmd audit` consulta el registro y requiere red.

El build genera `frontend/dist/`. El proxy configurado es de desarrollo: un despliegue futuro
deberá servir la API bajo el mismo origen o definir su propia estrategia de rutas.

## Decisiones y referencias

- Un único parser en Python evita duplicar interpretación en el navegador.
- `fetch`, estado local de React y componentes separados bastan para este sprint.
- Vite 6.4.5 se comprobó con el Node instalado. Vitest se actualizó a 5.0.5 tras detectar
  vulnerabilidades en la resolución inicial de Vitest 3; no se utilizó `audit fix --force`.
- Tailwind utiliza su plugin de Vite, sin duplicar configuración de PostCSS.
- Las entradas se presentan como texto React, sin `dangerouslySetInnerHTML`.
- El diff no se almacena ni se registra explícitamente; Uvicorn conserva su logging HTTP habitual.
  Solo la acción de revisar envía el diff parseado a Meta con `store: false`.
- Las pruebas HTTP usan `HTTPX AsyncClient` con `ASGITransport` y el plugin pytest de AnyIO
  sobre asyncio, como en la guía oficial de pruebas asíncronas de FastAPI. Se evita la ruta
  de compatibilidad de `Starlette TestClient` con HTTPX, deprecada en Starlette 1.10.0,
  sin cambiar dependencias de ejecución ni silenciar advertencias. Si se añaden eventos de
  lifespan en el futuro, estas pruebas deberán gestionarlos explícitamente.

Referencias oficiales: [formato de parches Git](https://git-scm.com/docs/diff-format),
[Vite](https://vite.dev/guide/),
[Tailwind con Vite](https://tailwindcss.com/docs/installation/using-vite),
[pruebas FastAPI](https://fastapi.tiangolo.com/tutorial/testing/),
[pruebas asíncronas FastAPI](https://fastapi.tiangolo.com/advanced/async-tests/).

## Licencia

Se conserva íntegramente la licencia GNU GPL v3 existente en [LICENSE](LICENSE).
