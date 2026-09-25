#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cross-check the shell's color and mascot JavaScript against their references.

1. components/Sprite.js (the shell's port of the mascot renderer) must compose the same 32×32 grids
   and palettes as design/mascot/jackson.js for every option combination, state, accent and mode.
2. core/Color.js (hover preview, «Свой…» contrast badge) must resolve accents exactly like the CLI
   (cli/svoya_cli/theme/accents.py: OKLCH lightness fit to 4.5:1 against `surface`, soft alpha,
   strong ±6 %, ink) on every base theme, and carry the same eight accents as themes/accents.toml.

Needs `node`. Usage: python3 shell/tools/check_mascot.py   (exit 1 on any difference)
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "shell"

CUSTOM = ["#ffcc00", "#7b61ff", "#d64fd8", "#c2410c", "#101010", "#fafafa", "#00ff00", "#2b3af7", "#777777"]

NODE = r"""
const fs = require('fs'), vm = require('vm');
const [shell, design, jobs] = process.argv.slice(-3);
function lib(path, ctx) {
  const src = fs.readFileSync(path, 'utf8').split('\n')
    .filter(l => !l.startsWith('.pragma') && !l.startsWith('.import')).join('\n');
  vm.runInContext(src, ctx);
}
const base = () => ({ Math, parseInt, parseFloat, String, Array, Object, JSON, Number, isNaN });
const C = vm.createContext(base());
lib(shell + '/core/Color.js', C);
const S = vm.createContext(Object.assign(base(), { Color: C }));
lib(shell + '/components/Sprite.js', S);
const ref = { window: {} };
vm.runInNewContext(fs.readFileSync(design + '/mascot/jackson.js', 'utf8'), ref);
const R = ref.window.JacksonSprite;
const out = { comparisons: 0, differences: [], accents: C.ACCENTS, resolved: [] };
for (const ch of ['imp', 'cat']) {
  const data = JSON.parse(fs.readFileSync(`${shell}/assets/jackson/${ch}.json`, 'utf8'));
  const o = data.options;
  for (const skin of o.skin) for (const style of o.style) for (const glasses of o.glasses)
    for (const headphones of o.headphones) for (const hood of (o.hood || [true])) {
      const opts = { skin, style, glasses, headphones, hood };
      for (const state of Object.keys(data.states)) {
        const a = R.compose(data, opts, state).map(r => r.map(k => k === null ? '.' : k).join(''));
        const b = S.compose(data, opts, state);
        out.comparisons++;
        if (JSON.stringify(a) !== JSON.stringify(b)) out.differences.push({ what: 'grid', ch, opts, state });
      }
    }
  for (const skin of o.skin) for (const outfit of ['accent', 'lilac', 'mono', '#7b61ff', '#c2410c'])
    for (const acc of ['signal', 'amber', 'ice', 'rose', 'mono', '#7b61ff', '#ffcc00'])
      for (const mode of ['dark', 'light']) for (const state of Object.keys(data.states)) {
        const opts = { skin, outfit };
        const a = R.palette(data, opts, state, mode, acc), b = S.palette(data, opts, state, mode, acc);
        const norm = p => JSON.stringify(Object.keys(p).sort().map(k => [k, String(p[k]).toLowerCase()]));
        out.comparisons++;
        if (norm(a) !== norm(b)) out.differences.push({ what: 'palette', ch, opts, state, mode, acc });
      }
}
for (const j of JSON.parse(jobs)) out.resolved.push(Object.assign({ job: j }, C.resolveAccent(j.choice, j.mode, j.surface)));
process.stdout.write(JSON.stringify(out));
"""


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("check_mascot: node is not installed", file=sys.stderr)
        return 2
    sys.dont_write_bytecode = True  # never leave .pyc files in the CLI's tree
    sys.path.insert(0, str(ROOT / "cli"))
    from svoya_cli.theme import accents as cli_accents  # noqa: PLC0415
    from svoya_cli.theme.colors import Color  # noqa: PLC0415

    catalog = tomllib.loads((ROOT / "themes" / "accents.toml").read_text(encoding="utf-8"))
    ids = [k for k, v in catalog.items() if isinstance(v, dict) and "dark" in v]
    themes = {}
    for t in ("graphite", "paper", "phosphor"):
        d = tomllib.loads((ROOT / "themes" / f"{t}.toml").read_text(encoding="utf-8"))
        themes[t] = (d.get("mode", "dark"), d["color"]["surface"])

    jobs = [{"theme": t, "mode": m, "surface": s, "choice": c}
            for t, (m, s) in themes.items() for c in ids + CUSTOM]
    res = subprocess.run([node, "-e", NODE, str(SHELL), str(ROOT / "design"), json.dumps(jobs)],
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        return 1
    out = json.loads(res.stdout)
    problems: list[str] = []

    for d in out["differences"][:20]:
        problems.append(f"sprite {d['what']} differs: {json.dumps(d, ensure_ascii=False)}")
    if len(out["differences"]) > 20:
        problems.append(f"… {len(out['differences']) - 20} more sprite differences")

    js_accents = {a["id"]: a for a in out["accents"]}
    if list(js_accents) != ids:
        problems.append(f"Color.js accents {list(js_accents)} != accents.toml {ids}")
    for aid in ids:
        a = js_accents.get(aid)
        if a and (a["dark"].lower() != catalog[aid]["dark"].lower() or a["light"].lower() != catalog[aid]["light"].lower()):
            problems.append(f"Color.js {aid}: {a['dark']}/{a['light']} != accents.toml {catalog[aid]['dark']}/{catalog[aid]['light']}")

    for r in out["resolved"]:
        j = r["job"]
        surface = Color.parse(j["surface"]).with_alpha(1.0)
        requested = Color.parse(catalog[j["choice"]][j["mode"]] if j["choice"] in catalog else j["choice"])
        color, adjusted = cli_accents.fit_contrast(requested, surface)
        want = {
            "color": color.hex.lower(),
            "adjusted": adjusted,
            "soft": color.with_alpha(cli_accents.SOFT_ALPHA["light" if j["mode"] == "light" else "dark"]).hexa.lower(),
            "strong": cli_accents.strong_variant(color, j["mode"]).hex.lower(),
            "ink": color.ink().hex.lower(),
        }
        got = {"color": r["color"].lower(), "adjusted": r["adjusted"], "soft": r["soft"].lower(),
               "strong": r["strong"].lower(), "ink": r["ink"].lower()}
        # QML colors are #AARRGGBB; the CLI's hexa is #RRGGBBAA or #AARRGGBB — compare as sets of bytes
        if want["soft"] != got["soft"] and not (len(want["soft"]) == 9 and want["soft"][7:] + want["soft"][1:7] == got["soft"][1:]):
            problems.append(f"{j['theme']} {j['choice']}: soft {got['soft']} != CLI {want['soft']}")
        for k in ("color", "adjusted", "strong", "ink"):
            if want[k] != got[k]:
                problems.append(f"{j['theme']} {j['choice']}: {k} {got[k]} != CLI {want[k]}")

    for p in problems:
        print("check_mascot:", p)
    print(f"check_mascot: {out['comparisons']} sprite comparisons, {len(out['resolved'])} accent resolutions, "
          f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
