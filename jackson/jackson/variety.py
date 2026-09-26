# SPDX-License-Identifier: Apache-2.0
"""Jackson does not say the same thing twice in a row.

``fresh()`` is ``rng.choice()`` that skips what the same pool said recently (about half of the
pool). The daemon runs for the whole session, so a greeting, a quip before a result or a joke comes
back only after the others had their turn. The random source stays the caller's (seeded by the turn,
repeatable in tests).
"""

from __future__ import annotations

import random
from collections import deque
from typing import Sequence, TypeVar

X = TypeVar("X")

_RECENT: dict[str, deque] = {}


def fresh(rng: random.Random, pool: str, options: Sequence[X]) -> X:
    if len(options) < 2:
        return options[0]
    keep = max(1, len(options) // 2)
    memory = _RECENT.get(pool)
    if memory is None or memory.maxlen != keep:
        memory = _RECENT[pool] = deque(memory or (), maxlen=keep)
    choices = [o for o in options if o not in memory] or list(options)
    choice = rng.choice(choices)
    memory.append(choice)
    return choice


def forget() -> None:
    """Every pool starts afresh (tests)."""
    _RECENT.clear()
