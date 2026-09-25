#!/usr/bin/env python3
"""Export the Jackson mascot system (DESIGN.md §13, format: FORMAT.md).

    python3 design/mascot/build.py

Writes
    shell/assets/jackson/imp.json, cat.json   the runtime data the shell renders (layers, states, slots, skins…)
    design/mascot/out/jackson-data.js           the same data as window.JACKSON for the HTML mockups
    design/mascot/out/<character>-<state>.png   default look, 32×32, Graphite + «Сигнал» (for quick use)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from characters import ANIMATIONS, CHARACTERS, SLOTS, STATES, STATE_SLOTS, TINT  # noqa: E402
from color import accents, detail, outfit  # noqa: E402
import render  # noqa: E402

OUT = HERE / "out"
SHELL = ROOT / "shell" / "assets" / "jackson"


def export(kind: str) -> dict:
    ch = CHARACTERS[kind]
    layers = {k: v.rows() for k, v in ch["layers"]().items()}
    states = {st: ch["state"](st).rows() for st in STATES}
    used = {c for grid in (*layers.values(), *states.values()) for row in grid for c in row} - {"."}
    used |= {"o", "e"}
    slots = {k: SLOTS[k] for k in SLOTS if k in used}
    acc = {}
    for aid, a in accents().items():
        acc[aid] = {m: {**detail(a[m]), **outfit(a[m], m)} for m in ("dark", "light")}
        acc[aid]["name"] = a["name"]
    skins = {}
    for sid, spec in ch["skins"].items():
        ru, cols = spec[0], spec[1]
        skins[sid] = {"name": {"ru": ru}, "colors": cols, "flags": list(spec[2]) if len(spec) > 2 else []}
    fixed = {k: v for k, v in ch["fixed"].items() if k in slots.values()}
    return {
        "format": "sos-jackson/1",
        "id": kind,
        "name": ch["name"],
        "size": 32,
        "slots": slots,
        "fixed": fixed,
        "aliases": {"led": "detail"},
        "stateSlots": STATE_SLOTS,
        "skins": skins,
        "accents": acc,
        "options": ch["options"],
        "defaults": ch["defaults"],
        "derive": ch["derive"],
        "compose": ch["compose"],
        "tint": TINT,
        "animations": ANIMATIONS,
        "states": states,
        "layers": layers,
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    SHELL.mkdir(parents=True, exist_ok=True)
    bundle = {}
    for kind in CHARACTERS:
        data = export(kind)
        bundle[kind] = data
        # one grid per line keeps the file diff-friendly and readable
        text = json.dumps(data, ensure_ascii=False, indent=1)
        (SHELL / f"{kind}.json").write_text(text + "\n")
        acc = data["accents"]["signal"]["dark"]["detail"]
        for st in STATES:
            render.image(data, {}, st, "dark", acc).save(OUT / f"{kind}-{st}.png")
        print(f"{kind}: {len(data['layers'])} layers, {len(data['states'])} states, {len(data['skins'])} skins → "
              f"{(SHELL / f'{kind}.json').relative_to(ROOT)} ({len(text) // 1024} КБ)")
    (OUT / "jackson-data.js").write_text("window.JACKSON = " + json.dumps(bundle, ensure_ascii=False) + ";\n")
    for old in OUT.glob("*-sheet*"):        # superseded by the layered format
        old.unlink()
    (OUT / "mascot-data.js").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
