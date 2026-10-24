# Memoria visual de MUSE

## 2026-10-23 — Criterios del usuario

- Mantener el trabajo centrado en la sala y el seguimiento visual de Codex, sin añadir chat.
- La cueva es descanso compartido; el campo representa trabajo. Las rocas son paredes.
- Se permite que los slimes se crucen y superpongan: el bloqueo mutuo producía atascos al salir todos.
- Alternar sueño con café, comida y pequeñas pausas. El café tiene un sprite integrado con el slime.
- No añadir manos ni pies artificiales a los sprites existentes.
- Evitar cambios de luz al animar el escenario. Los fondos completos generados por separado varían de color y sombreado; usar una base estable y cuadros locales con paleta y pivote fijos.
- Aplicar el contrato facilitado por el usuario: 4 cuadros preferidos, exposición de 100–200 ms, hojas de 4 columnas, movimientos pequeños y cierre del bucle.
- Cámara: mantener la proporción original del mapa. Las flechas indican hacia dónde mira la cámara; el dibujo se traslada en sentido contrario. Limitar la vista al terreno para no revelar huecos.
- Preferencia posterior del usuario: eliminar los grupos de follaje verde superpuestos y las hojas flotantes porque marean. Mantener la vegetación decorativa del marco estática.
- Aves: usar especies reconocibles y dibujos articulados de alas; evitar siluetas geométricas deformadas mediante escalado vertical. Referencias facilitadas: animales de bosque pixel art y aves pequeñas con proporciones naturales.

## Resultado de esta iteración

- Se sustituyó la alternancia de fondos completos por una base estable y hojas SVG de cuatro columnas para follaje, destellos y ondas.
- Configuración vigente: ondas, 4 × 150 ms; destello de cristal, 4 × 180 ms, con halo fijo. El follaje animado de la primera iteración se retiró a petición del usuario.
- Pendiente de valoración visual del usuario en su navegador. No implica aprobación estética ni medición de 60 FPS.
- Ajuste posterior de cámara comprobado en navegador a 1440, 900 y 540 px: proporción conservada, encuadre sin huecos y HUD fuera de la transformación. El usuario aún no ha valorado esta revisión.
- Revisión posterior de aves: petirrojo y gorrión con cuatro cuadros de 160 ms, golondrina con cuatro de 180 ms, planeo y pausas fuera de pantalla. El marco botánico estático y las proporciones se comprobaron a 1440, 900 y 540 px; la valoración estética del usuario queda pendiente.
