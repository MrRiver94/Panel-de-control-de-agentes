# Misiones reales con Codex local

## Uso desde el panel

1. Arranca la API con `.\start.ps1` desde `backend` y el front con `npm run start` desde `frontend`.
2. En **MISIONES REALES · CODEX**, comprueba que aparece «Codex conectado».
3. Elige la ruta absoluta de un proyecto Git. Por defecto se utiliza este repositorio.
4. Selecciona **Solo lectura** para análisis y propuestas, o **Permitir cambios en el proyecto** para implementar.
5. Escribe la orden en **NUEVA MISIÓN**, dentro de la sala, y pulsa **EJECUTAR**.
6. Abre la misión en el historial para consultar fases, sesiones, resultados y consumo. **CANCELAR MISIÓN** detiene la ejecución; conserva los cambios ya realizados.

Cada envío crea una misión independiente. Se ejecuta una sola misión a la vez.

## Motor y credenciales

El backend inicia `codex exec --json` y consume eventos JSONL. Reutiliza el inicio de sesión de Codex CLI; no necesita una clave nueva en el panel. Si falta autenticación, ejecuta `codex login` en una terminal y pulsa **RECONECTAR**.

La API busca `codex` en PATH y, en Windows, el ejecutable de la extensión de VS Code. Para otra instalación, define `AGENT_CODEX_BIN` con la ruta absoluta del ejecutable nativo antes de arrancar la API. Las credenciales se quedan en Codex; la API no las lee ni las devuelve al navegador.

## Turnos de los agentes

- DIRECTOR define alcance; NEXUS prepara el plan.
- El enrutamiento por palabras elige SCOUT, MUSE, FORGE y SENTINEL. Es determinista, no una decisión autónoma del modelo.
- Se reconocen palabras completas o sus raíces; `ui` y `ux` no se buscan dentro de otras palabras. Con permiso de escritura siempre se incluyen FORGE y SENTINEL, aunque la orden tenga una formulación distinta.
- Los turnos son secuenciales para evitar ediciones simultáneas del proyecto. Cada fase tiene su propia sesión Codex y recibe un extracto de los resultados anteriores.
- FORGE puede escribir cuando se selecciona `workspace-write`. Los demás roles utilizan `read-only`.
- Las instrucciones proceden de `agents/`; MUSE incluye también `muse-lessons.md`.
- Modelo y esfuerzo se copian de los controles al crear la misión. Modelo vacío utiliza la configuración de Codex local. El runtime actual admite el proveedor Codex.

Los eventos de comandos, edición, búsqueda, planificación y respuesta seleccionan las animaciones de trabajo. El descanso y los recorridos son una representación visual; una fase corta puede terminar antes de que el slime llegue a su puesto. La simulación visual sigue siendo una opción explícita y etiquetada.

## Datos medidos

Los tokens se actualizan al llegar `turn.completed`; no se estiman durante la ejecución. Entrada cacheada y razonamiento forman parte de entrada/salida: no se suman dos veces. Si Codex no proporciona consumo de un turno fallido o interrumpido, aparece como no disponible.

El presupuesto es una referencia por fase, no un límite duro ni un saldo de la cuenta. La CLI no garantiza detenerse exactamente en esa cantidad. La gráfica utiliza eventos `codex_usage`, separados de las antiguas muestras simuladas. La auditoría anterior se conserva.

## Ciclo de vida y límites

- SQLite guarda estados, resultados por fase y consumo. Recargar el navegador no detiene el trabajo.
- Se comparan las huellas de los archivos Git antes y después de FORGE, incluyendo cambios previos y archivos no ignorados. Un texto final no prueba una modificación: las misiones de escritura sin diferencias se muestran como **SIN CAMBIOS**. La lista de archivos refleja cambios durante la fase, sin atribuir como nuevos los que ya existían.
- **CAMBIOS GENERADOS** indica que hay diferencias en archivos; la revisión de SENTINEL y la comprobación visual determinan si satisfacen la petición. Los turnos de solo lectura se muestran como **PROPUESTA LISTA**.
- Al cerrar la API se cancelan sus procesos. En Windows, un Job Object termina el árbol si la API se cierra inesperadamente.
- Al reiniciar, las misiones inconclusas quedan interrumpidas. No se repiten automáticamente.
- Usa **un worker de Uvicorn**. Un bloqueo del sistema operativo impide dos runtimes sobre la misma base de datos.
- Tiempo máximo por fase: 1.800 segundos; configurable con `AGENT_RUN_TIMEOUT_SECONDS` (mínimo 30).
- Las aprobaciones interactivas no están habilitadas: una operación fuera del sandbox se deniega. No se utiliza acceso sin restricciones.
- Los controles solo aceptan conexiones y orígenes locales. El panel publicado no inicia procesos del ordenador. Los roles actuales son una selección de operador local, no autenticación para un servidor público.
- El panel no guarda salidas crudas de herramientas ni razonamiento privado. Las respuestas finales sí se guardan localmente.

## Código

| Archivo | Responsabilidad |
| --- | --- |
| `backend/app/execution.py` | Fases, estados, eventos y cancelación. |
| `backend/app/codex_process.py` | Ejecutable, login, proceso JSONL y tiempo máximo. |
| `backend/app/process_lifetime.py` | Árbol de procesos en Windows. |
| `backend/app/runtime_lock.py` | Una instancia del runtime por base de datos. |
| `backend/app/execution_store.py` | Historial SQLite y muestras reales. |
| `backend/app/routes/missions.py` | Estado, inicio, consulta y cancelación locales. |
| `frontend/src/js/features/executions.js` | Proyecto, permisos e historial. |

Referencia: [documentación oficial de ejecución no interactiva](https://developers.openai.com/codex/noninteractive/).
