# SPDX-License-Identifier: Apache-2.0
"""Model providers behind one streaming interface (see :mod:`.base`)."""

from __future__ import annotations

from ..config import Config, ProviderConfig
from .anthropic import AnthropicProvider
from .base import (CancelToken, Cancelled, ChatRequest, End, Event, Health, Progress, Provider, ProviderError,
                   TextDelta, ToolCall, ToolSpec, Usage)
from .gemini import GeminiProvider
from .openai_compat import OpenAIProvider

KINDS: dict[str, type[Provider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}

__all__ = [
    "AnthropicProvider", "CancelToken", "Cancelled", "ChatRequest", "End", "Event", "GeminiProvider",
    "Health", "KINDS", "OpenAIProvider", "Progress", "Provider", "ProviderError", "TextDelta", "ToolCall", "ToolSpec",
    "Usage", "make_provider", "price_for", "cost_eur",
]


def make_provider(cfg: ProviderConfig, api_key: str | None = None) -> Provider:
    cls = KINDS.get(cfg.kind, OpenAIProvider)
    return cls(cfg, api_key)


def price_for(config: Config, provider: str, model: str, local: bool) -> tuple[tuple[float, float], bool]:
    """EUR per 1M tokens (input, output) and whether the price is known exactly."""
    if local:
        return (0.0, 0.0), True
    for key in (f"{provider}/{model}", model, f"{provider}/*"):
        if key in config.pricing:
            return config.pricing[key], True
    from ..config import FALLBACK_PRICE
    return (FALLBACK_PRICE[0], FALLBACK_PRICE[1]), False


def cost_eur(config: Config, provider: str, model: str, local: bool, usage: Usage) -> tuple[float, bool]:
    """Cost of *usage* in EUR and whether it is an estimate."""
    (p_in, p_out), known = price_for(config, provider, model, local)
    billable_in = usage.billable_input if usage.billable_input is not None else usage.input_tokens
    cost = (billable_in * p_in + usage.output_tokens * p_out) / 1_000_000
    return round(cost, 6), (not known) or usage.estimated
