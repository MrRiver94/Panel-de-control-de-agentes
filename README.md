# AGENT ROSTER / SlimeOps

Panel visual para controlar un roster de agentes reutilizables. La sala de slimes es la pantalla principal; las tareas de mayor detalle se abren en ventanas popup para no perder el contexto operativo.

## Arranque local

Abre dos terminales en la carpeta del proyecto. En la primera, arranca el backend:

```powershell
cd backend
.\start.ps1
```

En la segunda, arranca el frontend:

```powershell
cd frontend
npm run start
```

El navegador se abre automáticamente en [http://127.0.0.1:4173](http://127.0.0.1:4173). El frontend compila `dist/` al arrancar y se conecta a `http://127.0.0.1:8000`; deja ambas terminales abiertas mientras lo usas. La primera vez, si todavía no existe `backend/.venv`, créalo desde `backend` con `python -m venv .venv` y ejecuta `pip install -r requirements.txt`.

El panel publicado se conecta a `http://127.0.0.1:8000`; por eso la API debe estar activa en el mismo equipo para ver telemetría, límites de Codex y auditoría real.

## Proveedor y modelo por agente

En **Control del agente** puedes elegir `Codex / OpenAI` o `Anthropic / Claude`, seleccionar un modelo y guardar la elección junto al límite de tokens y el esfuerzo. El backend conserva estos parámetros en SQLite y los devuelve en `/api/dashboard`. Los modelos sugeridos no implican acceso a la cuenta; la ejecución real de modelos aún no está conectada.

Para sustituir el catálogo sugerido por los modelos de tu entorno, define `AGENT_MODEL_CATALOG_JSON` antes de arrancar la API. Ejemplo en PowerShell:

```powershell
$env:AGENT_MODEL_CATALOG_JSON = '{"codex":["modelo-codex-configurado"],"anthropic":["modelo-claude-configurado"]}'
```

El selector lee ese catálogo desde `GET /api/models`. Un modelo ya asignado a un agente también aparece aunque no figure en el catálogo actual.

## Estructura

| Ruta | Responsabilidad |
| --- | --- |
| `frontend/src/` | Interfaz estática: sala, tarjetas de agentes, popups, estilos y comportamiento. |
| `frontend/src/assets/` | Fondos y sprites pixel art usados por la interfaz. |
| `frontend/build.mjs` | Genera `dist/`, el artefacto desplegable. |
| `backend/app/main.py` | API FastAPI, stream en vivo, controles, perfiles y auditoría SQLite. |
| `data/agent_activity.sqlite3` | Base local persistente; se crea automáticamente y no se versiona. |
| `agents/` | Especificaciones funcionales de los agentes. |
| `runtime/` | Base del runtime futuro que ejecutará agentes reales. |
| `docs/` | Guía técnica y registro de cambios del proyecto. |

Consulta [la guía técnica](docs/TECHNICAL_GUIDE.md) antes de extender el sistema y actualiza [el registro de cambios](docs/CHANGELOG.md) al introducir comportamiento, rutas o datos nuevos.

## Principios

- La pantalla principal comunica estado y actividad en directo.
- Las configuraciones detalladas viven en popups, sin abandonar la sala.
- La auditoría registra metadatos operativos y uso de tokens, nunca pensamiento interno.
- Cada cambio visual se compila y se publica sobre la misma URL privada.

## Control de acceso provisional

SQLite guarda tambiÃ©n el Ã¡rbol de roles, usuarios locales y el registro persistente de agentes. La semilla es `SUPER-ADMIN` (todos los permisos) y `OPERADOR DE MISIONES` (solo ver panel y enviar misiones).

Desde el popup `ACCESO`, el Super Admin puede crear, editar y borrar roles y usuarios no protegidos, ademÃ¡s de crear agentes. La API comprueba cada permiso usando el operador local activo.

Este control es local y provisional, no un sistema de autenticaciÃ³n. Antes de exponer la API fuera del equipo, debe sustituirse por inicio de sesiÃ³n real y sesiones emitidas por el servidor.
