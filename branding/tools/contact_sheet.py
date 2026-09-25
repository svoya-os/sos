#!/usr/bin/env python3
"""One review sheet for the whole SOS brand kit → branding/out/contact-sheet.png.

    python3 branding/tools/contact_sheet.py        (run the generators first; build.sh does)

SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import html
import json
import re
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import brand  # noqa: E402

B = brand.BRANDING
G = brand.theme("graphite")["color"]
P = brand.theme("paper")["color"]
F = brand.theme("phosphor")["color"]
U = lambda p: pathlib.Path(p).resolve().as_uri()  # noqa: E731


def swatches(theme_id: str, keys) -> str:
    c = brand.theme(theme_id)["color"]
    items = []
    for k in keys:
        v = c[k]
        hexv = "#" + v[-6:] if len(v) == 9 else v
        items.append(f'<div class="sw"><i style="background:{hexv}"></i><b>{k}</b><span>{hexv}</span></div>')
    return "".join(items)


def main() -> None:
    lock = [("horizontal-ru", 1.0), ("horizontal-en", 1.0), ("stacked-ru", 0.8), ("stacked-en", 0.8)]
    logos_dark = "".join(f'<div class="lg"><img src="{U(B / "logo/svg" / f"sos-lockup-{n}-on-dark.svg")}" style="height:{int(56 * k) if n.startswith("h") else 88}px"></div>' for n, k in lock)
    logos_light = "".join(f'<div class="lg"><img src="{U(B / "logo/svg" / f"sos-lockup-{n}-on-light.svg")}" style="height:{int(56 * k) if n.startswith("h") else 88}px"></div>' for n, k in lock)
    marks = (f'<div class="lg"><img src="{U(B / "logo/svg/sos-mark-on-dark.svg")}" style="width:300px"></div>'
             f'<div class="lg"><img src="{U(B / "logo/svg/sos-mark-folded-on-dark.svg")}" style="height:64px"></div>'
             f'<div class="lg"><img src="{U(B / "logo/svg/sos-mark-mono-white.svg")}" style="width:300px;opacity:.9"></div>')
    icons = "".join(
        f'<figure><div class="ic" style="width:{max(n, 16)}px;height:{max(n, 16)}px">'
        f'<img src="{U(B / "logo/icon/png" / f"sos-{n}.png")}" style="width:{n}px;height:{n}px;image-rendering:pixelated"></div>'
        f'<figcaption>{n}</figcaption></figure>' for n in [16, 24, 32, 48, 64, 128, 256])
    icons_light = "".join(
        f'<img src="{U(B / "logo/icon/png" / f"sos-{n}.png")}" style="width:{n}px;height:{n}px;image-rendering:pixelated">'
        for n in [16, 24, 32, 48, 64])
    walls = "".join(
        f'<figure><img class="wp" src="{U(B / "wallpapers" / t / f"signal-{t}-2880x1800.png")}">'
        f'<figcaption>signal · {t} · 1920×1080 · 2560×1440 · 2880×1800 · 3840×2160 · + lock</figcaption></figure>'
        for t in ["graphite", "paper", "phosphor"])
    frames_meta = [("1-power-on", "0,10 с · пятно"), ("2-warm-up", "0,52 с · линия"), ("3-boot-24", "загрузка 24 %"),
                   ("4-boot-71-message", "71 % · сообщение"), ("5-unlock", "ключ диска"), ("6-shutdown", "выключение")]
    frames = "".join(
        f'<figure><div class="frc"><img src="{U(B / "plymouth/frames" / f"frame-{n}.png")}"></div><figcaption>{i + 1} · {html.escape(c)}</figcaption></figure>'
        for i, (n, c) in enumerate(frames_meta))
    sounds = json.loads((B / "sounds/measurements.json").read_text(encoding="utf-8"))
    sound_rows = "".join(f'<tr><td>{k}</td><td>{v["seconds"]:.2f} s</td><td>{v["lufs"]:.1f}</td><td>{v["truePeakDb"]:.1f}</td></tr>'
                         for k, v in sounds.items())
    logo_txt = (B / "fastfetch/logo.txt").read_text(encoding="utf-8").splitlines()
    def ff_line(line: str) -> str:
        out, color = [], "d"
        for part in re.split(r"(\$[12])", line):
            if part in ("$1", "$2"):
                color = "d" if part == "$1" else "a"
            elif part:
                out.append(f'<span class="{color}">{html.escape(part)}</span>')
        return "".join(out)
    ff_logo = "\n".join(ff_line(line) for line in logo_txt)
    ff_info = ("<b>user@sos</b>\n\n<i>система</i>  SOS 26.10 «Первый сигнал»\n<i>ядро</i>     6.17.0-9-generic\n"
               "<i>оболочка</i> Hyprland · Svoya Shell\n\n<i>гп</i>       RTX 4090 · 24 ГБ\n<i>озу</i>      64 ГБ")

    doc = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>
{brand.font_face_css()}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ width: 2400px; background: {G['wall']}; color: {G['text']}; font: 400 15px/1.5 "Plex Sans";
       -webkit-font-smoothing: antialiased; padding: 72px 80px 80px; }}
h1 {{ font: 600 30px/1.2 "Plex Sans"; letter-spacing: -.005em; display: flex; align-items: center; gap: 22px; }}
h1 img {{ height: 11px; }}
.sub {{ font: 400 12px/1.6 "Plex Mono"; letter-spacing: .14em; text-transform: uppercase; color: {G['textFaint']}; margin: 10px 0 48px; }}
h2 {{ font: 500 11px/1 "Plex Mono"; letter-spacing: .16em; text-transform: uppercase; color: {G['textDim']};
     border-top: 1px solid {G['line']}; padding-top: 18px; margin: 44px 0 22px; display: flex; justify-content: space-between; }}
h2 span {{ color: {G['textFaint']}; letter-spacing: .08em; }}
.row {{ display: flex; gap: 20px; align-items: stretch; }}
.panel {{ border-radius: 11px; padding: 34px 40px; display: flex; gap: 56px; align-items: center; flex-wrap: wrap; }}
.dark {{ background: {G['wall']}; border: 1px solid {G['line']}; }}
.light {{ background: {P['wall']}; border: 1px solid {P['line']}; }}
.lg img {{ display: block; }}
figure {{ display: flex; flex-direction: column; gap: 10px; }}
figcaption {{ font: 400 11px/1.4 "Plex Mono"; letter-spacing: .06em; color: {G['textFaint']}; }}
.ic {{ display: grid; place-items: end start; }}
.icons {{ display: flex; gap: 34px; align-items: flex-end; }}
.wp {{ width: 733px; border-radius: 9px; border: 1px solid {G['line']}; display: block; }}
.frc {{ width: 733px; height: 412px; overflow: hidden; position: relative; border-radius: 9px; border: 1px solid {G['line']}; }}
.frc img {{ position: absolute; width: 977px; left: -122px; top: -127px; }}
.grid3 {{ display: grid; grid-template-columns: repeat(3, 733px); gap: 30px 20px; }}
.grub {{ width: 1120px; border-radius: 9px; border: 1px solid {G['line']}; display: block; }}
.term {{ width: 1100px; background: {G['surface']}; border: 1px solid {G['line']}; border-radius: 11px; overflow: hidden; }}
.term .bar {{ height: 36px; border-bottom: 1px solid {G['line']}; font: 400 12.5px/36px "Plex Sans"; color: {G['textDim']}; padding: 0 14px; }}
.term .bar b {{ color: {G['text']}; font-weight: 500; margin-right: 9px; }}
.term pre {{ font: 400 14px/1.6 "Plex Mono"; padding: 22px 26px; color: {G['text']}; display: grid; grid-template-columns: auto 1fr; gap: 48px; white-space: pre; }}
.term pre > span {{ white-space: pre; }}
.term .a {{ color: {G['accent']}; }} .term i {{ font-style: normal; color: {G['accent']}; }} .term .d {{ color: {G['text']}; }}
table {{ border-collapse: collapse; font: 400 12.5px/1 "Plex Mono"; color: {G['textDim']}; }}
td {{ padding: 7px 26px 7px 0; border-bottom: 1px solid {G['line']}; }}
td:first-child {{ color: {G['text']}; }}
.sws {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
.swc {{ border: 1px solid {G['line']}; border-radius: 11px; padding: 22px 24px; }}
.swc h3 {{ font: 500 14px/1 "Plex Sans"; margin-bottom: 16px; }}
.swc.paper .sw {{ color: {P['textDim']}; }} .swc.paper .sw b {{ color: {P['text']}; }} .swc.paper .sw i {{ border-color: {P['lineStrong']}; }}
.sw {{ display: grid; grid-template-columns: 26px 110px 1fr; align-items: center; gap: 10px; font: 400 12px/2 "Plex Mono"; color: {G['textDim']}; }}
.sw i {{ width: 22px; height: 16px; border-radius: 4px; border: 1px solid {G['lineStrong']}; }}
.sw b {{ font-weight: 400; color: {G['text']}; }}
.foot {{ margin-top: 48px; font: 400 11px/1.6 "Plex Mono"; letter-spacing: .1em; text-transform: uppercase; color: {G['textFaint']}; }}
</style></head><body>
<h1><img src="{U(B / 'logo/svg/sos-mark-on-dark.svg')}" alt="">SOS · brand kit</h1>
<div class="sub">{brand.NAME_RU} — {brand.TAGLINE_RU} · {brand.NAME} — {brand.TAGLINE_EN} · {brand.VERSION} «{brand.CODENAME_RU}» · branding/</div>

<h2>Logo · lockups <span>branding/logo/svg · on-dark / on-light / mono · text as outlines (IBM Plex Sans SemiBold)</span></h2>
<div class="panel dark">{logos_dark}</div>
<div style="height:16px"></div>
<div class="panel light">{logos_light}</div>
<div style="height:16px"></div>
<div class="panel dark">{marks}</div>

<h2>Icon · sos <span>branding/logo/icon · softly rounded square, circular corners · mark folded С / О / С · pixel-snapped ≤ 48</span></h2>
<div class="row"><div class="panel dark" style="flex:1"><div class="icons">{icons}</div></div>
<div class="panel light" style="width:520px"><div class="icons" style="gap:22px">{icons_light}</div></div></div>

<h2>Wallpapers · «Сигнал» <span>branding/wallpapers · identical to the approved mockup at 2880×1800</span></h2>
<div class="grid3">{walls}</div>

<h2>Plymouth · svoya-signal <span>branding/plymouth · preview.html frames; the same states rendered by plymouth's own script engine match within 5/255</span></h2>
<div class="grid3">{frames}</div>

<h2>GRUB · svoya <span>branding/grub · countdown fills the horizon toward the burst · fonts via make-fonts.sh</span></h2>
<div class="row" style="gap:40px;align-items:flex-start">
  <img class="grub" src="{U(B / 'grub/preview.png')}">
  <div style="display:flex;flex-direction:column;gap:28px">
    <div class="term"><div class="bar"><b>Терминал</b>fastfetch</div><pre><span>{ff_logo}</span><span>{ff_info}</span></pre></div>
    <table>{sound_rows}</table>
  </div>
</div>

<h2>Color <span>themes/*.toml — the only source of truth</span></h2>
<div class="sws">
  <div class="swc"><h3>Graphite · night</h3>{swatches('graphite', ['wall', 'surface', 'surface2', 'line', 'text', 'textDim', 'accent', 'accentInk'])}</div>
  <div class="swc paper" style="background:{P['wall']};border-color:{P['line']}"><h3 style="color:{P['text']}">Paper · day</h3>{swatches('paper', ['wall', 'surface', 'surface2', 'line', 'text', 'textDim', 'accent', 'accentInk'])}</div>
  <div class="swc" style="background:{F['wall']}"><h3>Phosphor · era</h3>{swatches('phosphor', ['wall', 'surface', 'surface2', 'line', 'text', 'textDim', 'accent', 'accentInk'])}</div>
</div>
<div class="foot">artwork CC BY-SA 4.0 · code Apache-2.0 · IBM Plex (SIL OFL 1.1, RFN “Plex”) · Departure Mono (MIT)</div>
</body></html>"""
    page_h = 5200
    out = brand.OUT / "contact-sheet.png"
    with brand.Renderer() as r:
        page = r.page(2400, page_h, 1)
        tmp = brand.write(brand.OUT / ".contact-sheet.html", doc)
        page.goto(tmp.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        h = page.evaluate("document.body.scrollHeight")
        page.set_viewport_size({"width": 2400, "height": h})
        page.screenshot(path=str(out), full_page=True)
        page.context.close()
        tmp.unlink()
    print(brand.rel(out), h, "px tall")


if __name__ == "__main__":
    main()
