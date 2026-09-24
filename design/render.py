#!/usr/bin/env python3
"""Render Svoya OS design mockups to PNG with headless Chromium (Playwright).

Usage:
    python3 design/render.py                      # all themes of desktop.html
    python3 design/render.py desktop graphite     # one page, one theme
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent
MOCKUPS = ROOT / "mockups"
OUT = ROOT / "out"
THEMES = ["graphite", "paper", "phosphor"]


async def render(page_name: str, themes: list[str], scale: float = 2.0) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=scale)
        page = await ctx.new_page()
        for theme in themes:
            url = (MOCKUPS / f"{page_name}.html").as_uri() + f"?theme={theme}"
            await page.goto(url)
            await page.evaluate("document.fonts.ready")
            await page.wait_for_timeout(250)
            target = OUT / f"{page_name}-{theme}.png"
            await page.screenshot(path=str(target))
            print(target)
        await browser.close()


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "desktop"
    themes = sys.argv[2:] or THEMES
    asyncio.run(render(name, themes))
