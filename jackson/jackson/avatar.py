# SPDX-License-Identifier: Apache-2.0
"""Jackson's look and name: ``~/.config/svoya/avatar.json`` (design/DESIGN.md §13), shared with the shell.

The file may be sparse — only what the user chose. Missing keys follow the character's defaults, so
«стань котом» gives a cat with the cat's defaults (jacket, shades) unless the user picked otherwise.
Unknown keys (written by a newer shell) are preserved on every write.

| key        | values                                                                 | default          |
|------------|------------------------------------------------------------------------|------------------|
| character  | imp · cat                                                              | imp              |
| skin       | imp: ember wine plum graphite mint · cat: blue ginger black snow siamese | ember / blue    |
| outfit     | accent · an accent id · #hex                                           | accent           |
| style      | hoodie · jacket · tee                                                  | imp hoodie, cat jacket |
| headphones | true · false                                                           | true             |
| glasses    | none · shades · round                                                  | imp none, cat shades |
| hood       | true · false (imp only)                                                | true             |
| name       | any short name                                                         | Джексон          |
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_NAME = "Джексон"
CHARACTERS = ("imp", "cat")
SKINS = {"imp": ("ember", "wine", "plum", "graphite", "mint"),
         "cat": ("blue", "ginger", "black", "snow", "siamese")}
STYLES = ("hoodie", "jacket", "tee")
GLASSES = ("none", "shades", "round")
ACCENT_IDS = ("signal", "amber", "ink", "phosphor", "ice", "lilac", "rose", "mono")
KEYS = ("character", "skin", "outfit", "style", "headphones", "glasses", "hood", "name")
DEFAULTS = {
    "imp": {"character": "imp", "skin": "ember", "outfit": "accent", "style": "hoodie", "headphones": True,
            "glasses": "none", "hood": True, "name": DEFAULT_NAME},
    "cat": {"character": "cat", "skin": "blue", "outfit": "accent", "style": "jacket", "headphones": True,
            "glasses": "shades", "hood": True, "name": DEFAULT_NAME},
}

# --- words people use (lower case, ё → е) --------------------------------------------------------
KEY_ALIASES = {
    "character": "character", "персонаж": "character", "герой": "character", "кто": "character",
    "skin": "skin", "окрас": "skin", "кожа": "skin", "скин": "skin", "шерсть": "skin", "цвет": "skin",
    "outfit": "outfit", "одежда": "outfit", "цвет одежды": "outfit", "наряд": "outfit",
    "style": "style", "стиль": "style", "фасон": "style",
    "headphones": "headphones", "наушники": "headphones", "уши": "headphones",
    "glasses": "glasses", "очки": "glasses",
    "hood": "hood", "капюшон": "hood",
    "name": "name", "имя": "name", "зовут": "name",
}
CHARACTER_ALIASES = {"imp": "imp", "черт": "imp", "чертик": "imp", "чертенок": "imp", "бес": "imp", "бесенок": "imp",
                     "devil": "imp", "cat": "cat", "кот": "cat", "котик": "cat", "кошка": "cat", "котэ": "cat",
                     "kitty": "cat"}
SKIN_ALIASES = {
    "ember": "ember", "огонь": "ember", "огненный": "ember", "огненная": "ember", "красный": "ember",
    "wine": "wine", "бордо": "wine", "бордовый": "wine", "винный": "wine",
    "plum": "plum", "слива": "plum", "сливовый": "plum", "фиолетовый": "plum",
    "graphite": "graphite", "графит": "graphite", "графитовый": "graphite",
    "mint": "mint", "мята": "mint", "мятный": "mint",
    "blue": "blue", "русский голубой": "blue", "голубой": "blue", "серый": "blue", "серо-голубой": "blue",
    "ginger": "ginger", "рыжий": "ginger", "рыжая": "ginger",
    "black": "black", "черный": "black", "черная": "black",
    "snow": "snow", "снежный": "snow", "белый": "snow", "белая": "snow",
    "siamese": "siamese", "сиамский": "siamese", "сиамская": "siamese",
}
STYLE_ALIASES = {"hoodie": "hoodie", "худи": "hoodie", "толстовка": "hoodie", "толстовку": "hoodie",
                 "jacket": "jacket", "куртка": "jacket", "куртку": "jacket", "косуха": "jacket", "косуху": "jacket",
                 "tee": "tee", "t-shirt": "tee", "tshirt": "tee", "футболка": "tee", "футболку": "tee", "майка": "tee",
                 "майку": "tee"}
GLASSES_ALIASES = {"none": "none", "no": "none", "off": "none", "нет": "none", "без": "none", "без очков": "none",
                   "shades": "shades", "sunglasses": "shades", "темные": "shades", "солнечные": "shades",
                   "солнцезащитные": "shades", "round": "round", "круглые": "round", "очки": "round",
                   "yes": "round", "да": "round", "on": "round"}
BOOL_ALIASES = {"true": True, "yes": True, "on": True, "1": True, "да": True, "вкл": True, "включить": True,
                "надеть": True, "false": False, "no": False, "off": False, "0": False, "нет": False,
                "выкл": False, "выключить": False, "снять": False, "долой": False}
OUTFIT_ALIASES = {"accent": "accent", "акцент": "accent", "как акцент": "accent", "авто": "accent",
                  "сигнал": "signal", "янтарь": "amber", "чернила": "ink", "фосфор": "phosphor", "лед": "ice",
                  "сирень": "lilac", "роза": "rose", "моно": "mono"}
NAME_RE = re.compile(r"^[\w][\w .'’-]{0,23}$", re.UNICODE)

LABELS = {
    "character": {"imp": ("Чёрт", "Imp"), "cat": ("Кот", "Cat")},
    "skin": {"ember": ("Огонь", "Ember"), "wine": ("Бордо", "Wine"), "plum": ("Слива", "Plum"),
             "graphite": ("Графит", "Graphite"), "mint": ("Мята", "Mint"), "blue": ("Русский голубой", "Russian blue"),
             "ginger": ("Рыжий", "Ginger"), "black": ("Чёрный", "Black"), "snow": ("Снежный", "Snow"),
             "siamese": ("Сиамский", "Siamese")},
    "style": {"hoodie": ("худи", "hoodie"), "jacket": ("куртка", "jacket"), "tee": ("футболка", "tee")},
    "glasses": {"none": ("без очков", "no glasses"), "shades": ("тёмные очки", "shades"),
                "round": ("круглые очки", "round glasses")},
    "outfit": {"accent": ("как акцент", "follows the accent"), "signal": ("Сигнал", "Signal"),
               "amber": ("Янтарь", "Amber"), "ink": ("Чернила", "Ink"), "phosphor": ("Фосфор", "Phosphor"),
               "ice": ("Лёд", "Ice"), "lilac": ("Сирень", "Lilac"), "rose": ("Роза", "Rose"), "mono": ("Моно", "Mono")},
}


class AvatarError(ValueError):
    def __init__(self, ru: str, en: str) -> None:
        super().__init__(en)
        self.ru, self.en = ru, en

    def text(self, lang: str) -> str:
        return self.ru if lang == "ru" else self.en


def _norm(value: Any) -> str:
    return str(value).strip().lower().replace("ё", "е").strip(" \t\"'«».,!?")


@dataclass
class Avatar:
    data: dict[str, Any]          # full, validated view (defaults filled in)
    stored: dict[str, Any]        # what the file says (sparse), including unknown keys

    @property
    def name(self) -> str:
        return str(self.data["name"])

    def display_name(self, lang: str) -> str:
        return "Jackson" if self.name == DEFAULT_NAME and lang != "ru" else self.name

    def to_event(self) -> dict[str, Any]:
        return {k: self.data[k] for k in KEYS}

    def label(self, key: str, lang: str) -> str:
        value = self.data.get(key)
        pair = LABELS.get(key, {}).get(value)
        if pair:
            return pair[0] if lang == "ru" else pair[1]
        if isinstance(value, bool):
            return ("да" if value else "нет") if lang == "ru" else ("yes" if value else "no")
        return str(value)


def resolve(stored: dict[str, Any]) -> dict[str, Any]:
    """Sparse/whatever file content → a complete, valid avatar (invalid values fall back to defaults)."""
    character = stored.get("character") if stored.get("character") in CHARACTERS else "imp"
    out = dict(DEFAULTS[character])
    skin = stored.get("skin")
    if skin in SKINS[character]:
        out["skin"] = skin
    outfit = stored.get("outfit")
    if isinstance(outfit, str) and (outfit in ("accent", *ACCENT_IDS) or re.fullmatch(r"#[0-9a-fA-F]{6}", outfit)):
        out["outfit"] = outfit.lower()
    if stored.get("style") in STYLES:
        out["style"] = stored["style"]
    if isinstance(stored.get("headphones"), bool):
        out["headphones"] = stored["headphones"]
    if stored.get("glasses") in GLASSES:
        out["glasses"] = stored["glasses"]
    if isinstance(stored.get("hood"), bool):
        out["hood"] = stored["hood"]
    name = stored.get("name")
    if isinstance(name, str) and NAME_RE.match(name.strip()):
        out["name"] = name.strip()
    return out


def read_stored(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load(path: Path) -> Avatar:
    stored = read_stored(path) or {}
    return Avatar(resolve(stored), stored)


def stamp(path: Path) -> tuple[float, int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime, st.st_size, st.st_ino)


def write(path: Path, stored: dict[str, Any]) -> None:
    """Atomic write (the shell reads the same file); 0644 — nothing secret in here."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".avatar-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(stored, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def parse_key(key: str) -> str:
    k = KEY_ALIASES.get(_norm(key))
    if k is None:
        raise AvatarError(f"Не знаю настройку «{key}». Можно: " + ", ".join(KEYS),
                          f"Unknown setting “{key}”. Use one of: " + ", ".join(KEYS))
    return k


def parse_value(key: str, value: Any, character: str) -> Any:
    """Validate/normalize one value (RU/EN aliases). Raises AvatarError with the allowed values."""
    v = _norm(value) if not isinstance(value, bool) else value
    if key == "character":
        out = CHARACTER_ALIASES.get(v) if isinstance(v, str) else None
        if out is None:
            raise AvatarError("Персонаж: чёрт или кот.", "Character: imp or cat.")
        return out
    if key == "skin":
        out = SKIN_ALIASES.get(v) if isinstance(v, str) else None
        if out is None or out not in SKINS[character]:
            names_ru = ", ".join(LABELS["skin"][s][0].lower() for s in SKINS[character])
            raise AvatarError(f"Окрас для {'кота' if character == 'cat' else 'чёрта'}: {names_ru}.",
                              f"Skins for the {character}: {', '.join(SKINS[character])}.")
        return out
    if key == "style":
        out = STYLE_ALIASES.get(v) if isinstance(v, str) else None
        if out is None:
            raise AvatarError("Стиль: худи, куртка или футболка.", "Style: hoodie, jacket or tee.")
        return out
    if key == "glasses":
        if isinstance(v, bool):
            return "round" if v else "none"
        out = GLASSES_ALIASES.get(v)
        if out is None:
            raise AvatarError("Очки: нет, круглые или тёмные.", "Glasses: none, round or shades.")
        return out
    if key in ("headphones", "hood"):
        if isinstance(v, bool):
            return v
        out = BOOL_ALIASES.get(v)
        if out is None:
            raise AvatarError("Значение: да или нет.", "Value: yes or no.")
        return out
    if key == "outfit":
        if isinstance(v, str):
            if v in OUTFIT_ALIASES:
                return OUTFIT_ALIASES[v]
            if v in ACCENT_IDS:
                return v
            m = re.fullmatch(r"#?([0-9a-f]{6})", v)
            if m:
                return "#" + m.group(1)
        raise AvatarError("Одежда: «акцент», цвет акцента (сирень, лёд…) или #rrggbb.",
                          "Outfit: accent, an accent id (lilac, ice…) or #rrggbb.")
    if key == "name":
        name = " ".join(str(value).split())
        if not NAME_RE.match(name):
            raise AvatarError("Имя — до 24 букв, цифр, пробелов или дефисов.",
                              "A name is up to 24 letters, digits, spaces or hyphens.")
        return name
    raise AvatarError(f"Не знаю настройку «{key}».", f"Unknown setting “{key}”.")


def apply_change(stored: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    """New sparse content after setting *key* (validated). Switching character drops a skin that
    does not exist for the new one and a hood choice for the cat."""
    current = resolve(stored)
    new = dict(stored)
    character = current["character"]
    normalized = parse_value(key, value, character)
    if key == "hood" and character == "cat":
        raise AvatarError("У кота нет капюшона.", "The cat has no hood.")
    new[key] = normalized
    if key == "character":
        if new.get("skin") not in SKINS[normalized]:
            new.pop("skin", None)
        if normalized == "cat":
            new.pop("hood", None)
    if key == "name" and normalized == DEFAULT_NAME:
        new.pop("name", None)
    return new
