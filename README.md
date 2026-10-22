# AGENT ROSTER

Repositorio base para una colección de agentes reutilizables. Cada archivo de `agents/` será la fuente de verdad de su identidad, rol, instrucciones, herramientas y permisos.

El proyecto se divide ahora en dos aplicaciones:

- `frontend/`: AgentOps Monitor, la interfaz visual. `frontend/build.mjs` publica el artefacto estático en `dist/`.
- `backend/`: API local para actividad, presupuestos de tokens y esfuerzo de razonamiento por agente.

El runtime de agentes sigue en `runtime/`. La telemetría registra configuración y uso; no guarda ni muestra el razonamiento interno de un modelo.
