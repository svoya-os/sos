# SPDX-License-Identifier: Apache-2.0
"""«Кто сделал, тот не проверяет»: a second look at a turn that changed things.

After Jackson's tool loop ends, a separate model request that did not do the work reads three
things only: what the person asked, the steps that ran with their results as the tools reported
them (not the model's own account), and the answer Jackson is about to give. It says whether the
request was done and the answer matches the results, as JSON: ``{"ok": true}`` or
``{"ok": false, "problems": ["…"]}``. Problems are added to the answer under «Проверка»; an answer
that checks out says nothing more (the ``done`` event carries ``check``).

When (``[checks] after_actions``): ``auto`` checks after two or more changes, after a change at
tier 2 or higher (outside the user's files, the system) and after a change a tool could not verify;
``always`` after any change; ``off`` never. A turn that only read and looked is never checked.
The idea is the harness rule of coding agents: the one who wrote it does not check it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .i18n import norm_lang

CHECK_TOKENS = 350
MAX_ANSWER_CHARS = 2500
MAX_ARGS_CHARS = 300


@dataclass
class Step:
    """One tool call that ran: what the tool itself reported."""

    name: str
    tier: int
    args: dict[str, Any]
    ok: bool
    verified: bool | None
    summary: str
    changed: bool


@dataclass
class Verdict:
    ok: bool
    problems: list[str] = field(default_factory=list)

    def event(self) -> dict[str, Any]:
        return {"ok": self.ok, "problems": list(self.problems)}


def needed(steps: list[Step], mode: str) -> bool:
    changes = [s for s in steps if s.changed and s.ok]
    if mode == "off" or not changes:
        return False
    if mode == "always":
        return True
    return len(changes) >= 2 or any(s.tier >= 2 for s in changes) or any(s.verified is False for s in changes)


_SYSTEM = {
    "ru": ("Ты «Проверяющий» в СОС. Эту работу делал не ты. Тебе дают просьбу пользователя, шаги, которые "
           "выполнились, с результатами от самих инструментов, и ответ, который получит пользователь. Проверь: "
           "сделано ли то, о чём просили, и не обещает ли ответ того, чего в результатах нет. Не придирайся к "
           "стилю. Ответь только JSON без пояснений: {\"ok\": true} или {\"ok\": false, \"problems\": "
           "[\"коротко, что не так\"]}. Проблемы пиши на русском."),
    "en": ("You are the Checker in SOS. You did not do this work. You get the user's request, the steps that "
           "ran with the results the tools themselves reported, and the answer the user will get. Check: was "
           "what they asked for done, and does the answer promise anything the results do not show? Do not "
           "nitpick the style. Reply with JSON only, no explanation: {\"ok\": true} or {\"ok\": false, "
           "\"problems\": [\"briefly, what is wrong\"]}."),
}


def system(lang: str) -> str:
    return _SYSTEM[norm_lang(lang)]


def message(request: str, steps: list[Step], answer: str, lang: str) -> str:
    ru = norm_lang(lang) == "ru"
    lines = [("## Просьба" if ru else "## Request"), request.strip(), "",
             ("## Шаги (результаты от инструментов)" if ru else "## Steps (results from the tools)")]
    for i, s in enumerate(steps, 1):
        args = json.dumps(s.args, ensure_ascii=False)
        if len(args) > MAX_ARGS_CHARS:
            args = args[:MAX_ARGS_CHARS] + "…"
        state = "ok" if s.ok else ("ошибка" if ru else "failed")
        if s.verified is not None:
            state += (", проверено" if s.verified else ", НЕ проверено") if ru else \
                (", verified" if s.verified else ", NOT verified")
        lines.append(f"{i}. {s.name} {args} → {state}: {s.summary}")
    text = answer.strip()
    if len(text) > MAX_ANSWER_CHARS:
        text = text[:MAX_ANSWER_CHARS] + "…"
    lines += ["", ("## Ответ пользователю" if ru else "## Answer to the user"), text]
    return "\n".join(lines)


_JSON = re.compile(r"\{.*\}", re.S)


def parse(text: str) -> Verdict | None:
    """The checker's JSON, also inside a code fence or after a stray word; None if there is none."""
    m = _JSON.search(text or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        return None
    problems = [str(p).strip() for p in data.get("problems") or [] if str(p).strip()][:5]
    if not data["ok"] and not problems:
        return None                 # «not ok» with nothing to say is no finding
    return Verdict(data["ok"] and not problems, problems)


def note(verdict: Verdict, lang: str, voice: bool = False) -> str:
    """What the person sees (or hears) after the answer when the check found something."""
    ru = norm_lang(lang) == "ru"
    if voice:
        head = "Проверка нашла проблему: " if ru else "The check found a problem: "
        return " " + head + verdict.problems[0]
    head = "**Проверка:** " if ru else "**Check:** "
    if len(verdict.problems) == 1:
        return "\n\n" + head + verdict.problems[0]
    return "\n\n" + head + "\n" + "\n".join(f"- {p}" for p in verdict.problems)
