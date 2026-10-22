# AGENT ROSTER / SlimeOps

Panel visual para controlar un roster de agentes reutilizables. La sala de slimes es la pantalla principal; las tareas de mayor detalle se abren en ventanas popup para no perder el contexto operativo.

## Arranque local

```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

El panel publicado se conecta a `http://127.0.0.1:8000`; por eso la API debe estar activa en el mismo equipo para ver telemetría, límites de Codex y auditoría real.

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
