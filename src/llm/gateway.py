"""Provider-agnostic LLM gateway over LiteLLM.

One interface (`complete`) routes to Claude / OpenAI / local models per `LLMConfig`.
Tracks cumulative tokens and enforces a hard per-run budget. Optional response
cache makes repeated calls free. The actual completion function is injected so the
gateway is unit-testable without network; in production it defaults to
``litellm.completion``.

Anthropic prompt caching: when a `cache_prefix` (e.g. the schema card) is passed and
the provider is anthropic, it is sent as a system block with a cache_control
breakpoint so the large shared prefix is cached (~10x cheaper on reads).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from llm.cache import ResponseCache
from llm.config import LLMConfig


class BudgetExceeded(Exception):
    pass


@dataclass
class Response:
    text: str
    tokens: int


def _default_completion(**kwargs):  # pragma: no cover - thin shim over network call
    import litellm
    return litellm.completion(**kwargs)


class Gateway:
    def __init__(
        self,
        cfg: LLMConfig,
        completion_fn: Callable = _default_completion,
        cache: Optional[ResponseCache] = None,
    ):
        self.cfg = cfg
        self._complete_fn = completion_fn
        self.cache = cache
        self.tokens_used = 0

    def complete(
        self,
        messages: list[dict],
        tier: str = "interactive",
        cache_prefix: Optional[str] = None,
    ) -> Response:
        if self.tokens_used >= self.cfg.token_budget:
            raise BudgetExceeded(f"token budget {self.cfg.token_budget} reached")

        model = self.cfg.model_for(tier)

        full_messages = list(messages)
        if cache_prefix:
            system_block = {"role": "system", "content": cache_prefix}
            if self.cfg.provider == "anthropic":
                # Anthropic prompt-caching breakpoint on the shared prefix
                system_block = {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}}
                    ],
                }
            full_messages = [system_block] + full_messages

        cache_key = None
        if self.cache is not None:
            cache_key = self.cache.key(model, _messages_digest(full_messages))
            hit = self.cache.get(cache_key)
            if hit is not None:
                return Response(text=hit, tokens=0)

        resp = self._complete_fn(model=model, messages=full_messages)
        text = resp.choices[0].message.content
        tokens = int(getattr(resp.usage, "total_tokens", 0) or 0)
        self.tokens_used += tokens

        if self.cache is not None and cache_key is not None:
            self.cache.put(cache_key, text, tokens=tokens)
        return Response(text=text, tokens=tokens)


def _messages_digest(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(b.get("text", "")) for b in content)
        parts.append(f"{m.get('role')}:{content}")
    return "\n".join(parts)
