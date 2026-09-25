"""Quick preview: all frames of both characters at ×10 on Graphite and Paper backgrounds."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from characters import STATES, frames  # noqa: E402
from pixel import N  # noqa: E402

S = 10
BG = {"graphite": "#191b1f", "paper": "#fdfcfa"}
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/mascot-preview.png")
rows = [(k, t) for k in ("imp", "cat") for t in BG]
im = Image.new("RGB", (len(STATES) * (N * S + 20) + 20, len(rows) * (N * S + 20) + 20), "#0c0d0f")
for r, (kind, theme) in enumerate(rows):
    fr = frames(kind)
    for c, st in enumerate(STATES):
        tile = fr[st].image(S, bg=BG[theme])
        im.paste(tile, (20 + c * (N * S + 20), 20 + r * (N * S + 20)))
im.save(out)
print(out)
