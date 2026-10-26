# Componentes redistribuidos

SlimeOps incluye CPython, Tcl/Tk, bibliotecas Python del backend y el cargador de
PyInstaller. Sus licencias deben conservarse en la distribución. La compilación
recoge los archivos de licencia disponibles en el entorno y los deposita en
`_internal/licenses/`; las versiones del entorno de construcción y las herramientas
de build se identifican en `_internal/components.json`.

Codex, Git, Visual Studio Code y los navegadores no forman parte de este paquete.
Las credenciales y los datos personales del equipo de compilación tampoco.
