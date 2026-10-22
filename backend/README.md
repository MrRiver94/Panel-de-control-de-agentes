# Backend — AgentOps API

API local de observabilidad y control del roster. Mantiene el estado en memoria para la primera versión; una base de datos se añadirá antes de operar en producción.

## Ejecutar

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

El frontend se conecta por defecto a `http://127.0.0.1:8000`.

## Endpoints

- `GET /api/dashboard`: roster, límites y eventos.
- `POST /api/agents/{agent_id}/controls`: cambia `token_budget` y `reasoning_effort`.
- `POST /api/activity`: registra una actividad con tokens de entrada, salida y razonamiento.

`reasoning_effort` es una política de ejecución (`low`, `medium`, `high`, `xhigh`), no contenido del pensamiento. Al conectar un proveedor, guarda solo los campos de uso que devuelva su API, como `reasoning_tokens`.
