"""RU/EN strings and locale-aware numbers (design/DESIGN.md §8).

Strings live next to the code as ``tr("English", "Русский")`` pairs, so both languages are
always reviewed together. Russian numbers use a decimal comma and a narrow no-break space
between thousands: ``11,2 ГБ``, ``48 213``.
"""
from __future__ import annotations

import os
from typing import Mapping

NNBSP = " "  # narrow no-break space (thousands separator, number–unit gap in RU)

_lang = "en"


def detect_lang(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    forced = env.get("SVOYA_LANG")
    if forced:
        return "ru" if forced.lower().startswith("ru") else "en"
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = env.get(key)
        if v:
            return "ru" if v.lower().startswith("ru") else "en"
    lang = env.get("LANGUAGE", "")
    if lang:
        return "ru" if lang.split(":")[0].lower().startswith("ru") else "en"
    return "en"


def set_lang(lang: str) -> None:
    global _lang
    _lang = "ru" if lang == "ru" else "en"


def lang() -> str:
    return _lang


def tr(en: str, ru: str) -> str:
    """Pick the string for the current language."""
    return ru if _lang == "ru" else en


def pick(d: Mapping[str, str] | str | None, default: str = "") -> str:
    """Pick from a ``{"en": ..., "ru": ...}`` table (TOML catalogs use this shape)."""
    if d is None:
        return default
    if isinstance(d, str):
        return d
    return d.get(_lang) or d.get("en") or next(iter(d.values()), default)


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def count(n: int, en_one: str, en_many: str, ru_one: str, ru_few: str, ru_many: str) -> str:
    """``count(3, "package", "packages", "пакет", "пакета", "пакетов")`` → ``3 пакета``."""
    if _lang == "ru":
        return f"{num(n)} {plural_ru(n, ru_one, ru_few, ru_many)}"
    return f"{num(n)} {en_one if n == 1 else en_many}"


def num(x: float | int, digits: int = 0) -> str:
    """Locale number: ``48213`` → ``48 213`` (ru) / ``48,213`` (en); ``11.24, 1`` → ``11,2``."""
    if digits <= 0:
        s = f"{int(round(x)):,}"
        return s.replace(",", NNBSP) if _lang == "ru" else s
    s = f"{x:,.{digits}f}"
    if _lang == "ru":
        s = s.replace(",", "\0").replace(".", ",").replace("\0", NNBSP)
    return s


def smart(x: float) -> str:
    """One decimal below 100, none above: 11,2 · 24 · 141."""
    if abs(x - round(x)) < 0.05 or abs(x) >= 100:
        return num(round(x))
    return num(x, 1)


def gib(nbytes: float | int | None) -> str:
    """Bytes → ``11,2 ГБ`` / ``11.2 GB`` (binary GiB, labelled ГБ/GB as users expect)."""
    if nbytes is None:
        return "—"
    return f"{smart(nbytes / 1024**3)} {tr('GB', 'ГБ')}"


def mib_to_gb(mib: float | int | None) -> str:
    if mib is None:
        return "—"
    return gib(mib * 1024**2)


def size(nbytes: float | int) -> str:
    """Human size with unit (KB/MB/GB/TB)."""
    units_en = ["B", "KB", "MB", "GB", "TB"]
    units_ru = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
    v = float(nbytes)
    i = 0
    while v >= 1024 and i < len(units_en) - 1:
        v /= 1024
        i += 1
    unit = units_ru[i] if _lang == "ru" else units_en[i]
    return f"{smart(v) if i else num(v)} {unit}"


def duration(sec: float | int | None) -> str:
    """``1080`` → ``18 мин``; ``7500`` → ``2 ч 5 мин``; ``40`` → ``40 с``."""
    if sec is None:
        return "—"
    sec = int(max(0, sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    H, M, S = tr("h", "ч"), tr("min", "мин"), tr("s", "с")
    if h:
        return f"{h} {H} {m} {M}" if m else f"{h} {H}"
    if m:
        return f"{m} {M}"
    return f"{s} {S}"


def ago(sec: float | int | None) -> str:
    if sec is None:
        return tr("never", "никогда")
    sec = int(max(0, sec))
    if sec < 90:
        return tr("just now", "только что")
    if sec < 3600:
        return tr(f"{sec // 60} min ago", f"{sec // 60} мин назад")
    if sec < 86400 * 2:
        return tr(f"{sec // 3600} h ago", f"{sec // 3600} ч назад")
    days = sec // 86400
    return tr(f"{days} days ago", f"{days} {plural_ru(days, 'день', 'дня', 'дней')} назад")
