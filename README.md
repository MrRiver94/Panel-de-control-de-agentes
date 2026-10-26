# AGENT ROSTER / SlimeOps

Panel visual para controlar un roster de agentes reutilizables. La sala de slimes es la pantalla principal; las tareas de mayor detalle se abren en ventanas popup para no perder el contexto operativo.

## Arranque local

Desde la raíz del repositorio:

```powershell
npm start
```

Arranca API y frontend y abre el navegador. Reutiliza los servicios identificados de SlimeOps que ya estén abiertos. `Ctrl+C` cierra solo los procesos que haya iniciado. [Instalación y comandos](docs/LOCAL_STARTUP.md). Para ejecutar todas las pruebas desde la raíz: `npm test`.

### Arranque independiente

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

En **Control del agente** puedes guardar proveedor, modelo, presupuesto orientativo de tokens y esfuerzo. El backend conserva estos parámetros en SQLite. Las misiones reales utilizan **Codex local**, su sesión iniciada y el modelo elegido; el proveedor Anthropic queda disponible como configuración, sin ejecución conectada. Los modelos sugeridos no implican acceso a la cuenta.

## Misiones reales

En **MISIONES REALES · CODEX**, selecciona la carpeta Git del proyecto y sus permisos. Envía la orden desde **NUEVA MISIÓN** en la sala. Los agentes se ejecutan por turnos mediante Codex CLI; el historial muestra sesiones, resultados y consumo medido. Puedes cancelar desde el mismo panel. Consulta [la guía de ejecución](docs/CODEX_EXECUTION.md) para configuración, límites y recuperación.

El modo eficiente activa solo los especialistas necesarios; puedes añadir DIRECTOR y NEXUS con planificación guiada. El panel permite cargar el diff guardado de cada misión y el informe de SENTINEL. Los reintentos son manuales y conservan el intento anterior.

Para trabajar directamente desde VS Code, se monitorizan las sesiones externas del proyecto seleccionado y se representan con el slime vinculado. Consulta [el monitor de VS Code](docs/VS_CODE_MONITOR.md).

**Salud operativa** muestra ocupación real de agentes de 0 a 100 %. Los tokens son una cifra separada; un presupuesto orientativo no se presenta como saldo o capacidad de la cuenta.

Para sustituir el catálogo sugerido por los modelos de tu entorno, define `AGENT_MODEL_CATALOG_JSON` antes de arrancar la API. Ejemplo en PowerShell:

```powershell
$env:AGENT_MODEL_CATALOG_JSON = '{"codex":["modelo-codex-configurado"],"anthropic":["modelo-claude-configurado"]}'
```

El selector lee ese catálogo desde `GET /api/models`. Un modelo ya asignado a un agente también aparece aunque no figure en el catálogo actual.

## Estructura

| Ruta | Responsabilidad |
| --- | --- |
| `frontend/src/` | Entrada de la interfaz, módulos JavaScript por función y estilos ordenados. |
| `frontend/src/assets/` | Fondos y sprites pixel art usados por la interfaz. |
| `frontend/build.mjs` | Genera `dist/`, el artefacto desplegable. |
| `backend/app/main.py` | Composición de FastAPI: inicio, CORS y registro de routers. |
| `backend/app/routes/` | Rutas HTTP de panel, agentes, accesos, Codex y misiones. |
| `backend/app/repository.py` | Esquema SQLite, persistencia de perfiles y auditoría. |
| `data/agent_activity.sqlite3` | Base local persistente; se crea automáticamente y no se versiona. |
| `agents/` | Especificaciones funcionales de los agentes. |
| `backend/app/execution.py` | Ejecución real mediante Codex CLI y ciclo de vida de misiones. |
| `runtime/` | Referencia anterior del Agents SDK; no interviene en las misiones del panel. |
| `docs/` | Guía técnica y registro de cambios del proyecto. |

Consulta [la guía técnica](docs/TECHNICAL_GUIDE.md) antes de extender el sistema y actualiza [el registro de cambios](docs/CHANGELOG.md) al introducir comportamiento, rutas o datos nuevos.

El [mapa del código](docs/CODE_STRUCTURE.md) explica dónde modificar cada función y cómo ejecutar las comprobaciones.

La [revisión por etapas](docs/IMPLEMENTATION_REVIEW.md) registra lo implementado y comprobado. El [plan de pruebas manuales](docs/MANUAL_TEST_PLAN.md) recoge los escenarios pendientes de validar con la aplicación.

## Principios

- La pantalla principal comunica estado y actividad en directo.
- Las configuraciones detalladas viven en popups, sin abandonar la sala.
- La auditoría registra metadatos operativos y uso de tokens, nunca pensamiento interno.
- Cada cambio visual se compila y se publica sobre la misma URL privada.

## Control de acceso provisional

SQLite guarda tambiÃ©n el Ã¡rbol de roles, usuarios locales y el registro persistente de agentes. La semilla es `SUPER-ADMIN` (todos los permisos) y `OPERADOR DE MISIONES` (solo ver panel y enviar misiones).

Desde el popup `ACCESO`, el Super Admin puede crear, editar y borrar roles y usuarios no protegidos, ademÃ¡s de crear agentes. La API comprueba cada permiso usando el operador local activo.

Este control es local y provisional, no un sistema de autenticaciÃ³n. Antes de exponer la API fuera del equipo, debe sustituirse por inicio de sesiÃ³n real y sesiones emitidas por el servidor.
