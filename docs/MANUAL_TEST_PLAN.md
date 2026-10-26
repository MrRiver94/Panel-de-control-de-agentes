# Pruebas manuales de SlimeOps

Esta lista contiene escenarios para comprobar la aplicación. No implica que todos se hayan ejecutado. Usar un repositorio de prueba para las misiones que escriben archivos.

## P0 · Flujo principal

| Prueba | Pasos | Resultado esperado |
| --- | --- | --- |
| Arranque único | Ejecutar `npm start` desde la raíz. | API y frontend disponibles; se abre el navegador. |
| Reutilización | Con ambos servicios abiertos, ejecutar `npm start` en otra terminal. | Se reutilizan; no aparecen instancias ni procesos Codex duplicados. |
| Cierre | Pulsar `Ctrl+C` en la terminal que inició los servicios. | Se cierran sus procesos. Los servicios que ya estaban abiertos se conservan. |
| Codex en VS Code | Seleccionar el proyecto y enviar una orden desde la extensión. | La sesión aparece y su slime vinculado se activa; al terminar vuelve a descansar. |
| Proyecto ajeno | Trabajar con Codex en otra carpeta Git. | No activa slimes del proyecto seleccionado. |
| Asociación | Vincular una sesión externa a SCOUT y recargar. | Se conserva la asociación; solo se representa el trabajo real observado. |
| Misión de escritura | En un repositorio de prueba, pedir un cambio pequeño con escritura habilitada. | FORGE modifica, SENTINEL revisa y se guardan archivos y diff. |
| Solo lectura | Pedir el mismo cambio en modo solo lectura. | Se produce una propuesta y no se alteran archivos del proyecto. |
| Sin cambios | Pedir una modificación ya satisfecha o que no pueda realizarse. | No se afirma que hubo implementación si no hay diferencias. |
| Revisión | Provocar un defecto verificable en un proyecto de prueba y pedir revisión. | Los hallazgos tienen severidad y ubicación; un informe inválido queda pendiente de revisión. |

## P0 · Integridad y recuperación

| Prueba | Pasos | Resultado esperado |
| --- | --- | --- |
| Doble envío | Repetir un envío tras una respuesta perdida con el mismo identificador. | Se devuelve la misma ejecución, sin otro proceso ni consumo duplicado. |
| Concurrencia | Iniciar otra misión mientras hay una activa. | Se rechaza con explicación; no se pisan las tareas. |
| Cancelación | Cancelar durante una fase larga. | Se detiene el árbol de procesos; las fases restantes se omiten y los cambios parciales se conservan. |
| Reinicio | Reiniciar la API durante una misión en un proyecto de prueba. | Queda interrumpida; no se relanza automáticamente ni se pierde su historial. |
| Reintento | Reintentar una misión fallida desde su botón. | Se crea otro intento y se conserva el anterior. |
| Desconexión | Detener la API y volverla a iniciar. | El panel indica desconexión y recupera el estado sin iniciar trabajo ficticio. |
| Credenciales/modelo | Probar con un modelo no disponible o sin login, en un entorno de prueba. | Error claro, sin presentar la misión como completada. |

## P1 · Datos y diff

- Con seis agentes: 0 activos = 0 %, 3 = 50 %, 6 = 100 %. Aumentar el consumo de tokens no altera esos porcentajes.
- Un agente con error o bloqueo no cuenta como disponible; una simulación visual no aumenta la ocupación operativa.
- Modificar un archivo antes de la misión y otro durante ella. El diff debe mostrar solo lo ocurrido durante la implementación, comparado con ese estado inicial.
- Comprobar altas, bajas, subcarpetas Git, archivos binarios y vistas truncadas.
- En fixtures sin credenciales reales, comprobar que `.env` y los patrones de secretos no se muestran en el diff. La protección es defensiva y no sustituye revisar lo que se comparte.
- Una misión antigua sin diff debe indicarlo, sin reconstruirlo con cambios posteriores.
- Entrada cacheada y razonamiento no deben sumarse dos veces al total. Un turno sin datos de uso debe mostrar que no están disponibles.
- Una sesión con inicio sin actividad reciente debe mostrar señal antigua, sin afirmar que finalizó.

## P1 · Interfaz y permisos

- Revisar anchos de 1440, 900 y 540 px: controles accesibles, sin desbordamiento horizontal y sala oculta/ajustada según el diseño actual.
- Comprobar zoom, cuatro flechas y «Ver todo»; no deben aparecer huecos fuera del mapa.
- Revisar sombrero de DIRECTOR, café, descanso y trabajo, conservando el escenario sin cambios bruscos de luz.
- Abrir resultados y diffs con texto que contenga etiquetas HTML: deben mostrarse como texto, sin ejecutarse.
- El operador limitado puede enviar misiones pero no cambiar asociaciones ni perfiles.
- Una página de origen remoto no puede iniciar, reintentar ni cancelar procesos locales.
- Verificar que el historial periódico descarga resúmenes y los resultados/diffs completos solo al solicitarlos.

## Automatización

Desde la raíz: `npm test`. Las regresiones usan procesos locales ficticios, repositorios y bases temporales; no lanzan inferencias. La comprobación real de Codex, si se hace, debe registrarse por separado con proyecto de prueba y número de turnos.
