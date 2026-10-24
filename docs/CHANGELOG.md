# Registro de cambios

## 2026-10-23 — Organización del código sin cambios funcionales

- Dividido el frontend en módulos ES de sala, controles, sesiones, actividad, conexión y composición de vistas. Conservadas las claves y los intervalos existentes.
- Separados los estilos en bloques importados en el orden de cascada anterior y aplicado formato común al código.
- API organizada en contratos, repositorio SQLite, estado, permisos, servicios y cinco routers; se mantiene el contrato HTTP.
- Cliente HTTP compartido por las sesiones y los demás paneles; reutilizado el formateador numérico y actualizado solo el transform de cámara al explorar.
- Compilación sin borrado completo de `dist/`, con reemplazo de archivos y versión al final; se publican solo los diez recursos usados por la interfaz.
- Añadidos comandos de pruebas y formato y documentada la estructura en `CODE_STRUCTURE.md`.

## 2026-10-23 — Marco botánico y aves articuladas

- Retirados los grupos de follaje verde superpuestos y las hojas flotantes que resultaban molestos.
- Añadido un marco estático de madera, hiedra, helechos y flores alrededor de la imagen, separado de la cámara y de los agentes.
- Sustituidas las siluetas de pájaros por sprites de petirrojo, gorrión y golondrina, con cuatro dibujos de alas por especie a 160–180 ms.
- Incorporados planeo, trayectorias en ambos sentidos y pausas entre apariciones para reducir el movimiento continuo del escenario.

## 2026-10-23 — Proporciones y cámara de la sala

- El mapa se encuadra con su proporción original de 1672 × 941, independiente de la altura de las tarjetas laterales.
- Reloj, estado, cámara y formulario quedan fuera del mundo transformado, manteniendo su tamaño y visibilidad al explorar.
- Corregido el sentido de las cuatro flechas: desplazan la vista hacia su dirección.
- Zoom de 1× a 2,4× y desplazamiento limitado al área ampliada para evitar huecos fuera del mapa. «Ver todo» restablece el encuadre completo.
- Añadidas regresiones de sentido de las flechas, límites de cámara y restablecimiento del zoom.

## 2026-10-23 — Contrato de animación MUSE e iluminación estable

- Incorporadas las reglas del usuario al perfil MUSE: 2 o 4 cuadros, máximo 8 justificados, hojas de cuatro columnas y exposición de 100–200 ms.
- El runtime opcional consume el perfil y la memoria de correcciones desde archivos versionados; no implica ejecución real ni entrenamiento automático desde el panel.
- Ampliado el enrutamiento de MUSE para peticiones de iluminación, paisaje, vegetación y sprites.
- Retirada la alternancia de fondos completos que producía cambios de luz; conservado el mapa estable con hojas locales de follaje, ondas y destellos de cuatro cuadros.
- Documentadas las duraciones y microcambios en `docs/SCENERY_ANIMATION.md`.

## 2026-10-23 — Muebles e interacciones en la sala de descanso

- Añadidos un armario, un sillón, una mesa para comer y una cama a escala slime en el espacio común central.
- Los slimes recorren ocho destinos de descanso y representan acciones al llegar: curiosear, sentarse, comer y dormir.
- Ampliada la pausa en cada destino a 12–18 segundos para que las interacciones se aprecien mejor.
- Las rutas de ocio pasan por el suelo abierto y se acercan a cada mueble desde un lado despejado, evitando cruzar paredes de los despachos.
- Repartidos los muebles a ambos lados de un pasillo central y ajustadas las rutas a sus bordes libres.
- Recuperada la secuencia animada del slime con café; añadidos gestos de comida y sueño en la cama.
- Ordenadas las capas por profundidad para que los muebles tapen a los slimes cuando pasan por detrás.

## 2026-10-23 — Plano base de la sala

- Retirada temporal de la ilustración de fondo y sustituida por una cuadrícula oscura de plano.
- Marcados en rojo los límites de cinco despachos, la zona común y los huecos de las puertas.
- Conservadas las posiciones de los agentes y los muebles para construir el nuevo paisaje sobre este plano.

## 2026-10-23 — Consola y estados reactivos

- Añadida una consola desplegable que presenta con marca de tiempo los eventos recibidos de la API local.
- Incorporados los estados `thinking`, `paused` y `error` al contrato del backend y un endpoint auditado para informarlos; la sala y las tarjetas muestran sus señales visuales.
- Estos estados requieren que un ejecutor o integración los informe; el panel todavía no ejecuta modelos ni herramientas desde la interfaz.

## 2026-10-23 — Gráficas de uso

- Añadida bajo salud operativa una gráfica de tokens por minuto de los agentes con pico resaltado e historial local persistente.
- Añadida bajo capacidad Codex una gráfica de tokens diarios de los últimos siete días a partir de datos reales del App Server.
- Introducidas muestras `usage_samples` cada 15 segundos y el endpoint `/api/usage-series`; las gráficas muestran un estado vacío cuando falta historial.

## 2026-10-23 — Selector de proveedor y modelo

- Añadido al control de agentes el proveedor Codex/OpenAI o Anthropic/Claude y un selector de modelo leído desde la API.
- Persistidos proveedor y modelo por agente en SQLite, con compatibilidad para registros anteriores sin modelo asignado.
- Añadido `GET /api/models` y `AGENT_MODEL_CATALOG_JSON` para configurar el catálogo sin modificar el frontend.
- Aclarado en la interfaz que la elección prepara el runtime futuro, pero aún no ejecuta inferencias reales.

## 2026-10-23 — Animaciones integradas de descanso

- Eliminados los objetos de café superpuestos en la sala y las tarjetas: las interacciones usan únicamente el sprite completo del slime.
- Añadidas secuencias de cuatro poses para beber café, consultar el móvil y jugar con una consola portátil. Cada fotograma incluye al slime sujetando el objeto.
- La sala y las tarjetas laterales reproducen esas secuencias sin superponer accesorios independientes; se respeta la preferencia de movimiento reducido.

## 2026-10-22 — Roles, usuarios y agentes persistentes

- AÃ±adidos roles, usuarios y registro de agentes a SQLite.
- AÃ±adido el Ã¡rbol de acceso con `SUPER-ADMIN` y `OPERADOR DE MISIONES`.
- AÃ±adida comprobaciÃ³n de permisos para ver, enviar misiones, crear, modificar y eliminar.
- AÃ±adidos popups para gestionar roles/usuarios y crear agentes desde el panel.
- Protegidos el super-admin y los seis agentes base contra eliminaciÃ³n accidental.
- Documentado el carÃ¡cter local y provisional del control de acceso.

## 2026-10-22 — Personalización y auditoría

- Añadido popup de personalización de agente: identidad, estilo visual, descanso, acción por defecto y acciones habilitadas.
- Añadida persistencia de perfiles en SQLite (`agent_profiles`).
- Añadida auditoría persistente (`activity_events`) y popup de historial con desglose de tokens.
- Documentada la arquitectura, flujos, endpoints, almacenamiento local y proceso de publicación.

## 2026-10-22 — Sala en directo

- Añadidas tarjetas laterales animadas por agente, cámara con zoom y desplazamiento limitado, rutas de descanso coordinadas y refresco de despliegue automático.

## 2026-10-23 — Arranque local simplificado

- Añadido `npm run start` en `frontend/` para compilar y servir el panel en `http://127.0.0.1:4173`.
- Añadido `backend/start.ps1` para iniciar la API local con el entorno virtual del proyecto.
- Permitido al frontend local comunicarse con la API mediante CORS.

## 2026-10-23 — Monitor local de sesiones Codex

- Añadida lectura de solo metadatos desde rollouts locales, con estado aproximado y tokens acumulados por sesión.
- Añadida una lista compacta de sesiones recientes a la sala.
- No se persisten prompts, respuestas ni transcripciones; la lectura usa una caché breve y un máximo de 40 rollouts recientes.
- Si Codex App Server no responde, los porcentajes de cuota se recuperan del último evento local de límites.
- `npm run start` abre automáticamente la interfaz local en el navegador predeterminado.

## 2026-10-23 — Ajustes responsive de la sala

- Las tarjetas de agentes pasan debajo de la sala antes, evitando columnas laterales estrechas.
- En móviles, la escena decorativa se oculta en una sala compacta y se mantiene accesible el envío de misiones.

