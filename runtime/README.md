# Runtime de agentes (siguiente fase)

MUSE lee su contrato de `agents/muse.md` y las correcciones documentadas de `agents/muse-lessons.md` al preparar cada ejecución. Esta memoria es editable y versionada; no entrena el modelo. El panel solo asigna y registra misiones, y no inicia este runtime automáticamente.

El panel publicado es una simulación de interfaz: conserva su estado en el navegador y no invoca un modelo todavía.

Para convertir las misiones en ejecuciones reales, este repositorio adopta como referencia el [OpenAI Agents SDK](https://github.com/openai/openai-agents-python). Es un proyecto público bajo licencia MIT y aporta agentes, herramientas, handoffs, guardrails y trazabilidad, justo las piezas que necesita este roster.

Cuando se habilite un entorno de ejecución y una clave de API segura, instala las dependencias de `requirements.txt`, configura `OPENAI_API_KEY` fuera del repositorio y ejecuta `agent_roster.py`.
