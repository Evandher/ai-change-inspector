# AI Change Inspector — Handoff

Documento portable para continuar en otra computadora y una sesión nueva de Codex.
Las rutas de archivos son relativas a la raíz del proyecto. No contiene configuración
privada del equipo, credenciales ni una copia de las instrucciones locales de agentes.

## 1. Objetivo y visión

AI Change Inspector es un auditor independiente de cambios producidos por agentes de IA,
preparado para la Meta AI Developer Hackathon 2026. Su valor es la trazabilidad entre
cambio capturado, hipótesis del modelo, referencias comprobadas y decisión humana.

Flujo implementado:

**Agente → MCP → captura Git autorizada → instantánea SQLite → Muse Spark → validación
independiente de referencias → revisión web → feedback humano → consulta MCP → nueva
auditoría vinculada, si el desarrollador la solicita.**

Una hipótesis no es un defecto confirmado. Una referencia estructuralmente válida solo
acredita la localización de texto en el diff. Ni una decisión humana ni la desaparición
de un hallazgo en otra auditoría prueban corrección o ejecución satisfactoria de tests.

No es un agente de corrección autónoma. No ejecuta código, pruebas ni comandos propuestos
por el modelo o por comentarios. Auditar y corregir requieren autorizaciones distintas.

Referencia principal: [README.md](README.md).

## 2. Arquitectura, stack y estructura

- Frontend: React 19, TypeScript, Vite 6 y Tailwind CSS 4; estado local y `fetch`.
- Backend: Python 3.12, FastAPI y Pydantic. SQLite mediante `sqlite3`, sin ORM.
- Proveedor: Meta Model API mediante SDK Python `openai`, Responses API.
- Integración de agentes: SDK Python `mcp`, servidor local `stdio` y Skill de instrucciones.
- Tests: pytest, HTTPX/AnyIO y Ruff; Vitest, Testing Library y ESLint en frontend.
- Licencia: conservar [LICENSE](LICENSE), GNU GPL v3.

Archivos relevantes:

```text
backend/
  requirements.txt              Dependencias directas de ejecución
  requirements-dev.txt          Dependencias directas de desarrollo
  requirements-lock.txt         Resolución exacta Python
  pyproject.toml                Configuración pytest/Ruff
  run_mcp.py                    Launcher stdio
  app/
    main.py                     Health, parser, análisis manual y montaje de API
    models.py                   Contratos del parser
    analysis_models.py          Salida estricta del modelo y respuesta validada
    inspection_models.py        Resultados/errores de herramientas
    review_models.py            Instantáneas, timeline y comparación
    feedback_models.py          Decisiones humanas y feedback
    review_api.py               Endpoints de revisiones/feedback/evolución
    review_store.py             SQLite, transacciones y protección de inmutabilidad
    local_settings.py           Configuración de operador y URLs loopback
    local_access.py             Controles de acceso HTTP local
    mcp_server.py               inspect_changes y get_review_feedback
    services/
      diff_parser.py            Parser puro, dataclasses y IDs deterministas
      analysis.py               Orquestación compartida de análisis
      model_client.py           Adaptador de Meta
      reference_validator.py    Comprobación independiente de evidencia
      git_capture.py            Captura Git aislada, acotada y de solo lectura
      egress_guard.py           Filtros conservadores antes de transmitir
      inbox_client.py           Cliente HTTP local del MCP
  tests/                        Tests con Git temporal y proveedor simulado
frontend/
  package.json, package-lock.json
  vite.config.ts                Proxy, puertos y configuración Vitest
  src/
    App.tsx                     Rutas y explorador manual
    index.css                   Tokens, layout, responsive y movimiento
    components/                 Shell, revisiones, diffs, hallazgos y feedback
    lib/                        API, errores, ejemplos e i18n
    types/                      Contratos TypeScript
    test/                       Setup y fixtures
examples/diffs/                 Ejemplos compartidos por aplicación y tests
skills/ai-change-inspector/     Paquete distribuible del Skill
```

Los límites son deliberados: Git queda fuera del parser; persistencia, proveedor y validador
son módulos separados. Desde Sprint 4 el MCP registra/consulta a través de FastAPI: la web
es dueña de SQLite y de las llamadas a Meta. No hay un almacén alternativo en el MCP.

## 3. Funcionalidades de Sprints 1–8

| Sprint | Implementado y a preservar |
| --- | --- |
| 1 | Estructura inicial, `GET /health`, parser determinista unified Git diff, `POST /api/diff/parse`, explorador manual, ejemplos y tests. |
| 2 | Análisis Muse Spark, JSON Schema estricto/Pydantic, validación independiente de referencias y panel de hipótesis. |
| 3 | MCP `inspect_changes`, autorización por ID/raíz, alcance staged o unstaged, captura Git aislada y filtros sensibles. |
| 4 | Review Inbox, SQLite, instantáneas inmutables previas al proveedor, ID/URL, estados y errores persistidos. Incluye corrección CRLF/LF y soporte EN/ES. |
| 5 | Decisiones `request_changes`, `accept_risk`, `dismiss`, comentarios y fechas en tablas separadas; MCP de feedback de solo lectura y relaciones padre-hija. |
| 6 | Skill portable para Codex/Claude Code, solicitudes explícitas, prevención de duplicados/reintentos y tratamiento seguro del feedback. |
| 7 | Timeline de familia, ramas/relaciones incompletas y comparación visual padre-hija de instantáneas guardadas, de solo lectura. |
| 8 | Rediseño carbón/celeste, sidebar persistente, Overview, tablas compactas, detalle centrado en código, feedback, responsive, accesibilidad y animaciones aprobadas. |

Los Sprints 1–7 se conservaron durante el rediseño. Sprint 8 está implementado con sus
refinamientos aprobados; no se ha definido ni autorizado aquí un Sprint 9.

## 4. Decisiones técnicas importantes

### Parser, IDs y evidencia

`backend/app/services/diff_parser.py` usa solo biblioteca estándar, sin red, filesystem,
subprocesos, FastAPI ni Pydantic. El límite es 1 MiB UTF-8 del campo diff, inclusive.
Normaliza CRLF para interpretar el parche y producir IDs, sin reescribir archivos.

`file_id` y `hunk_id` usan SHA-256 determinista. Cambiar un bloque de archivo cambia sus
IDs; no son identificadores de hallazgos estables entre auditorías. La vinculación usa
archivo, hunk, lado y rango de líneas; `diff_line` localiza la línea del texto de entrada.
Ver README, sección «Parser e identificadores», para las garantías exactas.

`reference_validator.py` comprueba pertenencia archivo/hunk, ruta del lado correcto,
rango completo y cita literal. Conserva referencias inválidas y explica el fallo; no
las sustituye por referencias plausibles. No valida semánticamente el supuesto defecto.

### Proveedor actual

Verificado en `backend/app/services/model_client.py`:

- Base: `https://api.meta.ai/v1`; modelo: `muse-spark-1.3`.
- Variable: `MODEL_API_KEY`, exclusivamente backend.
- `client.responses.create`, `text.format` de tipo `json_schema`, `strict: true`.
- **Configuración actual: `max_output_tokens=8192`**, timeout 60 s, `max_retries=0`.
  No restaurar valores históricos de 1024 o 4096 por referencias antiguas del chat.
- `store=False`, sin herramientas ni historial; una solicitud, sin fallback a texto libre.
- Entrada parseada serializada limitada a 128 KiB; no hay truncamiento silencioso.
- Prompts solicitan informes nuevos en inglés; citas e IDs permanecen literales.
- JSON malformado, respuesta incompleta, rechazo, timeout y errores del proveedor son fallos
  explícitos, no análisis aparentemente exitosos.

El uso del SDK `openai` no significa que OpenAI sea el proveedor. No sustituir la variable
ni asumir compatibilidad de parámetros no comprobados. Las referencias oficiales usadas
están enlazadas en README; reconfirmarlas antes de cambiar el contrato externo.

### Persistencia y relaciones

`review_store.py` registra UUID v4, repositorio/raíz, origen, alcance, UTC, diff exacto,
SHA-256 y parser output antes de llamar al proveedor. No mantiene la transacción abierta
durante la llamada. Triggers protegen instantáneas, resultados terminales y relaciones.

Estados: `pending → analyzing → completed/error`. Al reiniciar, análisis interrumpidos
quedan como `analysis_interrupted`; no se reanudan ni consumen créditos automáticamente.
Se usa **un único proceso/worker de API por base**.

`human_decisions`, `human_comments` y `review_links` están separados de la auditoría.
El feedback usa `(review_id, finding_index)`; los índices pertenecen al resultado inmutable.
Un padre puede tener varios hijos; ambos deben pertenecer al mismo ID y raíz autorizados.

### Git y protección local

`git_capture.py` ejecuta argumentos seguros, sin shell, con 10 s por invocación, 1 MiB de
diff y 64 KiB para consultas auxiliares. No hace staging, commits, pruebas ni ejecución de
código auditado. `staged` compara índice/HEAD; `unstaged` compara árbol/índice. No existe
alcance `all`; untracked quedan fuera y no se incorporan automáticamente.

Se aíslan configuración ejecutable, hooks, filtros, textconv y overrides del entorno.
La corrección CRLF recupera únicamente valores validados de `core.autocrlf`, `core.eol`
y `core.safecrlf` para unstaged. No sigue includes ni importa atributos externos; por eso
puede diferir del Git habitual si la política EOL depende exclusivamente de esas fuentes.
No normalizar archivos ni modificar configuración global para ocultar discrepancias.

`egress_guard.py` filtra rutas sensibles y patrones de secretos antes del registro/envío.
Es heurístico, no una garantía de ausencia de credenciales o información privada.

Loopback, Host/Origin y protecciones de solicitudes externas reducen riesgos del navegador;
**localhost no equivale a autenticación**. No exponer en LAN, túneles ni servicios públicos.

## 5. Frontend y sistema de diseño

La dirección aprobada es sobria, profesional y centrada en código: sin degradados, glow,
neón, estadísticas inventadas, controles decorativos ni biblioteca UI pesada.

- Tokens en `frontend/src/index.css`: carbón/antracita, bordes discretos, radios, espaciado,
  tipografía, focus y colores semánticos independientes de la marca.
- Accent `#59C3FF`, hover `#7AD0FF`, soft `rgba(89,195,255,0.14)`, usado moderadamente.
- Escala principal: títulos 34 px, cuerpo 15 px, sidebar expandido 262 px.
- `AppShell.tsx`: sidebar, navegación, tooltips, topbar y selección EN/ES.
- `Overview.tsx` y `ReviewTable.tsx`: total global del API; estados solo del lote reciente
  de hasta 20 revisiones; tabla de hasta cinco recientes. No confundirlos con totales históricos.
- `ReviewInbox.tsx`: tabla compartida, paginación y actualización explícita.
- `ReviewDetail.tsx`, `DiffExplorer.tsx`, `FindingsPanel.tsx`, `FeedbackEditor.tsx`:
  diff amplio, hipótesis/evidencia/pruebas separadas y decisiones humanas con guardado explícito.
- `ReviewEvolution.tsx`, `ReviewCompare.tsx`, `ReviewSnapshot.tsx`: timeline y dos snapshots
  independientes. No reconstruyen diffs desde Git ni generan nuevos análisis.
- `CodeText.tsx`: resaltado simple por extensión; conserva texto/espacios y no es un parser
  de lenguajes completo ni interpreta cadenas multilínea con precisión general.
- `AnimatedDisclosure.tsx`: apertura/cierre mediante CSS Grid, sin temporizadores;
  contenido montado, `aria-expanded`, `aria-controls`, `aria-hidden` e `inert`.
  El feedback queda fuera del contenido plegable; no se pierde al cerrarlo.
- Movimiento: sidebar/contenido 200 ms, pantalla 160 ms con opacidad y desplazamiento de
  4 px, bloques con desfases de 30 ms; no se animan filas ni se reinicia la entrada por refresh.
  `prefers-reduced-motion: reduce` desactiva animaciones y transiciones.
- `lib/translations.ts`, `lib/i18n.ts` y `LanguageProvider.tsx`: EN por defecto, ES opcional.
  `localStorage` conserva `ai-change-inspector.language` y
  `ai-change-inspector.sidebar-collapsed`; no son preferencias portables entre equipos.
- Informes históricos no se traducen ni regeneran al cambiar idioma.

Rutas web reales en `App.tsx`:

```text
/                                  Overview
/diff                              Explorador manual
/reviews                           Inbox
/reviews/{review_id}               Detalle
/reviews/{review_id}/evolution     Timeline y comparación directa disponible
/reviews/{parent_id}/compare/{child_id}  Comparación padre-hija
```

Las maquetas/capturas de la conversación y servidores temporales de prueba no deben asumirse
incluidos en el checkout. La referencia portable implementada son estos componentes y README.

## 6. MCP, Skill y configuración

### Herramientas

Fuente: `backend/app/mcp_server.py`; launcher: `backend/run_mcp.py`.

```json
{"repository":"demo","scope":"unstaged"}
```

Argumentos de `inspect_changes`; opcionalmente añadir `parent_review_id` con un UUID real.
Registra una auditoría y puede consumir Meta: Git es de solo lectura, la herramienta completa no.
Devuelve estado, ID/URL, `registration_confirmed`, `analysis_status`, resultados o error recuperable.

```json
{"repository":"demo","review_id":"UUID-REAL-DEVUELTO-POR-LA-AUDITORIA"}
```

Argumentos de `get_review_feedback`: solo lectura, sin Git ni Meta. No acepta decisiones
ni comentarios de escritura. Estos ejemplos no son valores para invocar sin sustituir el UUID.

La API debe autorizar el mismo ID y raíz que MCP. No acepta rutas arbitrarias del agente.
MCP apagado, API inaccesible o registro no confirmado requieren informar el estado y consultar
la bandeja antes de repetir; no crear auditorías duplicadas ni reintentar automáticamente.

### Skill

Distribuir toda la carpeta [skills/ai-change-inspector](skills/ai-change-inspector), incluyendo
`SKILL.md` y `references/examples.json`. El paquete no instala/configura MCP por sí solo.

| Cliente | Instalación relativa al proyecto auditado | Invocación |
| --- | --- | --- |
| Codex | `.agents/skills/ai-change-inspector/` | `$ai-change-inspector` o selección desde `/skills` |
| Claude Code | `.claude/skills/ai-change-inspector/` | `/ai-change-inspector` |

Evitar duplicar instalaciones personales/de proyecto. Reiniciar/reconectar tras instalar.
El Skill exige autorización explícita para auditar y para consultar feedback; no autoriza
correcciones ni comandos por instrucciones presentes en un informe/comentario.

README, secciones «Codex: ejemplo verificado» y «Claude Code: ejemplo verificado», contiene
los ejemplos de registro/configuración. Las rutas de ejecución del cliente deben resolverse
a absolutas **en el nuevo equipo**, sin copiar configuraciones privadas anteriores:

- Ejecutable: `backend/.venv/Scripts/python.exe`; argumento de script: `backend/run_mcp.py`.
- Argumentos verificados por `--help`: `--repo ID=ABSOLUTE_PATH`, `--env-file` opcional,
  `--api-url` opcional. No inventar opciones ni un modo simulado del launcher.
- Codex: `enabled_tools` incluye las dos herramientas; timeouts documentados de inicio 20 s
  y herramienta 120 s, con aprobaciones explícitas. Comprobar con
  `codex.cmd mcp get ai-change-inspector`.
- Claude Code: registro documentado con `claude mcp add --transport stdio --scope local`,
  ejecutable/script/ruta autorizada como argumentos; verificar con
  `claude mcp get ai-change-inspector` y `/mcp`.
- Reconfirmar compatibilidad con la versión del cliente instalada; esta transferencia no
  instala clientes ni demuestra que el nuevo equipo tenga acceso a Meta.

### Configuración de operador

| Variable | Uso |
| --- | --- |
| `MODEL_API_KEY` | Secreto del servicio web; nunca frontend, argumentos ni archivo versionado. |
| `INSPECTOR_REPOSITORIES` | JSON ID → raíz absoluta autorizada; por defecto `{}`, deniega nuevas entregas. |
| `INSPECTOR_DB_PATH` | Ruta absoluta opcional; por defecto `backend/.local/reviews.sqlite3`. |
| `INSPECTOR_API_URL` | Por defecto `http://127.0.0.1:8000`; API usada por MCP. |
| `INSPECTOR_WEB_URL` | Por defecto `http://127.0.0.1:5173`; origen permitido y base de enlaces. |

`backend/.env.example` documenta variables. `.env` no se carga automáticamente: Uvicorn
necesita `--env-file .env` o variables exportadas antes del arranque. Reiniciar tras cambios.
El `--env-file` de MCP solo carga `MODEL_API_KEY` para su filtro local; no configura la web.

## 7. Ejecución y verificaciones

Comandos Windows/PowerShell documentados en README. Versiones comprobadas durante esta
preparación: Node v22.14.0, npm 11.6.0 y Python 3.12.1. El frontend requiere Node >=22.12.
En otro SO adaptar activación/ruta del virtualenv y usar `npm` en lugar de `npm.cmd`.

Instalación desde la raíz, en un checkout nuevo:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
cd frontend
npm.cmd ci
```

Recrear entornos desde lockfiles; no transferir `.venv` ni `node_modules` del equipo anterior.
La reinstalación completa no se repitió al redactar este documento.

Backend, terminal nueva desde la raíz:

```powershell
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Si se utiliza un `backend/.env` privado ya preparado, añadir `--env-file .env` al comando.
Sin clave funciona el parser; el análisis devuelve un error de configuración.

Para el flujo de demo MCP, configurar primero las autorizaciones. Este ejemplo presupone
un repositorio Git de demostración ya existente en `../demo-repo`; esa carpeta es un ejemplo
a preparar, no un archivo incluido ni un comando para crear/stagear/commitear cambios:

```powershell
# Terminal de API, desde la raíz del inspector, antes de arrancar Uvicorn:
$demoRoot = (Resolve-Path ../demo-repo).Path
$env:INSPECTOR_REPOSITORIES = @{ demo = $demoRoot } | ConvertTo-Json -Compress
# Después iniciar la API con uno de los comandos anteriores en esta misma terminal.
```

Frontend, otra terminal desde la raíz:

```powershell
cd frontend
npm.cmd run dev
```

Abrir `http://127.0.0.1:5173/`. Vite usa puerto fijo y proxy `/api` y `/health` a 8000;
no habilitar CORS para resolver una configuración incorrecta. OpenAPI está en
`http://127.0.0.1:8000/docs`.

Comprobación/arranque del launcher desde la raíz (el arranque efectivo lo gestiona el cliente):

```powershell
backend/.venv/Scripts/python.exe backend/run_mcp.py --help
# Con ../demo-repo ya preparado y la API configurada con el mismo ID/raíz:
$demoRoot = (Resolve-Path ../demo-repo).Path
backend/.venv/Scripts/python.exe backend/run_mcp.py --repo "demo=$demoRoot"
```

El segundo comando espera JSON-RPC por stdin; no es una consola interactiva ni realiza una
auditoría por sí solo. El CLI `--help` se ejecutó y verificó durante este handoff.

Backend, desde `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest -q --tb=short
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pip check
```

Frontend, desde `frontend/`:

```powershell
npm.cmd run test -- --run
npm.cmd run lint
npm.cmd run build
```

Git, desde la raíz:

```powershell
git status --short
git diff --check
git diff --cached --stat
```

Última ejecución registrada en esta sesión, tras las animaciones del Sprint 8:
**67 tests frontend en 13 archivos, 244 tests backend**, ESLint y build TypeScript/Vite
correctos; comprobación de diff sin errores y staging vacío. Ruff/formato y `pip check`
también pasaron en verificaciones anteriores. Son antecedentes, no una ejecución nueva
de la suite al escribir este archivo ni una certificación del entorno de destino.

La comprobación visual fue con navegador integrado, escritorio 1536×960 y viewport móvil
390×844: sidebar sincronizado, inversión rápida, teclado, apertura/cierre y contenido inerte.
La regla CSS de movimiento reducido se inspeccionó; no se forzó la preferencia del SO.
No se hicieron llamadas reales a Meta durante el trabajo visual. Tests usan mocks.

Endpoints existentes, verificados en `main.py` y `review_api.py`:

```text
GET  /health
POST /api/diff/parse
POST /api/diff/analyze
POST /api/reviews
GET  /api/reviews
GET  /api/reviews/{review_id}
POST /api/reviews/{review_id}/analyze
GET  /api/reviews/{review_id}/feedback
PUT  /api/reviews/{review_id}/feedback/{finding_index}
GET  /api/reviews/{review_id}/timeline
GET  /api/reviews/{review_id}/compare/{other_id}
```

No eludir por HTTP los límites del Skill/MCP. Las escrituras humanas requieren Origin
permitido y `X-Inspector-Request: 1`; no constituyen autenticación de identidad humana.

## 8. Limitaciones y pendientes conocidos

- No autenticación, nube, colaboración, hooks, corrección autónoma, ejecución de tests
  auditados, comparación semántica con LLM ni empaquetado desktop. No autorizados como siguiente sprint.
- SQLite contiene diffs/comentarios privados sin cifrado de aplicación; no hay retención,
  limpieza automática, historial de comentarios ni control de concurrencia humana.
- Feedback admite comentario de hasta 4000 caracteres; última escritura confirmada prevalece.
  No hay borrado/retorno a pendiente. Borradores se pierden al salir/recargar, no al plegar hallazgos.
- Registro no confirmado no significa registro ausente. Revisar ID/bandeja antes de repetir.
  Cancelación/timeout del cliente no garantiza cancelar una llamada ya enviada a Meta.
- El timeline limita el recorrido a 200 IDs; una familia puede quedar truncada/incompleta.
  Comparación inicial solo padre-hija directa; no identifica hallazgos equivalentes ni resueltos.
- Git no soporta linked worktrees, bare repos, submódulos como raíz, partial clones ni
  almacenes de objetos externos. Las restricciones EOL/includes pueden diferir del Git habitual.
- Parser no soporta combined diff, prefijos personalizados, word-diff ni formatos ajenos
  a unified Git diff documentado. No aplica el parche ni comprueba archivos completos.
- No hay sondeo automático. La vista manual no persiste sus diffs; solo el flujo MCP registra snapshots.
- El proxy Vite es de desarrollo; no existe una estrategia de despliegue público aprobada.
- Los filtros no detectan todos los secretos. El acceso de otros procesos locales sigue siendo un límite.
- El launcher todavía describe su CLI como «Read-only»; se refiere a Git. `inspect_changes`
  sí registra revisiones. No interpretar esa frase como ausencia de efectos persistentes.
- La sesión anterior validó Sprint 5 E2E con proveedor simulado y Sprint 6 con Codex CLI real
  más proveedor simulado. Es contexto de sesión; los tests estáticos por sí solos no demuestran
  carga/obediencia real del Skill ni validación E2E del cliente Claude en el nuevo equipo.
- Los procesos, base y servidor de prueba temporales de esas validaciones no son un harness
  portable incluido. No hay un modo simulado de servidor documentado mediante una variable;
  no inventar `MOCK_PROVIDER` ni usar una clave falsa suponiendo que evita tráfico real.
- Migrar SQLite no remapea raíces: las instantáneas conservan la raíz absoluta original.
  Si cambia en el nuevo equipo, las consultas que exigen autorización coincidente y los
  vínculos con capturas nuevas pueden ser rechazados, aunque el ID del repositorio coincida.
  No hay herramienta de migración de raíces; para una demo portable, preferir una base nueva.
- Revalidar disponibilidad de Muse Spark, cuenta/créditos y clientes en destino. Una prueba
  simulada no acredita acceso actual al proveedor. Verificación visual limitada al navegador disponible.

## 9. Git y datos privados

Estado comprobado **antes de crear este archivo**:

- Rama `main`, commit `5656553` — `feat: add comprehensive testing and components for review management`.
- `git status --porcelain=v1` sin salida: checkout limpio, sin archivos pendientes ni staging.
- Los cambios acumulados de la conversación ya no estaban pendientes en ese momento;
  no reutilizar los listados antiguos del chat como estado actual de Git.
- Esta tarea solo añade `HANDOFF.md`; no hace staging, commits, pushes ni cambios de aplicación.
- `frontend/package-lock.json` y `backend/requirements-lock.txt` están versionados.

La política de [.gitignore](.gitignore) excluye `.env`/`.env.*` salvo `.env.example`,
`.venv`, `node_modules`, `dist`, caches, `.local`, SQLite y auxiliares. `AGENTS.md` también
está ignorado y no versionado: su contenido no se incluye aquí ni se debe transferir
automáticamente como documentación pública. Revisar las instrucciones locales que aporte
el operador en la nueva sesión; no sobrescribirlas con una copia de contexto.

Mantener privados claves/tokens, configuraciones locales de clientes MCP, raíces autorizadas,
bases, diffs, comentarios, logs y capturas con información privada. No basta con que un archivo
esté ignorado para que sea seguro compartirlo en un ZIP. No copiar indiscriminadamente el
directorio de trabajo ni el perfil del agente. Si se migra SQLite, hacerlo por un canal privado
y con la API detenida; conservar sus metadatos y considerar la limitación de raíces descrita
arriba. No modificar snapshots inmutables de forma ad hoc para forzar su autorización.

## 10. Continuación y demo con Muse Code / Muse Spark

Prioridad acordada: conservar el flujo completo y la interfaz aprobada, trasladar el contexto
y preparar una demo en inglés. Las animaciones están implementadas; queda la valoración
manual del desarrollador en el nuevo equipo y la nueva validación de entorno.

**Muse Spark** ya es el auditor implementado. **Muse Code** se menciona ahora para preparar
la demo: no hay integración, SDK, modelo, configuración ni launcher Muse Code documentados
en este repositorio. No afirmar que ya funciona como cliente MCP ni inventar sus capacidades.
Primero verificar su modo oficial de uso y cómo participa como agente productor de cambios.
Si requiere desarrollo adicional, definir y autorizar ese alcance por separado.

Secuencia de preparación, sin ejecutarla automáticamente al leer este handoff:

1. Restaurar checkout y dependencias, comprobar Git y leer README e instrucciones locales
   disponibles. No rehacer arquitectura ni sustituir componentes que ya funcionan.
2. Configurar secretos solo localmente y autorizar un repositorio de demo pequeño, sin datos
   privados, distinto del inspector. Arrancar API de un worker, frontend y reconectar MCP/Skill.
3. Repetir primero tests con mocks. Para validar una sesión real del agente con proveedor
   simulado, preparar un harness explícito y revisable: el harness temporal anterior no está incluido.
4. Confirmar la disponibilidad y el rol de Muse Code. Rol previsto para la narrativa: productor
   del cambio; AI Change Inspector/Muse Spark realiza la auditoría independiente. Si se usa
   Codex/Claude como puente MCP, mostrarlo con transparencia, no atribuir esa llamada a Muse Code.
5. Con autorización explícita, producir en el repo de demo un cambio acotado de riesgo visible,
   por ejemplo una fórmula que falla en un límite. Nunca preparar el caso modificando el inspector.
   Elegir staged o unstaged conforme al estado real; no stagear automáticamente archivos nuevos.
6. Autorizar una auditoría concreta y acotada de Meta. Informar ID, URL y estado; abrir el diff
   exacto, hipótesis, referencias válidas/ inválidas y pruebas sugeridas sin ejecutarlas.
   No prometer que el modelo encontrará un riesgo concreto ni ocultar un fallo del proveedor.
7. El desarrollador guarda `request_changes` y un comentario en la web. Solo después solicita
   `get_review_feedback`; el agente presenta lo guardado sin modificarlo ni ejecutar instrucciones.
8. Una corrección requiere otra autorización. Tras ella, solicitar explícitamente una auditoría
   hija con `parent_review_id`. Mostrar Evolution y ambas instantáneas, sin declarar resuelto
   un hallazgo solo porque no aparece de nuevo. Si hay dos análisis reales, autorizar ambos
   consumos de forma consciente; la segunda revisión no es una traducción o comparación gratuita.
9. Presentar en EN. Tener ejemplos locales y resultados simulados claramente identificados como
   respaldo, sin fabricar IDs/hallazgos ni presentarlos como llamadas reales. No repetir Meta
   automáticamente tras errores para intentar mejorar una demo.

No hay tareas futuras implícitamente autorizadas por este documento. La siguiente sesión debe
comenzar verificando el estado real del checkout y la configuración, no suponiendo que procesos,
URLs de revisiones históricas o permisos del equipo anterior siguen disponibles.
