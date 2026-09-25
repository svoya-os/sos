# SPDX-License-Identifier: Apache-2.0
"""Fast path: deterministic RU/EN commands answered without a model (target < 700 ms).

Matching is anchored (the whole normalized utterance must match), so "как сделать тёмную тему
в VS Code" goes to the model while "тёмная тема" switches the theme. Every action verifies its
effect and says honestly when it could not (no false "done").
"""

from __future__ import annotations

import datetime as dt
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import fun
from . import skills as skills_mod
from .i18n import fmt_bytes, fmt_latency, fmt_number, norm_lang, plural_ru
from .osctl import OsControl
from .persona import style_fast
from .tools.base import T0, T1, UndoSpec

# ---------------------------------------------------------------------------
# normalization and numbers

WAKE_RE = re.compile(r"^(эй |ну |слушай |hey |ok |okay )?(джексон|jackson)\b[ ,]*")
POLITE_RE = re.compile(r"\b(пожалуйста|плиз|please|pls|будь добр|будь другом)\b")
LEAD_RE = re.compile(r"^(а |ну |так |можешь |сможешь |ты можешь |could you |can you |would you |just )")

RU_NUMS = {
    "ноль": 0, "один": 1, "одну": 1, "одна": 1, "одной": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11,
    "двенадцать": 12, "пятнадцать": 15, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100,
}
EN_NUMS = {
    "zero": 0, "one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
NUM_WORDS = "|".join(sorted(set(RU_NUMS) | set(EN_NUMS), key=len, reverse=True))
NUM = rf"(?:\d{{1,3}}|(?:(?:{NUM_WORDS})(?: (?:{NUM_WORDS}))?))"


_WAKE_CACHE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _wake_re(names: tuple[str, ...]) -> re.Pattern[str]:
    extra = tuple(sorted({n.lower().replace("ё", "е") for n in names if n}))
    if not extra:
        return WAKE_RE
    pat = _WAKE_CACHE.get(extra)
    if pat is None:
        alts = "|".join(["джексон", "jackson", *(re.escape(n) for n in extra)])
        pat = re.compile(rf"^(эй |ну |слушай |hey |ok |okay )?({alts})\b[ ,]*", re.IGNORECASE)
        _WAKE_CACHE[extra] = pat
    return pat


def normalize(text: str, names: tuple[str, ...] = (), keep_case: bool = False) -> str:
    """Lower-case (unless *keep_case*), ё→е, no punctuation, no wake word («Джексон, …»), no «пожалуйста»."""
    s = text.strip() if keep_case else text.lower().replace("ё", "е").strip()
    s = re.sub(r"['’`]", "", s)  # what's → whats
    s = re.sub(r"[«»\"“”„!?.,;:()\[\]…]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    wake = _wake_re(names)
    for _ in range(3):
        before = s
        s = wake.sub("", s).strip()
        s = POLITE_RE.sub("", s).strip() if not keep_case else re.sub(POLITE_RE.pattern, "", s, flags=re.I).strip()
        s = LEAD_RE.sub("", s).strip() if not keep_case else re.sub(LEAD_RE.pattern, "", s, flags=re.I).strip()
        s = re.sub(r"\s+", " ", s)
        if s == before:
            break
    return s


def parse_number(text: str | None) -> int | None:
    if not text:
        return None
    text = text.strip()
    if text.isdigit():
        return int(text)
    total = 0
    found = False
    for word in text.split():
        value = RU_NUMS.get(word, EN_NUMS.get(word))
        if value is None:
            return None
        total += value
        found = True
    return total if found else None


DURATION = (rf"(?P<n>{NUM}|пару|полчаса|полтора часа|час|минуту|секунду|half an hour|an hour|a minute)"
            r"(?: ?(?P<unit>сек\w*|с|мин\w*|м|час\w*|ч|seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h))?")


def parse_duration(n: str | None, unit: str | None) -> int | None:
    n = (n or "").strip()
    unit = (unit or "").strip()
    fixed = {"полчаса": 1800, "half an hour": 1800, "полтора часа": 5400, "час": 3600, "an hour": 3600,
             "минуту": 60, "a minute": 60, "секунду": 1}
    if n in fixed and not unit:
        return fixed[n]
    count = 2 if n == "пару" else parse_number(n)
    if count is None:
        return None
    if unit.startswith(("сек", "s")) or unit == "с":
        mult = 1
    elif unit.startswith(("час", "h")) or unit == "ч":
        mult = 3600
    else:
        mult = 60  # minutes by default
    seconds = count * mult
    return seconds if 0 < seconds <= 24 * 3600 else None


# ---------------------------------------------------------------------------

@dataclass
class FastResult:
    ok: bool
    text: str
    summary: str = ""
    verified: bool | None = None
    undo: list[UndoSpec] = field(default_factory=list)
    data: dict[str, Any] | None = None
    after: Callable[[], Any] | None = None   # runs after the answer was delivered (e.g. `sos ai off`)


@dataclass
class FastCtx:
    osc: OsControl
    lang: str
    persona: str = "kent"
    humor: int = 1
    seed: str = ""
    # Engine callbacks for intents that need engine state.
    undo_last: Callable[[], tuple[bool, str]] | None = None
    new_chat: Callable[[], None] | None = None
    set_policy: Callable[[str], tuple[bool, str, UndoSpec | None]] | None = None
    models: Callable[[], list[dict[str, Any]]] | None = None
    route_info: Callable[[], str] | None = None
    avatar_path: Path | None = None                   # ~/.config/svoya/avatar.json
    on_avatar_change: Callable[[], None] | None = None
    ai_off_reason: Callable[[], str | None] | None = None

    @property
    def ru(self) -> bool:
        return norm_lang(self.lang) == "ru"

    def say(self, ru: str, en: str) -> str:
        return ru if self.ru else en


Handler = Callable[[FastCtx, dict[str, Any]], FastResult]


@dataclass
class Intent:
    name: str
    patterns: list[re.Pattern[str]]
    handler: Handler
    tier: int = T0


@dataclass
class FastMatch:
    intent: Intent
    args: dict[str, Any]
    normalized: str

    @property
    def name(self) -> str:
        return self.intent.name


def _p(*patterns: str) -> list[re.Pattern[str]]:
    return [re.compile(p) for p in patterns]


# ---------------------------------------------------------------------------
# handlers: audio

def _no_backend(ctx: FastCtx, what_ru: str, what_en: str) -> FastResult:
    return FastResult(False, ctx.say(f"Не могу: {what_ru}.", f"Can't: {what_en}."), ctx.say("нет бэкенда", "no backend"),
                      verified=False)


def _volume_change(ctx: FastCtx, delta: float | None = None, level: float | None = None) -> FastResult:
    before = ctx.osc.volume_get()
    if before is None:
        return _no_backend(ctx, "не нашёл управление звуком (wpctl/pactl)", "no volume control found (wpctl/pactl)")
    if not ctx.osc.volume_set(level=level, delta=delta):
        return FastResult(False, ctx.say("Громкость не изменилась: команда не прошла.",
                                         "Volume unchanged: the command failed."), verified=False)
    after = ctx.osc.volume_get()
    target = before.level + delta if delta is not None else level
    target = max(0.0, min(1.0 if delta is not None else 1.5, target or 0.0))
    verified = after is not None and abs(after.level - target) <= 0.015
    undo = [UndoSpec("volume", ctx.say(f"громкость {before.percent}% → {after.percent if after else '?'}%",
                                       f"volume {before.percent}% → {after.percent if after else '?'}%"),
                     {"prev": before.level})]
    if after is None or (abs(after.level - before.level) < 0.005 and abs(target - before.level) >= 0.005):
        return FastResult(False, ctx.say(f"Громкость осталась {before.percent}%.",
                                         f"Volume stayed at {before.percent}%."), verified=False)
    muted = ctx.say(" (звук выключен)", " (muted)") if after.muted else ""
    return FastResult(True, ctx.say(f"Громкость {after.percent}%{muted}.", f"Volume {after.percent}%{muted}."),
                      f"{before.percent}% → {after.percent}%", verified, undo)


def h_volume_up(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _volume_change(ctx, delta=(parse_number(a.get("n")) or 10) / 100)


def h_volume_down(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _volume_change(ctx, delta=-(parse_number(a.get("n")) or 10) / 100)


def h_volume_set(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    n = parse_number(a.get("n"))
    if n is None or n > 150:
        return FastResult(False, ctx.say("Громкость — число от 0 до 100.", "Volume is a number from 0 to 100."))
    return _volume_change(ctx, level=n / 100)


def h_volume_get(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    v = ctx.osc.volume_get()
    if v is None:
        return _no_backend(ctx, "не нашёл управление звуком (wpctl/pactl)", "no volume control found (wpctl/pactl)")
    muted = ctx.say(", звук выключен", ", muted") if v.muted else ""
    return FastResult(True, ctx.say(f"Громкость {v.percent}%{muted}.", f"Volume {v.percent}%{muted}."),
                      f"{v.percent}%", True)


def _mute(ctx: FastCtx, muted: bool) -> FastResult:
    before = ctx.osc.volume_get()
    if before is None:
        return _no_backend(ctx, "не нашёл управление звуком (wpctl/pactl)", "no volume control found (wpctl/pactl)")
    if not ctx.osc.mute_set(muted):
        return FastResult(False, ctx.say("Команда не прошла.", "The command failed."), verified=False)
    after = ctx.osc.volume_get()
    verified = after is not None and after.muted == muted
    if not verified:
        return FastResult(False, ctx.say("Не получилось — состояние звука не изменилось.",
                                         "It did not work — the sound state did not change."), verified=False)
    undo = [UndoSpec("mute", ctx.say("звук выключен" if muted else "звук включён", "muted" if muted else "unmuted"),
                     {"prev": before.muted})] if before.muted != muted else []
    return FastResult(True, ctx.say("Звук выключен." if muted else f"Звук включён, громкость {after.percent}%.",
                                    "Muted." if muted else f"Unmuted, volume {after.percent}%."),
                      ctx.say("без звука" if muted else "со звуком", "muted" if muted else "unmuted"), True, undo)


def h_mute(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _mute(ctx, True)


def h_unmute(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _mute(ctx, False)


# ---------------------------------------------------------------------------
# brightness

def _brightness(ctx: FastCtx, delta: float | None = None, level: float | None = None) -> FastResult:
    before = ctx.osc.brightness_get()
    if before is None:
        return _no_backend(ctx, "нет управления яркостью (brightnessctl) — у внешнего монитора его может не быть",
                           "no brightness control (brightnessctl) — external monitors may not support it")
    if not ctx.osc.brightness_set(level=level, delta=delta):
        return FastResult(False, ctx.say("Яркость не изменилась: команда не прошла.",
                                         "Brightness unchanged: the command failed."), verified=False)
    after = ctx.osc.brightness_get()
    b, a_ = round(before * 100), round((after or 0) * 100)
    if after is None or (a_ == b and (delta or (level is not None and round(level * 100) != b))):
        return FastResult(False, ctx.say(f"Яркость осталась {b}%.", f"Brightness stayed at {b}%."), verified=False)
    undo = [UndoSpec("brightness", ctx.say(f"яркость {b}% → {a_}%", f"brightness {b}% → {a_}%"), {"prev": before})]
    return FastResult(True, ctx.say(f"Яркость {a_}%.", f"Brightness {a_}%."), f"{b}% → {a_}%", True, undo)


def h_brightness_up(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _brightness(ctx, delta=(parse_number(a.get("n")) or 10) / 100)


def h_brightness_down(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _brightness(ctx, delta=-(parse_number(a.get("n")) or 10) / 100)


def h_brightness_set(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    n = parse_number(a.get("n"))
    if n is None or not 1 <= n <= 100:
        return FastResult(False, ctx.say("Яркость — число от 1 до 100.", "Brightness is a number from 1 to 100."))
    return _brightness(ctx, level=n / 100)


# ---------------------------------------------------------------------------
# apps, folders, session

APP_STOP = re.compile(r"(файл|папк|сайт|ссылк|страниц|документ|file|folder|site|link|page|\.\w{2,4}$|/)")


def h_open_app(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    entry = a["_entry"]
    started, seen = ctx.osc.launch(entry)
    if not started:
        return FastResult(False, ctx.say(f"Не получилось запустить {entry.name}.", f"Could not launch {entry.name}."),
                          verified=False)
    if seen:
        return FastResult(True, ctx.say(f"Запустил {entry.name}.", f"Launched {entry.name}."), entry.name, True)
    return FastResult(True, ctx.say(f"Запускаю {entry.name} — процесс пока не вижу, окно может появиться чуть позже.",
                                    f"Launching {entry.name} — no process yet, the window may take a moment."),
                      entry.name, False)


FOLDERS = {
    "загрузки": ("DOWNLOAD", "Downloads"), "downloads": ("DOWNLOAD", "Downloads"),
    "документы": ("DOCUMENTS", "Documents"), "documents": ("DOCUMENTS", "Documents"),
    "изображения": ("PICTURES", "Pictures"), "картинки": ("PICTURES", "Pictures"), "pictures": ("PICTURES", "Pictures"),
    "музыку": ("MUSIC", "Music"), "music": ("MUSIC", "Music"), "видео": ("VIDEOS", "Videos"),
    "videos": ("VIDEOS", "Videos"), "рабочий стол": ("DESKTOP", "Desktop"), "desktop": ("DESKTOP", "Desktop"),
    "домашнюю папку": ("HOME", ""), "home": ("HOME", ""), "home folder": ("HOME", ""), "домашнюю": ("HOME", ""),
    "скриншоты": ("SCREENSHOTS", ""), "screenshots": ("SCREENSHOTS", ""),
}


def h_open_folder(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    key, default = FOLDERS[a["folder"]]
    home = ctx.osc.paths.home
    if key == "HOME":
        path = home
    elif key == "SCREENSHOTS":
        path = ctx.osc.screenshots_dir()
    else:
        path = home / default
        try:
            text = (ctx.osc.paths.config_home / "user-dirs.dirs").read_text(encoding="utf-8")
            m = re.search(rf'^XDG_{key}_DIR="([^"]+)"', text, re.MULTILINE)
            if m:
                path = type(home)(m.group(1).replace("$HOME", str(home)))
        except OSError:
            pass
    shown = "~" + str(path)[len(str(home)):] if str(path).startswith(str(home)) else str(path)
    if not path.is_dir():
        return FastResult(False, ctx.say(f"Папки {shown} нет.", f"{shown} does not exist."), verified=False)
    if not ctx.osc.xdg_open(str(path)):
        return FastResult(False, ctx.say("Не нашёл xdg-open, чтобы открыть папку.", "xdg-open is not available."),
                          verified=False)
    return FastResult(True, ctx.say(f"Открываю {shown}.", f"Opening {shown}."), shown, None)


def h_lock(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    ok, verified = ctx.osc.lock()
    if not ok:
        return FastResult(False, ctx.say("Не получилось заблокировать экран (loginctl).",
                                         "Could not lock the screen (loginctl)."), verified=False)
    if verified:
        return FastResult(True, ctx.say("Экран заблокирован.", "Screen locked."), "locked", True)
    return FastResult(True, ctx.say("Отправил команду блокировки; подтверждения от сеанса пока нет.",
                                    "Lock requested; the session has not confirmed it yet."), "lock sent", False)


def h_screenshot(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    if not ctx.osc.has("grim"):
        return _no_backend(ctx, "нет grim для снимков экрана", "grim is not installed")
    path = ctx.osc.screenshot()
    if path is None:
        return FastResult(False, ctx.say("Снимок не получился.", "The screenshot failed."), verified=False)
    home = str(ctx.osc.paths.home)
    shown = "~" + str(path)[len(home):] if str(path).startswith(home) else str(path)
    return FastResult(True, ctx.say(f"Скриншот сохранён: {shown}", f"Screenshot saved: {shown}"), shown, True,
                      data={"path": str(path)})


THEME_WORDS = {"темн": "graphite", "dark": "graphite", "ночн": "graphite", "графит": "graphite", "graphite": "graphite",
               "светл": "paper", "light": "paper", "дневн": "paper", "бумаг": "paper", "paper": "paper",
               "авто": "auto", "auto": "auto", "фосфор": "phosphor", "phosphor": "phosphor"}


def h_theme(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    word = a.get("which") or ""
    theme = next((v for k, v in THEME_WORDS.items() if word.startswith(k)), None)
    if theme is None:
        return FastResult(False, ctx.say("Не понял, какую тему включить.", "Which theme?"))
    svoya = ctx.osc.svoya
    if not svoya.available():
        return _no_backend(ctx, "не нашёл команду sos (темы переключает она)", "the sos command is missing (it applies themes)")
    prev = svoya.theme_current()
    ok, out = svoya.theme_apply(theme)
    if not ok:
        return FastResult(False, ctx.say(f"Тема не сменилась: {out}", f"Theme not changed: {out}"), verified=False)
    now = svoya.theme_current()
    verified = now == theme or (theme == "auto" and now is not None)
    names = {"graphite": ("Графит", "Graphite"), "paper": ("Бумага", "Paper"), "phosphor": ("Фосфор", "Phosphor"),
             "auto": ("Авто", "Auto")}
    ru_name, en_name = names[theme]
    undo = [UndoSpec("theme", ctx.say(f"тема → {ru_name}", f"theme → {en_name}"), {"prev": prev, "new": theme})] \
        if prev and prev != theme else []
    if not verified:
        return FastResult(False, ctx.say(f"Команда прошла, но тема сейчас: {now or 'неизвестно'}.",
                                         f"The command ran, but the theme is now: {now or 'unknown'}."),
                          verified=False, undo=undo)
    return FastResult(True, ctx.say(f"Тема: {ru_name}.", f"Theme: {en_name}."), theme, True, undo)


def h_timer(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    seconds = parse_duration(a.get("n"), a.get("unit"))
    if seconds is None:
        return FastResult(False, ctx.say("Не понял длительность таймера.", "I did not get the timer duration."))
    label = (a.get("label") or "").strip() or ctx.say("Таймер", "Timer")
    unit = ctx.osc.timer_start(seconds, label)
    human = _duration_text(seconds, ctx)
    if unit is None:
        return FastResult(False, ctx.say("Не получилось поставить таймер (нужен systemd --user).",
                                         "Could not set the timer (needs systemd --user)."), verified=False)
    at = (dt.datetime.now() + dt.timedelta(seconds=seconds)).strftime("%H:%M")
    undo = [UndoSpec("timer", ctx.say(f"таймер на {human}", f"timer for {human}"), {"unit": unit})]
    return FastResult(True, ctx.say(f"Таймер на {human} — сработает в {at}.", f"Timer for {human} — rings at {at}."),
                      f"{human} → {at}", True, undo)


def _duration_text(seconds: int, ctx: FastCtx) -> str:
    if seconds % 3600 == 0:
        n = seconds // 3600
        return ctx.say(f"{n} {plural_ru(n, 'час', 'часа', 'часов')}", f"{n} h")
    if seconds % 60 == 0:
        n = seconds // 60
        return ctx.say(f"{n} {plural_ru(n, 'минуту', 'минуты', 'минут')}", f"{n} min")
    return ctx.say(f"{seconds} {plural_ru(seconds, 'секунду', 'секунды', 'секунд')}", f"{seconds} s")


# ---------------------------------------------------------------------------
# information

def h_gpu(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    gpus = ctx.osc.gpus()
    if not gpus:
        return FastResult(True, ctx.say("Видеокарту не вижу: нет nvidia-smi, sos status и данных в sysfs.",
                                        "I don't see a GPU: no nvidia-smi, sos status or sysfs data."), "—", True)
    lines = []
    for g in gpus:
        parts = [str(g.get("name", "GPU"))]
        if g.get("vramTotalMiB"):
            used = (g.get("vramUsedMiB") or 0) / 1024
            total = g["vramTotalMiB"] / 1024
            gb = ctx.say("ГБ", "GB")
            parts.append(ctx.say(f"видеопамять {fmt_number(used, 'ru', 1)} из {fmt_number(total, 'ru', 0)} {gb}",
                                 f"VRAM {fmt_number(used, 'en', 1)} of {fmt_number(total, 'en', 0)} {gb}"))
        if g.get("tempC") is not None:
            parts.append(f"{g['tempC']}°")
        if g.get("util") is not None:
            parts.append(ctx.say(f"загрузка {g['util']}%", f"load {g['util']}%"))
        if g.get("driver"):
            parts.append(ctx.say(f"драйвер {g['driver']}", f"driver {g['driver']}"))
        lines.append(" · ".join(parts))
    return FastResult(True, "\n".join(lines), lines[0][:80], True, data={"gpu": gpus})


def h_disk(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    lines = []
    for d in ctx.osc.disks():
        free = fmt_bytes(d["free"], ctx.lang)
        total = fmt_bytes(d["total"], ctx.lang)
        pct = round(100 * d["used"] / d["total"]) if d["total"] else 0
        lines.append(ctx.say(f"{d['mount']}: свободно {free} из {total} (занято {pct}%)",
                             f"{d['mount']}: {free} free of {total} ({pct}% used)"))
    if not lines:
        return FastResult(False, ctx.say("Не смог прочитать диски.", "Could not read the disks."))
    return FastResult(True, "\n".join(lines), lines[0], True)


def h_battery(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    b = ctx.osc.battery()
    if b is None:
        return FastResult(True, ctx.say("Батареи нет — похоже, это настольный компьютер.",
                                        "No battery — looks like a desktop."), "—", True)
    status = {"Charging": ("заряжается", "charging"), "Discharging": ("разряжается", "discharging"),
              "Full": ("полностью заряжена", "full"), "Not charging": ("не заряжается", "not charging")}
    ru_s, en_s = status.get(b["status"], (b["status"].lower(), b["status"].lower()))
    return FastResult(True, ctx.say(f"Батарея {b['percent']}%, {ru_s}.", f"Battery {b['percent']}%, {en_s}."),
                      f"{b['percent']}%", True)


def h_ram(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    m = ctx.osc.meminfo()
    total, avail = m.get("MemTotal"), m.get("MemAvailable")
    if not total:
        return FastResult(False, ctx.say("Не смог прочитать /proc/meminfo.", "Could not read /proc/meminfo."))
    used = total - (avail or 0)
    return FastResult(True, ctx.say(f"Память: занято {fmt_bytes(used, 'ru')} из {fmt_bytes(total, 'ru')}, "
                                    f"свободно {fmt_bytes(avail or 0, 'ru')}.",
                                    f"Memory: {fmt_bytes(used, 'en')} used of {fmt_bytes(total, 'en')}, "
                                    f"{fmt_bytes(avail or 0, 'en')} available."), fmt_bytes(used, ctx.lang), True)


def h_cpu(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    c = ctx.osc.cpu()
    model = c["model"] or ctx.say("процессор", "CPU")
    load = fmt_number(c["load1"], ctx.lang, 2)
    return FastResult(True, ctx.say(f"{model} · {c['cores']} потоков · нагрузка {load}",
                                    f"{model} · {c['cores']} threads · load {load}"), model[:60], True)


def h_uptime(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    up = ctx.osc.uptime()
    if up is None:
        return FastResult(False, ctx.say("Не смог прочитать /proc/uptime.", "Could not read /proc/uptime."))
    days, rest = divmod(int(up), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if ctx.ru:
        parts = ([f"{days} {plural_ru(days, 'день', 'дня', 'дней')}"] if days else []) + \
                ([f"{hours} {plural_ru(hours, 'час', 'часа', 'часов')}"] if hours else []) + \
                [f"{minutes} {plural_ru(minutes, 'минуту', 'минуты', 'минут')}"]
        text = "Компьютер работает " + " ".join(parts) + "."
    else:
        text = f"Up for {days} d {hours} h {minutes} min." if days else f"Up for {hours} h {minutes} min."
    return FastResult(True, text, text, True)


def h_time(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    now = dt.datetime.now()
    return FastResult(True, ctx.say(f"Сейчас {now:%H:%M}.", f"It's {now:%H:%M}."), f"{now:%H:%M}", True)


def h_date(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    from .persona import MONTHS_RU, WEEKDAYS_RU
    now = dt.datetime.now()
    text = ctx.say(f"Сегодня {WEEKDAYS_RU[now.weekday()]}, {now.day} {MONTHS_RU[now.month - 1]} {now.year}.",
                   now.strftime("Today is %A, %d %B %Y."))
    return FastResult(True, text, now.strftime("%Y-%m-%d"), True)


def h_ip(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    ips = ctx.osc.local_ips()
    if not ips:
        return FastResult(True, ctx.say("Сетевых адресов не вижу — похоже, сеть не подключена.",
                                        "No network addresses — looks like you're offline."), "—", True)
    note = ctx.say("(это локальные адреса; внешний IP я не узнаю без запроса в интернет)",
                   "(local addresses; I don't look up the public IP without going online)")
    return FastResult(True, "\n".join(ips) + "\n" + note, ips[0], True)


def _radio(ctx: FastCtx, kind: str, on: bool) -> FastResult:
    get = ctx.osc.wifi_get if kind == "wifi" else ctx.osc.bluetooth_get
    set_ = ctx.osc.wifi_set if kind == "wifi" else ctx.osc.bluetooth_set
    name = "Wi-Fi" if kind == "wifi" else "Bluetooth"
    before = get()
    if before is None:
        tool = "nmcli" if kind == "wifi" else "bluetoothctl"
        return _no_backend(ctx, f"нет {tool}", f"{tool} is not available")
    if before == on:
        return FastResult(True, ctx.say(f"{name} уже {'включён' if on else 'выключен'}.",
                                        f"{name} is already {'on' if on else 'off'}."), name, True)
    if not set_(on):
        return FastResult(False, ctx.say(f"Не получилось {'включить' if on else 'выключить'} {name}.",
                                         f"Could not turn {name} {'on' if on else 'off'}."), verified=False)
    after = get()
    if after != on:
        return FastResult(False, ctx.say(f"Команда прошла, но {name} {'не включился' if on else 'не выключился'}.",
                                         f"The command ran, but {name} is still {'off' if on else 'on'}."),
                          verified=False)
    undo = [UndoSpec(kind, ctx.say(f"{name} {'включён' if on else 'выключен'}", f"{name} {'on' if on else 'off'}"),
                     {"prev": before})]
    return FastResult(True, ctx.say(f"{name} {'включён' if on else 'выключен'}.", f"{name} {'on' if on else 'off'}."),
                      f"{name} {'on' if on else 'off'}", True, undo)


def h_wifi_on(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _radio(ctx, "wifi", True)


def h_wifi_off(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _radio(ctx, "wifi", False)


def h_bt_on(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _radio(ctx, "bluetooth", True)


def h_bt_off(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _radio(ctx, "bluetooth", False)


# ---------------------------------------------------------------------------
# Jackson itself

HELP_RU = """Без модели, мгновенно:
- звук: «громче», «тише», «громкость 30», «выключи звук»
- яркость: «ярче», «темнее», «яркость 60»
- «открой firefox», «открой загрузки», «заблокируй экран», «скриншот»
- программы: «установи телеграм», «поставь стим», «установи майнкрафт» (установка откроется в терминале)
- навыки: «открой навыки», «создай навык пицца»
- своя модель: «какая модель подойдёт», «установи модель»
- тема: «тёмная тема», «светлая тема», «тема авто», «включи бумагу/графит/фосфор»
- цвет: «сделай акцент фиолетовым», «акцент сирень», «верни оранжевый», «без цвета»
- мой вид: «стань котом/чёртом», «надень очки», «сними наушники», «капюшон долой»; имя: «тебя зовут Макс»
- «таймер на 10 минут», «напомни через 20 минут проверить духовку»
- «какая у меня видеокарта», «сколько места», «заряд батареи», «сколько памяти», «мой ip»
- «включи/выключи wi-fi», «включи/выключи bluetooth»
- «отмени» — откатить моё последнее действие, «новый разговор», «только локально», «выключи ИИ»
- поиграть: «подбрось монетку», «кинь кубик d20», «шар судьбы, …», «камень», «выбери за меня пиццу или суши»,
  «загадай число от 1 до 10», «расскажи анекдот», «морзянкой привет»

А если скажешь по-своему («сделай-ка потише, соседи жалуются») — локальная модель поймёт, какую команду ты имел в виду.

С моделью: вопросы, файлы («найди договор в документах»), команды в песочнице, заметки
(«запомни, что…»). Всё рискованное я сначала покажу и спрошу. Отмена — Super+Z или `jackson undo`."""

HELP_EN = """Instant, no model needed:
- sound: "louder", "quieter", "volume 30", "mute"
- brightness: "brighter", "dimmer", "brightness 60"
- "open firefox", "open downloads", "lock the screen", "screenshot"
- apps: "install telegram", "install steam", "install minecraft" (the install opens in a terminal)
- skills: "open skills", "create skill pizza"
- a model of my own: "which model fits", "install the model"
- theme: "dark theme", "light theme", "auto theme", "switch to paper/graphite/phosphor"
- color: "make the accent green", "lilac accent", "no color"
- my look: "become a cat/imp", "put on glasses", "take off headphones", "hood off"; name: "your name is Max"
- "timer for 10 minutes", "remind me in 20 minutes to check the oven"
- "what's my GPU", "disk space", "battery", "memory usage", "my ip"
- "turn wi-fi on/off", "bluetooth on/off"
- "undo" — revert my last action, "new chat", "local only", "turn AI off"
- play: "flip a coin", "roll a d20", "magic 8 ball …", "rock", "pick for me pizza or sushi",
  "random number from 1 to 10", "tell me a joke", "morse code hello"

Say it your own way ("make it a bit quieter, the neighbours complain") and the local model works out the command.

With a model: questions, files ("find the contract in Documents"), sandboxed commands, notes
("remember that…"). Anything risky is shown to you first. Undo: Super+Z or `jackson undo`."""


def h_help(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return FastResult(True, HELP_RU if ctx.ru else HELP_EN, ctx.say("справка", "help"), True)


def h_undo(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    if ctx.undo_last is None:
        return FastResult(False, ctx.say("Отмена недоступна.", "Undo is unavailable."))
    ok, text = ctx.undo_last()
    return FastResult(ok, text, text[:80], ok)


def h_new_chat(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    if ctx.new_chat is not None:
        ctx.new_chat()
    return FastResult(True, ctx.say("Начали с чистого листа.", "Fresh start."), ctx.say("новый разговор", "new chat"),
                      True)


def h_models(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    rows = ctx.models() if ctx.models else []
    if not rows:
        return FastResult(True, ctx.say("Моделей не вижу.", "No models configured."), "—", True)
    lines = []
    for r in rows:
        where = ctx.say("локально", "local") if r["local"] else r.get("label", r["provider"])
        state = ctx.say("готова", "ready") if r["available"] else ctx.say("недоступна", "unavailable")
        lines.append(f"- {r['model'] or r['id']} · {where} · {state}")
    head = ctx.route_info() if ctx.route_info else ""
    return FastResult(True, (head + "\n" if head else "") + "\n".join(lines), f"{len(rows)}", True)


def _policy(ctx: FastCtx, policy: str) -> FastResult:
    if ctx.set_policy is None:
        return FastResult(False, ctx.say("Не могу сменить политику.", "Cannot change the policy."))
    ok, text, undo = ctx.set_policy(policy)
    return FastResult(ok, text, policy, ok, [undo] if undo else [])


def h_route_local(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _policy(ctx, "local-only")


def h_route_any(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _policy(ctx, "any")


# ---------------------------------------------------------------------------
# look: accent (DESIGN.md §10) — `sos theme accent` resolves RU/EN color words itself

ACCENT_DEFAULT_WORDS = {"по умолчанию", "стандартный", "обычный", "как было по умолчанию", "default", "сброс",
                        "стандарт"}
ACCENT_NAMES = {"signal": ("Сигнал", "Signal"), "amber": ("Янтарь", "Amber"), "ink": ("Чернила", "Ink"),
                "phosphor": ("Фосфор", "Phosphor"), "ice": ("Лёд", "Ice"), "lilac": ("Сирень", "Lilac"),
                "rose": ("Роза", "Rose"), "mono": ("Моно", "Mono")}


def _accent_label(ctx: FastCtx, acc: dict[str, Any]) -> str:
    if acc.get("custom"):
        return str(acc.get("color") or acc["custom"])
    name = acc.get("name") if isinstance(acc.get("name"), dict) else {}
    ru, en = ACCENT_NAMES.get(str(acc.get("id")), (str(acc.get("id")), str(acc.get("id"))))
    return str(name.get("ru") or ru) if ctx.ru else str(name.get("en") or en)


def h_accent(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    svoya = ctx.osc.svoya
    if not svoya.available():
        return _no_backend(ctx, "не нашёл команду sos (цвет меняет она)", "the sos command is missing (it sets colors)")
    word = "mono" if a.get("mono") else str(a.get("color") or "").strip()
    if word in ACCENT_DEFAULT_WORDS:
        word = "default"
    res = svoya.accent_set(word)
    if not res.get("ok"):
        hint = res.get("hint")
        if hint:
            hint_ru, hint_en = ACCENT_NAMES.get(str(hint), (str(hint), str(hint)))
            return FastResult(False, ctx.say(f"Красный у нас — цвет ошибок, акцентом его не делаю. Может, «{hint_ru}»?",
                                             f"Red is reserved for errors. How about {hint_en}?"), verified=False)
        return FastResult(False, ctx.say(f"Не знаю такой цвет акцента: «{word}». Есть сигнал, янтарь, чернила, "
                                         "фосфор, лёд, сирень, роза, моно или свой #hex.",
                                         f"Unknown accent “{word}”. Try signal, amber, ink, phosphor, ice, lilac, "
                                         "rose, mono or a #hex."), verified=False)
    acc = res.get("accent") or {}
    label = _accent_label(ctx, acc)
    now = svoya.accent_current()
    verified = now is not None and now == acc.get("id")
    prev = (res.get("previous") or {}).get("accent") if isinstance(res.get("previous"), dict) else None
    if res.get("changed") is False:
        return FastResult(True, ctx.say(f"Акцент уже {label}.", f"The accent is already {label}."), label, verified)
    undo = [UndoSpec("accent", ctx.say(f"акцент → {label}", f"accent → {label}"),
                     {"prev": prev or "default", "new": acc.get("id")})]
    if not verified:
        return FastResult(False, ctx.say(f"sos ответил, что акцент теперь {label}, но тема этого пока не показывает.",
                                         f"sos says the accent is {label} now, but the theme does not show it yet."),
                          label, False, undo)
    note = ""
    if acc.get("custom") and acc.get("adjusted"):
        note = ctx.say(" (чуть поправил яркость для читаемости)", " (brightness adjusted for readability)")
    return FastResult(True, ctx.say(f"Акцент: {label}{note}.", f"Accent: {label}{note}."), label, True, undo)


# ---------------------------------------------------------------------------
# Jackson's look and name (DESIGN.md §13): ~/.config/svoya/avatar.json

SKIN_STEMS = (("рыж", "ginger"), ("черн", "black"), ("снежн", "snow"), ("бел", "snow"), ("сиамск", "siamese"),
              ("голуб", "blue"), ("сер", "blue"), ("огнен", "ember"), ("бордов", "wine"), ("винн", "wine"),
              ("сливов", "plum"), ("графитов", "graphite"), ("мятн", "mint"),
              ("ginger", "ginger"), ("black", "black"), ("snow", "snow"), ("white", "snow"), ("siamese", "siamese"),
              ("blue", "blue"), ("grey", "blue"), ("gray", "blue"), ("ember", "ember"), ("wine", "wine"),
              ("plum", "plum"), ("graphite", "graphite"), ("mint", "mint"))


def _change_avatar(ctx: FastCtx, changes: list[tuple[str, Any]], ok_ru: str, ok_en: str) -> FastResult:
    from . import avatar as av
    path = ctx.avatar_path
    if path is None:
        return FastResult(False, ctx.say("Не знаю, где мой внешний вид.", "I don't know where my look is stored."))
    prev = av.read_stored(path)
    stored = dict(prev or {})
    try:
        for key, value in changes:
            stored = av.apply_change(stored, key, value)
    except av.AvatarError as exc:
        return FastResult(False, exc.text("ru" if ctx.ru else "en"), verified=False)
    if av.resolve(stored) == av.resolve(prev or {}):
        return FastResult(True, ctx.say("Я и так такой.", "I already look like that."), "—", True)
    av.write(path, stored)
    after = av.load(path)
    verified = all(after.data.get(k) == av.resolve(stored).get(k) for k, _ in changes)
    if ctx.on_avatar_change is not None:
        ctx.on_avatar_change()
    text = ok_ru.format(name=after.display_name("ru")) if ctx.ru else ok_en.format(name=after.display_name("en"))
    undo = [UndoSpec("avatar", ctx.say("мой вид: ", "my look: ") + ", ".join(f"{k}={v}" for k, v in changes),
                     {"prev": prev})]
    return FastResult(verified, text if verified else ctx.say("Записал, но проверка не сошлась.",
                                                              "Saved, but the check did not match."),
                      ", ".join(f"{k}={after.data.get(k)}" for k, _ in changes), verified, undo)


def h_character(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    word = a.get("char", "")
    character = "cat" if word.startswith(("кот", "кош", "cat", "kitt")) else "imp"
    changes: list[tuple[str, Any]] = [("character", character)]
    skin_word = (a.get("skin") or "").strip()
    if skin_word:
        skin = next((v for stem, v in SKIN_STEMS if skin_word.startswith(stem)), None)
        if skin is not None:
            changes.append(("skin", skin))
    who_ru = "кот" if character == "cat" else "чёрт"
    who_en = "a cat" if character == "cat" else "an imp"
    return _change_avatar(ctx, changes, f"Готово — теперь я {who_ru}.", f"Done — I'm {who_en} now.")


def h_glasses(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    if a.get("off"):
        return _change_avatar(ctx, [("glasses", "none")], "Снял очки.", "Glasses off.")
    kind = (a.get("kind") or "").strip()
    value = "shades" if kind.startswith(("темн", "солнеч", "солнц", "sun", "dark")) or a.get("shades") else "round"
    return _change_avatar(ctx, [("glasses", value)], "Надел очки.", "Glasses on.")


def h_headphones(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    on = not a.get("off")
    return _change_avatar(ctx, [("headphones", on)], "Надел наушники." if on else "Снял наушники.",
                          "Headphones on." if on else "Headphones off.")


def h_hood(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    on = not a.get("off")
    return _change_avatar(ctx, [("hood", on)], "Капюшон на голове." if on else "Капюшон долой.",
                          "Hood up." if on else "Hood down.")


def h_style(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    word = a.get("style", "")
    style = "hoodie" if word.startswith(("худи", "толстов", "hood")) else \
        "jacket" if word.startswith(("курт", "косух", "jack")) else "tee"
    names = {"hoodie": ("худи", "a hoodie"), "jacket": ("куртку", "a jacket"), "tee": ("футболку", "a tee")}
    return _change_avatar(ctx, [("style", style)], f"Переоделся в {names[style][0]}.", f"Changed into {names[style][1]}.")


def h_rename(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    name = " ".join(str(a.get("name") or "").split())
    if name and name == name.lower():
        name = name[:1].upper() + name[1:]
    return _change_avatar(ctx, [("name", name)], "Окей, теперь я {name}.", "Okay, I'm {name} now.")


# ---------------------------------------------------------------------------
# the AI switch (WORKFLOWS.md §8)

def h_ai_off(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    svoya = ctx.osc.svoya
    if ctx.ai_off_reason is not None and ctx.ai_off_reason():
        return FastResult(True, ctx.say("ИИ уже выключен. Включить: `sos ai on`.", "AI is already off. Turn it on: `sos ai on`."),
                          "off", True)
    if not svoya.available():
        return _no_backend(ctx, "не нашёл команду sos — выключатель ИИ есть в центре управления",
                           "the sos command is missing — the AI switch is in the control center")
    text = ctx.say("Выключаю ИИ: я и локальные модели остановимся. Включить обратно — `sos ai on` "
                   "или «ИИ и приватность» в центре управления.",
                   "Turning AI off: I and the local model servers will stop. Turn it back on with `sos ai on` "
                   "or in the control center → AI & privacy.")
    return FastResult(True, text, ctx.say("выключаю ИИ", "turning AI off"), None,
                      [UndoSpec("ai", ctx.say("ИИ выключен", "AI turned off"), {"state": "off"})],
                      after=svoya.ai_off_later)


def h_ai_on(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    if ctx.ai_off_reason is not None and not ctx.ai_off_reason():
        return FastResult(True, ctx.say("ИИ и так включён.", "AI is already on."), "on", True)
    ok, out = ctx.osc.svoya.ai_on()
    verified = ctx.ai_off_reason is not None and ctx.ai_off_reason() is None
    if not ok:
        return FastResult(False, ctx.say(f"Не получилось включить ИИ: {out}", f"Could not turn AI on: {out}"),
                          verified=False)
    return FastResult(verified, ctx.say("ИИ включён." if verified else "Команда прошла, но ИИ всё ещё выключен.",
                                        "AI is on." if verified else "The command ran, but AI is still off."),
                      "on", verified)


# ---------------------------------------------------------------------------
# intent table (order matters: specific before generic)

BY = rf"(?: (?:на|by) (?P<n>{NUM})(?: ?%| процент\w*| percent)?)?"
SET_N = rf"(?P<n>{NUM})(?: ?%| процент\w*| percent)?"

# ---------------------------------------------------------------------------
# fun: games, jokes, memes, greetings, Morse (jackson/fun.py); instant, offline, read-only

def _rng(ctx: FastCtx) -> random.Random:
    return random.Random(ctx.seed or None)


def _kent(ctx: FastCtx) -> bool:
    return ctx.persona == "kent" and ctx.humor > 0


def _fun(ctx: FastCtx, pair: tuple[str, str], summary: str = "") -> FastResult:
    text = ctx.say(*pair)
    return FastResult(True, text, summary or text[:60], True)


def h_hello(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _fun(ctx, fun.greeting(dt.datetime.now(), _kent(ctx)))


def h_coin(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _fun(ctx, fun.coin(_rng(ctx), _kent(ctx)))


def h_dice(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    sides = parse_number(a.get("sides")) or 6
    if not 2 <= sides <= 1000:
        return FastResult(False, ctx.say("У кубика бывает от 2 до 1000 граней.", "A die has 2 to 1000 sides."))
    return _fun(ctx, fun.dice(_rng(ctx), sides, _kent(ctx)))


def h_ball(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _fun(ctx, fun.ball(_rng(ctx), _kent(ctx)))


def h_rps(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _fun(ctx, fun.rps(_rng(ctx), a.get("move"), _kent(ctx)))


def h_pick(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    first = re.sub(r"^(мне|for me) ", "", a.get("a", "").strip())
    return _fun(ctx, fun.pick(_rng(ctx), first, a.get("b", ""), _kent(ctx)))


def h_number(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    low, high = parse_number(a.get("lo")), parse_number(a.get("hi"))
    return _fun(ctx, fun.number(_rng(ctx), 1 if low is None else low, 100 if high is None else high))


def h_joke(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _fun(ctx, fun.joke(_rng(ctx)), "joke")


def h_pepe(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    return _fun(ctx, fun.pepe(_rng(ctx), _kent(ctx)), "meme")


def _meme(key: str) -> Handler:
    def handler(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
        return _fun(ctx, fun.meme(key, _kent(ctx)), key)
    return handler


def h_morse(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    text = a.get("text", "").strip()
    code = fun.morse(text)
    if not code:
        return FastResult(False, ctx.say("Тут нечего передавать морзянкой: нужны буквы или цифры.",
                                         "Nothing to send in Morse: letters or digits, please."))
    after = None
    if ctx.osc.has("sos"):                      # play it too (`sos morse` beeps through PipeWire)
        def after() -> None:
            ctx.osc.runner.run(["sos", "morse", "--quiet", text], timeout=120)
    return FastResult(True, code, code[:60], True, after=after)


# ---------------------------------------------------------------------------
# installs (a visible terminal: `sos install` asks there) and Jackson's skills folder

def h_install(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    item = a["_item"]
    name, key = (item.get("names") or {}).get(ctx.lang) or item["name"], item["key"]
    if item.get("installed"):
        return FastResult(True, ctx.say(f"{name} уже стоит. Запустить: «открой {name}».",
                                        f"{name} is already installed. To start it: \"open {name}\"."), name, True)
    if not ctx.osc.open_terminal(["sos", "install", key]):
        return FastResult(False, ctx.say(f"Не нашёл терминал. Поставь сам: sos install {key}",
                                         f"No terminal found. Install it yourself: sos install {key}"), verified=False)
    lead = ctx.say("Пока не установлено. ", "Not installed yet. ") if a.get("_open") else ""
    if item["kind"] == "module":
        what = ctx.say(f"Открыл установку модуля «{name}» в терминале: подтверди там, спросит пароль.",
                       f"Opened the “{name}” module install in a terminal: confirm there, it asks for the password.")
    else:
        what = ctx.say(f"Открыл установку {name} в терминале: подтверди там. Без пароля, из Flathub.",
                       f"Opened the {name} install in a terminal: confirm there. No password, from Flathub.")
    return FastResult(True, lead + what, f"sos install {key}", None)


def _suggested(ctx: FastCtx) -> tuple[dict[str, Any], str, bool] | None:
    """(the suggested model, its size, runs on a GPU) from `sos models suggest --json`."""
    data = ctx.osc.svoya.models_suggest()
    if data is None:
        return None
    d = data["default"]
    gpu = (data.get("hardware") or {}).get("backend") not in (None, "cpu")
    return d, fmt_bytes(d.get("sizeBytes") or 0, ctx.lang), gpu


def h_model_suggest(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    """«какая модель подойдёт этому компьютеру»: answered by `sos models suggest`, before any model exists."""
    got = _suggested(ctx)
    if got is None:
        return FastResult(False, ctx.say("Не смог подобрать: команда sos не ответила. В терминале: sos models suggest",
                                         "Could not pick one: the sos command did not answer. In a terminal: "
                                         "sos models suggest"), verified=False)
    d, size, gpu = got
    speed = d.get("tokensPerSecond")
    pace = ctx.say(f", около {speed} токенов в секунду {'на видеокарте' if gpu else 'на процессоре'}" if speed else "",
                   f", about {speed} tokens a second {'on the GPU' if gpu else 'on the CPU'}" if speed else "")
    return FastResult(True, ctx.say(f"Этой машине подойдёт {d.get('name', d['id'])} ({d.get('quant', '')}, {size}{pace}). "
                                    f"Поставить: «установи модель».",
                                    f"This machine suits {d.get('name', d['id'])} ({d.get('quant', '')}, {size}{pace}). "
                                    f"To install it: \"install the model\"."), d["id"], True)


def h_model_install(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    got = _suggested(ctx)
    if got is None:
        return FastResult(False, ctx.say("Не смог подобрать модель: команда sos не ответила. В терминале: sos models suggest",
                                         "Could not pick a model: the sos command did not answer. In a terminal: "
                                         "sos models suggest"), verified=False)
    d, size, _ = got
    if not ctx.osc.open_terminal(["sos", "install", d["id"]]):
        return FastResult(False, ctx.say(f"Не нашёл терминал. Поставь сам: sos install {d['id']}",
                                         f"No terminal found. Install it yourself: sos install {d['id']}"), verified=False)
    return FastResult(True, ctx.say(f"Открыл установку {d.get('name', d['id'])} ({size}) в терминале: подтверди там. "
                                    f"Потом я отвечаю сам, без облака.",
                                    f"Opened the {d.get('name', d['id'])} install ({size}) in a terminal: confirm there. "
                                    f"Then I answer on my own, no cloud."), f"sos install {d['id']}", None)


def _home_short(ctx: FastCtx, path: Path) -> str:
    home = str(ctx.osc.paths.home)
    return "~" + str(path)[len(home):] if str(path).startswith(home + "/") else str(path)


def h_skills(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    paths = ctx.osc.paths
    folder, _ = skills_mod.init_dir(paths.skills_dir, paths.config_home, ctx.lang)
    loaded = skills_mod.Skills(paths.skills_dir, system_dirs=[paths.system_skills_dir]).load()
    mine = sum(1 for s in loaded if str(s.path).startswith(str(folder)))
    shown = _home_short(ctx, folder)
    opened = ctx.osc.xdg_open(str(folder))
    head = ctx.say(f"Открыл папку навыков: {shown}." if opened else f"Папка навыков: {shown}.",
                   f"Opened the skills folder: {shown}." if opened else f"The skills folder: {shown}.")
    count = ctx.say(f" Навыков: {len(loaded)}, твоих {mine}. Новый: «создай навык пицца».",
                    f" Skills: {len(loaded)}, yours {mine}. A new one: \"create skill pizza\".")
    return FastResult(True, head + count, shown, None)


def h_new_skill(ctx: FastCtx, a: dict[str, Any]) -> FastResult:
    """Only an empty template from the user's own words: the model never writes skills."""
    name = a.get("name", "").strip()
    paths = ctx.osc.paths
    try:
        path = skills_mod.new_skill(paths.skills_dir, paths.config_home, name, ctx.lang)
        created = True
    except FileExistsError as exc:
        path, created = Path(str(exc)) / "SKILL.md", False
    except (ValueError, OSError):
        return FastResult(False, ctx.say("Такое имя для навыка не подходит: буквы, цифры, пробел, точка или дефис.",
                                         "That name does not work for a skill: letters, digits, space, dot or dash."))
    opened = ctx.osc.xdg_open(str(path))
    shown = _home_short(ctx, path)
    if not created:
        return FastResult(True, ctx.say(f"Навык «{name}» уже есть: {shown}" + (", открыл." if opened else "."),
                                        f"Skill “{name}” already exists: {shown}" + (", opened it." if opened else ".")),
                          shown, None)
    return FastResult(True, ctx.say(f"Создал навык «{name}»: {shown}. Опиши в нём, что делать, и я подхвачу сразу.",
                                    f"Created skill “{name}”: {shown}. Describe what to do there; I pick it up at once."),
                      shown, None)


FUN_INTENTS = ("hello", "coin", "dice", "ball", "rps", "pick", "number", "joke", "pepe", "preved", "fiasco",
               "houston", "good_job", "dont_touch", "oy_vse", "thanks", "how_are_you", "answer42", "morse")


INTENTS: list[Intent] = [
    Intent("help", _p(r"что ты (умеешь|можешь)( делать)?", r"что умеешь", r"помощь", r"справка", r"кто ты",
                      r"(какие|список) команд\w*", r"what can you do", r"help", r"commands", r"who are you"), h_help),
    Intent("undo", _p(r"отмени( это| последнее( действие)?| что сделал)?", r"верни (как было|обратно|назад)",
                      r"откати( это| назад)?", r"отмена", r"undo( that| it| the last (action|change))?",
                      r"revert( that)?", r"put it back"), h_undo, T1),
    Intent("new_chat", _p(r"новый (разговор|чат|диалог)", r"начн(ем|и) (сначала|заново|с чистого листа)",
                          r"забудь (этот )?(разговор|контекст)", r"очисти (историю|контекст)",
                          r"new (chat|conversation)", r"start over", r"clear (the )?(context|history)"), h_new_chat),
    Intent("ai_off", _p(r"(выключи|отключи|вырубь?и|останови) (ии|искусственный интеллект|нейросети|нейросеть|ai)",
                        r"(выключись|отключись|вырубись)", r"(turn off|disable|switch off|stop) (the )?(ai|artificial intelligence)",
                        r"turn (the )?ai off", r"ai off"), h_ai_off, T1),
    Intent("ai_on", _p(r"(включи|верни|запусти) (ии|искусственный интеллект|нейросети|ai)",
                       r"(turn on|enable|switch on) (the )?(ai|artificial intelligence)", r"turn (the )?ai on", r"ai on"),
           h_ai_on, T1),
    Intent("rename", _p(r"(тебя )?(теперь )?(зовут|звать) (?P<name>[\w .-]{1,24})",
                        r"(зови себя|называй себя|назовись|твое имя|твоё имя) (?P<name>[\w .-]{1,24})",
                        r"(хочу|буду) (звать|называть) тебя (?P<name>[\w .-]{1,24})",
                        r"(your name is|call yourself|you are now called|from now on you are|i will call you|ill call you)"
                        r" (?P<name>[\w .-]{1,24})"), h_rename, T1),
    Intent("route_local", _p(r"(работай |отвечай )?только локально", r"без облака", r"офлайн(-| )?режим",
                             r"не (используй|ходи в) облако", r"(stay |work )?local only", r"no cloud",
                             r"offline mode"), h_route_local, T1),
    Intent("route_any", _p(r"можно (использовать )?облако", r"разреши облако", r"(включи|разреши) облачные модели",
                           r"allow (the )?cloud", r"cloud is ok", r"enable (the )?cloud"), h_route_any, T1),
    Intent("models", _p(r"(какие )?(модели|нейросети)( доступны| есть| у тебя| подключены)?",
                        r"какая (сейчас )?модель", r"на какой модели( ты)?( работаешь| сейчас)?",
                        r"(which|what) models?( are available| do you have)?", r"list models",
                        r"which model are you( using)?"), h_models),
    Intent("volume_set", _p(rf"(поставь |сделай |установи )?(громкость|звук)( на)? {SET_N}",
                            rf"(set )?(the )?volume( to)? {SET_N}"), h_volume_set, T1),
    Intent("volume_up", _p(rf"(сделай |включи )?(погромче|громче|прибавь( звук| громкость)?|увеличь (звук|громкость)|"
                           rf"звук громче|громкость (выше|больше|вверх|повыше)){BY}",
                           rf"(turn (it |the volume |the sound )?up|volume up|louder|increase (the )?volume){BY}"),
           h_volume_up, T1),
    Intent("volume_down", _p(rf"(сделай )?(потише|тише|убавь( звук| громкость)?|уменьши (звук|громкость)|звук тише|"
                             rf"громкость (ниже|меньше|вниз|пониже)){BY}",
                             rf"(turn (it |the volume |the sound )?down|volume down|quieter|lower (the )?volume|"
                             rf"decrease (the )?volume){BY}"), h_volume_down, T1),
    Intent("volume_get", _p(r"какая (сейчас )?громкость", r"какой (сейчас )?уровень (звука|громкости)",
                            r"сколько (сейчас )?громкость", r"what(s| is) the volume( now)?", r"current volume"),
           h_volume_get),
    Intent("mute", _p(r"(выключи|отключи|убери|вырубь?и) (звук|громкость)", r"без звука", r"заглуши( звук)?",
                      r"мьют", r"mute( (the )?(sound|audio|volume))?", r"sound off"), h_mute, T1),
    Intent("unmute", _p(r"(включи|верни) (звук|громкость)", r"звук включи", r"unmute( (the )?(sound|audio))?",
                        r"sound on"), h_unmute, T1),
    Intent("brightness_set", _p(rf"(поставь |сделай |установи )?яркость( экрана)?( на)? {SET_N}",
                                rf"(set )?(the )?brightness( to)? {SET_N}"), h_brightness_set, T1),
    Intent("brightness_up", _p(rf"(сделай )?(экран )?(ярче|поярче|прибавь яркость|увеличь яркость|"
                               rf"яркость (выше|больше|вверх)){BY}",
                               rf"(brighter|brightness up|increase (the )?brightness|turn (the )?brightness up){BY}"),
           h_brightness_up, T1),
    Intent("brightness_down", _p(rf"(сделай )?(экран )?(темнее|потемнее|убавь яркость|уменьши яркость|"
                                 rf"яркость (ниже|меньше|вниз)){BY}",
                                 rf"(dimmer|brightness down|decrease (the )?brightness|dim the screen|"
                                 rf"turn (the )?brightness down){BY}"), h_brightness_down, T1),
    Intent("accent", _p(r"(сделай |поставь |смени |поменяй |измени |включи |хочу )?(цвет )?акцент\w*( на| в)? "
                        r"(?P<color>[\w#\- ]{2,30})",
                        r"(?P<color>[а-я]+(ый|ий|ой|ая|ую))( цвет)? акцент",
                        r"верни (?P<color>[а-я]+(ый|ий|ой|ую|ая))( цвет| акцент)?",
                        r"(?P<mono>(сделай )?(все |всё )?без цвета|убери цвет|бесцветн\w*( тема)?)",
                        r"(make |set |change |switch )?(the )?accent( colou?r)?( to| is)? (?P<color>[\w#\- ]{2,30})",
                        r"(make it |go )?(?P<color>violet|purple|blue|green|cyan|teal|pink|orange|yellow|white|black|gray|grey"
                        r"|lilac|amber|ink|phosphor|ice|rose|mono|signal) accent",
                        r"(?P<mono>no colou?r|colou?rless)"), h_accent, T1),
    Intent("theme", _p(r"(включи |поставь |сделай |переключи на |смени на |давай )?"
                       r"(?P<which>темн\w*|светл\w*|авто\w*|фосфор\w*|графит\w*|бумаг\w*|ночн\w*|дневн\w*) "
                       r"(тем[ау]|режим|оформление)",
                       r"тем[ау] (?P<which>темн\w*|светл\w*|авто|фосфор|графит|бумага)",
                       r"(switch to |use |enable |turn on )?(?P<which>dark|light|auto|phosphor|graphite|paper) "
                       r"(theme|mode)", r"theme (?P<which>dark|light|auto|phosphor|graphite|paper)",
                       r"(включи|поставь|сделай|переключи на|смени на|давай) (?P<which>бумагу|графит|фосфор)( тему)?",
                       r"(switch to|use|enable) (?P<which>paper|graphite|phosphor)( theme)?"), h_theme, T1),
    Intent("wifi_on", _p(r"(включи|включить|подключи) (wi-?fi|вай-?фай|wifi|беспроводную сеть)",
                         r"(turn on|enable) (the )?wi-?fi", r"wi-?fi on"), h_wifi_on, T1),
    Intent("wifi_off", _p(r"(выключи|выключить|отключи) (wi-?fi|вай-?фай|wifi|беспроводную сеть)",
                          r"(turn off|disable) (the )?wi-?fi", r"wi-?fi off"), h_wifi_off, T1),
    Intent("bluetooth_on", _p(r"(включи|включить) (блютуз|блютус|bluetooth)", r"(turn on|enable) bluetooth",
                              r"bluetooth on"), h_bt_on, T1),
    Intent("bluetooth_off", _p(r"(выключи|выключить|отключи) (блютуз|блютус|bluetooth)",
                               r"(turn off|disable) bluetooth", r"bluetooth off"), h_bt_off, T1),
    Intent("lock", _p(r"(заблокируй|блокируй|заблокировать|залочь) (экран|компьютер|комп|сеанс)",
                      r"блокировка( экрана)?", r"lock( the| my)?( screen| computer| session)?"), h_lock, T1),
    Intent("screenshot", _p(r"(сделай |сними )?(скриншот|снимок экрана|скрин)( экрана)?",
                            r"(take (a )?)?(screenshot|screen shot)", r"capture (the )?screen"), h_screenshot, T1),
    Intent("timer", _p(rf"(поставь |заведи |включи |засеки )?таймер( на)? {DURATION}",
                       rf"напомни( мне)? через {DURATION}(?: (?P<label>.{{1,80}}))?",
                       rf"засеки {DURATION}",
                       rf"(set )?(a )?timer( for)? {DURATION}",
                       rf"remind me in {DURATION}(?: (to )?(?P<label>.{{1,80}}))?"), h_timer, T1),
    Intent("gpu", _p(r"(какая|что за|что) (у меня )?(за )?(видеокарта|видюха|gpu|гпу)( у меня)?( стоит)?",
                     r"сколько (у меня )?(свободной )?(видеопамяти|vram)", r"(загрузка|температура) (видеокарты|gpu)",
                     r"видеокарта", r"видеопамять", r"vram", r"gpu", r"what(s| is) my (gpu|graphics card|video card)",
                     r"(how much )?(free )?vram( do i have)?", r"gpu (usage|status|temp\w*|load)", r"my gpu"), h_gpu),
    Intent("disk", _p(r"сколько (свободного )?места( на диске| осталось| свободно)?", r"(свободное )?место на диске",
                      r"свободное место", r"(how much )?(free )?disk space( left| do i have)?", r"free space",
                      r"storage left", r"disk usage"), h_disk),
    Intent("battery", _p(r"(какой |сколько )?(заряд|уровень заряда)( батареи| аккумулятора| ноутбука)?",
                         r"батарея", r"аккумулятор", r"сколько (осталось )?(заряда|зарядки)",
                         r"battery( level| status)?", r"how much battery( is left| left)?"), h_battery),
    Intent("ram", _p(r"сколько (свободной |оперативной )?(оперативной )?памяти( свободно| занято| осталось)?",
                     r"оперативка", r"озу", r"(how much )?(free )?(ram|memory)( is)?( free| used| left| available)?",
                     r"memory usage"), h_ram),
    Intent("cpu", _p(r"(какой )?(у меня )?процессор( у меня)?", r"загрузка (процессора|цп|cpu)",
                     r"(what(s| is) my )?(cpu|processor)( usage| load)?"), h_cpu),
    Intent("uptime", _p(r"(сколько|как долго) (уже )?(работает|включен) (компьютер|комп|система)", r"аптайм",
                        r"uptime", r"how long (has the (computer|system) been|have i been) (up|on|running)"), h_uptime),
    Intent("time", _p(r"(который|сколько) (сейчас )?час\w*", r"сколько (сейчас )?времени", r"время",
                      r"what time is it", r"(the )?time( now)?", r"current time"), h_time),
    Intent("date", _p(r"какое (сегодня )?число", r"какая (сегодня )?дата", r"какой (сегодня )?день( недели)?",
                      r"сегодня какое число", r"what(s| is) (the )?date( today)?", r"what day is (it|today)",
                      r"today'?s date"), h_date),
    Intent("ip", _p(r"(какой )?(у меня )?(мой )?(локальный )?(ip|айпи)( ?адрес)?( у меня)?",
                    r"(what(s| is) )?my (local )?ip( address)?", r"ip address"), h_ip),
    Intent("character", _p(r"(стань|будь|превратись в|обернись) (?P<skin>[а-я]+(ым|им) )?"
                           r"(?P<char>котом|котиком|кошкой|котэ|чертом|чертиком|чертенком|бесом|кота|черта)",
                           r"(become|be|turn into|switch to) (an? )?(?P<skin>[a-z]+ )?(?P<char>cat|kitty|imp|devil)"),
           h_character, T1),
    Intent("glasses", _p(r"(надень|одень|нацепи) (?P<kind>темные |солнечные |солнцезащитные |круглые )?очки",
                         r"(?P<off>сними|убери) очки", r"очки (?P<off>долой)",
                         r"(put on|wear) (some |your )?(?P<shades>sunglasses|shades|dark glasses)",
                         r"(put on|wear) (some |your )?(round )?glasses", r"glasses on",
                         r"(?P<off>take off|remove) (your |the )?(glasses|sunglasses|shades)", r"glasses (?P<off>off)"),
           h_glasses, T1),
    Intent("headphones", _p(r"(надень|одень|нацепи) наушники", r"(?P<off>сними|убери) наушники",
                            r"наушники (?P<off>долой)", r"(put on|wear) (your |the )?headphones", r"headphones on",
                            r"(?P<off>take off|remove) (your |the )?headphones", r"headphones (?P<off>off)"),
           h_headphones, T1),
    Intent("hood", _p(r"(?P<off>капюшон долой|сними капюшон|убери капюшон)", r"(надень|накинь) капюшон",
                      r"(?P<off>hood (off|down)|take off (your |the )?hood)", r"(hood (on|up)|put (your |the )?hood (on|up))"),
           h_hood, T1),
    Intent("style", _p(r"(надень|одень|переоденься в|переодень) (?P<style>худи|толстовку|куртку|косуху|футболку|майку)",
                       r"(put on|wear|change into) (a |an |your )?(?P<style>hoodie|jacket|tee|t-shirt|tshirt)"),
           h_style, T1),
    # fun (jackson/fun.py): read-only, no model
    Intent("hello", _p(r"(привет|приветик|здарова|здорово|здравствуй|здравствуйте|салют|хай|йо|добрый день|"
                       r"доброе утро|добрый вечер|доброй ночи)( джексон)?",
                       r"(hi|hello|hey|yo|good (morning|afternoon|evening))( jackson)?"), h_hello),
    Intent("coin", _p(r"(подбрось|подкинь|кинь|брось) монет(ку|у)", r"орел или решка", r"монетк(а|у)",
                      r"(flip|toss) a coin", r"heads or tails"), h_coin),
    Intent("dice", _p(r"(кинь|брось|подбрось)( мне)? (кубик|кубики|кости|кость|дайс)( d ?(?P<sides>\d{1,4}))?",
                      r"(кинь|брось) d ?(?P<sides>\d{1,4})", r"d(?P<sides>\d{1,4})",
                      r"(roll|throw)( a| the)? (die|dice|d ?(?P<sides>\d{1,4}))"), h_dice),
    Intent("ball", _p(r"(магический |волшебный )?шар( судьбы| предсказаний)?( (?P<q>.{2,120}))?",
                      r"(скажи )?да или нет( (?P<q>.{2,120}))?", r"magic (8|eight) ball( (?P<q>.{2,120}))?",
                      r"yes or no( (?P<q>.{2,120}))?"), h_ball),
    Intent("rps", _p(r"(?P<move>камень|ножницы|бумага|бумагу)",
                     r"(давай |го )?(сыграем |поиграем |играем )?(в )?камень ножницы бумага",
                     r"(?P<move>rock|paper|scissors)", r"(let'?s play )?rock paper scissors"), h_rps),
    Intent("pick", _p(r"(выбери|реши) за меня (?P<a>.{1,60}?) или (?P<b>.{1,60})",
                      r"выбери (?P<a>.{1,60}?) или (?P<b>.{1,60})",
                      r"(pick|choose) for me (?P<a>.{1,60}?) or (?P<b>.{1,60})"), h_pick),
    Intent("number", _p(r"(загадай|выбери|назови|дай)( мне)?( случайное)? число( от (?P<lo>\d{1,9}) до (?P<hi>\d{1,9}))?",
                        r"(random|pick a) number( (from|between) (?P<lo>\d{1,9}) (to|and) (?P<hi>\d{1,9}))?"), h_number),
    # «анекдот про кота» (a topic) goes to the model, which can make one up
    Intent("joke", _p(r"(расскажи|скажи|давай|травани)( мне)?( еще)? (анекдот|шутку|прикол)",
                      r"пошути( еще)?", r"рассмеши( меня)?", r"(еще )?(анекдот|шутку)",
                      r"tell (me )?(a|another) joke", r"make me laugh", r"(another )?joke"), h_joke),
    Intent("pepe", _p(r"((пепе|шнейне|фа|втфа|ватафа) ?){1,6}"), h_pepe),
    Intent("preved", _p(r"превед( медвед| кросавчег)?"), _meme("preved")),
    Intent("fiasco", _p(r"(это )?(полное )?фиаско( братан)?"), _meme("fiasco")),
    Intent("houston", _p(r"хьюстон( у нас (проблемы|проблема))?", r"houston( we have a problem)?"), _meme("houston")),
    Intent("good_job", _p(r"кто (тут )?молодец", r"я молодец"), _meme("good_job")),
    Intent("dont_touch", _p(r"работает не трогай", r"if it works dont touch it"), _meme("dont_touch")),
    Intent("oy_vse", _p(r"ой (все|всё)"), _meme("oy_vse")),
    Intent("thanks", _p(r"(спасибо|спс|пасиб|пасибки|благодарю)( большое| огромное)?( джексон)?",
                        r"(thanks|thank you|thx)( so much| a lot)?( jackson)?"), _meme("thanks")),
    Intent("how_are_you", _p(r"как (дела|ты|жизнь|сам|поживаешь|настроение)", r"how are you( doing)?",
                             r"whats up"), _meme("how_are_you")),
    Intent("answer42", _p(r"(в чем )?смысл жизни", r"ответ на (главный )?вопрос жизни( вселенной и всего такого)?",
                          r"42", r"(what is )?the meaning of life"), _meme("answer42")),
    Intent("morse", _p(r"(скажи |напиши |переведи |передай )?(это )?(азбукой морзе|морзянкой|на морзянку|в морзянку|"
                       r"на азбуку морзе) (?P<text>.{1,80})",
                       r"(say |write )?(it )?(in )?morse( code)? (?P<text>.{1,80})"), h_morse),
    Intent("skills", _p(r"(открой |покажи )?(мне )?(мои |свои |твои )?(папку )?навык(и|ов)( джексона)?",
                        r"где (лежат |хранятся )?(мои |твои )?навыки( джексона)?",
                        r"(open |show )?(me )?(my |your )?skills( folder)?", r"where are (my |your )?skills"),
           h_skills, T1),
    Intent("new_skill", _p(r"(создай|сделай|добавь|заведи)( новый| мне| свой)* навык (?P<name>[\w .-]{2,40})",
                           r"(create|make|add)( me)?( a)?( new)? skill (?P<name>[\w .-]{2,40})"), h_new_skill, T1),
    Intent("model_suggest", _p(r"(какая|какую) (модель|нейросеть|нейронка|нейронку) (мне )?(подойдет|подходит|влезет|"
                               r"поставить|выбрать|скачать|лучше)( для| на| в| к)?( этот| этого| этом| этому| мой| моего| "
                               r"моем| моему| мою)?( компьютер\w*| комп\w*| машин\w*| ноутбук\w*| ноут\w*| пк)?",
                               r"подбери (мне )?(модель|нейросеть|нейронку)", r"подобрать модель",
                               r"(which|what) model (fits|would fit|should i (use|install|download|get)|is best)( on| for| in)?"
                               r"( this| my)?( computer| machine| pc| laptop)?", r"(suggest|recommend|pick) (me )?(a )?model"),
           h_model_suggest),
    Intent("model_install", _p(r"(установи|поставь|скачай|загрузи)( мне)? (эту |ее |подходящую |рекомендованную |лучшую )?"
                               r"(модель|нейросеть|нейронку)",
                               r"(install|download|get)( me)? (the |that |this |a )?(recommended |suggested |best )?"
                               r"(local )?model"), h_model_install, T1),
    Intent("install", _p(r"(установи|поставь|скачай|загрузи|инсталлируй)( мне)? (?P<app>[\w .+-]{2,40})",
                         r"(install|download|get me) (?P<app>[\w .+-]{2,40})"), h_install, T1),
    Intent("open_folder", _p(r"(открой|покажи) (мне )?(папку )?(?P<folder>загрузки|документы|изображения|картинки|"
                             r"музыку|видео|рабочий стол|домашнюю папку|домашнюю|скриншоты)",
                             r"(open|show) (my )?(the )?(?P<folder>downloads|documents|pictures|music|videos|desktop|"
                             r"home folder|home|screenshots)( folder)?"), h_open_folder, T1),
    Intent("open_app", _p(r"(открой|запусти|открыть|запустить|включи) (?P<app>[\w .+-]{2,40})",
                          r"(open|launch|start|run) (?P<app>[\w .+-]{2,40})"), h_open_app, T1),
]


INSTALL = next(i for i in INTENTS if i.name == "install")


def match(text: str, osc: OsControl | None = None, names: tuple[str, ...] = ()) -> FastMatch | None:
    """Return the matching intent or None (then the request goes to a model).

    *names* are extra wake words (Jackson's custom name from avatar.json: «Макс, громче»)."""
    if len(text) > 160 or "\n" in text.strip():
        return None
    norm = normalize(text, names)
    if not norm:
        return None
    found = _match(norm, text, osc, names)
    if found is None:
        # «привет, что ты умеешь» / "hi, what can you do": the greeting, then a command
        rest = GREET_RE.sub("", norm, count=1)
        if rest != norm:
            found = _match(rest, text, osc, names)
    return found


# a greeting in front of a command (the greeting alone is the «hello» intent)
GREET_RE = re.compile(r"^(привет|приветик|здарова|здорово|здравствуй|здравствуйте|салют|хай|йо|добрый день|доброе утро|"
                      r"добрый вечер|hi|hello|hey|yo)( джексон| jackson)? (?=\S)")


def _match(norm: str, text: str, osc: OsControl | None, names: tuple[str, ...]) -> FastMatch | None:
    for intent in INTENTS:
        for pattern in intent.patterns:
            m = pattern.fullmatch(norm)
            if not m:
                continue
            args = {k: v for k, v in m.groupdict().items() if v is not None}
            if intent.name in ("rename", "new_skill"):  # keep the user's spelling of the name (case, ё)
                cased = normalize(text, names, keep_case=True)
                m2 = re.compile(pattern.pattern, re.IGNORECASE).fullmatch(
                    cased.replace("Ё", "Е").replace("ё", "е")) if cased else None
                if m2 and m2.group("name"):
                    start, end = m2.span("name")
                    args["name"] = cased[start:end]
            if intent.name == "install":
                app = args.get("app", "").strip()
                item = osc.svoya.find_installable(app) if osc is not None and len(app.split()) <= 3 else None
                if item is None:
                    break                   # not in the catalog (a model, a package…): other intents, then the model
                args["_item"] = item
            if intent.name == "open_app":
                app = args.get("app", "").strip()
                if APP_STOP.search(app) or len(app.split()) > 3 or osc is None:
                    return None
                entry = osc.find_app(app)
                if entry is None:
                    # «открой стим» before Steam is installed: offer the install instead
                    item = osc.svoya.find_installable(app)
                    if item is not None and not item.get("installed"):
                        return FastMatch(INSTALL, {"app": app, "_item": item, "_open": True}, norm)
                    return None
                args["_entry"] = entry
                args["app"] = app
            return FastMatch(intent, args, norm)
    return None


# ---------------------------------------------------------------------------
# decisions: a short command the patterns missed («сделай-ка потише, соседи жалуются») is mapped to
# an intent by the local model in one step (jackson/decide.py), and run only when the model is sure

# (intent, what it does in Russian, in English) — commands without arguments only
DECIDABLE: list[tuple[str, str, str]] = [
    ("volume_up", "сделать звук громче", "make the sound louder"),
    ("volume_down", "сделать звук тише", "make the sound quieter"),
    ("mute", "выключить звук совсем", "mute the sound"),
    ("unmute", "снова включить звук", "unmute the sound"),
    ("brightness_up", "сделать экран ярче", "make the screen brighter"),
    ("brightness_down", "сделать экран темнее", "make the screen dimmer"),
    ("wifi_on", "включить Wi-Fi", "turn Wi-Fi on"),
    ("wifi_off", "выключить Wi-Fi", "turn Wi-Fi off"),
    ("bluetooth_on", "включить Bluetooth", "turn Bluetooth on"),
    ("bluetooth_off", "выключить Bluetooth", "turn Bluetooth off"),
    ("lock", "заблокировать экран", "lock the screen"),
    ("screenshot", "сделать снимок экрана", "take a screenshot"),
    ("battery", "сказать заряд батареи", "tell the battery level"),
    ("time", "сказать, который час", "tell the time"),
]
NOT_A_COMMAND = ("ничего из этого: вопрос «как», «почему», «что», просьба о другом или разговор",
                 "none of these: a how/why/what question, another request or a chat")
DECIDE_HINT = re.compile(r"(звук|громк|тиш|тих|музык|колонк|наушник|яркост|ярч|темн|экран|вай ?фай|wi ?fi|интернет|"
                         r"блют|bluetooth|блок|скрин|снимок|заряд|батаре|который час|сколько времени|врем|"
                         r"sound|volume|loud|quiet|music|bright|dim|screen|internet|lock|screenshot|battery|"
                         r"charge|time)")
READ_ONLY_HINT = re.compile(r"(заряд|батаре|который час|сколько времени|врем|battery|charge|time)")
QUESTION_RE = re.compile(r"^(почему|зачем|как|что|какой|какая|какие|где|когда|откуда|можно ли|правда ли|"
                         r"why|how|what|which|where|when|is|are|can|could|does|do)\b")
DECIDE_MAX_WORDS = 12
DECIDE_MIN_P = 0.8          # read-only intents (battery, time)
DECIDE_MIN_P_CHANGE = 0.9   # intents that change something (volume, Wi-Fi, lock)


def decision_candidate(text: str, names: tuple[str, ...] = ()) -> str | None:
    """The normalized request when it is short and sounds like a system command, else None."""
    if len(text) > 160 or "\n" in text.strip():
        return None
    norm = normalize(text, names)
    if not norm or len(norm.split()) > DECIDE_MAX_WORDS or not DECIDE_HINT.search(norm):
        return None
    # a question can only be answered by a read-only intent: don't spend a model step on the rest
    if (QUESTION_RE.match(norm) or text.strip().endswith("?")) and not READ_ONLY_HINT.search(norm):
        return None
    return norm


def decision_options(lang: str) -> list[str]:
    ru = norm_lang(lang) == "ru"
    return [(d_ru if ru else d_en) for _, d_ru, d_en in DECIDABLE] + [NOT_A_COMMAND[0 if ru else 1]]


def decided_match(index: int, p: float, norm: str, question: bool | None = None) -> FastMatch | None:
    """The intent the model picked, if it is sure enough; a question («почему не работает Wi-Fi»)
    never switches anything, it can only be answered by a read-only intent."""
    if not 0 <= index < len(DECIDABLE):
        return None                                   # «none of these»
    name = DECIDABLE[index][0]
    intent = next((i for i in INTENTS if i.name == name), None)
    if intent is None:
        return None
    changes = intent.tier != T0
    if question is None:
        question = bool(QUESTION_RE.match(norm)) or norm.endswith("?")
    if changes and question:
        return None
    if p < (DECIDE_MIN_P_CHANGE if changes else DECIDE_MIN_P):
        return None
    return FastMatch(intent, {}, norm)


def run(m: FastMatch, ctx: FastCtx) -> FastResult:
    result = m.intent.handler(ctx, m.args)
    if m.name not in ("help", "models", *FUN_INTENTS):  # listings stay plain; the fun ones have their own voice
        result.text = style_fast(ctx.persona, ctx.lang, result.text, result.ok, ctx.humor, ctx.seed)
    return result


def public_args(m: FastMatch) -> dict[str, Any]:
    """Arguments safe to show/log (no internal objects)."""
    out = {k: v for k, v in m.args.items() if not k.startswith("_")}
    if "_entry" in m.args:
        out["app_id"] = m.args["_entry"].id
    return out


def latency_note(ms: float, lang: str) -> str:  # pragma: no cover - convenience for the CLI
    return fmt_latency(ms, lang)
