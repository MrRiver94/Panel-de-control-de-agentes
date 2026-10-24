# Mapa del código

## Frontend

La interfaz usa módulos ES nativos del navegador. `frontend/src/app.js` conecta los eventos, restaura la sala e inicia las tareas periódicas; la lógica está en `frontend/src/js/`.

| Ruta bajo `src/js/` | Responsabilidad |
| --- | --- |
| `config.js` | Valores iniciales, catálogo sugerido, posiciones y reglas visuales. |
| `state.js` | Estado compartido de la interfaz. |
| `dom.js` | Consultas DOM y formateadores reutilizables. |
| `agents/model.js` | Adaptación de agentes de la API y etiquetas de estado. |
| `room/geometry.js` | Suelo transitable y límites de roca. |
| `room/navigation.js` | Recorridos, avances por frame y actividades de descanso/trabajo. |
| `room/camera.js` | Proporciones lógicas de zoom, desplazamiento y botones de cámara. |
| `room/render.js` | Creación y actualización de slimes en el mapa. |
| `room/storage.js` | Guardado y restauración de posiciones y recorridos. |
| `room/simulation.js` | Simulación visual y recuperación del estado anterior. |
| `features/controls.js` | Presupuestos, modelo, esfuerzo y personalización. |
| `features/access.js` | Roles, usuarios y altas/bajas de agentes. |
| `features/agent-watch.js` | Tarjetas de seguimiento y detalles de actividad. |
| `features/metrics.js`, `charts.js` | Medidores, cuotas y gráficas. |
| `features/activity.js` | Actividad, consola e historial. |
| `features/missions.js` | Asignaciones y envío de misiones. |
| `features/executions.js` | Proyecto, permisos, historial de misiones reales y cancelación. |
| `features/sessions.js` | Lista de sesiones de Codex. |
| `services/api.js` | Cliente HTTP y cabecera de operador, compartido por todos los paneles. |
| `services/live.js` | Dashboard, SSE, consultas periódicas y versión publicada. |
| `ui/dashboard.js`, `events.js` | Composición de vistas y conexión de controles de la pantalla. |

Las funciones que conectan distintas vistas se llaman después del arranque. Los módulos de renderizado no deben iniciar temporizadores al importarse. Las pruebas cargan el grafo real de módulos en contextos aislados, sustituyendo únicamente las vistas que no pertenecen a cada comprobación.

## Estilos y recursos

La ejecución real está documentada en [CODEX_EXECUTION.md](CODEX_EXECUTION.md). Sus servicios se encuentran en `backend/app/execution.py`, `codex_process.py`, `execution_store.py`, `process_lifetime.py` y `runtime_lock.py`.

`frontend/src/styles/app.css` es la entrada única de estilos. Importa los archivos por bloques en el mismo orden que tenían los estilos anteriores para conservar el resultado visual. Algunas reglas de base se completan en archivos posteriores: no reordenar los imports sin comprobar sus efectos en navegador.

- `base.css`: cimientos y reglas históricas compartidas.
- `dashboard.css`, `agent-watch.css`, `room.css`: paneles, tarjetas, sala, escenario y cámara.
- `activity.css`, `customizer.css`, `access.css`, `sessions.css`: sus vistas correspondientes.
- `breaks.css`, `work.css`: sprites y estados animados de los agentes.

El arte original permanece en `frontend/src/assets/`. `build.mjs` localiza las referencias `assets/...`, comprueba que existan y publica solo esos recursos en `dist/`. Los archivos de `dist/` se generan; no son la fuente para editar.

## Backend

`backend/app/main.py` crea la aplicación y conecta el ciclo de vida y los routers. Se mantiene el arranque `uvicorn app.main:app`.

| Ruta bajo `backend/app/` | Responsabilidad |
| --- | --- |
| `config.py` | Ruta del proyecto, CORS y catálogo sugerido. |
| `models.py` | Validación Pydantic de solicitudes, respuestas y agentes. |
| `state.py` | Roster, ubicación de SQLite, bloqueos y cachés compartidas. |
| `repository.py` | Esquema y lectura/escritura persistente de SQLite. |
| `permissions.py` | Árbol de acceso y comprobación de permisos. |
| `catalog.py` | Catálogo de proveedores y modelos. |
| `telemetry.py` | Medidor existente y muestras de uso. |
| `codex_usage.py`, `codex_sessions.py` | Lectura de las fuentes locales de Codex. |
| `agent_utils.py`, `timeutils.py` | Búsqueda validada de agentes y reloj UTC. |
| `routes/dashboard.py` | Salud, dashboard, stream, modelos, gráficas e historial. |
| `routes/agents.py`, `access.py` | Controles, perfiles, actividad y administración. |
| `routes/codex.py`, `missions.py` | Sesiones/cuotas y asignación de misiones. |

El repositorio conserva sus tablas y datos, los contratos HTTP, los intervalos y las claves del navegador. Esta reorganización mantiene también los modos de demostración y las limitaciones de ejecución descritos en la guía técnica.

## Comprobaciones

Desde `frontend`: `npm ci`, `npm test`, `npm run format:check` y `npm run build`. Desde `backend`: `.venv/Scripts/python.exe -m unittest discover -s tests`.

Antes de la reorganización se capturaron el contrato OpenAPI y los tamaños/estilos del navegador. La revisión compara los endpoints y modelos con ese contrato, y la apariencia en anchos de 1440, 900 y 540 px. Un cambio visual nuevo debe revisarse además con el zoom, los controles y la simulación.
