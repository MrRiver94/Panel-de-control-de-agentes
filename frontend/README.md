# Frontend — AgentOps Monitor

Panel estático de monitorización. El código fuente vive en `src/` y `build.mjs` genera el directorio `../dist/`, que es el artefacto publicado por Sites.

El panel consulta por defecto `http://127.0.0.1:8000`. Se puede cambiar desde la interfaz. Si la API no está disponible, muestra datos de demostración sin persistencia.
