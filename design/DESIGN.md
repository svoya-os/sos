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
4. **One signal.** One accent color, chosen by the user (§10), used sparingly (§11 accent budget). The brand
   default «Сигнал» is amber by night and ink blue by day; Phosphor defaults to phosphor green.
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
  highlight on the top edge (horizontal gradient transparent → accent → transparent, 55% opacity, inset 88px) — only the live Jackson panel
  keeps it; every other floating panel uses a neutral edge.
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
Left → right: **Morse mark** (dots/dashes 3.2px high, `text` color; the `———` light up in accent only while
Jackson listens or works; opens the СОС menu) ·
**workspaces** (19×19 squares, radius 5; active = `text` fill + `surface` text (neutral); occupied = textDim;
empty = textFaint) · **window title** (Plex Sans 12.5, app name `text`, `/` separator `textFaint`, detail `textDim`).
Right: **job** (dot + label + 34×4 meter + %) · **GPU** (`GPU 64° · 11,2/24 ГБ`) · icons (network, volume,
battery; 15px, 1.5px stroke) · keyboard layout (`RU`) · **Jackson mini-scope** (22×10; tinted chip when
Jackson is active) · clock (`Чт 24 сен` dim + `18:42` text).
Segments hide gracefully when data is missing (no GPU → no GPU segment).

### Window decorations (Hyprland + hyprbars)
36px title bar, `surface` color, 1px bottom `line`; title left-aligned (Plex Sans 12.5; app name 500 +
detail `textDim`); buttons right: three 14px circles in `surface3` with 8px glyphs (minimize, maximize, close).
Border 1px `line`, radius 11, inactive windows keep the same colors (no dimming), active window border
`lineStrong`. Tiled layouts ("Hacker" preset) hide title bars and use a 1px `textDim` border for the active window.

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
WCAG AA for all text tokens and every accent variant (checked). Focus ring: 2px `text` outline at 70%, 2px offset
(text fields: 1px `text` border + 3px `line` halo). Reduce-motion and
high-contrast variants of every theme. Everything reachable by keyboard; nothing requires a chord.


## 10. Accent system (user-chosen color)

The accent is independent from the base theme (Graphite / Paper / Phosphor). Canonical data: `themes/accents.toml`.
Every accent has a dark-base and a light-base variant; both pass WCAG AA against surfaces (≥ 5:1) and for
text on the accent fill (`accentInk`, ≥ 5.4:1).

| id | RU | dark base | light base | ink |
|---|---|---|---|---|
| `signal` (default) | Сигнал | `#ffb547` (amber) | `#2b3af7` (ink) | auto |
| `amber` | Янтарь | `#ffb547` | `#9a5200` | dark `#141518` · light `#ffffff` |
| `ink` | Чернила | `#8f9dff` | `#2b3af7` | ″ |
| `phosphor` | Фосфор | `#5cf08f` | `#0f7a3a` | ″ |
| `ice` | Лёд | `#62d4f2` | `#006f8e` | ″ |
| `lilac` | Сирень | `#bba4ff` | `#6a3fd6` | ″ |
| `rose` | Роза | `#ff82b2` | `#b8185a` | ″ |
| `mono` | Моно | `#ebe8e1` | `#151515` | ″ |
| custom | Свой | any hex → lightness adjusted in OKLCH (hue and chroma kept) until contrast ≥ 4.5:1 | | auto |

Derived tokens: `accentSoft` (dark 14% / light 9% alpha), `accentStrong` (hover/pressed: OKLCH lightness ±6%),
`accentInk` (near-black or white, whichever contrasts more).

How the user changes it (all live, 260 ms cross-fade, undoable):
* Control center → «Оформление»: base theme segmented control + 8 swatches + «Свой…» (hex field with live
  contrast badge). Two clicks from anywhere.
* First-run wizard, step «Оформление»: same controls with a live full-size preview.
* `sos theme accent <id|#hex>` (RU names accepted: `sos theme accent сирень`).
* Jackson: «сделай акцент фиолетовым» / "make the accent violet" (fast path, T1, undoable).
Everything follows at once: bar, panels, Jackson (scope + mascot outfit), window title-bar buttons on hover (hyprbars),
terminal (cursor/selection), GTK/Qt accent, wallpaper signal, lock screen. The login screen follows when
«Использовать на экране входа» is on (the first user's choice is applied system-wide).

Semantic colors never reuse the accent: ok green, warn yellow (`#f5cf52` dark / `#8a6100` light), bad red,
cloud cyan — and always come with an icon + word, never color alone.

## 11. Accent budget (the rule that keeps SOS calm)

At rest a view may show **one** accent-colored element (normally the primary button) plus the **live signal**.
The accent MAY color: the single primary action of a surface · the live signal (Jackson's scope, the Morse mark
while Jackson is active, the wallpaper burst, progress of running jobs) · the text caret and text selection ·
inline links.
The accent MUST NOT color: selection rings, checkmarks, toggles, radio buttons, step indicators, eyebrow labels,
headings, icons, active workspace, focus rings, borders. These use `text` (selected/on) and `line`/`lineStrong`
(off). Eyebrow labels are `textFaint`.
Transient states may borrow it because they are never visible at rest: the hover glyphs of the window buttons,
the pressed state of the primary action, the swatch under the pointer while picking an accent.

## 12. Pre-login surfaces are neutral

GRUB, Plymouth and the POST screen use no accent: the signal line, Morse mark and wordmark are drawn in
`text` (`#ebe8e1`) and `textFaint` on Graphite. They can never clash with whatever accent the user picks.

**The login screen continues the boot line** («Линия» + Jackson, chosen 25.09;
`design/mockups/greeter.html`, `shell/components/LoginLine.qml`). Plymouth ends on a lit line across
the middle of the screen; the greeter keeps it there. Left, above the line: «ВХОД · host» and the user's
name (Plex Sans Light 46; Tab or the chip switches users). On the line: the password, one Morse dot per
character, and the caret — the only accent on the screen. Middle: Jackson stands on the line and reacts
(listening while you type → thinking while PAM checks, the dots run into him → a red jitter and the dots
fall off on a wrong password, with the reason: layout or Caps Lock → a grin and a sweep to the burst on
success, then the session starts). Right: «СЕЙЧАС», the time, the ··· ——— ··· burst in `text`, the date.
Footer in mono text buttons: sessions and accessibility left; RU/EN, sleep, restart and shut down right
(restart and shut down ask for a second press). The greeter is always dark (`/etc/svoya/theme.json`);
Jackson's look comes from `/etc/svoya/avatar.json`, exported with «Использовать на экране входа»
(default Jackson otherwise). The lock screen is the same line inside the session: your theme (light too),
«ЗАБЛОКИРОВАНО», your Jackson, and while a job runs he says how far it got.

## 13. Jackson's look (mascot system)

Two characters, both always available: **«Чёрт»** (imp in a hoodie) and **«Кот»** (2000s cat). Sprites are
32×32 palette-indexed grids (`shell/assets/jackson/<character>.json`: states × 32 rows of palette keys) drawn at
integer scale by the shell, so recoloring is instant.

Palette slots: `outline` · `skin` (+ shade, light) · `outfit` (+ shade, light) · `detail` (horns, LEDs,
drawstrings: the accent) · `eyes` · `mouth` · `headphones` · `glasses`.

Customization (`~/.config/svoya/avatar.json`, shared by the shell and Jackson):

| key | values | default |
|---|---|---|
| `character` | `imp` · `cat` | `imp` |
| `skin` | imp: `ember` (Огонь) · `wine` (Бордо) · `plum` (Слива) · `graphite` (Графит) · `mint` (Мята); cat: `blue` (Русский голубой) · `ginger` (Рыжий) · `black` (Чёрный) · `snow` (Снежный) · `siamese` (Сиамский) | `ember` / `blue` |
| `outfit` | `accent` · any accent id · `#hex` | `accent` |
| `style` | `hoodie` · `jacket` · `tee` | imp `hoodie`, cat `jacket` |
| `headphones` | `true` · `false` | `true` |
| `glasses` | `none` · `shades` · `round` | imp `none`, cat `shades` |
| `hood` | `true` · `false` (imp only) | `true` |
| `name` | any short name | `Джексон` |

The outfit's three shades are derived from the chosen color (dark themes: lightness 0.32/0.25/0.40 in OKLCH;
light themes: 0.45/0.36/0.56), `detail` = the accent itself, so the mascot always matches the system.
Where: Jackson panel head (32 px, radius 8, `surface3` backing), toasts (32 px — the sprite is only drawn at integer scales), the wizard (128 px intro),
the customizer (192 px, animated states). Customizer entry points: right-click the mascot → «Настроить
Джексона», Settings → Джексон, `j avatar …`, or ask Jackson («стань котом»).

**Voice.** The default persona, «Кентафурик» (id `kent`), is a laid-back dude from the ICQ-and-forums internet who
knows today's memes too. He calls the user «кентафурик» (also «кент», «чувак», «братишка»), says «здарова», agrees
with «базар» / «базару нет», calls the obviously right thing «база», and stretches one word when glad («чуваааак»,
«красаааава») — in most answers at humor 1, in almost every one at 2, never at 0, and never when something broke or
it is about security, money or permissions. No swearing, no prison slang. The shell's fixed lines (greeter, lock
screen, setup greeting) follow the same voice through `Strings.kentVoice`: «Здарова, кентафурик! Пароль?»,
«Не, чувак, не то. Раскладка — EN.», «Базару нет — заходим!», «Отошёл, кентафурик? Я присмотрю.»,
«Чуваааак, с возвращением!»; the other personas and humor 0 get plain lines («Привет, Максим. Пароль?»). The greeter
learns the voice with the exported look (`voice=plain` in `/etc/svoya/avatar.json`; absent = кентафурик).
