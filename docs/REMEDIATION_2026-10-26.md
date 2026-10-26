# Correcciones de la revisión de arquitectura

Fecha: 26 de octubre de 2026. Este registro acompaña a la [revisión original](ARCHITECTURE_REVIEW_2026-10-26.md). Los hallazgos H01–H18 se han abordado en el código; la revisión original se conserva como diagnóstico del commit anterior.

## Cambios y evidencia

| Hallazgo | Corrección | Regresión principal |
| --- | --- | --- |
| H01 | Los datos de usuarios, roles, permisos y agentes se construyen con nodos de texto y `dataset`, sin interpolarlos como HTML. | `frontend/tests/fixtures/dom-regressions.js`: HTML/IDs como texto literal. |
| H02 | Protocolo de cuotas con plazo global, espera corta del lock y cierre del árbol, tuberías e hilo; descubrimiento compartido de Codex. | `backend/tests/test_codex_usage.py`: silencio, espera acumulada, lock ocupado, terminación ignorada, concurrencia y recuperación. |
| H03 | Configuración, perfil, registro y auditoría comparten transacción. Se publican copias en memoria tras el commit. Los eventos de uso confirman auditoría, agente y snapshot juntos y revierten el paso si falla el commit. | `test_roster_integrity.py` y `test_dashboard_consistency.py`: fallos entre escrituras, rollback y estado recuperable. |
| H04 | Locks del roster con orden manager → roster → SQLite; reserva persistente de ID y lectores coherentes. | `test_roster_integrity.py`: altas/bajas y asociación de sesión concurrentes. |
| H05 | El generador de SSE obtiene proyecciones mediante un hilo; el escaneo externo queda fuera del lock del roster. | `test_dashboard_consistency.py`: una lectura lenta no bloquea el event loop. |
| H06 | Stream mediante fetch con `X-Operator-Id` explícito; el servidor exige identidad y vuelve a comprobar permisos. El cambio de operador aborta el transporte y las respuestas pendientes. | Pruebas de stream y `live-sync.test.mjs`: cabecera, denegación y cierre por cambio de contexto. |
| H07 | Generación de contexto y revisiones de snapshot; consultas sin solapamiento y descarte de respuestas antiguas. Polling queda como respaldo de SSE. | `live-sync.test.mjs`: respuestas inversas, cambio de workspace, reinicio y cancelación. |
| H08 | Reconciliación por ID, retirada de nodos ausentes y movimiento de tarjetas entre laterales. | Regresión DOM de altas, bajas y redistribución de agentes. |
| H09 | El perfil confirmado solo cambia tras un POST correcto; un error conserva el formulario y explica que no se guardó. | Regresión DOM de guardado rechazado y posterior guardado correcto. |
| H10 | Registros de historial estables por ID; resultados y diffs no se destruyen al actualizar resúmenes. | Regresión DOM de expansión, nodos cargados y selección de texto. |
| H11 | Una actualización de acceso recompone árbol, selectores y acciones CRUD; los formularios explican los errores. | Regresión DOM de acciones de registros recién creados. |
| H12 | Artefacto regenerado; `buildId` deriva del contenido y `build.mjs --check` detecta diferencias sin escribir. | `build.test.mjs`: builds idénticos y rechazo de un artefacto alterado. |
| H13 | Colisiones de identificadores se traducen a 409 con transacciones intactas. | `test_validation.py`: nombres repetidos y slugs coincidentes. |
| H14 | Normalización anterior a constraints, acciones individuales validadas y permisos contra catálogo. Eventos `codex_` reservados al runtime. | `test_validation.py`: espacios, acciones/permisos inválidos y eventos de uso manuales rechazados. |
| H15 | Historial con cursor `(created_at, id)`, índice y botón para cargar anteriores; compatible con listado por limit/offset. | `test_dashboard_consistency.py` y DOM: nueva misión entre páginas sin perder registros. |
| H16 | FORGE y SENTINEL trabajan en una copia aislada. Publicación restringida al workspace seleccionado, con comparación del estado original, rollback y recuperación ante conflictos. | `test_workspace_transaction.py` y `test_execution.py`: dirty/staged/untracked, borrados, conflictos, fallos de publicación y cancelación. |
| H17 | Selección por proyecto antes del límite de sesiones. Índice persistente de sesiones propias con backfill versionado. | `test_dashboard_consistency.py`: sesión de proyecto detrás de más de 40 sesiones ajenas. |
| H18 | Ventanas de uso derivadas de eventos persistidos por minuto de finalización; las lecturas del panel no crean muestras. | `test_telemetry.py`: igualdad con/sin lecturas, primer turno, límites UTC y ausencia de escrituras. |

También se corrigieron los riesgos de procesos descendientes POSIX y reutilización de servicios de otro checkout. El monitor de procesos sigue activo hasta terminar la lectura; el lanzador verifica la raíz del backend y frontend. Hay pruebas específicas por plataforma y una comprobación de identidad entre copias.

La integración corrigió dos interacciones adicionales: al salir de simulación se reaplica el último snapshot aunque tenga la misma revisión, y recuperar un transporte válido actualiza la conexión sin exigir cambios de datos. Una misión sigue activa hasta terminar la publicación y puede recibir cancelación durante esa fase.

## Arquitectura y entrega

- Se mantiene FastAPI + SQLite + módulos JavaScript nativos y un worker de ejecución.
- Las mutaciones del roster tienen una unidad de confirmación y lectores sincronizados. La serie de uso no depende del navegador.
- Los snapshots HTTP/SSE tienen identidad de servidor y revisión; el frontend separa respuestas de contextos distintos y conserva sus detalles de interacción.
- Las sesiones propias disponen de una tabla indexada y una migración identificada en `schema_migrations`.
- `backend/requirements.lock.txt` fija el conjunto de versiones del entorno Python 3.12 comprobado. El lock de frontend se conserva.
- El workflow `.github/workflows/verify.yml` prepara Windows y Linux, ejecuta pruebas incluidas las de DOM, comprueba formato y verifica que `dist` corresponde a la fuente. Su ejecución remota se comprobará al subir los cambios; crear el archivo no equivale a haberlo ejecutado en GitHub.

## Escritura aislada y recuperación

La copia contiene el código fuente no ignorado de la raíz Git y tiene un commit de referencia propio. Cuando se selecciona una subcarpeta se devuelve esa ruta dentro de la copia, conservando el contexto fuente y las reglas de exclusión de sus padres. La publicación solo afecta a la carpeta seleccionada. El HEAD y el staging originales no cambian.

Las dependencias y credenciales ignoradas no se copian. Una tarea puede necesitar instalar dependencias dentro de la copia para ejecutar herramientas. El frontend de este proyecto se construye con módulos nativos de Node.

Los fallos y cancelaciones conservan los cambios parciales cuando pueden aplicarse con seguridad. Ante deriva del original o fallo de publicación, el historial muestra `recovery_workspace`; se debe revisar esa copia y compararla con el proyecto antes de recuperar sus archivos. No se aplica automáticamente una copia interrumpida tras reiniciar.

La publicación usa comprobaciones optimistas antes/después y rollback. No ofrece atomicidad del sistema de archivos ante una caída del proceso/OS o un escritor que compita durante cada reemplazo. Enlaces simbólicos, junctions, submódulos y cambios archivo↔directorio incompatibles se rechazan para evitar aplicar resultados fuera del alcance permitido. Las copias retenidas ocupan disco hasta que el usuario las revise y retire.

## Validación y límites

La comprobación integrada final terminó con 120 casos backend: 117 aprobados y 3 omitidos por plataforma o privilegios; los 34 casos frontend aprobaron, incluidos los ocho escenarios DOM en Chromium. Comando: `node --preserve-symlinks --preserve-symlinks-main scripts/test.mjs`.

Se ejecutaron procesos Python de prueba, Git en repositorios temporales, API con SQLite temporal, módulos JavaScript aislados y Chromium headless con una API simulada. No se lanzaron misiones Codex reales ni inferencias de pago. También aprobaron la construcción, `build.mjs --check`, Prettier, `pip check` y la comprobación de diferencias y enlaces de documentación. El transporte HTTP de TestClient emite una advertencia de deprecación en las versiones fijadas, sin fallos en estas comprobaciones.

Los tests de proceso POSIX se omiten en Windows; crear un symlink también puede omitirse si faltan privilegios. La regresión de junction sí se ejecuta en Windows. La comprobación DOM puede omitirse localmente si no hay Chromium; en CI es obligatoria.

Los roles siguen siendo una selección local provisional, no autenticación de red. El diseño de sesiones para varios usuarios remotos, la evolución del planificador de agentes personalizados y una separación más amplia de controladores/estado/vistas siguen siendo decisiones posteriores del informe; no se presentan como implementadas por estas correcciones.
