"""``sos morse [text]`` (the SOS call sign ··· ——— ··· by default) and a couple of hidden jokes.

Morse beeps are a small WAV (a soft-edged 650 Hz tone, timing from the words-per-minute) played
with ``pw-play`` (PipeWire), ``paplay`` or ``aplay``, whichever exists; without any, the code is
only printed. Letters are Latin and Cyrillic (the Russian Morse alphabet), digits and a few signs.
"""
from __future__ import annotations

import io
import math
import os
import re
import struct
import tempfile
import wave

from . import ui
from .context import Ctx
from .i18n import tr

MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....", "i": "..",
    "j": ".---", "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
    "7": "--...", "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..", "!": "-.-.--",
    "-": "-....-", "/": "-..-.", "@": ".--.-.", "(": "-.--.", ")": "-.--.-", ":": "---...",
    "а": ".-", "б": "-...", "в": ".--", "г": "--.", "д": "-..", "е": ".", "ё": ".", "ж": "...-", "з": "--..",
    "и": "..", "й": ".---", "к": "-.-", "л": ".-..", "м": "--", "н": "-.", "о": "---", "п": ".--.", "р": ".-.",
    "с": "...", "т": "-", "у": "..-", "ф": "..-.", "х": "....", "ц": "-.-.", "ч": "---.", "ш": "----",
    "щ": "--.-", "ъ": "--.--", "ы": "-.--", "ь": "-..-", "э": "..-..", "ю": "..--", "я": ".-.-",
}
TONE_HZ = 650
RATE = 22050


def encode(text: str) -> list[list[str]]:
    """Words → letters → codes (``.-``); characters without a code are skipped."""
    out = []
    for word in re.split(r"\s+", text.strip().lower()):
        codes = [MORSE[ch] for ch in word if ch in MORSE]
        if codes:
            out.append(codes)
    return out


def pretty(words: list[list[str]]) -> str:
    return " / ".join(" ".join(c.replace(".", "·").replace("-", "—") for c in word) for word in words)


def timeline(words: list[list[str]], wpm: int) -> list[tuple[bool, float]]:
    """(tone?, seconds) pieces: dot 1, dash 3, gap in a letter 1, between letters 3, between words 7 units."""
    unit = 1.2 / max(5, min(wpm, 40))
    out: list[tuple[bool, float]] = []
    for wi, word in enumerate(words):
        if wi:
            out.append((False, 7 * unit))
        for li, code in enumerate(word):
            if li:
                out.append((False, 3 * unit))
            for si, sym in enumerate(code):
                if si:
                    out.append((False, unit))
                out.append((True, (1 if sym == "." else 3) * unit))
    return out


def wav_bytes(pieces: list[tuple[bool, float]]) -> bytes:
    frames = bytearray()
    edge = int(RATE * 0.005)                 # 5 ms fade in and out: no clicks
    for tone, seconds in pieces:
        n = int(RATE * seconds)
        for i in range(n):
            if not tone:
                frames += b"\x00\x00"
                continue
            env = min(1.0, i / edge, (n - i) / edge) if edge else 1.0
            frames += struct.pack("<h", int(0.35 * 32767 * env * math.sin(2 * math.pi * TONE_HZ * i / RATE)))
    frames += b"\x00\x00" * int(RATE * 0.05)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def play(ctx: Ctx, data: bytes) -> bool:
    player = next((p for p in ("pw-play", "paplay", "aplay") if ctx.runner.which(p)), None)
    if player is None:
        return False
    fd, path = tempfile.mkstemp(prefix="sos-morse-", suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        argv = [player, path] if player != "aplay" else [player, "-q", path]
        return ctx.runner.run(argv, timeout=120).ok
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def main_morse(args, ctx: Ctx) -> int:
    text = " ".join(args.text) or "SOS"
    words = encode(text)
    if not words:
        ui.err(tr("sos: nothing to send: letters or digits, please", "sos: нечего передавать: нужны буквы или цифры"))
        return 2
    code = pretty(words)
    played = False
    if not args.no_sound:
        played = play(ctx, wav_bytes(timeline(words, args.wpm)))
    if args.json:
        ui.print_json({"text": text, "morse": code, "played": played})
        return 0
    if not args.quiet:
        st = ui.style()
        ui.out(f"{st.accent(code)}  {st.faint(text)}")
        if not played and not args.no_sound:
            ui.note(tr("no sound: pw-play, paplay or aplay not found", "без звука: нет pw-play, paplay или aplay"))
    return 0


TEAPOT = r"""
                    ) )
           ()      ( (
       .--'  '--.
  .-. /          \   __
 ( ( |            |_/ /
  '-'|            | _/
      \__________/"""


def main_tea(args, ctx: Ctx) -> int:
    """A hidden one: HTTP 418 (RFC 2324)."""
    st = ui.style()
    ui.out(st.faint(TEAPOT.lstrip("\n")))
    ui.head(tr("418 I'm a teapot", "418: я чайник"))
    ui.note(tr("SOS does not brew coffee. Tea, though: \"j timer 3 min\".",
               "СОС кофе не варит, а чай — пожалуйста: «j таймер на 3 минуты»."))
    return 0
