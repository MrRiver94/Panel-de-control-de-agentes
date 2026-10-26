# Revisión por etapas · 24 de octubre de 2026

## Porcentaje de salud operativa

Sustituida la proporción de consumo/presupuesto orientativo por **ocupación de agentes**. Ocupación = activos / roster; disponibilidad = agentes en espera / roster. Ambas permanecen entre 0 y 100 %. Los tokens se presentan como una cifra separada y los errores tienen prioridad visual sobre el estado de ruta.

Comprobación: 12 pruebas frontend aprobadas, incluidas las regresiones de consumo elevado, roster vacío, simulación y prioridad del error.

## 1. Sesiones externas de VS Code

Implementados lector defensivo, proyección por proyecto, exclusión de sesiones propias/internas y asociación persistente con un slime. Sin configuración global ni contenido privado en el payload del panel. Véase `VS_CODE_MONITOR.md`.

Comprobación de etapa: 14 pruebas backend y 12 frontend aprobadas. Fixtures de inicio/fin/cancelación, archivo grande, lectura parcial, antigüedad, privacidad y prioridad del runtime.

## 2. Fiabilidad y recuperación

Añadida deduplicación persistente por identificador de envío, reintento manual de intentos fallidos, reconexión del frontend, límite de espera HTTP y cierre del stream al desconectar el cliente. Se conserva el historial de cada intento. El proceso JSONL drena ambas tuberías y cierra el árbol en cancelación o tiempo máximo.

Comprobación de etapa: 25 pruebas backend aprobadas. Se usan procesos Python locales para probar ambas tuberías, salida con error, cancelación y tiempo máximo; el resto utiliza transporte simulado, SQLite y repositorios temporales. No se consumen inferencias para estas regresiones.

## 3. Diff de cambios y revisión de resultados

Guardados diffs antes/después por misión, con lectura diferida desde el panel. Se comparan con el contenido que existía antes de FORGE, incluyendo archivos que ya estaban modificados. Las vistas de binarios, enlaces, archivos sensibles y contenido grande se omiten o acotan. Se ocultan patrones de credenciales en el texto del diff.

SENTINEL devuelve un informe estructurado validado; una aprobación contradictoria o no interpretable queda pendiente de revisión. Una misión de escritura con observaciones se distingue de una misión revisada sin bloqueos.

Comprobación de etapa: 39 pruebas backend aprobadas. La prueba de subcarpetas detectó una diferencia de Git entre rutas de `status` y `ls-files`; corregida y cubierta. También se comprueban cambios previos, altas/bajas, binarios, límites de tamaño, redacción, permisos HTTP y validación de revisiones.

## 4. Selección y contexto eficientes

El modo predeterminado ejecuta solo especialistas necesarios. El modo guiado añade DIRECTOR y NEXUS. Una petición de sombrero con escritura pasa de cinco turnos a tres; una investigación sencilla puede usar solo SCOUT. Se mantienen FORGE y SENTINEL en cualquier misión de escritura.

El contexto compartido se limita a las tres aportaciones recientes, 2.000 caracteres por aportación y 6.000 en total. Se mantienen el objetivo completo y los perfiles versionados. El historial periódico descarga resúmenes; los resultados y diffs se cargan cuando se solicitan. El monitor externo comparte caché acotada y no reprocesa archivos sin cambios.

Comprobación de etapa: 46 pruebas backend y 15 frontend aprobadas. Se comprueban selección eficiente/guiada, regresión de «Quiero», inclusión del implementador, límite de contexto, reducción de payload y transporte HTTP.

## 5. Arranque conjunto

Añadidos `npm start` y `npm test` desde la raíz. El arranque compila el frontend, comprueba la identidad de los servicios existentes, inicia los que faltan y abre el navegador. No toma el control de un servicio ajeno ni cierra procesos reutilizados. `Ctrl+C` solicita cancelar las misiones del backend propio y cierra los procesos iniciados por esa terminal.

Comprobación de etapa: 19 pruebas frontend aprobadas, incluidas identidad del servidor, puerto ajeno, cancelación de arranque y cierre del proceso hijo propio. Se detectó y corrigió el rechazo de `taskkill` en el entorno restringido del editor.

La revisión final integrada y la lista de pruebas manuales se documentan al terminar.

## Comprobación integrada

- `npm start` arrancó la API real y reutilizó el frontend ya abierto. Se comprobó el cierre y posterior arranque sin cerrar el frontend reutilizado.
- Navegador en 1440, 900 y 540 px: sin excepciones JavaScript ni desbordamiento horizontal. API y Codex conectados, seis slimes y porcentajes dentro de 0–100.
- Asociación de una sesión externa a SCOUT desde el navegador: persistió al recargar y se restauró después su valor anterior.
- Una misión real de dos turnos (FORGE y SENTINEL), en un repositorio aislado, cambió `saludo.txt` de «Hola» a «Hola SlimeOps». Se guardó el diff y SENTINEL devolvió un informe estructurado aprobado. Resultados y diff se abrieron correctamente desde el navegador.
- Los primeros intentos de esa prueba se detuvieron antes de iniciar Codex porque Git rechazó el propietario del repositorio creado por el sandbox. Se recreó el repositorio con el usuario de la API, sin desactivar la protección de Git. Se añadió diagnóstico claro y una regresión que conserva ese rechazo.
- Se eliminaron también los porcentajes de tokens de las tarjetas individuales: muestran el consumo medido y la referencia orientativa por separado.
- Perfiles, roles y usuarios comparados con la copia anterior al reinicio: sin cambios. Las regresiones usan bases temporales; la misión real queda identificable por su carpeta aislada en el historial local.

Los artefactos detallados de navegador y las carpetas de comprobación están en `backend/.venv/verification/`, ignorados por Git. La lista de escenarios manuales figura en `MANUAL_TEST_PLAN.md`; no se presenta como una lista de pruebas ya ejecutadas.
