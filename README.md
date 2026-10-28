# AI Change Inspector

Explorador de cambios de Git para la Meta AI Developer Hackathon 2026.
Sprint 1: pegar un diff, validarlo y explorar archivos, hunks y líneas con sus números originales.
El análisis con modelos queda para un sprint posterior. No hay integración Meta AI, autenticación,
base de datos ni persistencia de diffs.

## Requisitos

- Node.js 22.12 o superior (verificado con 22.14.0) y npm (verificado con 11.6.0).
- Python 3.12 (verificado con 3.12.1).
- Git para producir diffs; el parser no ejecuta Git.

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
`package-lock.json` fija la resolución del frontend. No se necesita ningún secreto ni archivo `.env`.

Abre dos terminales nuevas en la raíz del repositorio.

Terminal 1:

```powershell
cd backend
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
en el proyecto y no realizan análisis con IA. Cambiar el texto invalida el resultado anterior.

## Estructura

```text
backend/
  app/main.py                 # Adaptador HTTP y errores
  app/models.py               # Contrato Pydantic
  app/services/diff_parser.py # Parser puro, dataclasses inmutables
  tests/                     # Parser y contrato HTTP
frontend/
  src/components/            # DiffExplorer y futuro FindingsPanel separados
  src/lib/                   # Cliente HTTP y ejemplos compartidos
  src/types/                 # Contrato TypeScript
examples/diffs/               # Fixtures válidos y un ejemplo inválido
AGENTS.md                     # Reglas para agentes que trabajen en el proyecto
```

## API del Sprint 1

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

Para futuros hallazgos, usar `file_id`, `hunk_id`, lado (`old`/`new`) y número de línea de ese lado.
`diff_line` sirve para localizar el texto de entrada, pero cambia si se anteponen otros archivos.
El explorador expone IDs de archivo/hunk en el DOM; no existe todavía un contrato de hallazgos de IA.

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
el envío, estados de carga/error, texto seguro, navegación y separación del panel futuro.
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
