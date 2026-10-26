# Validación de la primera aplicación local

Fecha: 26 de octubre de 2026. Alcance y uso: [LOCAL_APP.md](LOCAL_APP.md).

## Resultado comprobado

- Suite completa: 134 casos backend, 131 aprobados y 3 omitidos por plataforma o privilegios; 37 casos frontend aprobados, incluidos 10 escenarios DOM en Chromium.
- Tras ampliar el cierre del ejecutable con un stream SSE abierto: 14 casos específicos de aplicación local y diagnóstico aprobados de nuevo.
- Build, correspondencia de `dist`, formato, `pip check`, diferencias y enlaces locales de documentación comprobados sin errores.
- Ejecutable Windows x64 construido y verificado desde otra carpeta, sin Python ni Node en PATH, con `CODEX_HOME` temporal vacío. Sirve panel/API, crea sus datos fuera de la instalación, rechaza un origen remoto y cierra con un stream abierto. No ejecuta inferencias.
- ZIP de aproximadamente 23,8 MiB. Inventario de 1165 archivos, sin bases SQLite, `auth.json`, `.env` ni copias de trabajo del usuario. El checksum exacto acompaña al ZIP en `releases/SlimeOps-Windows-x64.zip.sha256`.
- Comprobación de lectura del entorno real: cuenta conectada, 22 sesiones compatibles, cinco proyectos, 18 sesiones de VS Code y cuatro subagentes. No se lanzaron tareas para realizar esta comprobación. La terminal se cubre con fixtures, no con una nueva inferencia real.
- Panel de desarrollo reiniciado en modo monitor: `monitor_only=true` y ejecución de misiones desactivada.

El primer intento de ejecutar Tcl/Tk en el sandbox falló por restricciones del
entorno. La misma comprobación fuera del sandbox aprobó; el empaquetado final
incluyó esa comprobación con el entorno de ejecución independiente.

## Pendiente para una versión estable

- Aceptación manual en otro Windows x64 sin herramientas de desarrollo: VS Code y terminal, selección de proyecto, desconexiones, segunda apertura y cierre.
- Ejecutar el workflow de GitHub sobre los cambios subidos. Se ha preparado pero no se ha ejecutado remotamente en esta entrega.
- La firma del ejecutable, un instalador y las actualizaciones automáticas no están implementados. La entrega actual es portátil y preliminar.
- Anthropic y una extensión de VS Code propia quedan para una iteración posterior.

No se presenta esta validación en el equipo de desarrollo como una prueba en otro
ordenador ni como una certificación de compatibilidad con todas las versiones de
Codex o Windows.
