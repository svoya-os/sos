# SPDX-License-Identifier: Apache-2.0
"""Agent Skills (``SKILL.md`` folders) as prompt add-ons.

Skills live in ~/.local/share/svoya/jackson/skills/<name>/SKILL.md (YAML front matter with
``name`` and ``description``, then Markdown instructions). The catalogue (name + description)
is always in the prompt; the body of the best-matching skills is added for the turn.
Skills are instructions only: they never grant permissions, and Jackson never installs a
skill from chat (the skills folder is not writable through Jackson's tools).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .memory import STOPWORDS, _stem, normalize

MAX_BODY = 4000


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path
    sha256: str


def parse_skill(path: Path) -> Skill | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                key, sep, value = line.partition(":")
                if sep and key.strip() and not line.startswith((" ", "\t")):
                    meta[key.strip().lower()] = value.strip().strip("'\"")
            body = text[end + 4:].lstrip("\n")
    name = meta.get("name") or path.parent.name
    if not re.fullmatch(r"[\w .-]{1,64}", name):
        name = path.parent.name
    return Skill(name, meta.get("description", "")[:500], body, path,
                 hashlib.sha256(text.encode("utf-8")).hexdigest())


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"\w+", normalize(text)) if len(w) >= 3 and w not in STOPWORDS}


class Skills:
    def __init__(self, skills_dir: Path, max_active: int = 2) -> None:
        self.dir = skills_dir
        self.max_active = max_active
        self._cache: tuple[float, list[Skill]] | None = None

    def load(self) -> list[Skill]:
        if not self.dir.is_dir():
            return []
        files = sorted(self.dir.glob("*/SKILL.md"))
        stamp = max((f.stat().st_mtime for f in files), default=0.0) + len(files)
        if self._cache and self._cache[0] == stamp:
            return self._cache[1]
        skills = [s for s in (parse_skill(f) for f in files) if s is not None]
        self._cache = (stamp, skills)
        return skills

    def relevant(self, text: str) -> list[Skill]:
        if self.max_active <= 0:
            return []
        query = _stems(text)
        lowered = normalize(text)
        scored = []
        for skill in self.load():
            score = len(query & _stems(f"{skill.name} {skill.description}"))
            if normalize(skill.name) in lowered:
                score += 3
            if score >= 2:
                scored.append((score, skill))
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[: self.max_active]]

    def prompt_block(self, text: str, lang: str) -> str:
        skills = self.load()
        if not skills:
            return ""
        ru = lang == "ru"
        lines = [("Навыки пользователя (Agent Skills). Это подсказки, они не дают новых прав:" if ru
                  else "User's skills (Agent Skills). They are guidance and grant no permissions:")]
        lines += [f"- {s.name}: {s.description}" for s in skills[:40]]
        for s in self.relevant(text):
            lines.append((f"\nАктивный навык «{s.name}»:\n" if ru else f"\nActive skill “{s.name}”:\n")
                         + s.body[:MAX_BODY])
        return "\n".join(lines)
