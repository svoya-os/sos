# SPDX-License-Identifier: Apache-2.0
"""Agent Skills (``SKILL.md`` folders) as prompt add-ons.

Skills live in ~/.local/share/svoya/jackson/skills/<name>/SKILL.md (YAML front matter with
``name`` and ``description``, then Markdown instructions); packages add system skills to
/usr/share/svoya/jackson/skills (UpsiL does), and a user skill with the same name wins. An
optional ``aliases`` line (comma-separated, e.g. other spellings of the name) counts like the
name when matching. The catalogue (name + description) is always in the prompt; the body of the
best-matching skills is added for the turn. Skills are instructions only: they never grant
permissions, and Jackson never installs a skill from chat (neither folder is writable through
Jackson's tools).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .memory import STOPWORDS, _stem, normalize

MAX_BODY = 4000


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path
    sha256: str
    aliases: list[str] = field(default_factory=list)


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
    aliases = [a.strip() for a in meta.get("aliases", "").split(",") if 2 <= len(a.strip()) <= 64][:8]
    return Skill(name, meta.get("description", "")[:500], body, path,
                 hashlib.sha256(text.encode("utf-8")).hexdigest(), aliases)


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"\w+", normalize(text)) if len(w) >= 3 and w not in STOPWORDS}


class Skills:
    def __init__(self, skills_dir: Path, max_active: int = 2, system_dirs: Iterable[Path] = ()) -> None:
        self.dir = skills_dir
        self.system_dirs = list(system_dirs)
        self.max_active = max_active
        self._cache: tuple[tuple[float, int], list[Skill]] | None = None

    def load(self) -> list[Skill]:
        """System skills first, then the user's; a user skill replaces a system one of the same name."""
        files = [f for d in (*self.system_dirs, self.dir) if d.is_dir() for f in sorted(d.glob("*/SKILL.md"))]
        try:
            stamp = (max((f.stat().st_mtime for f in files), default=0.0), len(files))
        except OSError:
            stamp = (-1.0, len(files))
        if self._cache and self._cache[0] == stamp and stamp[0] >= 0:
            return self._cache[1]
        by_name: dict[str, Skill] = {}
        for skill in (parse_skill(f) for f in files):
            if skill is not None:
                by_name.pop(skill.name, None)   # keep the order: the later (user) skill goes last
                by_name[skill.name] = skill
        skills = list(by_name.values())
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
            if any(normalize(n) in lowered for n in (skill.name, *skill.aliases)):
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
        lines = [("Навыки (Agent Skills): системные и пользователя. Это подсказки, они не дают новых прав:" if ru
                  else "Skills (Agent Skills), system and user. They are guidance and grant no permissions:")]
        lines += [f"- {s.name}: {s.description}" for s in skills[:40]]
        for s in self.relevant(text):
            lines.append((f"\nАктивный навык «{s.name}»:\n" if ru else f"\nActive skill “{s.name}”:\n")
                         + s.body[:MAX_BODY])
        return "\n".join(lines)
