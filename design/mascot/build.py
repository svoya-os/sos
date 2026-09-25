#!/usr/bin/env python3
"""Export the Jackson mascot concepts: 1× frames, sprite sheets (1× and 8×) and raw pixel JSON.

    python3 design/mascot/build.py

Output in design/mascot/out/:
    imp-<state>.png, cat-<state>.png     32×32 frames (use with image-rendering: pixelated)
    imp-sheet.png, cat-sheet.png         horizontal strips, frame order = STATES
    imp-sheet@8x.png, cat-sheet@8x.png   the same, nearest-neighbour ×8
    imp-sheet.json, cat-sheet.json       palette + rows of palette keys per frame ('.' = transparent)
    mascot-data.js                       both characters as window.MASCOT (for the HTML concept pages)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from characters import STATES, frames  # noqa: E402
from pixel import save_sheet  # noqa: E402

OUT = HERE / "out"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    bundle = {}
    for kind in ("imp", "cat"):
        fr = frames(kind)
        for st in STATES:
            fr[st].image(1).save(OUT / f"{kind}-{st}.png")
        save_sheet(fr, OUT / f"{kind}-sheet.png", 1)
        save_sheet(fr, OUT / f"{kind}-sheet@8x.png", 8)
        (OUT / f"{kind}-sheet@8x.json").unlink(missing_ok=True)   # one JSON per character is enough
        bundle[kind] = {"palette": fr[STATES[0]].palette, "frames": {st: fr[st].rows() for st in STATES}}
        print(kind, "→", OUT.relative_to(HERE.parent.parent), f"({len(STATES)} frames)")
    # same data for HTML pages opened from disk (file:// cannot fetch JSON)
    (OUT / "mascot-data.js").write_text("window.MASCOT = " + json.dumps(bundle, ensure_ascii=False) + ";\n")


if __name__ == "__main__":
    main()
