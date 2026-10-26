# Monitor de Codex en VS Code

El panel consulta los metadatos de los rollouts locales en `$CODEX_HOME/sessions` (por defecto `~/.codex/sessions`). No ejecuta una segunda misión ni añade instrucciones al editor. El adaptador es de solo lectura y no cambia la configuración global de Codex.

## Uso

1. Arranca SlimeOps y selecciona la ruta del proyecto en **MISIONES REALES · CODEX**.
2. Trabaja normalmente con Codex en VS Code sobre ese proyecto.
3. El slime vinculado pasa a trabajar al observar un inicio explícito de turno y vuelve a descansar al observar su fin o cancelación.
4. Abre **CODEX EN VS CODE · SESIONES DEL PROYECTO** para cambiar qué slime representa cada sesión. La asociación se guarda en SQLite.

Una sesión sin rol conocido se representa por FORGE. Es una asociación visual, no una afirmación de que Codex haya creado nuestros seis especialistas. Los roles y nombres reconocidos pueden seleccionar otro slime; la asociación manual prevalece. Si varias sesiones comparten slime, se indica cuántas están activas. Una fase iniciada por el panel tiene prioridad sobre la proyección externa de ese mismo slime.

Se excluyen las sesiones propias del runtime y los procesos internos de seguridad. Se filtra por la ruta del proyecto y sus subcarpetas, normalizando mayúsculas en Windows. Cambiar el proyecto actualiza el stream y se recuerda en el navegador.

## Límites y datos

- Los archivos JSONL locales no constituyen un protocolo público estable. El lector tolera registros desconocidos, líneas incompletas y archivos grandes; un formato no reconocido no inventa estados.
- Se consulta cada dos segundos con caché por tamaño/fecha. Se conserva la cabecera aunque el historial supere la lectura acotada de la cola.
- Un inicio sin eventos recientes durante tres minutos se muestra como señal antigua; no prueba que el agente haya terminado.
- Solo se devuelve identidad operativa, proyecto, ciclo de vida y uso. No se copian prompts, mensajes de herramientas ni razonamiento privado.
- El consumo externo usa el último registro de turno disponible y no se añade a la gráfica de misiones administradas, evitando contabilizarlo dos veces.

Referencia de extensión futura: [hooks oficiales de Codex](https://learn.chatgpt.com/docs/hooks). Esta versión usa el lector local y no instala hooks.

## Comprobación

`backend/tests/test_external_monitor.py` cubre ciclo de vida, cancelación, señal antigua, cabeceras de archivos grandes, privacidad, filtro de proyecto, exclusión de sesiones propias y prioridad del ejecutor. Las pruebas usan fixtures y bases temporales.
