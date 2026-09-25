# SPDX-License-Identifier: Apache-2.0
"""Local decisions: pick one of a few options, with probabilities, in one model step.

The options are labelled A, B, C…; the local model (llama.cpp behind ``sos models serve``)
writes a single token and the server's ``logprobs`` give each letter's probability. No text is
generated, nothing leaves the machine. The fast path uses it to understand a system command
phrased in a way its patterns did not foresee (the idea of TypeSafe's Jev and of UpsiL's
``-> choice``). Every failure (no server, no logprobs, a model that starts to reason instead of
answering with a letter) returns None, and the request simply goes to the model as before.
"""

from __future__ import annotations

import json
import logging
import math
import string
from dataclasses import dataclass
from typing import Any

from .providers.http import post_json

log = logging.getLogger(__name__)

LETTERS = string.ascii_uppercase
MIN_MASS = 0.5     # at least half of the first token's probability on the option letters
SYSTEM = ("You map the user's request to one of the options. Reply with the letter of exactly one option "
          "and nothing else.")


@dataclass
class Picked:
    index: int
    p: float
    probs: list[float]


def build_messages(text: str, options: list[str]) -> list[dict[str, str]]:
    """The options come first: they are the same every time, so llama.cpp's prompt cache keeps them
    and only the request itself is read again (seconds saved on a machine without a GPU)."""
    lines = ["Options:"]
    lines += [f"{LETTERS[i]}. {opt}" for i, opt in enumerate(options)]
    lines += ["", f"Request: {text}", "", "Answer with one letter: " + ", ".join(LETTERS[:len(options)]) + "."]
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


def _letter(token: str, count: int) -> int | None:
    t = token.strip().strip(".):*").strip().upper()
    if len(t) == 1 and t in LETTERS[:count]:
        return LETTERS.index(t)
    return None


def letter_probabilities(data: Any, count: int) -> list[float] | None:
    """Probabilities of the option letters, or None when the reply is not a usable decision."""
    try:
        first = data["choices"][0]["logprobs"]["content"][0]
        tops = first.get("top_logprobs") or [first]
    except (KeyError, IndexError, TypeError):
        return None
    mass = [0.0] * count
    for item in tops:
        if not isinstance(item, dict):
            continue
        idx = _letter(str(item.get("token") or ""), count)
        try:
            lp = float(item.get("logprob"))
        except (TypeError, ValueError):
            continue
        if idx is not None:
            mass[idx] += math.exp(lp)
    total = sum(mass)
    if total < MIN_MASS:
        return None
    return [m / total for m in mass]


def choose(provider: Any, model: str, text: str, options: list[str], timeout: float = 6.0) -> Picked | None:
    """Ask the (local, OpenAI-compatible) *provider* to pick one of *options* for *text*."""
    if not 2 <= len(options) <= len(LETTERS):
        return None
    payload = {"model": model, "messages": build_messages(text, options), "stream": False, "max_tokens": 1,
               "temperature": 0, "logprobs": True, "top_logprobs": 20,
               # llama.cpp (--jinja) and vLLM: no <think> block before the one-letter answer
               "chat_template_kwargs": {"enable_thinking": False}}
    headers = provider._headers() if hasattr(provider, "_headers") else {}
    try:
        status, data = post_json(provider.cfg.base_url + "/chat/completions", payload, headers, timeout=timeout,
                                 use_proxy=not provider.cfg.local, provider=provider.name)
        if status == 400:           # a server that does not know chat_template_kwargs
            payload.pop("chat_template_kwargs")
            status, data = post_json(provider.cfg.base_url + "/chat/completions", payload, headers,
                                     timeout=timeout, use_proxy=not provider.cfg.local, provider=provider.name)
    except Exception as exc:  # a decision must never break a turn
        log.debug("decision request failed: %s", exc)
        return None
    if status != 200:
        log.debug("decision request: HTTP %s %s", status, json.dumps(data)[:200] if data is not None else "")
        return None
    probs = letter_probabilities(data, len(options))
    if probs is None:
        return None
    best = max(range(len(options)), key=lambda i: probs[i])
    return Picked(best, probs[best], probs)
