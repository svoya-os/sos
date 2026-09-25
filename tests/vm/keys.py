# SPDX-License-Identifier: Apache-2.0
"""Keyboard input for QMP send-key: combos ("meta_l+spc", "Super+J") and typed text (US layout)."""
from __future__ import annotations

ALIASES = {
    "super": "meta_l", "meta": "meta_l", "win": "meta_l", "cmd": "meta_l",
    "space": "spc", "enter": "ret", "return": "ret", "escape": "esc",
    "control": "ctrl", "ctrl_l": "ctrl", "shift_l": "shift", "alt_l": "alt",
    "backspace": "backspace", "del": "delete", "pageup": "pgup", "pagedown": "pgdn",
}

SHIFTED = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7", "*": "8", "(": "9",
    ")": "0", "_": "minus", "+": "equal", "{": "bracket_left", "}": "bracket_right", "|": "backslash",
    ":": "semicolon", '"': "apostrophe", "<": "comma", ">": "dot", "?": "slash", "~": "grave_accent",
}
PLAIN = {
    " ": "spc", "-": "minus", "=": "equal", "[": "bracket_left", "]": "bracket_right",
    "\\": "backslash", ";": "semicolon", "'": "apostrophe", ",": "comma", ".": "dot", "/": "slash",
    "`": "grave_accent", "\n": "ret", "\t": "tab",
}


def normalize(key: str) -> str:
    k = key.strip().lower()
    return ALIASES.get(k, k)


def parse_combo(spec: str | list[str]) -> list[str]:
    """"Super+Space" / "meta_l+spc" / ["meta_l", "spc"] -> ["meta_l", "spc"]."""
    parts = spec if isinstance(spec, list) else spec.split("+")
    keys = [normalize(p) for p in parts if p.strip()]
    if not keys:
        raise ValueError(f"empty key combo: {spec!r}")
    return keys


def text_to_combos(text: str) -> list[list[str]]:
    """Each character becomes one send-key combo (US layout)."""
    combos: list[list[str]] = []
    for ch in text:
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            combos.append([ch])
        elif "A" <= ch <= "Z":
            combos.append(["shift", ch.lower()])
        elif ch in PLAIN:
            combos.append([PLAIN[ch]])
        elif ch in SHIFTED:
            combos.append(["shift", SHIFTED[ch]])
        else:
            raise ValueError(f"cannot type {ch!r} with a US layout")
    return combos
