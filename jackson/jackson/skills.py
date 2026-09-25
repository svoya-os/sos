# SPDX-License-Identifier: Apache-2.0
"""Agent Skills (``SKILL.md`` folders) as prompt add-ons.

Skills live in ~/.local/share/svoya/jackson/skills/<name>/SKILL.md (YAML front matter with
``name`` and ``description``, then Markdown instructions); packages add system skills to
/usr/share/svoya/jackson/skills (UpsiL does), and a user skill with the same name wins. An
optional ``aliases`` line (comma-separated, e.g. other spellings of the name) counts like the
name when matching. The catalogue (name + description) is always in the prompt; the body of the
best-matching skills is added for the turn. Skills are instructions only: they never grant
permissions, and Jackson never installs a skill from chat (neither folder is writable through
Jackson's tools; the fast-path «создай навык X», the user's own words, only makes an empty template). ``init_dir`` makes the user's folder on the first login (``sos session-start``
runs ``jackson skills init``), with a README and a file-manager bookmark; ``jackson skills new``
starts a skill from a template.
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


# ---------------------------------------------------------------------------
# the user's folder: created on the first login, with a README and a bookmark in the file manager

README_RU = """# Навыки Джексона

Навык — папка с файлом `SKILL.md`: короткая инструкция, которую Джексон читает, когда
разговор по теме. Навыки — подсказки, а не права: разрешений они не добавляют.

## Свой навык

    jackson skills new пицца

или руками: папка `пицца/`, в ней `SKILL.md`:

    ---
    name: пицца
    description: Как я заказываю пиццу: любимая пиццерия, что не ем.
    aliases: pizza, пиццу
    ---
    Заказываю в «Додо» на Ленина, 5, всегда без оливок. На вопрос «что заказать»
    предложи две пиццы и напиток.

- `description` — одна строка: по ней Джексон понимает, что навык нужен.
- `aliases` — другие слова и написания имени, через запятую.
- Дальше обычный Markdown, до 4000 символов.
- Свой навык с тем же `name`, что у системного, заменяет системный.

Системные навыки (от пакетов СОС и UpsiL): /usr/share/svoya/jackson/skills.
Все навыки: `jackson skills`. Формат — Agent Skills (SKILL.md), как у других ассистентов.
"""

README_EN = """# Jackson's skills

A skill is a folder with a `SKILL.md` file: a short instruction Jackson reads when the
conversation is about its topic. Skills are guidance, not permissions: they grant nothing.

## Your own skill

    jackson skills new pizza

or by hand: a folder `pizza/` with `SKILL.md` inside:

    ---
    name: pizza
    description: How I order pizza: my place, what I never eat.
    aliases: pizzas
    ---
    I order from the place on Main St 5, never with olives. When I ask "what should
    I order", suggest two pizzas and a drink.

- `description`: one line; Jackson uses it to tell when the skill is needed.
- `aliases`: other words and spellings of the name, comma-separated.
- Then plain Markdown, up to 4000 characters.
- Your skill with the same `name` as a system one replaces it.

System skills (from SOS and UpsiL packages): /usr/share/svoya/jackson/skills.
All skills: `jackson skills`. The format is Agent Skills (SKILL.md), as with other assistants.
"""

TEMPLATE_RU = """---
name: {name}
description: Одна строка: о чём навык и когда он нужен (по ней Джексон его находит).
aliases:
---
Что делать, когда разговор про «{name}». Пиши как новому коллеге: коротко, по пунктам,
с примерами. До 4000 символов.

- 
"""

TEMPLATE_EN = """---
name: {name}
description: One line: what the skill is about and when it is needed (Jackson finds it by this).
aliases:
---
What to do when the conversation is about "{name}". Write as for a new colleague: short,
in points, with examples. Up to 4000 characters.

- 
"""

BOOKMARK_LABEL = {"ru": "Навыки Джексона", "en": "Jackson's skills"}


def init_dir(skills_dir: Path, config_home: Path, lang: str = "ru") -> tuple[Path, bool]:
    """Make the user's skills folder. Only when it is created: the README and a bookmark in the
    file manager (GTK: Thunar, Nautilus), so deleting either is respected."""
    created = not skills_dir.is_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    if created:
        (skills_dir / "README.md").write_text(README_RU if lang == "ru" else README_EN, encoding="utf-8")
        bookmarks = config_home / "gtk-3.0" / "bookmarks"
        uri = skills_dir.as_uri()
        try:
            text = bookmarks.read_text(encoding="utf-8") if bookmarks.exists() else ""
            if uri not in text.split():
                bookmarks.parent.mkdir(parents=True, exist_ok=True)
                with open(bookmarks, "a", encoding="utf-8") as f:
                    f.write(("" if not text or text.endswith("\n") else "\n")
                            + f"{uri} {BOOKMARK_LABEL.get(lang, BOOKMARK_LABEL['en'])}\n")
        except OSError:
            pass
    return skills_dir, created


def slug(name: str) -> str:
    return re.sub(r"[^\w.-]+", "-", name.strip().lower()).strip("-.")[:64]


def new_skill(skills_dir: Path, config_home: Path, name: str, lang: str = "ru") -> Path:
    """A skill from the template; FileExistsError when one with this folder name exists."""
    folder = slug(name)
    if not folder or not re.fullmatch(r"[\w .-]{1,64}", name.strip()):
        raise ValueError(name)
    init_dir(skills_dir, config_home, lang)
    path = skills_dir / folder / "SKILL.md"
    if path.parent.exists():
        raise FileExistsError(path.parent)
    path.parent.mkdir(parents=True)
    path.write_text((TEMPLATE_RU if lang == "ru" else TEMPLATE_EN).format(name=name.strip()), encoding="utf-8")
    return path
