"""Punto de partida para ejecutar el roster con OpenAI Agents SDK.

No guarda claves ni se publica como parte del panel estático.
"""
from pathlib import Path

from agents import Agent, Runner

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def muse_instructions() -> str:
    """Read the versioned design contract and reviewed lessons on each execution."""
    return "\n\n".join(
        (PROJECT_ROOT / path).read_text(encoding="utf-8")
        for path in ("agents/muse.md", "agents/muse-lessons.md")
    )

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
muse = Agent(
    name="MUSE",
    instructions=lambda context, agent: muse_instructions(),
)
nexus = Agent(
    name="NEXUS",
    instructions=(
        "Eres el orquestador. Convierte el objetivo en un plan breve. "
        "Delega investigación a SCOUT, creación a FORGE, dirección de arte a MUSE y revisión a SENTINEL cuando aporte valor."
    ),
    handoffs=[scout, forge, sentinel, muse],
)

director = Agent(
    name="DIRECTOR",
    instructions=(
        "Eres la dirección global del roster. Mantén la prioridad estratégica, "
        "asigna la misión a NEXUS y pide una síntesis ejecutiva cuando termine."
    ),
    handoffs=[nexus],
)


def run_mission(objective: str) -> str:
    """Ejecuta una misión. Requiere OPENAI_API_KEY configurada en el entorno."""
    return Runner.run_sync(director, objective).final_output


if __name__ == "__main__":
    objective = input("Misión: ").strip()
    if objective:
        print(run_mission(objective))
