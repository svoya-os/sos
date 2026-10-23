"""The SOS ASCII symbol layer as the system sees it (the shell's ``Theme.symbols``): which parts of
it are on for a theme, read from the shell's settings (``~/.config/svoya/shell.json``: ``asciiStyle``
"auto" = with Phosphor, "always", "off"; ``asciiParts``). ``sos theme apply`` uses it to pick the
same icon theme the shell sets (folders in symbols: SOS-Symbols-Dark/-Light), so neither undoes the
other, and the cursor theme Hyprland hands to every app it starts (XCURSOR_THEME in svoya-colors.conf).
"""
from __future__ import annotations

from ..paths import Paths
from ..util import read_json

PARTS = ("widgets", "folders", "cursor", "browser")


def parts(paths: Paths, theme_id: str) -> set[str]:
    s = read_json(paths.user_config_dir / "shell.json") or {}
    style = s.get("asciiStyle", "auto")
    on = style == "always" or (style != "off" and theme_id == "phosphor")
    if not on:
        return set()
    chosen = s.get("asciiParts", list(PARTS))
    return {p for p in chosen if p in PARTS} if isinstance(chosen, list) else set(PARTS)


def icon_theme(paths: Paths, theme_id: str, mode: str, exists=lambda name: True) -> str:
    """The GTK icon theme for a theme: folders in symbols when the layer covers them (and the theme
    is installed), Papirus otherwise."""
    plain = "Papirus-Dark" if mode == "dark" else "Papirus-Light"
    if "folders" in parts(paths, theme_id):
        sym = "SOS-Symbols-Dark" if mode == "dark" else "SOS-Symbols-Light"
        if exists(sym):
            return sym
    return plain


def cursor_theme(paths: Paths, theme_id: str, exists=lambda name: True) -> str:
    """XCURSOR_THEME for the session: the symbol cursor when the layer covers it (and it is installed)."""
    if "cursor" in parts(paths, theme_id) and exists("sos-symbols"):
        return "sos-symbols"
    return "Adwaita"
