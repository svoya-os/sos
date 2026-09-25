#!/usr/bin/env python3
"""Render every SOS screen mockup to PNG with headless Chromium (Playwright).

Sibling of render.py (which renders only the approved desktop). Canvas 1440×900 @2x.

Usage:
    python3 design/render_all.py                     # every screen in every theme it ships in + contact sheet
    python3 design/render_all.py launcher lock       # only these pages (all their themes and variants)
    python3 design/render_all.py lock --theme phosphor
    python3 design/render_all.py --sheet             # only rebuild the contact sheet from existing PNGs
    python3 design/render_all.py --scale 1 launcher  # quick 1x preview

Output: design/out/<page>[-<variant>]-<theme>.png, design/out/contact-sheet-screens.png and the
Jackson mascot sheets design/out/jackson-concepts.png, jackson-in-panel.png (run design/mascot/build.py first).
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
from dataclasses import dataclass, field

from playwright.async_api import Page, async_playwright

ROOT = pathlib.Path(__file__).resolve().parent
MOCKUPS = ROOT / "mockups"
OUT = ROOT / "out"
SHEET = OUT / "contact-sheet-screens.png"


@dataclass
class Screen:
    page: str
    themes: list[str]
    caption: str
    variants: dict[str, str] = field(default_factory=lambda: {"": ""})  # file suffix → extra query


# Order = order on the contact sheet (four columns: keep Graphite/Paper pairs on one row).
SCREENS: list[Screen] = [
    Screen("launcher", ["graphite", "paper"], "Лаунчер · Super+Space"),
    Screen("jackson-approval", ["graphite", "paper"], "Джексон · разрешение T2"),
    Screen("jackson-voice", ["graphite", "paper"], "Джексон · голос"),
    Screen("control-center", ["graphite", "paper"], "Центр управления"),
    Screen("notifications", ["graphite", "paper"], "Уведомления"),
    Screen("greeter", ["graphite", "paper"], "Экран входа"),
    Screen("lock", ["graphite", "paper", "phosphor"], "Экран блокировки"),
    Screen("post", ["graphite"], "POST после входа"),
    Screen("setup-look", ["graphite", "paper"], "Первый запуск · 3/7 оформление"),
    Screen("setup-profile", ["graphite", "paper"], "Первый запуск · 5/7 профиль"),
    Screen("setup-ai", ["graphite", "paper"], "Первый запуск · 6/7 ИИ"),
    Screen("desktop-classic", ["graphite", "paper"], "Раскладка «Классика»"),
    Screen("desktop-hacker", ["graphite", "paper"], "Раскладка «Хакер»"),
    Screen("settings-models", ["graphite", "paper"], "Модели · хранилище /srv/ai"),
    Screen("boot", ["graphite"], "Загрузка", {"": "", "grub": "frame=grub", "sequence": "frame=seq"}),
]

THEME_RU = {"graphite": "Графит", "paper": "Бумага", "phosphor": "Фосфор"}

# Concept sheets with fixed output names (not part of the screens contact sheet).
# page, output file, viewport height (None = 900), full page?
EXTRAS = [
    ("jackson-concepts", "jackson-concepts.png", 900, True),
    ("jackson-in-panel", "jackson-in-panel.png", 900, False),
]


def targets(screens: list[Screen], only_theme: str | None):
    for s in screens:
        for suffix, query in s.variants.items():
            for theme in s.themes:
                if only_theme and theme != only_theme:
                    continue
                name = f"{s.page}-{suffix}-{theme}" if suffix else f"{s.page}-{theme}"
                caption = s.caption + {"": "", "grub": " · GRUB", "sequence": " · прогрев"}.get(suffix, "")
                yield s, name, f"theme={theme}" + (f"&{query}" if query else ""), caption, theme


async def settle(page: Page) -> None:
    await page.wait_for_function("document.body && document.body.dataset.ready === '1'", timeout=10_000)
    await page.evaluate("document.fonts.ready")
    await page.wait_for_timeout(120)


async def render(screens: list[Screen], only_theme: str | None, scale: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=scale)
        page = await ctx.new_page()
        page.on("console", lambda m: print("  console:", m.text) if m.type in ("warning", "error") else None)
        page.on("pageerror", lambda e: print("  page error:", e))
        for s, name, query, _, _ in targets(screens, only_theme):
            await page.goto((MOCKUPS / f"{s.page}.html").as_uri() + "?" + query)
            await settle(page)
            target = OUT / f"{name}.png"
            await page.screenshot(path=str(target))
            print(target.relative_to(ROOT.parent))
        await browser.close()


async def extras(names: list[str] | None, scale: float) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=scale)
        page = await ctx.new_page()
        page.on("pageerror", lambda e: print("  page error:", e))
        for page_name, out, _, full in EXTRAS:
            if names and page_name not in names:
                continue
            await page.goto((MOCKUPS / f"{page_name}.html").as_uri() + "?theme=graphite")
            await settle(page)
            await page.screenshot(path=str(OUT / out), full_page=full)
            print((OUT / out).relative_to(ROOT.parent))
        await browser.close()


async def contact_sheet(scale: float = 1.5) -> None:
    entries = []
    for i, (s, name, _, caption, theme) in enumerate(targets(SCREENS, None)):
        png = OUT / f"{name}.png"
        if png.exists():
            entries.append({"src": png.as_uri(), "caption": caption, "theme": THEME_RU[theme], "file": png.name})
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1712, "height": 900}, device_scale_factor=scale)
        page = await ctx.new_page()
        await page.goto((MOCKUPS / "contact-sheet.html").as_uri())
        await page.evaluate("(e) => build(e)", entries)
        await page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
        await settle(page)
        await page.screenshot(path=str(SHEET), full_page=True)
        print(SHEET.relative_to(ROOT.parent), f"({len(entries)} screens)")
        await browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pages", nargs="*", help="page names (default: all)")
    ap.add_argument("--theme", help="render only this theme")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--sheet", action="store_true", help="only rebuild the contact sheet")
    ap.add_argument("--no-sheet", action="store_true", help="skip the contact sheet")
    a = ap.parse_args()
    extra_names = {e[0] for e in EXTRAS}
    if not a.sheet:
        chosen = [s for s in SCREENS if not a.pages or s.page in a.pages]
        unknown = set(a.pages) - {s.page for s in SCREENS} - extra_names
        if unknown:
            raise SystemExit(f"unknown page(s): {', '.join(sorted(unknown))}")
        if chosen and (not a.pages or set(a.pages) - extra_names):
            asyncio.run(render(chosen, a.theme, a.scale))
        wanted = [n for n in a.pages if n in extra_names]
        if not a.pages or wanted:
            asyncio.run(extras(wanted or None, a.scale))
    if a.sheet or (not a.pages and not a.no_sheet):
        asyncio.run(contact_sheet())


if __name__ == "__main__":
    main()
