# Animación de escenario: contrato MUSE

El mapa base `slime-habitat-map-v3.png` permanece fijo. Alternar ilustraciones completas generadas por separado introducía diferencias de exposición y sombras. Los elementos animados usan hojas locales de cuatro columnas: SVG para ondas y destellos, y una hoja PNG para aves. Conservan la paleta y la geometría de colisión.

El navegador mantiene su ritmo de presentación mediante CSS y `requestAnimationFrame`. 60 FPS es el objetivo de renderizado, no una frecuencia medida ni una garantía. Los dibujos del escenario cambian por separado cada 150–180 ms. Las trayectorias de aves, hojas y peces son independientes del número de dibujos.

| Elemento | Cuadros / celdas | Exposición | Ciclo |
| --- | --- | --- | --- |
| Plantas del marco | Ilustración fija con centro transparente | Sin animación | Fijo |
| Ondas de agua | 4 columnas de 32 × 32 px | 150 ms cada uno | 600 ms |
| Destello de cristal | 4 columnas de 32 × 32 px | 180 ms cada uno | 720 ms |
| Petirrojo y gorrión | 4 dibujos articulados por especie | 160 ms cada uno | 640 ms |
| Golondrina | 4 dibujos articulados | 180 ms cada uno | 720 ms |

## Microcambios por cuadro

### Aves

1. Alas elevadas, plumas abiertas y cuerpo estable.
2. Alas extendidas durante la bajada.
3. Alas bajas con articulación y puntas visibles.
4. Alas de vuelta hacia arriba para cerrar el ciclo.

`forest-birds-flight-v1.png` contiene cuatro columnas de 362 px y tres especies. Se utilizan ventanas iguales de 362 × 320 px, iniciadas en Y=128, 450 y 766; los márgenes transparentes evitan que el aleteo muestre fragmentos de otra fila. Las hojas generadas no se deforman verticalmente para simular el aleteo.

El planeo mantiene el segundo dibujo; se alterna con periodos de aleteo. Tres trayectorias independientes cruzan a diferentes alturas y sentidos, con pausas fuera de pantalla de más de veinte segundos por especie. La vegetación verde superpuesta y las hojas flotantes se han retirado por petición del usuario.

El marco de madera, hiedra y flores está fuera de `RoomViewport`. Su imagen con transparencia usa nueve regiones de borde para preservar las esquinas al cambiar de tamaño; no tapa el mapa ni se mueve con el zoom.

### Agua

1. Líneas de onda en su posición base.
2. Desplazamiento horizontal de un píxel.
3. Regreso exacto a la posición base.
4. Desplazamiento horizontal de un píxel a la izquierda. Se conservan los colores y el número de píxeles de las ondas.

### Cristales

1. Núcleo fijo con rayos de dos píxeles alrededor.
2. Los rayos crecen un píxel.
3. Retorno al dibujo del cuadro 1.
4. Los rayos se acortan un píxel. La luz ambiental, el núcleo y el halo permanecen constantes durante todo el bucle.

## Mantenimiento

- `agents/muse.md` es el perfil de diseño y `agents/muse-lessons.md` conserva las correcciones del usuario.
- El runtime opcional lee ambos archivos en las instrucciones de MUSE al ejecutarse. El panel enruta y registra asignaciones; no inicia ese runtime por sí mismo.
- Añadir a la memoria solo observaciones comprobadas o preferencias expresas; identificar lo pendiente de revisión.
- No regenerar el escenario entero para simular viento: cualquier ajuste futuro a las ilustraciones debe conservar las paredes, las rutas y la iluminación entre cuadros.
