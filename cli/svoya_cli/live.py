"""The live ISO session (casper): the root is an overlay in RAM and nothing survives a reboot.

There the first-run wizard does not start (its choices would vanish, and a model it offers would
download into memory); Jackson greets instead and offers the installer, and ``sos models pull``
says where the files would go.
"""
from __future__ import annotations

from .context import Ctx
from .theme import avatar_export

INSTALLER = "/usr/bin/sos-install"

# Waits for the shell's notification server, then shows Jackson's greeting with one button; the
# button starts the installer. notify-send blocks until the toast is answered or closed.
HELLO_SH = r'''
for _ in $(seq 1 30); do
    busctl --user status org.freedesktop.Notifications >/dev/null 2>&1 && break
    sleep 1
done
a=$(notify-send -a "$1" -i sos -t 20000 -A install="$4" "$2" "$3") || exit 0
[ "$a" = install ] && exec "$5"
exit 0
'''


LIVE_MARKER = "/etc/svoya/live"      # written by image/hooks/50-live.sh, removed by the installer


def is_live(ctx: Ctx) -> bool:
    """Booted from the live medium: ``boot=casper`` on the kernel command line, or the image's marker."""
    if ctx.sys(LIVE_MARKER).exists():
        return True
    try:
        words = ctx.sys("/proc/cmdline").read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return False
    return "boot=casper" in words


def hello(ctx: Ctx, ru: bool) -> tuple[str, str, str, str]:
    """(app, title, body, button) — Jackson's greeting in his voice (кентафурик or plain)."""
    kent = avatar_export.user_voice(ctx) == "kent"
    if ru:
        body = ("Здарова, кентафурик! Это живая сессия: всё, что сделаешь, пропадёт после перезагрузки. "
                "Зайдёт — ставь СОС на диск, базару нет." if kent else
                "Это живая сессия: всё, что сделаешь, пропадёт после перезагрузки. "
                "Понравится — установи СОС на диск.")
        return "Джексон", "Живая сессия", body, "Установить СОС"
    body = ("Yo, buddy! This is a live session: whatever you do is gone after a reboot. "
            "Like it? Put SOS on your disk." if kent else
            "This is a live session: whatever you do is gone after a reboot. Like it? Install SOS on your disk.")
    return "Jackson", "Live session", body, "Install SOS"
