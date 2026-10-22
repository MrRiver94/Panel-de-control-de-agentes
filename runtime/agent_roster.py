"""Punto de partida para ejecutar el roster con OpenAI Agents SDK.

No guarda claves ni se publica como parte del panel estático.
"""
from agents import Agent, Runner

scout = Agent(
    name="SCOUT",
    instructions="Investiga el objetivo, separa hechos de hipótesis y cita las fuentes usadas.",
)
forge = Agent(
    name="FORGE",
    instructions="Convierte el objetivo y la investigación disponible en entregables concretos y verificables.",
)
sentinel = Agent(
    name="SENTINEL",
    instructions="Revisa el resultado contra el objetivo; comunica riesgos, huecos y correcciones.",
)
nexus = Agent(
    name="NEXUS",
    instructions=(
        "Eres el orquestador. Convierte el objetivo en un plan breve. "
        "Delega investigación a SCOUT, creación a FORGE y revisión a SENTINEL cuando aporte valor."
    ),
    handoffs=[scout, forge, sentinel],
)


def run_mission(objective: str) -> str:
    """Ejecuta una misión. Requiere OPENAI_API_KEY configurada en el entorno."""
    return Runner.run_sync(nexus, objective).final_output


if __name__ == "__main__":
    objective = input("Misión: ").strip()
    if objective:
        print(run_mission(objective))
