"""Friendly command surface: short verbs, Russian aliases, theme shortcuts, "did you mean …?".

``normalize(argv)`` rewrites what people type into the canonical argparse form, e.g.::

    sos fix                      → doctor --fix
    sos видеокарта               → doctor --gpu
    sos установить obsidian      → install obsidian
    sos тема ночь                → theme apply graphite
    sos theme auto               → theme apply auto
    sos акцент сирень            → theme accent сирень      (also: sos theme lilac, sos тема сирень)
    sos ии выкл                  → ai off
    sos модели                   → models list
"""
from __future__ import annotations

import difflib

# canonical commands (argparse sub-parsers)
COMMANDS = ("status", "doctor", "fix", "gpu", "install", "remove", "modules", "models", "theme", "accent", "accents",
            "ai", "new", "update", "undo", "snapshot", "run", "job", "session-start", "menu", "help", "version")

ALIASES = {
    # English short forms
    "st": "status", "doc": "doctor", "check": "doctor", "add": "install", "rm": "remove", "uninstall": "remove",
    "upgrade": "update", "rollback": "undo", "mod": "modules", "model": "models", "themes": "theme",
    "snap": "snapshot", "snapshots": "snapshot",
    # Russian
    "статус": "status", "состояние": "status",
    "доктор": "doctor", "проверить": "doctor", "проверка": "doctor",
    "починить": "fix", "исправить": "fix",
    "видеокарта": "gpu", "гп": "gpu",
    "установить": "install", "поставить": "install", "добавить": "install",
    "удалить": "remove", "убрать": "remove",
    "модули": "modules", "модели": "models", "модель": "models",
    "тема": "theme", "темы": "theme", "акцент": "accent", "акценты": "accents", "colour": "accent",
    "ии": "ai", "иии": "ai",
    "новый": "new", "проект": "new",
    "обновить": "update", "обновление": "update",
    "откатить": "undo", "отменить": "undo", "откат": "undo",
    "снимок": "snapshot", "снимки": "snapshot",
    "запустить": "run", "задача": "job",
    "меню": "menu", "помощь": "help", "справка": "help",
}

THEME_WORDS = {
    "night": "graphite", "ночь": "graphite", "ночная": "graphite", "dark": "graphite", "тёмная": "graphite",
    "темная": "graphite", "графит": "graphite",
    "day": "paper", "день": "paper", "дневная": "paper", "light": "paper", "светлая": "paper", "бумага": "paper",
    "auto": "auto", "авто": "auto", "автоматически": "auto",
    "фосфор": "phosphor", "retro": "phosphor", "ретро": "phosphor",
}
THEME_SUBCOMMANDS = ("list", "current", "apply", "accent", "accents")
THEME_SUB_RU = {"список": "list", "текущая": "current", "сейчас": "current", "применить": "apply",
                "акцент": "accent", "акценты": "accents"}
AI_SUB = {"off": "off", "выкл": "off", "выключить": "off", "выключи": "off", "стоп": "off",
          "on": "on", "вкл": "on", "включить": "on", "включи": "on",
          "status": "status", "статус": "status", "состояние": "status"}
MODELS_SUB_RU = {"список": "list", "скачать": "pull", "влезет": "fit", "подобрать": "suggest", "совет": "suggest",
                 "удалить": "rm", "дубликаты": "dedup", "представления": "views"}
MODULES_SUB_RU = {"список": "list", "инфо": "info", "добавить": "add", "установить": "add", "удалить": "remove",
                  "профили": "profiles"}


def known_words() -> list[str]:
    return sorted(set(COMMANDS) | set(ALIASES))


def suggest(word: str) -> list[str]:
    """Close matches among commands and aliases, mapped to canonical commands (unique, ordered)."""
    hits = difflib.get_close_matches(word.lower(), known_words(), n=4, cutoff=0.6)
    out: list[str] = []
    for h in hits:
        c = ALIASES.get(h, h)
        label = h if h == c else f"{h} ({c})"
        if label not in out:
            out.append(label)
    return out


def normalize(argv: list[str]) -> list[str]:
    """Rewrite friendly forms into canonical argv (leaves unknown words for did-you-mean)."""
    if not argv:
        return ["menu"]
    head, rest = argv[0], list(argv[1:])
    if head.startswith("-"):
        return argv
    cmd = ALIASES.get(head.lower(), head)
    if cmd == "help":
        return ["--help"] if not rest else [ALIASES.get(rest[0].lower(), rest[0]), "--help"]
    if cmd == "version":
        return ["--version"]
    if rest[:1] in (["-h"], ["--help"]) and cmd in COMMANDS and cmd not in ("fix", "gpu", "accent", "accents"):
        return [cmd, *rest]                             # `sos theme --help` is the group's help, not `current`'s
    if cmd == "fix":
        return ["doctor", "--fix", *rest]
    if cmd == "gpu":
        return ["doctor", "--gpu", *rest]
    if cmd == "accent":
        return ["theme", "accent", *rest]
    if cmd == "accents":
        return ["theme", "accents", *rest]
    if cmd == "ai":
        if not rest or rest[0].startswith("-"):
            return ["ai", "status", *rest]
        return ["ai", AI_SUB.get(rest[0].lower(), rest[0]), *rest[1:]]
    if cmd == "theme":
        if not rest:
            return ["theme", "current"]
        w = rest[0].lower()
        sub = THEME_SUB_RU.get(w, w)
        if sub in THEME_SUBCOMMANDS:
            if sub == "apply" and len(rest) > 1 and rest[1].lower() in THEME_WORDS:
                rest[1] = THEME_WORDS[rest[1].lower()]
            return ["theme", sub, *rest[1:]]
        if w.startswith("-"):
            return ["theme", "current", *rest]
        if w not in THEME_WORDS and w not in _theme_ids() and is_accent_word(rest[0]):
            return ["theme", "accent", *rest]           # sos theme lilac · sos тема сирень · sos theme '#7f5af0'
        return ["theme", "apply", THEME_WORDS.get(w, rest[0]), *rest[1:]]
    if cmd == "models":
        if not rest or rest[0].startswith("-"):
            return ["models", "list", *rest]
        rest[0] = MODELS_SUB_RU.get(rest[0].lower(), rest[0])
        return ["models", *rest]
    if cmd == "modules":
        if not rest or rest[0].startswith("-"):
            return ["modules", "list", *rest]
        rest[0] = MODULES_SUB_RU.get(rest[0].lower(), rest[0])
        return ["modules", *rest]
    if cmd == "undo" and rest and rest[0].lower() in ("список", "list"):
        return ["undo", "--list", *rest[1:]]
    return [cmd, *rest]


def _theme_ids() -> set[str]:
    """Base theme ids win over accent names (`sos theme phosphor` is the theme, not the accent)."""
    ids = {"graphite", "paper", "phosphor"}
    try:
        from .paths import Paths
        from .theme.apply import theme_dirs
        for d in theme_dirs(Paths()):
            if d.is_dir():
                ids.update(f.stem for f in d.glob("*.toml") if f.stem != "accents")
    except Exception:
        pass
    return ids


def is_accent_word(word: str) -> bool:
    """An accent name, color word or #hex (not a reset word, not a theme)."""
    from .theme.accents import AccentError, parse_choice
    try:
        return parse_choice(word) is not None
    except AccentError:
        return False


# ---------------------------------------------------------------- shell completion backend

def complete(words: list[str]) -> list[str]:
    """Candidates for the last word, given all words after ``sos`` (used by cli/completions/*)."""
    cur = words[-1] if words else ""
    prev = words[:-1]
    if not prev:
        return [w for w in known_words() if w.startswith(cur)]
    cmd = ALIASES.get(prev[0].lower(), prev[0])
    pool: list[str] = []
    if cmd == "accent" or (cmd == "theme" and len(prev) > 1 and prev[1].lower() in ("accent", "акцент")):
        pool = _accent_words()
    elif cmd == "theme":
        pool = list(THEME_SUBCOMMANDS) + ["night", "day", "auto", "phosphor", "graphite", "paper"]
    elif cmd == "ai":
        pool = ["off", "on", "status", "--system", "--json"]
    elif cmd == "models":
        pool = ["list", "pull", "fit", "suggest", "rm", "dedup", "views"] if len(prev) == 1 else _ladder_ids()
    elif cmd == "modules":
        pool = ["list", "info", "add", "remove", "profiles"] if len(prev) == 1 else _module_ids()
    elif cmd in ("install", "remove"):
        pool = _module_ids() + _app_names() + _ladder_ids()
    elif cmd == "new":
        pool = ["--template", "torch", "llm-finetune", "comfy-node", "agent"]
    elif cmd == "snapshot":
        pool = ["create", "list"]
    elif cmd == "job":
        pool = ["progress", "done", "start", "list"]
    elif cmd == "doctor":
        pool = ["--fix", "--gpu", "--json", "--dry-run"]
    return [w for w in pool if w.startswith(cur)]


def _accent_words() -> list[str]:
    try:
        from .paths import Paths
        from .theme.accents import load_catalog
        cat = load_catalog(Paths())
        words = list(cat.accents) + [str(a.name.get("ru", "")).lower() for a in cat.accents.values()]
        return [w for w in words if w] + ["default", "--undo", "--system"]
    except Exception:
        return []


def _module_ids() -> list[str]:
    try:
        from .modules import load_catalog
        from .paths import Paths
        cat = load_catalog(Paths().modules_dir)
        ids = list(cat)
        for m in cat.values():
            ids += list(m.get("aliases", []))
        return sorted(set(ids))
    except Exception:  # completion must never crash the shell
        return []


def _app_names() -> list[str]:
    try:
        from .install import load_apps
        return sorted(load_apps())
    except Exception:
        return []


def _ladder_ids() -> list[str]:
    try:
        from .models.suggest import load_ladder
        lad = load_ladder()
        out = []
        for mid, m in lad["models"].items():
            out.append(mid)
            out += [f"{mid}:{q['name']}" for q in m["quants"]]
        return out
    except Exception:
        return []
