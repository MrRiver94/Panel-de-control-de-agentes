# Backend — AgentOps API

API local de observabilidad y control del roster. El historial de actividad se guarda de forma persistente en SQLite en `data/agent_activity.sqlite3`, por lo que sobrevive a reinicios del backend.

## Ejecutar

Con el entorno virtual y las dependencias instalados, arranca la API desde esta carpeta con:

```powershell
.\start.ps1
```

Para preparar el entorno por primera vez:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

El frontend se conecta por defecto a `http://127.0.0.1:8000`.

## Endpoints

- `GET /api/dashboard`: roster, límites y los 50 eventos más recientes.
- `GET /api/activity/history?limit=100`: historial persistente para auditoría (hasta 500 eventos por consulta).
- `POST /api/agents/{agent_id}/controls`: cambia `token_budget` y `reasoning_effort`.
- `POST /api/activity`: registra una actividad con tokens de entrada, salida y razonamiento.
- `POST /api/agents/{agent_id}/profile`: persiste nombre, rol, estilo, descanso y acciones habilitadas.

`reasoning_effort` es una política de ejecución (`low`, `medium`, `high`, `xhigh`), no contenido del pensamiento. Al conectar un proveedor, guarda solo los campos de uso que devuelva su API, como `reasoning_tokens`.

La auditoría registra asignaciones de misiones, cambios de límites/esfuerzo y actividades enviadas a `POST /api/activity`, con tokens de entrada, salida y razonamiento separados.

Consulta `../docs/TECHNICAL_GUIDE.md` para la arquitectura completa, las tablas SQLite y la guía de integración.

## Organización y pruebas

`app/main.py` conecta FastAPI con los routers de `app/routes/`. Los contratos están en `app/models.py`; SQLite, en `app/repository.py`; el estado compartido, en `app/state.py`. Los servicios de catálogo, permisos, telemetría y Codex tienen módulos independientes.

El comando de arranque `./start.ps1` y las rutas de la API se mantienen. Para ejecutar las regresiones desde `backend`:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests
```

Las pruebas usan bases temporales y no modifican los datos locales del panel. Consulta [el mapa del código](../docs/CODE_STRUCTURE.md) para localizar cada responsabilidad.
