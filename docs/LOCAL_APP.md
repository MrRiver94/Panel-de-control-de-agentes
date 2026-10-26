# SlimeOps como aplicación local

## Alcance acordado

SlimeOps es principalmente un monitor de agentes del ordenador. Detecta sesiones
locales de Codex iniciadas desde VS Code, su terminal u otra terminal. El panel
representa actividad observada; no inicia tareas para aparentar actividad. La
simulación visual sigue identificada como simulación.

Codex es el primer proveedor. Anthropic no está implementado. No se crea un
sistema de cuentas propio, servidor público ni base de datos remota. La extensión
del editor puede añadirse después como acceso al mismo monitor; no es necesaria
para utilizarlo fuera de VS Code.

## Uso en Windows

1. Extrae **todo** `SlimeOps-Windows-x64.zip` en una carpeta local.
2. Abre `SlimeOps/SlimeOps.exe` con doble clic.
3. El navegador muestra el panel en `http://127.0.0.1:47831`.
4. Selecciona un proyecto detectado o deja la selección automática. También
   puedes escribir la ruta de otra carpeta.
5. Cierra la ventana de control de SlimeOps para detener su servidor local.

El paquete incluye Python, Tcl/Tk, las bibliotecas y el panel. El usuario no
necesita instalar Python ni Node. Codex se instala por separado; para las
funciones adicionales de ejecución también se necesita Git.

El ejecutable requiere su carpeta `_internal`: no debe distribuirse o moverse
solo. Es una versión preliminar sin firma de código. No hay actualizador ni
instalador del sistema en esta primera entrega.

Una segunda apertura reutiliza la aplicación si coinciden su puerto, carpeta de
datos y modo. Si el puerto pertenece a otro servicio se informa del conflicto y
no se detiene ese proceso. Puede elegirse otro puerto con `--port 47832`.

## Detección y conexión

El diagnóstico del panel distingue carpeta ausente, historial vacío, lectura sin
permisos y sesiones encontradas. La conexión del proveedor se comprueba aparte:
un fallo de autenticación o la ausencia de CLI no borra el historial disponible.

SlimeOps busca el binario en PATH, instalaciones conocidas de VS Code/Insiders y
las ubicaciones nativas del paquete npm en Windows. `AGENT_CODEX_BIN` permite
seleccionar otro ejecutable nativo. No ejecuta un wrapper `.cmd`, `.bat` o `.ps1`.
La disponibilidad del modelo o de una suscripción no se deduce del historial.

La sesión se gestiona con Codex. SlimeOps consulta `codex login status` y no abre
`auth.json` ni copia credenciales. La [documentación oficial de autenticación](https://learn.chatgpt.com/docs/auth)
describe el inicio de sesión y el almacenamiento de credenciales del proveedor.

`CODEX_HOME` cambia la ubicación del estado local, incluidas las sesiones; se
respeta cuando está definido. Véanse las [variables oficiales de Codex](https://learn.chatgpt.com/docs/config-file/environment-variables).

La lista separa VS Code, terminal y subagentes. Las sesiones internas de seguridad
se excluyen antes del límite de 40 sesiones. La selección automática sigue el
proyecto externo más reciente que todavía exista en el disco. Una selección
manual se conserva en el navegador. Los agentes asociados a una sesión se
configuran como antes desde el listado del proyecto.

El lector JSONL es un adaptador defensivo para un formato local que puede cambiar.
Lee metadatos y contadores, no devuelve prompts, razonamiento ni argumentos de
herramientas. Una señal activa sin nuevas escrituras durante 180 segundos se
presenta como no confirmada; no se afirma que el proceso siga vivo. El historial
encontrado no equivale a una conexión actual a la cuenta.

## Modo monitor y funciones adicionales

La aplicación portátil y `npm start` arrancan en modo monitor. Oculta los controles
de misiones y el backend rechaza los nuevos envíos: no basta con mostrar otra
interfaz para habilitarlos.

Para habilitar voluntariamente las funciones existentes de ejecución:

```powershell
.\SlimeOps.exe --enable-missions
```

En desarrollo, define `$env:SLIMEOPS_MONITOR_ONLY = '0'` antes de `npm start`, con
los servicios anteriores cerrados. El backend lanzado directamente conserva su
comportamiento previo; utiliza `SLIMEOPS_MONITOR_ONLY=1` para limitarlo al monitor.

## Datos y cierre

En el ejecutable, SQLite, copias de recuperación y logs se guardan en
`%LOCALAPPDATA%\SlimeOps`. No se escriben dentro de la instalación. Los logs rotan
a 1 MB con dos copias y no incluyen respuestas de autenticación.

`--data-dir RUTA` o `SLIMEOPS_DATA_DIR` permiten elegir otra carpeta. No se migra ni
se empaqueta la base de datos del desarrollador. En una ejecución desde el código
fuente, el directorio predeterminado continúa siendo `data/` del repositorio.

El servidor solo escucha en loopback y la aplicación portátil rechaza hosts y
orígenes ajenos al ordenador. Esto no constituye aislamiento frente a otros
programas ejecutados con tu mismo usuario.

Cerrar una pestaña no detiene la aplicación. La ventana de control permite
reabrir el panel y cerrar el proceso de forma ordenada. Si se habilitaron misiones,
el cierre utiliza la cancelación del runtime existente.

## Construcción del paquete

Se compila en Windows x64 con Python 3.12 y Node 20 o posterior, desde la raíz:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-build.txt
npm run package:windows
```

El script genera `releases/SlimeOps/SlimeOps.exe`,
`releases/SlimeOps-Windows-x64.zip` y su archivo `.sha256`. Comprueba el ejecutable
desde otra carpeta y sin Python ni Node en PATH antes de crear el ZIP. `releases/` y `.build/`
se excluyen de Git. Se empaquetan únicamente el código analizado, `dist`, los
perfiles, el esquema de revisión y los avisos de licencia; no la carpeta `data`,
los proyectos ni el estado de Codex del equipo.

Los avisos se recogen en `_internal/licenses/` y las versiones del entorno de
construcción en `_internal/components.json`, indicando cuáles son herramientas de
build. El formato de carpeta y las rutas de recursos siguen la
[documentación de PyInstaller](https://www.pyinstaller.org/en/stable/runtime-information.html).
La licencia Tcl incluida como respaldo procede del [repositorio oficial de Tcl](https://github.com/tcltk/tcl/blob/core-8-6-branch/license.terms).

La comprobación de arranque no llama a Codex ni lanza inferencias:

```powershell
$checkProcess = Start-Process -FilePath '.\releases\SlimeOps\SlimeOps.exe' -ArgumentList '--smoke-test','--headless','--no-browser','--data-dir','.build/smoke-data' -PassThru -Wait -WindowStyle Hidden
$checkProcess.ExitCode
```

El código de salida debe ser 0. Comprueba el arranque, recursos del panel, creación
de datos, disponibilidad de Tcl/Tk en Windows, rechazo de un origen remoto y
cierre del servidor. No sustituye la prueba manual en otro ordenador.

El workflow manual `.github/workflows/package-windows.yml` permite generar el
mismo paquete en un runner Windows limpio, ejecutar las pruebas y descargar ZIP y
checksum como artefactos. Preparar el workflow no implica haberlo ejecutado en
GitHub; necesita que los cambios se suban al repositorio.

## Validación de distribución pendiente

El [registro de validación de esta entrega](LOCAL_APP_VALIDATION_2026-10-26.md)
separa las comprobaciones ejecutadas de la aceptación externa pendiente.

Antes de etiquetar una versión estable, probar el ZIP en otro Windows x64 sin
Python ni Node: primer arranque, proyecto automático/manual, Codex en VS Code y
terminal, ausencia de Codex, desconexión de cuenta, segunda apertura y cierre.
Anotar versión de Windows, de Codex y resultado de cada caso. Una prueba en el
equipo de desarrollo o en CI no se presenta como esta aceptación externa.
