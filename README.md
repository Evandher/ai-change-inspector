# AI Change Inspector

Auditor independiente de cambios de Git para la Meta AI Developer Hackathon 2026.
Conserva el explorador y parser determinista del Sprint 1. En Sprint 2, Muse Spark 1.3 propone
riesgos y el backend valida sus referencias de forma independiente. Los hallazgos siguen siendo
hipótesis, incluso cuando todas sus referencias coinciden con el diff.
Sprint 3 añade un MCP local por stdio; Sprint 4 incorpora **Agent Review Inbox** con SQLite.
El agente registra una instantánea antes del análisis y el desarrollador abre su URL en la web.
Sprint 5 añade decisiones humanas por hallazgo, consulta de feedback por MCP y enlaces entre entregas.
Sprint 6 añade un Skill portable para el ciclo de auditoría y feedback.
No hay autenticación, colaboración, nube, hooks ni ejecución de código del diff.

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

## Idioma de la interfaz y de los informes

La demo abre en **inglés (EN)** para usuarios nuevos, independientemente del idioma del navegador.
El selector EN/ES en la navegación permite elegir español. Es un control nativo etiquetado,
accesible por teclado; actualiza también el atributo `lang` del documento y los formatos de fechas
y números. No requiere instalar una biblioteca de internacionalización.

La preferencia se guarda en `localStorage` con la clave `ai-change-inspector.language` y valores
`en` / `es`, se conserva al navegar y recargar y es propia de cada origen/perfil del navegador.
Si se borra o contiene otro valor, se usa inglés. Si el navegador bloquea el almacenamiento,
la selección funciona durante la sesión actual, pero puede perderse al recargar.

Los catálogos tipados están centralizados en `frontend/src/lib/translations.ts`. Incluyen navegación,
explorador, bandeja/detalle, estados, severidades, accesibilidad, ayuda y errores. Los errores se
presentan por código, con línea cuando existe; un código desconocido muestra un mensaje localizado
genérico y el código, sin copiar mensajes arbitrarios del servidor. Los contratos JSON, enums,
identificadores y respuestas originales de la API no cambian.

El prompt solicita **inglés para informes nuevos**: resumen, títulos, explicaciones y pruebas
sugeridas. Cambiar EN/ES solo cambia la interfaz, no el idioma solicitado al modelo. Las citas,
rutas y código deben conservarse literalmente. Los informes históricos mantienen su texto original,
incluidos los que están en español; no se traducen, modifican ni regeneran al cambiar el selector.
No hay llamadas de traducción a Meta. El idioma de la salida real depende del cumplimiento del
prompt por el proveedor; las pruebas automáticas usan mocks, no consumen créditos.

Los nombres españoles de botones usados en las instrucciones siguientes corresponden al modo ES:

| EN (demo predeterminada) | ES |
| --- | --- |
| Parse diff | Analizar diff |
| Review with Muse Spark | Revisar con Muse Spark |
| Review inbox | Revisiones recibidas |
| Refresh review | Actualizar revisión |
| Analyze pending snapshot | Analizar instantánea pendiente |

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

## Sprint 4: Agent Review Inbox

Flujo: **agente → MCP → registro confirmado en SQLite → Muse Spark → revisión web**.
El registro y el análisis son pasos distintos. La API web es dueña del almacén y de las llamadas a
Meta; el MCP conserva la autorización de rutas, captura y filtros del Sprint 3, pero ya no llama
directamente al proveedor ni guarda un outbox alternativo si la web está apagada.

### Arranque del servicio con inbox

Usa un único proceso/worker de API para una misma base. Desde una terminal PowerShell en la raíz:

```powershell
# Autoriza exactamente los mismos IDs y raíces que en el comando MCP --repo.
$env:INSPECTOR_REPOSITORIES = '{"project":"C:\\work\\ai-change-inspector"}'
# Opcional: ruta absoluta. Si se omite, usa backend/.local/reviews.sqlite3.
$env:INSPECTOR_DB_PATH = 'C:\work\ai-change-inspector\backend\.local\reviews.sqlite3'
cd backend
# .env es privado y debe existir para esta variante. También puedes exportar MODEL_API_KEY
# y omitir --env-file. El modelo se configura en la WEB, no mediante el agente.
.venv/Scripts/python.exe -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --workers 1
```

En otra terminal, desde `frontend/`, ejecuta `npm.cmd run dev`. Abre
<http://127.0.0.1:5173/reviews>. Los enlaces individuales tienen la forma `/reviews/<UUID>` y
funcionan al abrirlos directamente o recargar la página con Vite. Si una versión anterior de la
API ya está en ejecución, reiníciala para cargar estas rutas.

Configuración del operador (nunca son argumentos de la herramienta):

| Variable | Valor por defecto / uso |
| --- | --- |
| `INSPECTOR_REPOSITORIES` | `{}`: deniega nuevas revisiones hasta configurar IDs con raíces absolutas; no limita la consulta de instantáneas ya guardadas |
| `INSPECTOR_DB_PATH` | `backend/.local/reviews.sqlite3`; para cambiarla debe ser una ruta absoluta |
| `INSPECTOR_API_URL` | `http://127.0.0.1:8000`; base local usada por MCP y por la validación Host de la web |
| `INSPECTOR_WEB_URL` | `http://127.0.0.1:5173`; origen permitido y base para enlaces de revisión |
| `MODEL_API_KEY` | Solo el servicio web necesita la clave para analizar |

Solo se aceptan URLs HTTP con una IP literal loopback y puerto explícito, sin credenciales, rutas,
query ni fragmento. Si cambias puertos, configura las variables correspondientes en la API y MCP,
además del proxy Vite. No se admiten destinos externos. En MCP, `--api-url` puede elegir otra base
loopback. `--repo` sigue siendo obligatorio y la web comprueba de nuevo ID y raíz: configuraciones
distintas se rechazan, no se reemplazan silenciosamente.

### Qué se conserva y qué puede cambiar

SQLite usa la biblioteca estándar `sqlite3`, sin ORM ni nuevas dependencias. Cada revisión tiene:

- UUID v4 aleatorio generado antes del envío, raíz e ID autorizados, origen `mcp`, alcance y fecha UTC.
- El **texto exacto capturado**, su SHA-256 y el diff parseado con los IDs deterministas originales.
- Estado de análisis, fecha de finalización, resultado validado o error recuperable.

El diff, IDs y metadatos de la instantánea no se actualizan: un trigger SQLite protege esos campos.
El estado sigue `pending → analyzing → completed/error`; los estados terminales no se sobrescriben.
La consulta del detalle no vuelve a leer Git ni inicia análisis. Las capturas posteriores son otras
revisiones; no se implementa comparación visual ni resolución automática de hallazgos.
Las decisiones humanas del Sprint 5 se guardan por separado.

El registro se confirma en una transacción corta **antes** de llamar a Meta. No se mantiene una
transacción SQLite abierta mientras responde el proveedor. Si falla Meta, se conserva el diff y
`analysis=null`, `status=error` y el error sanitizado. Una respuesta sin hallazgos es `completed`
con `findings=[]`, que no equivale a una garantía de corrección.

El mismo ID con la misma instantánea es idempotente; un contenido distinto para ese ID devuelve
conflicto. La reclamación atómica evita dos análisis de una revisión. Repetir la solicitud sobre
una revisión completada, con error o ya en curso no genera otra llamada. No hay reintentos automáticos.
Los errores recuperables indican que el operador puede corregir la causa y solicitar una revisión
nueva; no autorizan a reescribir un resultado terminal ni a repetir créditos automáticamente.

Al reiniciar, los análisis que quedaron `analyzing` pasan a error `analysis_interrupted`, conservando
la instantánea. Los `pending` siguen pendientes y se pueden analizar explícitamente desde su detalle.
No hay cola de trabajadores ni reanudación automática de llamadas cuyo resultado sea desconocido.
Ejecutar varias APIs contra la misma base no está soportado: una segunda instancia podría interpretar
el trabajo de la primera como interrumpido. No uses varios workers ni compartas esta base en red.

### Servicio apagado y pérdidas de conexión

- **API apagada o inaccesible:** MCP devuelve `error`, `web_service_unavailable`, ID de correlación,
  URL y `registration_confirmed=false`. Esto significa *registro no confirmado*, no que el registro
  necesariamente no exista. No se analiza desde MCP ni se afirma que se guardó localmente.
- Si la respuesta de registro se perdió después del commit, ese mismo ID permite encontrar el diff
  que sí quedó guardado. Consulta la URL/bandeja antes de solicitar otra auditoría.
- Si el registro fue confirmado pero se interrumpe la segunda solicitud, MCP conserva ID y URL con
  `registration_confirmed=true`; el estado real puede ser pendiente, en curso o terminal. Actualiza
  el detalle antes de repetir. El timeout o cancelación del agente no cancela necesariamente Meta.
- Si únicamente Vite está apagado, la API puede registrar y analizar normalmente. La instantánea
  permanece guardada y el enlace será accesible al iniciar el frontend; no se pierde la revisión.

La interfaz permite refrescar explícitamente la bandeja y cada detalle; no sondea ni gasta créditos
al abrir una revisión. Muestra el diff original, el explorador, los hallazgos y sus citas verificadas.
Una revisión con error sigue siendo legible. La vista manual continúa funcionando y **no persiste**
sus diffs automáticamente: el inbox registra las capturas enviadas por MCP.

### API del inbox

Todas estas rutas son locales. Los POST requieren JSON y `X-Inspector-Request: 1`, un marcador
anti-solicitudes simples desde el navegador, **no un secreto ni autenticación**.

| Método y ruta | Comportamiento |
| --- | --- |
| `POST /api/reviews` | Registra la instantánea tras autorización, parser y filtros; devuelve 201 sin llamar a Meta |
| `GET /api/reviews?limit=20&offset=0` | Lista metadatos, estados y total; límite 1–100, sin incluir el diff completo |
| `GET /api/reviews/{review_id}` | Devuelve instantánea, parseado y resultado/error; 404 si no existe, 422 si el ID es inválido |
| `POST /api/reviews/{review_id}/analyze` | Analiza únicamente una instantánea pendiente; devuelve su detalle/estado persistido |

El registro recibe `repository`, `repository_root`, `scope`, `diff` y un `review_id` UUID4 opcional
(MCP siempre lo genera aleatoriamente antes del POST). No acepta estado, origen, fecha ni hallazgos
declarados por el agente. El análisis devuelve HTTP 200 cuando pudo consultar el estado persistido;
**hay que comprobar `status`**, que será `error` si falló Meta. No se disfraza el fallo como éxito.
Problemas de registro/configuración/almacenamiento devuelven errores HTTP sanitizados. Un ID ya usado
con otro contenido da 409. El cuerpo HTTP está acotado a 8 MiB y los presupuestos del parser/modelo
se mantienen. Los filtros se aplican antes de persistir y de nuevo antes de enviar a Meta.

El resultado MCP añade `review_id`, `review_url`, `registration_confirmed` y `analysis_status`.
El estado superior es el resultado de la operación MCP; si no se pudo confirmar la última respuesta,
`analysis_status=null` evita inventar el estado del registro. La herramienta declara un efecto de
escritura porque ahora registra revisiones, aunque Git continúa siendo estrictamente de lectura.

### Datos locales y límites de seguridad

- `.local/`, SQLite y sus archivos auxiliares están ignorados por Git y bloqueados por Vite. Puedes
  colocar la base fuera del repositorio. No la compartas ni la incluyas en commits/copias públicas.
- SQLite contiene diffs privados sin cifrado de aplicación. Protégelos con permisos del sistema
  operativo y copias de seguridad privadas. No hay borrado automático, retención programada ni nube.
- La API rechaza peers no loopback, Host desconocido, Origin ajeno o `null`, y solicitudes
  `Sec-Fetch-Site: cross-site`. No se habilita CORS; la web usa el proxy de mismo origen de Vite.
  También se rechazan formularios simples en POST y faltas del marcador del inbox. Las respuestas
  no se cachean y no permiten framing ni sniffing de contenido; Vite también bloquea framing/CORS.
- Esto reduce ataques desde páginas externas y DNS rebinding, pero **localhost no autentica**.
  Otro proceso local puede fabricar cabeceras y acceder a la API o al archivo SQLite. No es una
  arquitectura multiusuario ni debe exponerse mediante túneles, proxies públicos o en una LAN.
- El UUID de la URL no es una credencial ni concede acceso por sí mismo. La lista tampoco es un
  control de acceso. Solo se previene adivinación trivial; no se sustituye autenticación.
- Se conservan autorización y filtros del Sprint 3, ampliados para `.local` y archivos SQLite.
  Siguen siendo heurísticos: no detectan todos los secretos ni toda información confidencial.
  Una referencia válida prueba una localización en la instantánea, no que exista un bug.

## Sprint 5: Human Review & Agent Feedback

El desarrollador abre una revisión completada y usa **Human review / Revisión humana** en cada
hallazgo. La decisión inicial es pendiente: no existe una decisión guardada. Puede elegir:

| Valor interno | EN | ES |
| --- | --- | --- |
| `request_changes` | Request changes | Solicitar cambios |
| `accept_risk` | Accept risk | Aceptar riesgo |
| `dismiss` | Dismiss finding | Descartar hallazgo |

Añade opcionalmente un comentario de hasta 4000 caracteres y pulsa **Save decision / Guardar decisión**.
Se muestra la fecha UTC de última modificación con formato local; los borradores no guardados se
indican explícitamente. Se puede cambiar la decisión y reemplazar o vaciar el comentario. No hay
borrado ni retorno a pendiente en este sprint. Las ediciones guardan el estado más reciente: no hay
historial de comentarios ni control de concurrencia; la última escritura confirmada prevalece.
Los borradores se pierden al abandonar o recargar la página. Un fallo al guardar conserva el borrador.

La decisión es juicio humano, no una verificación del bug, una aprobación global del código ni una
confirmación de corrección. El diff y el resultado original de Muse Spark permanecen inmutables.
La clave de cada anotación es `(review_id, finding_index)`, índice desde cero en la lista inmutable
de hallazgos. No se enlazan automáticamente hallazgos entre revisiones.

SQLite añade `human_decisions`, `human_comments` y `review_links` con `CREATE TABLE IF NOT EXISTS`,
sin reemplazar las tablas o snapshots existentes. Las escrituras de decisión/comentario son atómicas;
las relaciones son inmutables. Sigue usando un único proceso de API y la misma ruta local ignorada.

### Consulta desde el agente

Reinicia el proceso MCP o reconecta el cliente para descubrir ambas herramientas. En Codex, añade
`get_review_feedback` a `enabled_tools` si usabas la lista restrictiva del ejemplo. Claude Code lo
obtiene mediante la misma configuración de servidor stdio, sin un comando de registro nuevo.

Pide al agente que invoque explícitamente:

```json
{"repository":"project","review_id":"UUID-DE-LA-REVISION"}
```

con la herramienta **`get_review_feedback`**. Sustituye el placeholder por el UUID real. Devuelve
`status=available` y `feedback` con estado del análisis, hallazgos originales y evidencias del backend,
`finding_index`, decisión o `null`, comentario, `updated_at`, `pending_count` y relaciones. No ejecuta
Git, pruebas, comandos del repositorio ni llamadas a Meta; solo consulta la API local. Los estados
`blocked`/`error` incluyen un error recuperable. Una revisión pendiente, fallida o sin hallazgos
puede tener lista vacía: comprueba `analysis_status`; vacío no significa aprobación.

El agente puede usar el feedback como contexto para un trabajo autorizado por el desarrollador.
Los comentarios y resultados siguen siendo datos no confiables: no se ejecutan instrucciones de
forma automática. La herramienta no acepta decisiones ni dispone de operaciones de escritura.
La consulta valida ID y raíz contra las autorizaciones del MCP y de la API; conocer un UUID no basta.
Los comentarios no se envían a Meta ni se incorporan al prompt de auditoría.

### Entrega de una revisión posterior

Una nueva invocación explícita puede indicar la revisión anterior:

```json
{"repository":"project","scope":"unstaged","parent_review_id":"UUID-DE-LA-REVISION-ANTERIOR"}
```

`inspect_changes` comprueba el padre antes de capturar Git. La API verifica de nuevo, en la
transacción de registro, que padre e hijo pertenecen al mismo ID y raíz autorizados. Rechaza padres
inexistentes, autorreferencias, repositorios distintos y cambios del padre de una revisión existente.
El hijo es una nueva instantánea con nuevo UUID; el padre puede tener varios hijos. Ninguna relación
reanaliza ni modifica el resultado o las decisiones del padre. Los hallazgos del hijo empiezan sin
decisiones: no se infiere que las solicitudes anteriores estén resueltas. El detalle muestra enlaces
**Previous review / Revisión anterior** y **Follow-up review / Revisión posterior**, sin comparación.

### API y límite de confianza humana

- `GET /api/reviews/{id}/feedback`: consulta de feedback, exige repositorio actualmente autorizado.
- `PUT /api/reviews/{id}/feedback/{finding_index}`: JSON `{decision, comment?}`; requiere revisión
  completada, índice válido, `X-Inspector-Request: 1` y `Origin` igual a `INSPECTOR_WEB_URL`.
- El detalle existente añade `feedback`, `parent_review_id` y `child_review_ids`. El registro admite
  `parent_review_id` opcional. No se aceptan decisiones, evidencias ni fechas suministradas al registrar.
- Errores: 404 para revisión/hallazgo/padre inexistente; 409 para estado no revisable o relación
  incompatible; 422 para decisión, UUID, índice o comentario inválido; 403 para origen/autorización.

No se añade autenticación. El control de Origin protege frente a páginas externas y rechaza un
cliente MCP normal sin Origin en escrituras humanas, pero no demuestra identidad humana: otro
proceso local con acceso al puerto puede falsificar cabeceras o abrir SQLite. La separación garantiza
que estas herramientas MCP no pueden escribir decisiones, no que un agente con acceso arbitrario al
sistema no pueda eludir la UI. No expongas el servicio mediante túneles ni lo compartas entre usuarios.
Feedback puede contener información privada; se conserva localmente y se devuelve al agente autorizado
que lo consulta. No hay filtros infalibles ni anonimización de comentarios.

## Sprint 6: Agent Skill para Codex y Claude Code

El paquete fuente es [skills/ai-change-inspector/SKILL.md](skills/ai-change-inspector/SKILL.md).
Contiene instrucciones en inglés y [ejemplos de llamadas](skills/ai-change-inspector/references/examples.json),
sin scripts ejecutables, hooks, credenciales ni herramientas adicionales. Los UUID de los ejemplos
son ficticios: usa los ID devueltos por tus auditorías. El agente puede responder en EN/ES sin
traducir ni modificar el contenido original de los informes o comentarios.

### Instalación y activación

Copia **toda** la carpeta `skills/ai-change-inspector`, incluido `references/`, a uno de los destinos
siguientes. Las rutas relativas se interpretan desde la raíz del repositorio que vas a auditar:

| Cliente | Instalación por proyecto | Instalación personal |
| --- | --- | --- |
| Codex | `.agents/skills/ai-change-inspector/` | `~/.agents/skills/ai-change-inspector/` |
| Claude Code | `.claude/skills/ai-change-inspector/` | `~/.claude/skills/ai-change-inspector/` |

El formato común es una carpeta con `SKILL.md` y frontmatter YAML `name` / `description`.
No requiere adaptar su contenido ni añadir `allowed-tools`, permisos preaprobados o metadatos de
un proveedor. El directorio fuente `skills/` de este proyecto es distribuible, no una instalación
automática. No sobrescribas una instalación existente sin revisarla; evita duplicar el mismo Skill
en ámbitos personal y de proyecto. Esta entrega no instala nada en tu perfil ni cambia tu cliente.

Configura previamente el MCP como se documenta más abajo y habilita **ambas** herramientas,
`inspect_changes` y `get_review_feedback`. Inicia API y frontend con los pasos existentes y autoriza
el mismo ID/raíz en API y MCP. No copies `.env`, SQLite ni rutas privadas al paquete del Skill.

En Codex CLI/IDE, usa `/skills` o menciona `$ai-change-inspector` en el mensaje. Si no aparece,
reinicia Codex. En Claude Code, invoca `/ai-change-inspector` seguido de tu solicitud; reinicia la
sesión si tu cliente no descubre la copia. La carpeta elegida y la sintaxis de invocación son las
únicas adaptaciones necesarias entre ambos clientes. Políticas de administración pueden impedir
la carga de Skills. Este paquete no cambia esas políticas ni configura/instala MCP por sí solo.

El cliente puede descubrir el Skill por su descripción; **cargarlo no autoriza una auditoría**.
Cada llamada de auditoría exige una solicitud explícita del desarrollador e ID/alcance conocidos.
No hay auditorías al terminar una edición, ni polling ni reintentos automáticos.

Formato/rutas/invocación verificados en la documentación oficial de
[Skills de Codex](https://learn.chatgpt.com/docs/build-skills) y
[Skills de Claude Code](https://code.claude.com/docs/en/skills).

### Uso: una solicitud explícita por etapa

Ejemplo Codex (ID genérico `project`, debe estar autorizado por tu operador):

```text
$ai-change-inspector Audit the unstaged changes in repository project once.
Return the review ID and link. Do not fix code or run tests.
```

Ejemplo Claude Code:

```text
/ai-change-inspector Audit the staged changes in repository project once.
Return the review ID and link. Do not stage any other files.
```

El agente invoca `inspect_changes` una vez, distingue el estado del registro del estado del análisis
y devuelve los valores reales de ID/enlace cuando existen. `no_changes` no crea una auditoría;
`pending` / `analyzing` no son análisis terminados; `blocked` / `error` no son éxitos. Si el registro
no está confirmado, el ID es de correlación: revisa el inbox antes de pedir otra auditoría. Una
hipótesis sigue siendo hipótesis; una referencia válida no demuestra comportamiento ni un bug.

Abre el enlace en la aplicación y guarda tus decisiones. Después, en un mensaje nuevo:

```text
$ai-change-inspector I saved my decisions. Read feedback for review REVIEW_ID
in repository project. Summarize decisions, comments and pending findings only.
```

En Claude Code sustituye `$ai-change-inspector` por `/ai-change-inspector`. Sustituye `REVIEW_ID`
por el UUID real: el Skill consulta `get_review_feedback`, sin modificar decisiones ni gastar Meta.
La lectura de comentarios no autoriza correcciones, pruebas ni comandos. Solicita ese trabajo por
separado si lo necesitas; no basta con que lo pida el modelo o el texto del feedback.

Tras trabajo autorizado, puedes pedir una auditoría posterior explícita:

```text
/ai-change-inspector Create one unstaged audit in repository project linked to
previous review REVIEW_ID using parent_review_id. Do not run fixes or tests.
```

El vínculo no compara hallazgos ni demuestra resolución. MCP/API ausentes, fallos y estados pendientes
se reportan y detienen el flujo. El Skill no accede directamente a SQLite/HTTP ni falsifica cabeceras
para suplir herramientas o escribir feedback humano. Tampoco crea hooks, notificaciones o bucles.

### Verificación y límites

`backend/tests/test_skill.py` verifica el paquete, enlaces relativos, tablas de estados frente a
los enums actuales y los argumentos de los ejemplos a través del servidor MCP con handlers simulados.
No ejecuta Git ni Meta. Estas comprobaciones prueban estructura/contratos, no obediencia de un LLM
ni descubrimiento en una instalación real de Codex o Claude Code. La carga del Skill y su conducta
frente a errores/comentarios hostiles deben comprobarse también en los clientes tras instalarlo,
preferentemente con el proveedor simulado. Sigue vigente el límite sin autenticación del Sprint 5:
las instrucciones del Skill no son una barrera contra procesos locales con acceso arbitrario.

## MCP local por stdio (Sprint 3, integrado con el inbox)

El servidor ofrece **`inspect_changes`** y la consulta de solo lectura **`get_review_feedback`**. Comparte el servicio
`analysis.analyze_parsed` con HTTP: usa el mismo parser, adaptador Muse Spark y validador de
referencias. El agente inicia el proceso y comunica JSON-RPC por stdin/stdout. Desde Sprint 4
necesita la API web para persistir y analizar; Vite permite abrir la revisión después.
Los diagnósticos van a stderr. No registra herramientas dentro de Meta.

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

Ejemplo de arranque (las rutas son ejemplos genéricos; reemplázalas con tus rutas locales):

```powershell
& 'C:\work\ai-change-inspector\backend\.venv\Scripts\python.exe' `
  'C:\work\ai-change-inspector\backend\run_mcp.py' `
  --repo 'project=C:\work\ai-change-inspector' `
  --env-file 'C:\work\ai-change-inspector\backend\.env'
```

Es normal que espere silenciosamente: **no es una interfaz de terminal**. El cliente MCP debe
controlar stdin/stdout. `--env-file` es opcional y se conserva por compatibilidad para el filtro
local de la clave; no configura la clave del servicio web ni la envía por HTTP. La API debe cargar
su propia `MODEL_API_KEY`, por ejemplo con el comando de arranque del Sprint 4.

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

No se heredan credenciales ni overrides `GIT_*` del agente. El proceso del diff desactiva la
configuración global y de sistema, atributos externos, fsmonitor y hooks, salvo la lista acotada
de ajustes de finales de línea descrita abajo. Antes del diff, una consulta local con
`--no-includes` rechaza includes, filtros clean/process, fsmonitor y configuraciones de almacenamiento
no admitidas. Esto también evita ejecutar filtros del repositorio durante `git diff`.
No se ejecuta ningún comando de salida del modelo ni contenido del repositorio.

#### Finales de línea en la captura Git

Un checkout CRLF puede depender de `core.autocrlf=true` global o de sistema para que Git compare
su contenido con los blobs LF del índice. Ignorar ese ajuste producía cambios falsos: en la
reproducción temporal, Git normal mostró 2 líneas añadidas y la captura aislada 120 líneas
cambiadas. No era un problema del parser ni de SQLite.

Para `unstaged`, una consulta fija de solo lectura, `git config --no-includes --null --get-regexp`,
lee únicamente `core.autocrlf`, `core.eol` y `core.safecrlf` desde los archivos estándar de Git.
Se validan y canonicalizan sus valores; la última definición prevalece, incluida la configuración
local sobre la de usuario/sistema. Solo esos valores se pasan como argumentos `-c` al diff aislado.
La consulta usa el perfil HOME/USERPROFILE/XDG del operador, pero no hereda overrides `GIT_*`,
credenciales ni includes. No habilita filtros, ejecutables, hooks ni atributos globales en el diff.
Las advertencias de stderr se descartan: no forman parte del diff; los códigos de salida fallidos
siguen devolviendo errores sanitizados. Se mantienen los límites de tiempo/tamaño y filtros sensibles.

Git aplica la conversión conforme a esos ajustes y a `.gitattributes` / `.git/info/attributes`
locales. La aplicación no reescribe archivos, configura Git ni elimina CR de la captura por su
cuenta. Con `core.autocrlf=false` o `-text`, los cambios reales de finales de línea permanecen
visibles. `staged` sigue comparando los blobs ya almacenados, sin necesitar esta consulta adicional.
El parser conserva su normalización CRLF documentada más abajo; la instantánea guarda el diff
original que emitió Git, no una copia del archivo de trabajo byte a byte.

Limitaciones: no se siguen `include`/`includeIf` globales o de sistema y se mantienen bloqueados los
includes locales. Una política EOL definida solo mediante includes, atributos globales/externos o
variables `GIT_CONFIG_*` del shell puede producir diferencias frente a su `git diff` habitual.
Tampoco se importa ninguna otra opción de presentación/comparación global. Los valores EOL inválidos,
la configuración ilegible o una consulta fuera de presupuesto fallan explícitamente; no se infiere
la política a partir de los bytes ni se usa `--ignore-space-at-eol`, que ocultaría cambios relevantes.
El perfil de Git pertenece al proceso del MCP: debe representar al operador que preparó el checkout.
La configuración y los archivos pueden cambiar simultáneamente; no hay snapshot atómico de Git.

Las regresiones comparan Git real y la captura en clones temporales para LF, CRLF, `true`/`false`/
`input`, precedencia local, `eol=lf/crlf` y `-text`, comprobando que índice, configuración y archivo
no se modifican. Requieren Git y un checkout fuente con `.git`; se omiten si faltan esos requisitos.
No hacen staging ni commits ni llaman a Meta. Contratos: [git-config](https://git-scm.com/docs/git-config)
y [gitattributes](https://git-scm.com/docs/gitattributes).

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
El endpoint HTTP manual conserva su análisis del Sprint 2. Los filtros de capturas se aplican tanto
en el adaptador MCP como en los endpoints de registro/análisis de instantáneas.

### Resultado estructurado y errores recuperables

El SDK publica `inputSchema`/`outputSchema` y devuelve JSON en `structuredContent`, además de texto.
El resultado contiene:

- `status`: `completed`, `no_changes`, `blocked`, `error`, `pending` o `analyzing`.
- `repository`, `scope`, `untracked_policy: "excluded"`.
- `review_id`, `review_url`, `registration_confirmed` y `analysis_status` (ver Sprint 4).
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
command = 'C:\work\ai-change-inspector\backend\.venv\Scripts\python.exe'
args = ['C:\work\ai-change-inspector\backend\run_mcp.py', '--repo', 'project=C:\work\ai-change-inspector', '--env-file', 'C:\work\ai-change-inspector\backend\.env']
startup_timeout_sec = 20
tool_timeout_sec = 120
enabled_tools = ["inspect_changes", "get_review_feedback"]
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
  'C:\work\ai-change-inspector\backend\.venv\Scripts\python.exe' `
  'C:\work\ai-change-inspector\backend\run_mcp.py' `
  --repo 'project=C:\work\ai-change-inspector' `
  --env-file 'C:\work\ai-change-inspector\backend\.env'
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
- El análisis manual no guarda el diff; el inbox sí persiste las instantáneas MCP en SQLite.
  Uvicorn conserva logging HTTP de rutas, sin registrar explícitamente el cuerpo del diff.
  Solo el análisis solicitado envía el diff parseado a Meta con `store: false`.
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
