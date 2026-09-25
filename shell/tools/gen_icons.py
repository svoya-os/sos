#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the Svoya Shell icon set.

1. Copies the Lucide SVGs we use into shell/assets/icons/ (ISC, see
   LICENSE-lucide.txt next to them) and writes our own custom glyphs there
   (svoya-*.svg: the exact bar icons from design/mockups/desktop.html).
2. Converts every SVG (path/circle/ellipse/rect/line/polyline/polygon) into
   plain SVG path data and writes core/Icons.qml, a singleton registry the
   Icon component renders with QtQuick.Shapes (PathSvg). This keeps the SVG
   files as the source of truth while letting QML recolor strokes freely.

    python3 shell/tools/gen_icons.py [path/to/lucide/icons]

Default Lucide checkout: /tmp/ref/lucide/icons. Only the stdlib is used.
"""
import pathlib
import re
import shutil
import sys
import xml.etree.ElementTree as ET

SHELL = pathlib.Path(__file__).resolve().parent.parent
ICONS = SHELL / "assets" / "icons"
REGISTRY = SHELL / "core" / "Icons.qml"
LUCIDE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ref/lucide/icons")

# Lucide icons used by the shell (name in the registry == Lucide file name).
LUCIDE_NAMES = """
wifi wifi-off wifi-low wifi-high wifi-zero network volume-x volume-1 volume-2
battery-charging bluetooth bluetooth-off sun sun-dim moon bell bell-off lock
log-out power rotate-ccw search clipboard scan-text copy check x chevron-right
chevron-down settings package zap terminal folder file file-text cpu monitor
keyboard undo-2 stethoscope cloud cloud-off shield-check eye mic app-window
layout-grid panel-bottom hard-drive download arrow-right corner-down-left
refresh-cw triangle-alert circle-alert info user image trash sparkles clock
globe list box circle-check circle-x chevron-left plus
""".split()

# Custom glyphs, drawn exactly as in design/mockups/desktop.html (bar icons,
# window-control glyphs). Same stroke rules as Lucide: 24 grid, round caps.
CUSTOM = {
    "svoya-wifi": """
      <path d="M2.5 9a15 15 0 0 1 19 0"/><path d="M5.5 12.5a10.5 10.5 0 0 1 13 0"/>
      <path d="M8.7 16a6 6 0 0 1 6.6 0"/><circle cx="12" cy="19.3" r="0.6"/>""",
    "svoya-volume": """
      <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4.5 4.5 0 0 1 0 6"/>
      <path d="M18 6.5a8 8 0 0 1 0 11"/>""",
    "svoya-volume-low": """
      <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4.5 4.5 0 0 1 0 6"/>""",
    "svoya-volume-mute": """
      <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M16 9.5l5 5"/><path d="M21 9.5l-5 5"/>""",
    # battery outline only; the charge level is drawn by the Battery component
    "svoya-battery": """
      <rect x="2.5" y="7.5" width="17" height="9" rx="2"/><path d="M21.5 10.5v3"/>""",
    "svoya-ethernet": """
      <rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 17v2.5h8V17"/>
      <path d="M8.5 9v2.5"/><path d="M11 9v2.5"/><path d="M13 9v2.5"/><path d="M15.5 9v2.5"/>""",
    "svoya-grip": """<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/>
      <circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/>
      <circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>""",
    # greeter, lock and first-run wizard glyphs (design/mockups/shell.js)
    "svoya-accessibility": """
      <circle cx="12" cy="4.6" r="1.6"/><path d="M4.8 8.6 12 10l7.2-1.4M12 10v5.2M8.6 21l3.4-5.8 3.4 5.8"/>""",
    "svoya-gpu": """
      <rect x="2.5" y="6" width="19" height="11" rx="1.8"/><circle cx="9" cy="11.5" r="2.8"/>
      <path d="M14.5 9.5h4M14.5 13.5h4M5 17v2.2M8 17v2.2"/>""",
    "svoya-play": """<path d="M7.5 4.8v14.4L19 12z"/>""",
    "svoya-flask": """
      <path d="M9 3h6M10 3v6.2L4.8 18.3A1.8 1.8 0 0 0 6.4 21h11.2a1.8 1.8 0 0 0 1.6-2.7L14 9.2V3"/>
      <path d="M7.4 15h9.2"/>""",
    "svoya-nodes": """
      <circle cx="6" cy="12" r="2.6"/><circle cx="18" cy="5.8" r="2.6"/><circle cx="18" cy="18.2" r="2.6"/>
      <path d="m8.3 10.8 7.4-3.8M8.3 13.2l7.4 3.8"/>""",
    "svoya-compass": """<circle cx="12" cy="12" r="8.8"/><path d="m15.6 8.4-2.2 5-5 2.2 2.2-5z"/>""",
    "svoya-aperture": """
      <circle cx="12" cy="12" r="8.8"/>
      <path d="m14.2 7.9 5 8.6M9.8 7.9h9.9M7.6 12l5-8.6M9.8 16.1l-5-8.6M14.2 16.1H4.3M16.4 12l-5 8.6"/>""",
    "svoya-tiles": """
      <rect x="3" y="3.5" width="9.5" height="17" rx="1.8"/><rect x="15" y="3.5" width="6" height="7.3" rx="1.6"/>
      <rect x="15" y="13.2" width="6" height="7.3" rx="1.6"/>""",
    "svoya-windows": """
      <rect x="3" y="6.5" width="13" height="10" rx="1.8"/>
      <path d="M7.5 6.5V5.2A1.7 1.7 0 0 1 9.2 3.5h10.1A1.7 1.7 0 0 1 21 5.2v8.1a1.7 1.7 0 0 1-1.7 1.7H16"/>
      <path d="M3 20.5h18"/>""",
    "svoya-restart": """<path d="M20 12a8 8 0 1 1-2.35-5.65L20 8.7"/><path d="M20 3.8v4.9h-4.9"/>""",
    "svoya-shield": """<path d="M12 3 5 6v5.2c0 4.3 2.9 7.9 7 9.8 4.1-1.9 7-5.5 7-9.8V6z"/>""",
    "svoya-key": """
      <circle cx="8" cy="15.5" r="4.4"/><path d="m11.2 12.4 8.3-8.3M16.4 7.2l2.6 2.6M14 9.6l2 2"/>""",
    "svoya-globe": """
      <circle cx="12" cy="12" r="8.8"/>
      <path d="M3.2 12h17.6M12 3.2c2.5 2.4 3.8 5.3 3.8 8.8s-1.3 6.4-3.8 8.8c-2.5-2.4-3.8-5.3-3.8-8.8S9.5 5.6 12 3.2z"/>""",
}

NUM = r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def f(el: ET.Element, key: str, default: float = 0.0) -> float:
    v = el.get(key)
    return float(v) if v is not None else default


def circle_path(cx: float, cy: float, rx: float, ry: float) -> str:
    return (f"M{fmt(cx - rx)} {fmt(cy)}a{fmt(rx)} {fmt(ry)} 0 1 0 {fmt(2 * rx)} 0"
            f"a{fmt(rx)} {fmt(ry)} 0 1 0 {fmt(-2 * rx)} 0Z")


def rect_path(x: float, y: float, w: float, h: float, rx: float, ry: float) -> str:
    if rx <= 0 and ry <= 0:
        return f"M{fmt(x)} {fmt(y)}h{fmt(w)}v{fmt(h)}h{fmt(-w)}Z"
    rx = min(rx or ry, w / 2)
    ry = min(ry or rx, h / 2)
    return (f"M{fmt(x + rx)} {fmt(y)}h{fmt(w - 2 * rx)}"
            f"a{fmt(rx)} {fmt(ry)} 0 0 1 {fmt(rx)} {fmt(ry)}v{fmt(h - 2 * ry)}"
            f"a{fmt(rx)} {fmt(ry)} 0 0 1 {fmt(-rx)} {fmt(ry)}h{fmt(-(w - 2 * rx))}"
            f"a{fmt(rx)} {fmt(ry)} 0 0 1 {fmt(-rx)} {fmt(-ry)}v{fmt(-(h - 2 * ry))}"
            f"a{fmt(rx)} {fmt(ry)} 0 0 1 {fmt(rx)} {fmt(-ry)}Z")


def points_path(points: str, close: bool) -> str:
    nums = [float(n) for n in re.findall(NUM, points)]
    pts = list(zip(nums[0::2], nums[1::2]))
    if not pts:
        return ""
    d = f"M{fmt(pts[0][0])} {fmt(pts[0][1])}" + "".join(f"L{fmt(x)} {fmt(y)}" for x, y in pts[1:])
    return d + ("Z" if close else "")


def absolutize_leading_move(d: str) -> str:
    """A leading relative moveto is absolute per the SVG spec, but it would turn
    relative once several subpaths are concatenated into one PathSvg. Rewrite
    `m x y a b c d` as `M x y l a b c d` (implicit pairs after `m` are relative
    linetos, after `M` they would be absolute)."""
    if not d.startswith("m"):
        return d
    m = re.match(rf"m\s*({NUM})[\s,]*({NUM})", d)
    if not m:
        return d
    rest = d[m.end():].lstrip(" ,")
    head = f"M{fmt(float(m.group(1)))} {fmt(float(m.group(2)))}"
    if rest and not rest[0].isalpha():
        return f"{head} l{rest}"
    return f"{head} {rest}".strip()


def element_path(el: ET.Element) -> str:
    tag = el.tag.split("}")[-1]
    if tag == "path":
        return absolutize_leading_move(" ".join(el.get("d", "").split()))
    if tag == "circle":
        r = f(el, "r")
        return circle_path(f(el, "cx"), f(el, "cy"), r, r)
    if tag == "ellipse":
        return circle_path(f(el, "cx"), f(el, "cy"), f(el, "rx"), f(el, "ry"))
    if tag == "rect":
        rx, ry = el.get("rx"), el.get("ry")
        rxv = float(rx) if rx is not None else (float(ry) if ry is not None else 0.0)
        ryv = float(ry) if ry is not None else rxv
        return rect_path(f(el, "x"), f(el, "y"), f(el, "width"), f(el, "height"), rxv, ryv)
    if tag == "line":
        return f"M{fmt(f(el, 'x1'))} {fmt(f(el, 'y1'))}L{fmt(f(el, 'x2'))} {fmt(f(el, 'y2'))}"
    if tag == "polyline":
        return points_path(el.get("points", ""), False)
    if tag == "polygon":
        return points_path(el.get("points", ""), True)
    return ""


def convert(svg_text: str) -> tuple[str, str]:
    """Return (stroke path data, fill path data) for one icon."""
    root = ET.fromstring(svg_text)
    strokes, fills = [], []
    for el in root.iter():
        if el is root:
            continue
        if el.get("transform"):
            raise ValueError(f"transform not supported: {el.attrib}")
        d = element_path(el)
        if not d:
            continue
        (fills if el.get("fill") == "currentColor" else strokes).append(d)
    return " ".join(strokes), " ".join(fills)


SVG_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
            'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
            'stroke-linejoin="round">')


def main() -> None:
    if not LUCIDE.is_dir():
        sys.exit(f"Lucide icons not found at {LUCIDE}; clone github.com/lucide-icons/lucide")
    ICONS.mkdir(parents=True, exist_ok=True)
    for old in ICONS.glob("*.svg"):
        old.unlink()
    shutil.copyfile(LUCIDE.parent / "LICENSE", ICONS / "LICENSE-lucide.txt")

    registry: dict[str, tuple[str, str]] = {}
    for name in LUCIDE_NAMES:
        src = LUCIDE / f"{name}.svg"
        text = src.read_text()
        (ICONS / f"{name}.svg").write_text(text)
        registry[name] = convert(text)
    for name, body in CUSTOM.items():
        text =f"{SVG_HEAD}{' '.join(body.split())}</svg>\n"
        (ICONS / f"{name}.svg").write_text(text)
        registry[name] = convert(text)

    lines = [
        "pragma Singleton",
        "// GENERATED by shell/tools/gen_icons.py from shell/assets/icons/*.svg - do not edit.",
        "// Lucide icons (ISC, assets/icons/LICENSE-lucide.txt) + svoya-* glyphs from the mockup.",
        "// Every entry: s = stroke path data, f = fill path data (24x24 viewBox).",
        "",
        "import QtQuick",
        "import Quickshell",
        "",
        "Singleton {",
        "    id: root",
        "",
        "    function get(name) {",
        "        const icon = root.map[name];",
        "        return icon !== undefined ? icon : root.map[\"circle-alert\"];",
        "    }",
        "",
        "    function has(name) {",
        "        return root.map[name] !== undefined;",
        "    }",
        "",
        "    readonly property var map: ({",
    ]
    items = sorted(registry.items())
    for i, (name, (s, fl)) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f'        "{name}": {{ s: "{s}", f: "{fl}" }}{comma}')
    lines += ["    })", "}", ""]
    REGISTRY.write_text("\n".join(lines))
    print(f"{len(registry)} icons -> {REGISTRY.relative_to(SHELL.parent)}")


if __name__ == "__main__":
    main()
