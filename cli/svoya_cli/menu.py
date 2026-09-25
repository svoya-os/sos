"""``sos`` with no arguments: a calm interactive menu.

Arrow keys + Enter, digits as shortcuts, ``q``/Esc to leave. Without a TTY (or when curses is not
available) it falls back to a numbered prompt; with no input at all it just prints the menu.
Every entry runs a normal ``sos`` command, so the menu never does anything the CLI cannot.
"""
from __future__ import annotations

import os
import sys
from typing import Callable

from .i18n import lang, tr

# (key, English, Russian, hint EN, hint RU)
MAIN = [
    ("install", "Install…", "Установить…", "a module, an app or a model", "модуль, приложение или модель"),
    ("models", "Models", "Модели", "the best local model for this machine", "лучшая локальная модель для этой машины"),
    ("fix", "Fix", "Починить", "check and repair (snapshot first)", "проверить и починить (сначала снимок)"),
    ("gpu", "Graphics card", "Видеокарта", "driver, CUDA/ROCm, sleep", "драйвер, CUDA/ROCm, сон"),
    ("update", "Update", "Обновить", "system update with a snapshot", "обновление системы со снимком"),
    ("undo", "Undo", "Откатить", "roll back a change", "откатить изменение"),
    ("theme", "Theme", "Тема", "night · day · auto", "ночь · день · авто"),
    ("jackson", "Jackson", "Джексон", "the assistant (Super+J)", "ассистент (Super+J)"),
    ("exit", "Exit", "Выход", "", ""),
]
THEMES = [
    ("graphite", "Graphite — night", "Графит — ночь", "", ""),
    ("paper", "Paper — day", "Бумага — день", "", ""),
    ("auto", "Auto", "Авто", "by sunrise and sunset", "по восходу и закату"),
    ("phosphor", "Phosphor", "Фосфор", "green CRT", "зелёный ЭЛТ"),
    ("__accent", "Accent color…", "Цвет акцента…", "8 colors or your own", "8 цветов или свой"),
]


def _accent_items() -> list:
    from .paths import Paths
    from .theme.accents import load_catalog
    items = []
    for a in load_catalog(Paths()).accents.values():
        n = a.name
        items.append((a.id, n.get("en", a.id), n.get("ru", n.get("en", a.id)),
                      f"{a.dark.hex} · {a.light.hex}", f"{a.dark.hex} · {a.light.hex}"))
    items.append(("__custom", "Your own…", "Свой…", "#rrggbb", "#rrggbb"))
    return items
ACCENT_256 = 215   # amber, close to Graphite's accent


def _label(item) -> tuple[str, str]:
    ru = lang() == "ru"
    return (item[2] if ru else item[1]), (item[4] if ru else item[3])


def _curses_select(stdscr, title: str, items: list) -> str | None:
    import curses
    curses.curs_set(0)
    accent = curses.A_BOLD
    dim = curses.A_DIM
    if curses.has_colors():
        curses.use_default_colors()
        try:
            curses.init_pair(1, ACCENT_256 if curses.COLORS >= 256 else curses.COLOR_YELLOW, -1)
            curses.init_pair(2, 245 if curses.COLORS >= 256 else curses.COLOR_WHITE, -1)
            accent = curses.color_pair(1) | curses.A_BOLD
            dim = curses.color_pair(2)
        except curses.error:
            pass
    idx = 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        stdscr.addnstr(1, 2, title, w - 3, accent)
        for i, item in enumerate(items):
            name, hint = _label(item)
            y = 3 + i
            if y >= h - 2:
                break
            marker = "›" if i == idx else " "
            stdscr.addnstr(y, 2, f"{marker} {i + 1}  ", w - 3, accent if i == idx else dim)
            stdscr.addnstr(y, 8, name.ljust(18), max(0, w - 9), curses.A_BOLD if i == idx else curses.A_NORMAL)
            if hint and w > 30:
                stdscr.addnstr(y, 27, hint, max(0, w - 28), dim)
        foot = tr("↑↓ choose · Enter open · 1–9 jump · q quit", "↑↓ выбрать · Enter открыть · 1–9 сразу · q выход")
        stdscr.addnstr(min(h - 1, 4 + len(items)), 2, foot, w - 3, dim)
        stdscr.refresh()
        k = stdscr.getch()
        if k in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(items)
        elif k in (curses.KEY_DOWN, ord("j"), 9):
            idx = (idx + 1) % len(items)
        elif k in (curses.KEY_ENTER, 10, 13, ord(" ")):
            return items[idx][0]
        elif ord("1") <= k <= ord("9") and k - ord("1") < len(items):
            return items[k - ord("1")][0]
        elif k in (ord("q"), 27, ord("й")):
            return None


def prompt_select(title: str, items: list, read: Callable[[str], str] = input, write: Callable[[str], None] = print) -> str | None:
    write(f"› {title}")
    for i, item in enumerate(items):
        name, hint = _label(item)
        write(f"  {i + 1}  {name.ljust(18)} {hint}".rstrip())
    try:
        ans = read(tr("number (Enter to quit): ", "номер (Enter — выход): ")).strip()
    except EOFError:
        return None
    if ans.isdigit() and 1 <= int(ans) <= len(items):
        return items[int(ans) - 1][0]
    for item in items:            # typing the name works too
        if ans and ans.lower() in (item[0], item[1].lower(), item[2].lower()):
            return item[0]
    return None


def select(title: str, items: list) -> str | None:
    if sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "dumb") != "dumb":
        try:
            import curses
            return curses.wrapper(_curses_select, title, items)
        except Exception:  # curses missing or the terminal refused: fall back, never crash
            pass
    if not sys.stdin.isatty():
        prompt_select(title, items, read=lambda _p: (_ for _ in ()).throw(EOFError()))
        return None
    return prompt_select(title, items)


def _run(argv: list[str]) -> int:
    from .main import main as sos_main
    try:
        return sos_main(argv)
    except SystemExit as e:
        return int(e.code or 0)


def action(key: str, run: Callable[[list[str]], int] = _run, ask: Callable[[str], str] = input) -> int | None:
    """Run the command behind a menu entry. Returns its exit code (None = leave the menu)."""
    if key == "exit" or key is None:
        return None
    if key == "install":
        from .modules import load_catalog, load_state
        from .context import Ctx
        ctx = Ctx()
        cat = load_catalog(ctx.paths.modules_dir)
        state = load_state(ctx)
        items = [(m["id"], m["name"]["en"], m["name"].get("ru", m["name"]["en"]), m["summary"]["en"][:60], m["summary"].get("ru", "")[:60])
                 for m in cat.values() if m["id"] not in state["modules"]]
        items.append(("__other", "Something else…", "Другое…", "an app or a model by name", "приложение или модель по имени"))
        choice = select(tr("Install", "Установить"), items)
        if choice is None:
            return 0
        if choice == "__other":
            name = ask(tr("name (e.g. obsidian, telegram, qwen3.5-9b): ", "имя (например obsidian, telegram, qwen3.5-9b): ")).strip()
            return run(["install", name]) if name else 0
        return run(["install", choice])
    if key == "models":
        rc = run(["models", "suggest"])
        ans = ask(tr("Install the suggested model? [y/N] ", "Установить предложенную модель? [д/Н] ")).strip().lower()
        if ans[:1] in ("y", "д", "l"):
            from .context import Ctx
            from .models.suggest import suggest
            return run(["models", "pull", suggest(Ctx())["default"]["id"], "--yes"])
        return rc
    if key == "fix":
        return run(["doctor", "--fix"])
    if key == "gpu":
        return run(["doctor", "--gpu"])
    if key == "update":
        return run(["update"])
    if key == "undo":
        run(["undo", "--list"])
        n = ask(tr("id to undo (Enter to cancel): ", "id для отмены (Enter — отмена): ")).strip()
        return run(["undo", n]) if n and n.replace("-", "").isalnum() else 0
    if key == "theme":
        t = select(tr("Theme", "Тема"), THEMES)
        if t == "__accent":
            a = select(tr("Accent color", "Цвет акцента"), _accent_items())
            if a == "__custom":
                a = ask(tr("color as #rrggbb: ", "цвет в виде #rrggbb: ")).strip()
            return run(["theme", "accent", a]) if a else 0
        return run(["theme", "apply", t]) if t else 0
    if key == "jackson":
        import shutil
        if shutil.which("jackson"):
            os.execvp("jackson", ["jackson"])
        print(tr("› Jackson is one key away: Super+J (hold to talk).", "› Джексон — на расстоянии клавиши: Super+J (удерживайте, чтобы говорить)."))
        return 0
    return 0


def main() -> int:
    title = tr("SOS  ··· ——— ···   what shall we do?", "СОС  ··· ——— ···   что делаем?")
    while True:
        key = select(title, MAIN)
        rc = action(key)
        if rc is None:
            return 0
        if not sys.stdin.isatty():
            return rc
        try:
            again = input(tr("\nEnter — back to the menu · q — quit ", "\nEnter — в меню · q — выход ")).strip().lower()
        except EOFError:
            return rc
        if again in ("q", "й", "exit", "выход"):
            return rc
