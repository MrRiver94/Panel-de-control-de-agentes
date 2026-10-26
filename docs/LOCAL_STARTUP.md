# Arranque local con un comando

Desde la raíz del repositorio:

```powershell
npm start
```

Se compila `dist`, se inicia la API en `127.0.0.1:8000`, se inicia el front en `127.0.0.1:4173` y se abre el navegador. La terminal permanece abierta. `Ctrl+C` cierra únicamente los servicios iniciados desde ella. Si inició una API con una misión activa, solicita su cancelación antes de cerrar.

Los servicios de SlimeOps ya abiertos se reutilizan. Un servicio desconocido o una versión antigua de la API ocupando esos puertos provoca un error explicativo; el lanzador no lo detiene. En ese caso, cierra la instancia antigua desde su terminal y vuelve a arrancar.

## Primera instalación

Se necesita Node 20 o posterior y el entorno virtual del backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..
npm start
```

El arranque no necesita instalar dependencias JavaScript: build y servidor usan módulos de Node. Para dar formato al frontend, instala sus dependencias de desarrollo con `npm install --prefix frontend`.

Codex CLI debe estar instalado y autenticado con `codex login` para ejecutar misiones. El panel puede arrancar sin esa sesión; mostrará su disponibilidad. Véase `CODEX_EXECUTION.md`.

## Comandos independientes

- Frontend: `cd frontend` y `npm start`.
- API: `cd backend` y `.\start.ps1`.
- Todas las pruebas: `npm test` desde la raíz.
- Solo backend: desde `backend`, `.\.venv\Scripts\python.exe -m unittest discover -s tests`.
- Solo frontend: desde `frontend`, `npm test`.
- Compilar: desde `frontend`, `npm run build`.

Para una ejecución sin abrir navegador, establece `SLIMEOPS_NO_BROWSER=1`. El lanzador no publica el panel ni lo expone fuera de localhost.
