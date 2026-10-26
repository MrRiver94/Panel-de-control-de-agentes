"""Catalog operations."""
from __future__ import annotations

import json
import os
import re

from . import state
from .config import DEFAULT_MODEL_CATALOG


def configured_model_catalog() -> dict[str, list[str]]:
    """Suggested models; deployments can replace them with AGENT_MODEL_CATALOG_JSON."""
    raw = os.getenv("AGENT_MODEL_CATALOG_JSON")
    if not raw:
        catalog = {provider: models.copy() for provider, models in DEFAULT_MODEL_CATALOG.items()}
    else:
        configured = json.loads(raw)
        if not isinstance(configured, dict):
            raise ValueError("AGENT_MODEL_CATALOG_JSON must be an object")
        catalog = {}
        for provider in DEFAULT_MODEL_CATALOG:
            models = configured.get(provider, [])
            if not isinstance(models, list) or any(
                not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,120}", model)
                for model in models
            ):
                raise ValueError(f"Invalid model list for {provider}")
            catalog[provider] = list(dict.fromkeys(models))
    with state.roster_lock:
        for agent in state.agents.values():
            if agent.model and agent.model not in catalog[agent.provider]:
                catalog[agent.provider].append(agent.model)
    return catalog
