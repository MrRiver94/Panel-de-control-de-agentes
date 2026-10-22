# Guía técnica de SlimeOps

## Objetivo

SlimeOps observa y configura un conjunto de agentes. No ejecuta todavía modelos desde el panel: representa su estado, enruta misiones y recibe actividad declarada por el runtime o por integraciones futuras.

## Arquitectura

```text
Navegador (Site privado)
  ├─ Sala, controles y popups
  └─ HTTP + SSE a 127.0.0.1:8000
          │
          ├─ FastAPI: roster, routing y perfiles
          ├─ SQLite: actividad y configuración persistente
          └─ Codex App Server local: límites y uso de cuenta
```

El Site es estático. Las llamadas a `127.0.0.1` solo funcionan desde el ordenador que ejecuta la API; no exponen la base de datos a Internet.

## Interfaz

La pantalla principal contiene la sala, las tarjetas laterales de cada slime, controles rápidos de tokens/esfuerzo, salud operativa, capacidad de Codex y actividad reciente.

Los popups existentes son:

- `HISTORIAL`: consulta hasta 100 eventos persistidos con fecha, tipo y desglose de tokens.
- `PERSONALIZAR AGENTE`: modifica nombre, rol, color, matiz, zona de descanso, acción por defecto y acciones habilitadas.

La sala usa `RoomWorld` como cámara transformable. Las unidades se insertan en ese mundo desde `renderSlimeRoom`; las ventanas popup se mantienen fuera para no verse afectadas por el zoom.

## Backend y datos

`backend/app/main.py` es el único punto de entrada de la API. La base `data/agent_activity.sqlite3` tiene dos tablas:

| Tabla | Contenido |
| --- | --- |
| `activity_events` | Misiones, cambios de controles/perfil y actividad declarada, con tokens de entrada, salida y razonamiento. |
| `agent_profiles` | Personalización persistida por agente. |

La base se inicializa al arrancar. Está ignorada por Git para mantener los registros locales privados.

### Endpoints

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/api/dashboard` | Estado del roster y últimos 50 eventos. |
| GET | `/api/stream` | Actualizaciones SSE del panel. |
| GET | `/api/activity/history?limit=100` | Auditoría persistente; máximo 500. |
| POST | `/api/dispatch` | Enruta una misión y registra las asignaciones. |
| POST | `/api/activity` | Un runtime informa de un paso real y sus tokens. |
| POST | `/api/agents/{id}/controls` | Actualiza límite de tokens y esfuerzo. |
| POST | `/api/agents/{id}/profile` | Persiste identidad, estilo y acciones del agente. |
| GET | `/api/codex-usage` | Lee límites reales del Codex local, con caché corta. |

### Control de acceso y CRUD

La base incorpora estas tablas adicionales:

| Tabla | Contenido |
| --- | --- |
| `roles` | Identificador, nombre y lista JSON de permisos. |
| `users` | Usuario local y rol asignado. |
| `agent_registry` | Estado completo y persistente de cada agente creado o actualizado. |

Las capacidades son `dashboard.view`, `mission.create`, `agents.create`, `agents.update`, `agents.delete` y `access.manage`. La semilla contiene `super-admin` con `*` y `operador-misiones` con solo `dashboard.view` y `mission.create`.

El frontend transporta el operador activo en `X-Operator-Id` y FastAPI comprueba el permiso en cada mutaciÃ³n. Es una capa local provisional para controlar el panel, no autenticaciÃ³n de red: no debe exponerse fuera de `127.0.0.1` sin identidad real, sesiones firmadas y protecciÃ³n CSRF.

Las rutas CRUD son `GET /api/access/tree`, `POST /api/access/roles`, `POST /api/access/roles/{id}`, `DELETE /api/access/roles/{id}`, y sus equivalentes de usuarios. Los agentes se crean con `POST /api/agents`; los agentes creados pueden eliminarse con `DELETE /api/agents/{id}`. Los seis agentes base y el super-admin estÃ¡n protegidos contra borrado.

### Integrar un ejecutor real

Cuando exista un runtime, debe:

1. Llamar a `/api/dispatch` al aceptar una misión.
2. Enviar a `/api/activity` cada hito relevante con `agent_id`, `kind`, `message`, `input_tokens`, `output_tokens` y `reasoning_tokens` si el proveedor lo expone.
3. No enviar ni persistir cadenas de razonamiento privadas.

Así la auditoría refleja acciones reales y no solo la animación de la interfaz.

## Convenciones de desarrollo

- Conserva la estética pixel art: petróleo oscuro, crema, lima, cian y bordes pixelados.
- Reutiliza componentes JS: las tarjetas laterales nacen en `createAgentWatchCard`, los slimes de sala en `createSlimeUnit`.
- Los estilos incrementales van en `frontend/src/room-upgrades.css`; los cimientos del layout están en `styles.css`.
- Añade una migración compatible dentro de `create_audit_schema()` al crear una tabla o columna SQLite.
- Registra toda mutación de operador en `activity_events`.
- Actualiza este documento y `docs/CHANGELOG.md` con cada capacidad material.

## Publicación

1. Ejecutar `node frontend/build.mjs`.
2. Validar `node --check frontend/src/app.js` y `python -m py_compile backend/app/main.py`.
3. Publicar `dist/` en el Site privado existente. `app-version.json` hace que la pestaña publicada se recargue automáticamente al detectar una versión nueva.

La URL publicada no cambia entre versiones.
