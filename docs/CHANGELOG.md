# Registro de cambios

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
