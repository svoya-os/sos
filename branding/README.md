# SOS brand kit — `branding/`

**SOS** (English) / **«СОС»** (Russian) — *Svoya Operating System / Своя Операционная Система*.
The mark is Morse `··· ——— ···`: S O S in international Morse and С О С in Russian Morse. It is the same
signal in both alphabets. The brand's own signal is amber `#ffb547` on Graphite and ink blue `#2b3af7`
on Paper. In the OS the accent is the user's choice (`themes/accents.toml`, design/DESIGN.md §10–§11).
**Pre-login surfaces are neutral** (§12): GRUB, Plymouth and the console use only Graphite `text`
`#ebe8e1`, `textDim` `#9d9a92` and `textFaint` `#67655f`. They can never clash with the accent a
user picks.

Everything here is generated from code plus `themes/*.toml`, the only source of color truth. Review it
all at once in [`out/contact-sheet.png`](out/contact-sheet.png).

## Inventory

```
branding/
├── build.sh                    regenerate everything (below)
├── tools/brand.py              shared: tokens, Morse geometry, Plex outlines → SVG paths, Chromium renderer
├── tools/contact_sheet.py      → out/contact-sheet.png
├── logo/generate.py
│   ├── svg/sos-<piece>-<variant>.svg   piece: mark · mark-folded · wordmark-ru («СОС») · wordmark-en (SOS)
│   │                                   · lockup-horizontal-{ru,en} · lockup-stacked-{ru,en}
│   │                                   variant: on-dark · on-light · mono-black · mono-white
│   └── icon/sos.svg · sos-symbolic.svg · src/sos-<n>.svg · png/sos-{16,24,32,48,64,128,256,512}.png
├── wallpapers/generate.py      «Сигнал»: {graphite,paper,phosphor}/signal-<theme>[-lock]-<W>x<H>.png
│   │                           desktop = theme accent (the approved mockup) · lock = neutral · --accent <id|#hex>
│   └── wallpapers.json         index (id, theme, variant, accent, sizes, author, license)
├── plymouth/
│   ├── svoya-signal/           the theme (neutral): .plymouth, .script, 37 PNG sprites
│   ├── generate.py             sprites + the script's geometry block + preview frames
│   ├── preview.html            JS simulation of the script (interactive; keys in the file header)
│   ├── frames/frame-*.png      6 key frames from preview.html · engine-*.png from plymouth's own engine
│   └── harness/                builds plymouth 24.004's script engine headless and runs the theme (test only)
├── grub/
│   ├── svoya/                  theme.txt (ru) · theme-en.txt · PNG assets, neutral (fonts come from make-fonts.sh)
│   ├── generate.py · make-fonts.sh · default-grub.cfg · preview.png · preview-en.png
├── sounds/
│   ├── svoya/index.theme · svoya/stereo/*.oga   freedesktop sound theme, 17 sounds
│   ├── generate.py · measurements.json · README.md (listening sheet)
├── os/root/…                   os-release · lsb-release · upstream-release/lsb-release · issue · issue.net · motd
├── os/generate.py · os/README.md (why ID_LIKE, codenames, LOGO)
├── fastfetch/config.jsonc · fastfetch/logo.txt
└── out/                        review renders: contact sheet, logo previews, plymouth strip, grub preview
```

## Regenerate

```sh
branding/build.sh            # all generators in order, then the contact sheet (≈ 3 min)
python3 branding/logo/generate.py
python3 branding/wallpapers/generate.py [graphite|paper|phosphor] [1920x1080 …]
python3 branding/wallpapers/generate.py --accent lilac --out DIR [--variant desktop|lock|both]   # user accent
python3 branding/plymouth/generate.py [--no-frames]
python3 branding/grub/generate.py
python3 branding/sounds/generate.py
python3 branding/os/generate.py
python3 branding/tools/contact_sheet.py
branding/plymouth/harness/build.sh && branding/plymouth/harness/run.sh     # optional engine check
```

Requirements: Python ≥ 3.11 with Pillow, numpy, scipy, fontTools and Playwright (Chromium); ffmpeg with
libvorbis. Fonts are read from `design/fonts/` and never copied into `branding/`. Outputs are
deterministic, apart from Chromium's anti-aliasing and dither noise (±2/255).

## The mark and the name

* **Mark** `··· ——— ···`: dots and dashes are fully rounded rectangles of one height *d*. The dash is
  2.5 *d*, the gap between symbols 0.75 *d*, the gap between letters 1.75 *d*, so the whole mark is
  21.5 *d* wide (the same proportions as the shell bar). The dots use the ink color and the dashes use the
  signal color.
* **Folded mark** (icon, avatars, favicons): the same nine symbols in three lines, С / О / С. Dots sit
  centred over the dashes, and rows are 1.25 *d* apart.
* **Wordmarks**: «СОС» (Cyrillic) and SOS (Latin), IBM Plex Sans SemiBold with +0.20 em tracking, drawn as
  outlines. Taglines: «Своя Операционная Система» / "Svoya Operating System", set in text, not locked up.
* **Lockups**. Horizontal: *d* = 0.18 × cap height, and the mark sits 0.62 × cap height from the wordmark,
  centred on the cap height. Stacked: the mark is exactly as wide as the wordmark's ink, with a gap of
  0.46 × cap height.

### Clear space and minimum sizes

| element | clear space (all sides) | minimum on screen | minimum in print |
|---|---|---|---|
| linear mark | 2 *d* (one dash) | 44 px wide (*d* = 2 px) | 12 mm wide |
| horizontal lockup | 1 × cap height | 96 px wide | 25 mm wide |
| stacked lockup | 1 × cap height | 48 px wide | 14 mm wide |
| wordmark alone | 0.5 × cap height | 11 px cap height | 2 mm cap height |
| icon | its own tile margin | 16 px (use the pixel-snapped PNGs ≤ 48 px) | 5 mm |

### Do

* Use the SVGs as they are: `on-dark` on Graphite or any dark surface, `on-light` on Paper or light
  surfaces, and `mono-*` where only one color is possible (print, emboss, laser).
* In brand artwork, keep the dashes in the signal color and the dots in the ink color. Inside the OS the
  shell draws the mark live: in the user's accent while Jackson is active, otherwise in `text`
  (the accent budget, §11).
* Let the mark breathe: one signal per view. If the wallpaper burst is visible, do not add another mark
  next to it.
* Use the folded mark only where the linear one would be smaller than 44 px wide.

### Don't

* Don't put any accent on pre-login surfaces (GRUB, Plymouth, POST, console, `os-release` colors). They
  are neutral by rule (§12).
* Don't redraw the letters, change the tracking, or set «СОС»/SOS in another typeface or weight.
* Don't recolor the dots and dashes arbitrarily, add gradients, glass, bevels, outlines or drop shadows.
  The only glow allowed is the soft signal glow used by the dark themes.
* Don't change the rhythm (proportions, spacing, number of symbols), animate it with anything other than
  Morse timing, or rotate it.
* Don't put the mark on busy photos or low-contrast mid-tones. Don't put the icon tile inside another tile.
* Don't use an iOS-style squircle for the icon: its corners are plain circular arcs (radius 0.1875 of
  the tile).

## Color

Base themes come from `themes/*.toml`; accents come from `themes/accents.toml` (never duplicate them elsewhere):

| token | Graphite (night) | Paper (day) | Phosphor (era) |
|---|---|---|---|
| wall | `#0c0d0f` | `#e9e6de` | `#050806` |
| surface / surface2 | `#141518` / `#191b1f` | `#f8f7f3` / `#fdfcfa` | `#0b100d` / `#0f1611` |
| line / lineStrong | `#25282d` / `#363a41` | `#dcd8ce` / `#bfbab0` | `#1a261e` / `#2b3d31` |
| text / textDim / textFaint | `#ebe8e1` / `#9d9a92` / `#67655f` | `#151515` / `#5d5a54` / `#8e8a81` | `#d4f4dd` / `#85a68f` / `#56705e` |
| **accent (signal)** | **`#ffb547`** | **`#2b3af7`** | **`#5cf08f`** |
| accentInk | `#1b1204` | `#ffffff` | `#03140a` |

The icon tile is matte graphite, a gradient from `#1d1f23` to `#101114` with a `#2d3036` edge. Print
references (Pantone/CMYK) are not defined yet. The ink blue is outside the CMYK gamut, so pick spot
colors against a physical proof.

## Packaging map (for `svoya-branding`)

| from | to |
|---|---|
| `logo/icon/png/sos-<n>.png`, `logo/icon/sos.svg`, `sos-symbolic.svg` | `/usr/share/icons/hicolor/<n>x<n>/apps/sos.png`, `…/scalable/apps/sos.svg`, `…/symbolic/apps/sos-symbolic.svg` (`LOGO=sos`) |
| `logo/svg/*` | `/usr/share/svoya/branding/logo/` |
| `wallpapers/{graphite,paper,phosphor}/*`, `wallpapers.json` | `/usr/share/svoya/wallpapers/` (keep the sub-folders; the index uses relative paths) |
| `plymouth/svoya-signal/` | `/usr/share/plymouth/themes/svoya-signal/`, then `plymouth-set-default-theme svoya-signal` and rebuild the initrd |
| `grub/svoya/` + fonts from `grub/make-fonts.sh` | `/usr/share/grub/themes/svoya/`, copied by postinst to `/boot/grub/themes/svoya/`; `grub/default-grub.cfg` → `/etc/default/grub.d/90-sos-theme.cfg`; then `update-grub` |
| `sounds/svoya/` | `/usr/share/sounds/svoya/`, plus `/usr/share/svoya/sounds → ../../sounds/svoya` (ARCHITECTURE §3) |
| `os/root/**` | as laid out (see `os/README.md`) |
| `fastfetch/*` | `/usr/share/svoya/fastfetch/` |

Theme and file IDs stay in the technical `svoya` namespace (`svoya-signal`, `svoya`). The icon is the
exception: it is named `sos` because `os-release` says `LOGO=sos`.

### Plymouth: what the initrd must contain

* **Fonts.** The theme's `.plymouth` declares `TitleFont=IBM Plex Sans` and `MonospaceFont=IBM Plex Mono`.
  dracut's `plymouth-populate-initrd` copies those font files. With initramfs-tools, add a hook that
  copies `IBMPlexMono-Regular.ttf` and runs `fc-cache`, because Debian's hook only ships DejaVu. Every
  static text (wordmark, captions, CAPS LOCK) is a pre-rendered PNG, so only the password prompt and
  messages depend on fonts.
* **UTF-8 locale for Cyrillic.** dracut installs the `label-freetype` plugin, which decodes UTF-8 with
  `mbrtowc()` in plymouthd's locale. The harness shows that Cyrillic from `Image.Text` renders correctly
  under `LANG=C.UTF-8` and as boxes under `LANG=C`. So give plymouthd a UTF-8 locale in the initrd, for
  example `LC_ALL=C.UTF-8` (built into glibc, no locale files needed) through a drop-in for
  `plymouth-start.service`, or install `label-pango`. English prompts from cryptsetup are not affected.
* **Language.** `[script-env-vars] svoya_lang=ru|en` in `svoya-signal.plymouth` picks the caption
  sprites. The installer may rewrite it.
* **HiDPI.** Plymouth draws scale-1 sprites and upscales them when its device scale is 2, so the art
  stays the right size but a little soft. The script API does not expose the scale.

## Verification status

* **Rendered and checked visually:** all lockups and icons (16–512 px, zoomed pixel checks), 24
  wallpapers, 6 Plymouth frames, GRUB previews (ru/en) and the contact sheet. The 2880×1800 Graphite
  wallpaper matches `design/out/desktop-graphite.png` within 2/255 wherever the wallpaper is visible.
* **Plymouth, verified in its own engine:** `plymouth/harness` builds the script interpreter of
  plymouth 24.004.60 (parser, executor, image/sprite/math/string libraries, label-freetype) with a fake
  display. The theme parses and runs through every callback and mode. Its frames match `preview.html`
  within 6/255, apart from text rasterisation.
* **Neutrality:** no pixel in the Plymouth frames or the GRUB preview is more saturated than the `text`
  color itself (maximum channel spread ≤ 12). The default desktop wallpapers are byte-identical to the
  previous render. The lock wallpapers are neutral. The engine silently ignores calls to undefined
  functions, so the frame comparison is the real test.
* **Needs a real system:** the Plymouth theme on real DRM and initrd (dracut/initramfs-tools, LUKS
  prompt, HiDPI); `grub-mkfont` and the GRUB theme in real GRUB (the preview only emulates gfxmenu's
  layout rules); listening to the sounds on speakers and headphones; and fastfetch's rendering of the
  config (the JSONC is valid, but the keys have not been run through fastfetch).

## Licenses

* Artwork (logos, icons, wallpapers, Plymouth sprites, GRUB assets, sounds): **CC BY-SA 4.0**,
  © SOS contributors. Code (generators, the Plymouth script, configs): **Apache-2.0**.
* **IBM Plex** (© IBM Corp., SIL OFL 1.1, Reserved Font Name "Plex"): logo and wordmark text are drawn as
  outlines. That makes them artwork, not font software. The GRUB PFF2 fonts are a format conversion,
  which the OFL treats as a Modified Version, so they are named **"Svoya Mono"**. Ship the OFL text with them.
* **Departure Mono** (MIT, © Helena Zhang & Tobias Fried): referenced by the design system and not used
  in these assets.
* `plymouth/harness/` links GPL-2.0-or-later Plymouth sources, which it clones at build time from
  `github.com/deepin-community/plymouth` (Debian packaging of 24.004.60). It is a test tool and is not
  shipped. Its own files are GPL-2.0-or-later.
* Nothing else third-party is embedded. The sounds are synthesized, and the GRUB and Plymouth APIs were
  checked against upstream sources (`rhboot/grub2`, plymouth 24.004).
