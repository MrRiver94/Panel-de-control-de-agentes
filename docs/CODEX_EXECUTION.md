# Misiones reales con Codex local

## Uso desde el panel

1. Ejecuta `npm start` desde la raíz para abrir API y frontend juntos; los comandos independientes siguen disponibles.
2. En **MISIONES REALES · CODEX**, comprueba que aparece «Codex conectado».
3. Elige la ruta absoluta de un proyecto Git. Por defecto se utiliza este repositorio.
4. Selecciona **Solo lectura** para análisis y propuestas, o **Permitir cambios en el proyecto** para implementar.
5. Escribe la orden en **NUEVA MISIÓN**, dentro de la sala, y pulsa **EJECUTAR**.
6. Abre la misión en el historial para consultar fases, sesiones, resultados y consumo. **CANCELAR MISIÓN** detiene la ejecución; conserva los cambios ya realizados.

Cada envío crea una misión independiente. Se ejecuta una sola misión a la vez.

Las misiones de escritura preparan una copia aislada con el contenido actual del repositorio, incluidos los cambios previos no confirmados y archivos no ignorados. FORGE y SENTINEL trabajan en esa copia. Al terminar, el panel comprueba contenido, HEAD e índice del original antes de aplicar el resultado. Si detecta cambios concurrentes, conserva el original y muestra una ruta de recuperación en el historial. Los diffs corresponden a la copia de la misión.

La copia tiene un Git propio de referencia; el panel no hace commits en el repositorio original ni cambia su staging. No se copian las dependencias ni credenciales ignoradas. Otros proyectos pueden necesitar preparar sus dependencias dentro de la copia para ejecutar herramientas. Si seleccionas una subcarpeta, se conserva el contexto fuente de su raíz Git, pero se publican cambios solo dentro de la carpeta seleccionada. Enlaces simbólicos, junctions y submódulos no compatibles se rechazan antes de publicar.

La aplicación de archivos comprueba conflictos antes y después y revierte sus cambios si falla, conservando la recuperación. No es una transacción atómica del sistema de archivos ante una caída del proceso o del sistema operativo. Revisa los cambios antes de usarlos.

## Motor y credenciales

El backend inicia `codex exec --json` y consume eventos JSONL. Reutiliza el inicio de sesión de Codex CLI; no necesita una clave nueva en el panel. Si falta autenticación, ejecuta `codex login` en una terminal y pulsa **RECONECTAR**.

La API busca `codex` en PATH y, en Windows, el ejecutable de la extensión de VS Code. Para otra instalación, define `AGENT_CODEX_BIN` con la ruta absoluta del ejecutable nativo antes de arrancar la API. Las credenciales se quedan en Codex; la API no las lee ni las devuelve al navegador.

## Turnos de los agentes

- En modo guiado, DIRECTOR define alcance y NEXUS prepara el plan. En modo eficiente se ejecutan solo los especialistas necesarios; es el valor predeterminado.
- El enrutamiento por palabras elige SCOUT, MUSE, FORGE y SENTINEL. Es determinista, no una decisión autónoma del modelo.
- Se reconocen palabras completas o sus raíces; `ui` y `ux` no se buscan dentro de otras palabras. Con permiso de escritura siempre se incluyen FORGE y SENTINEL, aunque la orden tenga una formulación distinta.
- Los turnos son secuenciales para evitar ediciones simultáneas del proyecto. Cada fase tiene su propia sesión Codex y recibe un extracto acotado de las tres aportaciones recientes (máximo 2.000 caracteres cada una y 6.000 en total). El objetivo y los perfiles de los agentes se mantienen completos.
- FORGE puede escribir cuando se selecciona `workspace-write`. Los demás roles utilizan `read-only`.
- Las instrucciones proceden de `agents/`; MUSE incluye también `muse-lessons.md`.
- Modelo y esfuerzo se copian de los controles al crear la misión. Modelo vacío utiliza la configuración de Codex local. El runtime actual admite el proveedor Codex.

Los eventos de comandos, edición, búsqueda, planificación y respuesta seleccionan las animaciones de trabajo. El descanso y los recorridos son una representación visual; una fase corta puede terminar antes de que el slime llegue a su puesto. La simulación visual sigue siendo una opción explícita y etiquetada.

## Datos medidos

Los tokens se actualizan al llegar `turn.completed`; no se estiman durante la ejecución. Entrada cacheada y razonamiento forman parte de entrada/salida: no se suman dos veces. Si Codex no proporciona consumo de un turno fallido o interrumpido, aparece como no disponible.

El presupuesto es una referencia por fase, no un límite duro ni un saldo de la cuenta. La CLI no garantiza detenerse exactamente en esa cantidad. La gráfica agrupa los eventos persistidos `codex_usage` por minuto de finalización del turno; funciona aunque el panel haya estado cerrado y no reconstruye consumo por segundo. Las muestras antiguas no alimentan la nueva serie. La auditoría anterior se conserva.

## Ciclo de vida y límites

- SQLite guarda estados, resultados por fase y consumo. Recargar el navegador no detiene el trabajo.
- Cada envío del formulario lleva un identificador persistente en el servidor: repetirlo recupera la misma ejecución. **REINTENTAR MISIÓN** crea un intento nuevo, sin borrar el anterior; no hay reintentos automáticos de trabajos que puedan modificar archivos.
- El historial periódico usa resúmenes y permite cargar misiones anteriores mediante un cursor estable. Resultados, revisión y diff se descargan al solicitarlos y se conservan abiertos durante los refrescos. El diff se captura durante la implementación, no se reconstruye después con el estado actual del proyecto. Los intentos antiguos pueden no tenerlo.
- Los diffs tienen límites de tamaño, omiten rutas sensibles y contenido binario, y ocultan patrones de credenciales. Es una protección defensiva, no una garantía de reconocer todo secreto posible.
- Se comparan las huellas de los archivos Git antes y después de FORGE, incluyendo cambios previos y archivos no ignorados. Un texto final no prueba una modificación: las misiones de escritura sin diferencias se muestran como **SIN CAMBIOS**. La lista de archivos refleja cambios durante la fase, sin atribuir como nuevos los que ya existían.
- **CAMBIOS GENERADOS** indica que hay diferencias en archivos; la revisión de SENTINEL y la comprobación visual determinan si satisfacen la petición. Los turnos de solo lectura se muestran como **PROPUESTA LISTA**.
- Las nuevas revisiones de SENTINEL siguen `runtime/schemas/review.json`: aprobación, cambios solicitados o falta de evidencia. Informes inválidos o contradictorios quedan pendientes de revisión. Una escritura con observaciones aparece como **CAMBIOS CON OBSERVACIONES**.
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
| `backend/app/workspace_transaction.py` | Copia aislada, detección de conflictos y aplicación recuperable. |
| `backend/app/routes/missions.py` | Estado, inicio, consulta y cancelación locales. |
| `frontend/src/js/features/executions.js` | Proyecto, permisos e historial. |

Referencia: [documentación oficial de ejecución no interactiva](https://developers.openai.com/codex/noninteractive/).
