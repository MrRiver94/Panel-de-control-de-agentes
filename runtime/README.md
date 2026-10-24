# Referencia anterior del Agents SDK

El panel ejecuta ahora misiones reales con Codex CLI a través de `backend/app/execution.py`. Esta carpeta conserva la referencia anterior del Agents SDK y no participa en ese flujo. Consulta [la guía vigente](../docs/CODEX_EXECUTION.md).

El runtime de Codex consume los perfiles de `agents/`, incluido el contrato y las correcciones documentadas de MUSE. Esta memoria es editable y versionada; no entrena el modelo.

Para convertir las misiones en ejecuciones reales, este repositorio adopta como referencia el [OpenAI Agents SDK](https://github.com/openai/openai-agents-python). Es un proyecto público bajo licencia MIT y aporta agentes, herramientas, handoffs, guardrails y trazabilidad, justo las piezas que necesita este roster.

Cuando se habilite un entorno de ejecución y una clave de API segura, instala las dependencias de `requirements.txt`, configura `OPENAI_API_KEY` fuera del repositorio y ejecuta `agent_roster.py`.
