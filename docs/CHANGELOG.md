# Registro de cambios

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
