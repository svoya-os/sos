# SOS — Design System

Approved direction (2026-09-24): **Graphite** (dark, amber signal) + **Paper** (light, ink blue) as one
brand's night/day pair; **Phosphor** (green CRT) as an optional "era" theme.
Reference renders: `design/out/desktop-graphite.png`, `desktop-paper.png`, `desktop-phosphor.png`.
Tokens: `themes/*.toml` (single source of truth).

## 1. Principles

1. **Quiet by default, alive on demand.** Calm surfaces. Motion, glow and color appear only when something
   happens (Jackson listens, a job runs, a warning needs attention).
2. **Matte, not glass.** No blur, no translucency. Solid graphite or paper, 1px hairlines, a faint grain on
   the wallpaper only. This is our deliberate difference from Apple's Liquid Glass.
3. **Type carries the brand.** IBM Plex Sans for reading, IBM Plex Mono for system facts, Departure Mono
   (pixel) only for tiny labels, boot and POST screens.
4. **One signal.** One accent color per theme. Amber (Graphite), ink blue (Paper), phosphor green (Phosphor).
   Everything else is neutral. Semantic colors (ok/warn/bad/cloud) only for state.
5. **Retro in the details, not in the chrome.** The Morse mark `··· ——— ···`, the oscilloscope trace,
   mono metadata lines, keycaps, the colophon. Never bevels, neon overload or fake CRT on text.
6. **Honest status.** The user always sees: which model answered, local or cloud, what it cost, whether data
   left the machine, what an agent is doing, how to undo it.
7. **Keyboard-first, mouse-complete.** Every action has a shortcut; every action is also clickable.

## 2. Typography

| Role | Font | Size / line | Weight | Use |
|---|---|---|---|---|
| Display | Plex Sans | 96/100 | 300 | lock & greeter clock (tabular figures) |
| Title | Plex Sans | 20/28 | 400 | Jackson input, launcher query |
| Heading | Plex Sans | 16/22 | 500 | panel headings, wizard step titles (28/34 in wizard) |
| Body | Plex Sans | 14/22 | 400 | answers, notifications, settings text |
| UI | Plex Sans | 13/18 | 400–500 | buttons (500), list rows, window titles (12.5) |
| System | Plex Mono | 11.5/1 | 500 | the bar |
| Meta | Plex Mono | 11/16 | 400 | metadata lines, table cells, hints |
| Pixel | Departure Mono | 11 / 22 / 33 | 400 | tiny labels, POST screen, boot; only at multiples of 11px |

Rules: letter-spacing 0 for sans (−0.005em at ≥ 20px); mono uppercase labels use +0.14em tracking.
Never pixel font for body text. Minimum text size 11px.

## 3. Space, shape, elevation

* 4px grid: 4 · 8 · 12 · 16 · 18 · 24 · 32 · 48.
* Radii: windows 11 · floating panels (Jackson, launcher, control center) 16 · buttons 9 · chips pill ·
  keycaps 5 · small controls 6.
* Borders: 1px `line` inside surfaces; floating panels use `lineStrong`; floating panels get a thin accent
  highlight on the top edge (horizontal gradient transparent → accent → transparent, 55% opacity, inset 88px).
* Shadows: one soft, large shadow per level (see `shadow` token); nothing else.
* Bar: 30px, flush to the top edge, solid `bar` color, 1px bottom `line`.

## 4. Motion

* Durations 120 / 180 / 260 ms, easing OutCubic. No bounce, no overshoot.
* Panels open: opacity 0→1 + scale 0.985→1 + translateY −6→0 (180 ms). Close: 120 ms.
* **CRT warm-up** (signature, Jackson only): the scope starts as a centered dot, stretches to a line (160 ms),
  then the waveform fades in (100 ms).
* Scope states: idle = flat line breathing (opacity 0.35↔0.6 at 0.2 Hz) · listening = live mic level ·
  thinking = slow travelling sine · working = Lissajous-like figure · speaking = follows TTS envelope ·
  error = collapses to a dot.
* `reduce motion` (setting) → all durations 0, scope static.

## 5. Components

### Bar (30px)
Left → right: **Morse mark** (dots/dashes 3.2px high, the `———` in accent; opens the СОС menu) ·
**workspaces** (19×19 squares, radius 5; active = accent fill + accentInk text; occupied = textDim;
empty = textFaint) · **window title** (Plex Sans 12.5, app name `text`, `/` separator `textFaint`, detail `textDim`).
Right: **job** (dot + label + 34×4 meter + %) · **GPU** (`GPU 64° · 11,2/24 ГБ`) · icons (network, volume,
battery; 15px, 1.5px stroke) · keyboard layout (`RU`) · **Jackson mini-scope** (22×10; tinted chip when
Jackson is active) · clock (`Чт 24 сен` dim + `18:42` text).
Segments hide gracefully when data is missing (no GPU → no GPU segment).

### Window decorations (Hyprland + hyprbars)
36px title bar, `surface` color, 1px bottom `line`; title left-aligned (Plex Sans 12.5; app name 500 +
detail `textDim`); buttons right: three 14px circles in `surface3` with 8px glyphs (minimize, maximize, close).
Border 1px `line`, radius 11, inactive windows keep the same colors (no dimming), active window border
`lineStrong`. Tiled layouts ("Hacker" preset) hide title bars and use a 1px accent border for the active window.

### Jackson panel (Super+J)
Width 704, top 118px, centered, radius 16, `surface2`, `lineStrong` border, top accent highlight.
Head: scope (92×22, glow in dark themes) · "Джексон" (Plex Sans 13/500) · route chip (`локально · qwen3.5-14b`
with ok-dot; cloud route uses `cloud` dot and names the provider) · keycaps `Super` `J`.
Input: Plex Sans 20, 2px accent caret. Answer: Plex Sans 14.2/1.6 Markdown; tables in Plex Mono 12 inside a
bordered 10px-radius block; actions: primary (accent fill) + secondary (outline).
Footer (40px, mono 11, `textFaint`): `latency · tokens · cost € · local/cloud statement` left, keycap hints right.
Approval requests appear inline as a card with the exact preview and three buttons:
`Разрешить один раз` · `Всегда в этом проекте` · `Отклонить`.

### Launcher (Super+Space)
Same shell as Jackson (width 640, radius 16), input "Найти приложение, файл, настройку… (? — спросить Джексона)".
Rows 40px: 20px icon, name (Plex Sans 13.5), secondary (mono 11 `textFaint`), right-aligned keycap for the top hit.
Groups with mono uppercase captions (`ПРИЛОЖЕНИЯ`, `ФАЙЛЫ`, `НАСТРОЙКИ`, `МОДУЛИ`, `ДЕЙСТВИЯ`).
Typing `?` or pressing Tab on a query hands it to Jackson.

### Notifications
Toast 330px, top-right (right 18, top 44), radius 12, `surface2`, `line` border. Head: mono 11 app name +
time; body Plex Sans 13/1.5; up to two actions as small buttons. Jackson notifications carry the mini-scope.
Notification center lives inside the control center.

### Control center (click on status icons)
Dropdown 380px from the right under the bar. Blocks: Wi-Fi · Bluetooth · Sound (slider) · Brightness ·
Theme (Графит / Бумага / Авто) · Focus mode (Работа · Обучение · Презентация) · **AI & privacy**
(local/cloud route, today's spend, "data left the machine today: N requests") · notification list.

### Lock screen and greeter
Full screen wallpaper (with the signal line), centered big clock (Display style) and date (mono),
user row (avatar circle 40px, name), password field (320px, radius 9, `surface2`), Morse mark at the bottom.
Greeter adds session/user switchers as mono text buttons.

### POST screen (first second after login)
Full-screen `wall` color, Departure Mono 11/22 lines appearing one by one (30 ms each), real data:
```
SOS 26.10  ··· ——— ···
ЦП   Ryzen 9 7950X · 16 ядер
ГП   RTX 4090 · драйвер 595.58 · 24 ГБ
ОЗУ  64 ГБ · диск 1,8 ТБ свободно
ДЖЕКСОН  qwen3.5-14b готов · локально
```
then a 180 ms fade to the desktop. Can be disabled.

### First-run wizard (≤ 7 steps, each skippable, every choice reversible)
0 Accessibility (always reachable with Super+Alt+A) · 1 Language & keyboard · 2 Look (Graphite / Paper /
Auto / Phosphor with live preview) · 3 Layout (Clean floating · Classic taskbar · Hacker tiling) ·
4 Profile (Newcomer · Creator · ML Engineer · Agent Builder · Hacker, + "Offline only" modifier) ·
5 AI (GPU detected, suggested local model that fits, optional cloud keys) · 6 Privacy summary + first snapshot
+ shortcut cheat sheet.

## 6. Iconography
Line icons, 1.5px stroke, round caps/joins, 15–16px in bars, 20px in lists. Use **Lucide** (ISC) as the base
set; custom glyphs (Morse mark, scope, Jackson) follow the same stroke rules. App icons: Papirus (GPL-3.0) for
coverage until our own set exists.

## 7. Sound
Soft, short, synthesized (no samples): startup = the Morse `··· ——— ···` as sine blips (≈1.8 s, −18 LUFS);
notification = one soft tick; Jackson listen = rising two-note blip; Jackson done = falling blip;
error = low double blip. freedesktop sound naming. Startup sound can be disabled in the wizard.

## 8. Copy (RU/EN)
Short, calm, concrete. Lowercase labels in the bar (`обучение 62%`), sentence case elsewhere.
Numbers use the locale (Russian: `11,2 ГБ`, thin spaces in thousands). Never nag, never "Oops!".
Jackson speaks in the second person informal (`ты`) in Russian by default (setting: `вы`).

## 9. Accessibility
WCAG AA for all text tokens (checked). Focus ring: 2px accent outline, 2px offset. Reduce-motion and
high-contrast variants of every theme. Everything reachable by keyboard; nothing requires a chord.
