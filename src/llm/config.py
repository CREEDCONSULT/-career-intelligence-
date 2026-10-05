"""LLM layer configuration, resolved from environment.

Provider-agnostic: ``LLM_PROVIDER`` plus per-tier model overrides select which
model LiteLLM routes to. Tiers: ``batch`` (high-volume, cheap), ``interactive``
(Q&A/chat), ``hard`` (difficult narration).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULTS = {
    "anthropic": {
        "batch": "anthropic/claude-haiku-4-5-20251001",
        "interactive": "anthropic/claude-sonnet-5",
        "hard": "anthropic/claude-opus-4-8",
    },
    "openai": {
        "batch": "openai/gpt-4o-mini",
        "interactive": "openai/gpt-4o",
        "hard": "openai/gpt-4o",
    },
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    models: dict
    token_budget: int

    @classmethod
    def from_env(cls) -> "LLMConfig":
        provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
        base = dict(_DEFAULTS.get(provider, _DEFAULTS["anthropic"]))
        base["batch"] = os.getenv("LLM_MODEL_BATCH", base["batch"])
        base["interactive"] = os.getenv("LLM_MODEL_INTERACTIVE", base["interactive"])
        base["hard"] = os.getenv("LLM_MODEL_HARD", base["hard"])
        budget = int(os.getenv("LLM_TOKEN_BUDGET", "2000000"))
        return cls(provider=provider, models=base, token_budget=budget)

    def model_for(self, tier: str) -> str:
        return self.models.get(tier, self.models["interactive"])
