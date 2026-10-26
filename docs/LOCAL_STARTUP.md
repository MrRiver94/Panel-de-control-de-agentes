# Arranque local con un comando

Desde la raíz del repositorio:

```powershell
npm start
```

Se compila `dist`, se inicia la API en `127.0.0.1:8000`, se inicia el front en `127.0.0.1:4173` y se abre el navegador. El modo predeterminado es monitor; para habilitar las misiones define `SLIMEOPS_MONITOR_ONLY=0` antes de arrancar con los servicios anteriores cerrados. La terminal permanece abierta. `Ctrl+C` cierra únicamente los servicios iniciados desde ella. Si inició una API con una misión activa, solicita su cancelación antes de cerrar.

Para usar el ejecutable sin instalar Python ni Node, consulta [la aplicación local](LOCAL_APP.md).

Los servicios de SlimeOps ya abiertos se reutilizan cuando identifican el mismo checkout. Un servicio desconocido, otra copia del proyecto o una API antigua ocupando esos puertos provoca un error explicativo; el lanzador no lo detiene. En ese caso, cierra la instancia antigua desde su terminal y vuelve a arrancar.

## Primera instalación

Se necesita Node 20 o posterior y Python 3.12 para el entorno virtual del backend. `requirements.txt` utiliza las versiones fijadas en `requirements.lock.txt`:

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
- Comprobar que `dist` coincide con la fuente: desde la raíz, `node --preserve-symlinks-main frontend/build.mjs --check`.

Las regresiones de interfaz usan Chromium headless con un perfil temporal y una API simulada. Se detectan Chrome/Edge en las rutas habituales; `SLIMEOPS_TEST_BROWSER` permite indicar otro ejecutable. Si no hay navegador local se informa la omisión; en integración continua estas comprobaciones son obligatorias.

Para una ejecución sin abrir navegador, establece `SLIMEOPS_NO_BROWSER=1`. El lanzador no publica el panel ni lo expone fuera de localhost.
