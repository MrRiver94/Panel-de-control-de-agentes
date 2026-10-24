# Frontend — AgentOps Monitor

Panel estático de monitorización. El código fuente vive en `src/` y `build.mjs` genera el directorio `../dist/`, que es el artefacto publicado por Sites.

El panel consulta por defecto `http://127.0.0.1:8000`, definido en `src/js/config.js`. El comportamiento de demostración y las claves de almacenamiento existentes se conservan.

## Trabajar con el código

Desde `frontend`, instala las herramientas de desarrollo con `npm ci`. Los comandos son:

| Comando | Uso |
| --- | --- |
| `npm run start` | Compila, sirve el panel y abre el navegador. |
| `npm run build` | Actualiza `../dist/` con la aplicación y sus recursos usados. |
| `npm test` | Ejecuta las regresiones de cámara, recorridos, simulación y estados. |
| `npm run format` | Aplica el formato común a JS, HTML y CSS. |
| `npm run format:check` | Comprueba el formato sin editar archivos. |

`src/app.js` inicia la aplicación. `src/js/room/` contiene la sala; `features/`, los paneles y formularios; `services/`, HTTP y sincronización; `ui/`, los eventos y la composición de la pantalla. `state.js` conserva el estado compartido y `config.js` reúne los valores por defecto.

`src/styles/app.css` importa los estilos en el orden de cascada existente. Los recursos originales permanecen en `src/assets/`; el build incluye solo los referenciados por el código. No editar `dist/` directamente.

Consulta [el mapa del código](../docs/CODE_STRUCTURE.md) para localizar cada responsabilidad.
