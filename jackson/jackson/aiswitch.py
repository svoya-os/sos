# SPDX-License-Identifier: Apache-2.0
"""The AI switch (design/WORKFLOWS.md §8), owned by `sos ai off|on`.

AI is off when ``/etc/svoya/ai.off`` (every user) or ``~/.config/svoya/ai.off`` (this user) exists,
or ``[ai] enabled = false`` is set in ``~/.config/svoya/svoya.toml``. While it is off Jackson answers
only deterministic fast-path commands and explains how to turn AI back on (`sos ai on`).
"""

from __future__ import annotations

import tomllib

from .paths import Paths


def off_reason(paths: Paths) -> str | None:
    """"system" | "user" | "config" — or None when AI is on. Cheap: two stats and a small TOML read."""
    system, user = paths.ai_off_markers
    if system.exists():
        return "system"
    if user.exists():
        return "user"
    try:
        with open(paths.svoya_toml, "rb") as fh:
            data = tomllib.load(fh)
        if (data.get("ai") or {}).get("enabled") is False:
            return "config"
    except (OSError, tomllib.TOMLDecodeError):
        pass
    return None


def state(paths: Paths) -> dict:
    reason = off_reason(paths)
    return {"enabled": reason is None, "off": reason}
