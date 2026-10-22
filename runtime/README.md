# Runtime de agentes (siguiente fase)

El panel publicado es una simulación de interfaz: conserva su estado en el navegador y no invoca un modelo todavía.

Para convertir las misiones en ejecuciones reales, este repositorio adopta como referencia el [OpenAI Agents SDK](https://github.com/openai/openai-agents-python). Es un proyecto público bajo licencia MIT y aporta agentes, herramientas, handoffs, guardrails y trazabilidad, justo las piezas que necesita este roster.

Cuando se habilite un entorno de ejecución y una clave de API segura, instala las dependencias de `requirements.txt`, configura `OPENAI_API_KEY` fuera del repositorio y ejecuta `agent_roster.py`.
