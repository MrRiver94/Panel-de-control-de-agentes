# Análisis de Claude-Code_Agent_Monitor como referencia

Fecha de revisión: 2026-10-23. Se revisó la copia local `Proyectos/Claude-Code_Agent_Monitor/Claude-Code-Agent-Monitor-master`, en particular `ARCHITECTURE.md`, `README-ES.md`, `server/lib/codex-ingest.js`, `server/lib/codex-process-overlay.js`, `scripts/codex-hook-handler.js` y las rutas de hooks. Este documento registra ideas para SlimeOps; no incorpora código de ese repositorio.

## Qué hace la referencia

Es un monitor local de sesiones, principalmente para Claude Code, que también integra Codex y Cursor. Su backend Node/Express recibe eventos de hooks, lee registros JSONL locales, mantiene sesiones, agentes, eventos y tokens en SQLite y difunde cambios por WebSocket. La interfaz es una SPA React/TypeScript con páginas separadas para panel, sesiones, analítica, actividad, ajustes y otros módulos.

Para Codex combina dos señales:

1. **Hooks nativos:** un script pequeño reenvía eventos de ciclo de vida al servidor y termina aunque el servidor no responda. El procesamiento de la transcripción queda en segundo plano.
2. **Rollouts locales:** un sincronizador busca los archivos `rollout-*.jsonl` bajo `CODEX_HOME/sessions`, conserva cursores por bytes y procesa líneas completas conforme crecen. Los hooks aceleran la actualización; el barrido de archivos recupera sesiones o eventos que no llegaron por hook.

También detecta procesos interactivos de Codex para mostrar una tarjeta provisional antes de que exista una sesión persistida. La referencia separa esa tarjeta volátil de las sesiones duraderas. El sondeo de procesos depende de la plataforma y está desactivado en Windows; la ingesta local de rollouts y hooks es otro camino independiente.

La referencia es mucho más amplia que SlimeOps: incluye lectura y reproducción de conversaciones, inicio de sesiones de Codex desde el panel, MCP, marketplace, extensión de VS Code, app de escritorio, fuentes remotas, importador y herramientas de administración. Esas capacidades no son necesarias para el objetivo actual.

## Comparación con SlimeOps

| Área | SlimeOps actual | Referencia | Aplicación a SlimeOps |
| --- | --- | --- | --- |
| Interfaz | Sala pixel art, tarjetas de agentes, popups, HTML/CSS/JS estático | React/TypeScript, varias páginas y tema profesional oscuro | Conservar la sala y su identidad. Modularizar solo cuando el crecimiento lo pida; no migrar por moda. |
| API | FastAPI en Python, SQLite y SSE | Express, SQLite y WebSocket | SSE ya cubre el panel local. No hace falta cambiar el transporte para empezar a medir sesiones. |
| Agentes | Registro local y estados; el runtime aún no ejecuta modelos. Parte de la telemetría del prototipo es simulada. | Sesiones detectadas desde hooks/transcripciones y estados por eventos | Separar claramente datos reales de simulación antes de usar métricas de agentes para tomar decisiones. |
| Codex | Consulta al App Server local para mostrar cuota, ventanas 5 h/semanal e historial diario disponible | Observa sesiones locales, rollouts, eventos y tokens por sesión | Son señales complementarias: conservar cuotas de cuenta y añadir, en una fase aparte, actividad local por sesión. |
| Persistencia | SQLite local para perfiles, agentes, auditoría y muestras | SQLite con entidades más normalizadas para sesiones, agentes, eventos y uso | Mantener SQLite; añadir solo tablas y migraciones acotadas si la vista de sesiones reales llega a implementarse. |
| Privacidad | Auditoría sin cadenas de razonamiento; runtime futuro | Puede indexar y mostrar mensajes y transcripciones completas | No copiar la vista de conversación. No guardar prompts ni respuestas para el monitor actual. |

## Ideas recomendadas

### 1. Mantener dos contadores de Codex con nombres distintos

La cuota de la cuenta (ventanas de uso y límites del plan) no equivale al consumo de una sesión local. El endpoint actual `/api/codex-usage` consulta la primera. La lectura de rollouts podría aportar tokens observados por sesión, agente o proyecto. La interfaz debe etiquetar ambas fuentes y no sumarlas como si fueran la misma métrica.

### 2. Añadir observación local de Codex en modo de solo lectura

La siguiente capacidad útil sería reconocer rollouts locales y derivar metadatos operativos acotados: ID de sesión, hora de actividad, estado deducible, modelo si el registro lo expone, herramientas usadas y deltas de tokens. Mantener el parseo limitado a esos campos; excluir cuerpos de mensajes, prompts, respuestas y razonamiento. Respetar `CODEX_HOME` si está definido y usar la ruta de usuario estándar como fallback.

El patrón de la referencia que merece reutilizarse es combinar señales: hooks para baja latencia y lectura incremental del rollout como fuente durable o recuperación. Para la primera iteración puede bastar la lectura local incremental; instalar o modificar hooks debería ser una acción explícita y separada, pues cambia la configuración del usuario de Codex.

### 3. Tratar la falta de señal como «desconocido», no como inactividad

La referencia es cuidadosa con sesiones que están silenciosas: el silencio por sí solo no prueba que un agente haya terminado. SlimeOps debería distinguir activo, esperando, terminado, error y desconocido, y aplicar tiempos de expiración conservadores. Las tarjetas provisionales de procesos no deberían inflar los totales persistidos.

### 4. Hacer la ingesta idempotente y acotada

Cada sesión necesita identidad estable; cada rollout, un cursor de bytes; cada evento, una clave de deduplicación. Leer solo líneas JSONL completas y procesar en lotes acotados evita duplicados y grandes picos de memoria. Las rutas y archivos externos se deben abrir en modo de solo lectura.

### 5. Mantener la tecnología actual por ahora

React/TypeScript y la separación por módulos de la referencia son buenas opciones para una interfaz con muchas páginas y componentes. SlimeOps tiene una sola sala especializada, una API pequeña y ya cuenta con SSE y SQLite. Una reescritura a Node/React ahora sumaría dependencias y migración sin mejorar la calidad de los datos de Codex. Se puede extraer módulos de JS o adoptar TypeScript/React más adelante si las nuevas vistas hacen difícil mantener la interfaz actual, sin rehacer backend, base de datos ni sala de una vez.

## Fuera de alcance por decisión de producto

- No añadir chat, prompt box, historial de conversaciones ni reproducción de transcripciones.
- No iniciar Codex ni enviarle instrucciones desde SlimeOps.
- No importar marketplace, MCP de control, integración de Claude, plugins de agentes, webhooks, app de escritorio o infraestructura distribuida de la referencia.
- No reemplazar los slimes ni la estética pixel art.
- No cambiar la cuota de Codex existente: complementarla con actividad por sesión si los datos locales lo permiten.

## Ruta de trabajo sugerida

1. Verificar qué formatos y rutas Codex deja disponibles en el equipo y confirmar qué campos de uso se pueden leer sin almacenar contenido de conversación.
2. Añadir al backend una ingesta local de solo lectura e idempotente que entregue sesiones y muestras agregadas.
3. Incorporar una vista compacta en la sala para sesiones y actividad real, separando con etiquetas lo real de lo simulado.
4. Conservar límites de cuenta y añadir gráficas por sesión solo cuando la fuente local proporcione datos suficientes.
5. Añadir hooks opcionales únicamente si el sondeo incremental no ofrece la latencia deseada, preservando toda configuración no gestionada por SlimeOps.

La implementación debe seguir las convenciones existentes: migraciones SQLite compatibles, endpoints FastAPI, SSE ya disponible, y actualización del registro de cambios. El contenido de conversaciones no forma parte del modelo de datos propuesto.
