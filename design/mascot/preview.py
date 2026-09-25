"""Design-review matrix (not shipped): python3 design/mascot/preview.py [out.png] [state]

Rows: every look option of both characters; columns: Graphite and Paper with a few accents.
"""
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402

DATA = {k: json.loads((HERE.parents[1] / "shell/assets/jackson" / f"{k}.json").read_text()) for k in ("imp", "cat")}
BG = {"dark": "#191b1f", "light": "#fdfcfa"}
S = 6


def looks():
    yield "imp", {}
    yield "imp", {"hood": False}
    yield "imp", {"style": "jacket"}
    yield "imp", {"style": "tee", "glasses": "round"}
    yield "imp", {"glasses": "shades"}
    yield "imp", {"style": "jacket", "headphones": False, "glasses": "shades"}
    for sk in ("wine", "plum", "graphite", "mint"):
        yield "imp", {"skin": sk}
    yield "cat", {}
    yield "cat", {"glasses": "none"}
    yield "cat", {"glasses": "round", "style": "tee"}
    yield "cat", {"style": "hoodie", "headphones": False}
    for sk in ("ginger", "black", "snow", "siamese"):
        yield "cat", {"skin": sk, "glasses": "none" if sk == "siamese" else "shades"}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/mascot-matrix.png")
    state = sys.argv[2] if len(sys.argv) > 2 else "idle"
    cols = [("dark", "signal"), ("dark", "lilac"), ("dark", "phosphor"), ("light", "signal"), ("light", "rose"), ("light", "mono")]
    rows = list(looks())
    tile = 32 * S
    im = Image.new("RGB", (len(cols) * (tile + 8) + 8, len(rows) * (tile + 8) + 8), "#0c0d0f")
    for r, (kind, opts) in enumerate(rows):
        d = DATA[kind]
        for c, (mode, aid) in enumerate(cols):
            acc = d["accents"][aid][mode]["detail"]
            im.paste(render.image(d, opts, state, mode, acc, S, BG[mode]), (8 + c * (tile + 8), 8 + r * (tile + 8)))
    im.save(out)
    print(out, im.size)


if __name__ == "__main__":
    main()
