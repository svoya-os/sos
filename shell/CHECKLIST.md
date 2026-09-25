# SOS Shell — VM checklist

Nothing in `shell/` has run on a real compositor yet: the build machine has no Qt 6.10/Quickshell.
What *was* checked: `python3 shell/tools/qmlcheck.py` (brackets, imports, singleton members, ids,
qmldir, icon names and paths, ambiguous types, IPC keybindings, the Quickshell/Qt API of every file —
see "Pre-flight review" below — and, with `node`, the JavaScript of every function, handler and
binding), `python3 shell/tools/check_mascot.py` (the mascot renderer `components/Sprite.js` against
`design/mascot/jackson.js`: 7 760 grids/palettes, 0 differences; the accent math `core/Color.js`
against the CLI's `theme/accents.py` on all three bases: 51 resolutions, identical) and the Hyprland
options/keywords/dispatchers against the 0.53.3 source (and 0.56.2).
Work through the list top to bottom on the SOS ISO in a VM (virtio-gpu, 2 outputs if possible) and on
one NVIDIA machine. Log: `quickshell log -p /usr/share/svoya/shell` (or run it in a terminal).

Targets: **Quickshell 0.3.1** (Qt 6.10, Ubuntu 26.04), **Hyprland 0.53.3** + **hyprbars 0.53.0** from the
archive (hyprlang syntax; checked up to 0.56.2). Hyprland after 0.56 is Lua-only → port `hypr/*.conf`.

## 0. Run from a checkout

```sh
SVOYA_SHELL_DEV=1 quickshell -p ~/sos/shell            # live reload on save
quickshell -p ~/sos/shell ipc show                      # list IPC targets and functions
# point the keybindings and `sos session-start` at the checkout (in ~/.config/hypr/user.conf):
env = SVOYA_SHELL_DIR,/home/me/sos/shell
```

## Pre-flight review (source-verified, 2026-09-25)

Every Quickshell/Qt use was checked against the real sources: Quickshell **v0.3.1**, qtdeclarative
**6.10.2**, Hyprland **v0.53.3**, hyprlang **0.6.7**, hyprland-plugins (hyprbars) **v0.53.0**.
The `api` rule of qmlcheck makes that permanent: `tools/qmlapi.json` (generated) lists every
QML type, property (type, writable, FINAL), signal, method, enum, default and attached property;
`tools/qmlapi_check.py` parses each file and checks bindings, grouped/attached properties,
handlers, `Connections` targets, enum values, singleton members, `id.a.b` chains, literal types,
ReferenceErrors, assignments to read-only properties, IpcHandler signatures (typed args and return),
delegate context (`modelData`/`index` vanish when a delegate has required properties) and
Variants delegates. Regenerate after a Quickshell/Qt bump (clones of both at the new tags):

```sh
python3 shell/tools/gen_qmlapi.py ~/src/quickshell ~/src/qtdeclarative   # rewrites tools/qmlapi.json
```

Fixed by the review (would have failed or misbehaved on first boot):

- `components/NotificationCard.qml` — `HoverHandler` has `hovered`, not `containsMouse` (hover
  highlight never showed; "undefined" binding warnings).
- `bar/StatusIcons.qml` — visibility came from `row.visibleChildren`, which counts *effective*
  visibility: once hidden (e.g. before Pipewire is ready) the group could never reappear.
- `bar/WindowTitle.qml` + `bar/Bar.qml` — the detail width was derived from the item's own width,
  which follows the content: it shrank by ~4 px per polish until empty. Now clamped by `maxWidth`.
- `panels/ToolRow.qml` — `property string state` shadowed `Item.state` (States machinery;
  assigning an unknown state warns). Renamed `callState`.
- `setup/StepProfile.qml` — `visible: a && a.b && …` assigned `null`/`undefined` to a bool when
  `suggest` was missing (binding error, stayed visible). Now `!!(…)`.
- `core/Strings.qml`, `greeter/Face.qml` — `override` is a QML keyword after Qt 6.10; renamed
  `langOverride`.
- `notifications/Toasts.qml` — `Notification.expireTimeout` is the D-Bus value in **milliseconds**
  (notification.cpp:115; the "seconds" doc comment is wrong); `*1000` made every timed toast stay 20 s.
- `core/Icons.qml` (`zap`) + `tools/gen_icons.py` — compact SVG arc flags (`0 00-2.474`) are
  misread by Qt's PathSvg parser; the generator now re-emits such paths with separated flags.

What static checks cannot settle — watch `quickshell log` on the first boot:

1. Module loading through the explicit `qmldir` files (`module qs.core` …), also via the symlinked
   `greeter/` and `setup/` configs (traced in Quickshell's scanner and URL interceptor, never run).
2. The overlay changing `screen` (Ui.screen) while mapped recreates its layer surface; watch focus
   hand-over overlay ↔ lock ↔ wizard (`WlrKeyboardFocus.Exclusive` on all three).
3. `panels/Launcher.qml` list height follows `contentHeight` (converges; at worst a binding-loop
   warning while typing).
4. `core/Settings.qml` writes on every change: a change made before `shell.json` finished loading
   (only possible by a user action in the first milliseconds) would overwrite the file.
5. hyprbars plugin path (item 2 below) and every line of `hyprctl configerrors`.
6. `Behavior on <color>` inside the `Theme` singleton drives the 260 ms cross-fade; if a Qt build
   does not animate singleton properties, colors simply switch at once (nothing else depends on it).
7. `components/PixelSprite.qml` is a `Canvas` (Cooperative, no smoothing): check the mascot at 1×
   and 2× output scale for blur, and that it repaints only on state/look/accent changes
   (`QSG_RENDER_TIMING=1` stays quiet while Jackson idles between blinks).

## 1. Highest risk first

1. **Session start.** Log in → Hyprland starts with `/usr/share/svoya/hypr/hyprland.conf`, no red
   error bar (a bar means a key/rule name differs in this Hyprland build: `hyprctl configerrors`).
   `sos session-start` starts the shell; wallpaper, bar and POST splash appear. `hyprctl layers` lists
   `svoya-wallpaper`, `svoya-bar` (and `svoya-post` for ~1.2 s).
2. **hyprbars.** Title bars 36px, Plex Sans left, three 14px buttons right (from `svoya-colors.conf`).
   Check the plugin path `/usr/lib/x86_64-linux-gnu/hyprland/plugins/libhyprbars.so` and that
   `hyprctl plugin list` shows hyprbars. GTK4/Firefox/Chromium/Obsidian windows must not get a
   second bar (`hyprbars:no_bar` rule) — extend the class list if some app does.
3. **Presets and Super+T.** Settings → layout Clean/Classic/Hacker rewrites
   `~/.config/hypr/svoya-shell.conf` and reloads: Clean floats new windows, Classic moves the bar down
   and shows the taskbar, Hacker tiles, hides title bars, 1px `textDim` border. Super+T on workspace 2 flips it
   (open two terminals: they tile/float); after `hyprctl reload` the flip survives (named rules
   `svoya-ws<N>` re-enabled on `configreloaded`). Dialogs stay floating on tiled workspaces.
4. **Lock.** Super+L, `loginctl lock-session`, idle (Settings: 1 min) and suspend (`systemctl
   suspend`: the lock must be up before the machine sleeps). Wrong password → red ring + message;
   right one unlocks. PAM file: `/etc/pam.d/svoya-lock` (shipped by svoya-shell). Kill the shell while
   locked → session stays locked; restart it → it can take the lock over
   (`misc:allow_session_lock_restore`).
5. **Jackson socket.** With `jacksond` running: Super+J tap opens/closes the panel, an answer streams
   (Markdown, tables, approval card with the three buttons), footer shows latency/tokens/cost/route.
   `systemctl --user stop jacksond` → panel says Jackson is not answering; start it again → reconnects
   within ~30 s (backoff). Hold Super+J > 350 ms → push-to-talk only if `welcome.capabilities`
   contains `voice` (protocol extension, see gaps).
6. **Greeter.** Reboot → greetd → `greeter-session` → Hyprland (`hypr/greeter.conf` →
   `greeter/hyprland.conf`) → Quickshell greeter. Users from `/etc/passwd`, Tab cycles, sessions from
   `/usr/share/wayland-sessions` (SOS first), RU/EN, power buttons need two presses. Wrong password
   → message, retry works; right one starts `/usr/bin/svoya-session`. Keyboard layout from
   `/etc/default/keyboard` (input.conf found by the `/run/user/*/svoya-greeter` glob).
7. **First-run wizard.** `rm ~/.config/svoya/first-run-done; sos session-start`. Seven steps; each
   choice applies live: language (UI flips), layouts (Hyprland reload, try field), look (theme and
   accent: the whole screen cross-fades; hovering a swatch previews; `sos theme current`; «На экране
   входа» is **on** when `/etc/svoya/theme.json` does not exist yet), preset, profile + Obsidian
   (nothing installs yet), Jackson page 1 (Чёрт/Кот, skin, name, humor → `j avatar show --json`,
   `j persona`; the sample answer follows the humor), Jackson page 2 (one model from `sos models
   suggest --json`, «Установить» — an outline button — shows accent progress and survives going
   forward/back; cloud key → `secret-tool lookup service svoya provider anthropic`), privacy
   (snapshot). «Начать работу» hides the wizard, writes `first-run-done`, then **one polkit prompt at a
   time**: `sos theme apply --system` (if «На экране входа» is on), then `sos modules add … --yes`; a
   notification reports the result; the process quits only after both and `jackson route set` ended.
   Super+Alt+A later → only the accessibility step.
8. **NVIDIA.** On an NVIDIA box `hyprctl getoption cursor:no_hardware_cursors` → `int: 2` **and
   `set: true`** from `nvidia.conf` (gated on `__GLX_VENDOR_LIBRARY_NAME`, exported by svoya-session;
   2 is also the 0.53.3 default, so only `set: true` proves the gate); no flicker in Electron apps;
   cursor visible on all outputs.

## 2. Look (compare with design/out/*.png at 1440×900, scale 1)

- Bar 30px: Morse mark (all `text`; the dashes turn accent only while Jackson listens/thinks/works/
  speaks), workspaces 19×19 radius 5 (active = `text` fill), title `app / detail`, job meter (accent:
  a running job), `GPU 64° · 11,2/24 ГБ`, icons 15px, layout code, Jackson mini-scope (textDim and
  still at rest; accent on an accentSoft chip only while live), `Чт 24 сен 18:42`.
- Wallpaper per theme: Graphite glow + horizon + Morse burst + grain; Paper 22px dot grid; Phosphor
  scanlines. Colophon `SOS 26.10 · первый сигнал` bottom right.
- Jackson panel 704px at 118px, launcher 640px, control center 380px from the right, toasts 330px
  (right 18, top 44), OSD pill, session menu, clipboard, cheat sheet, screenshot actions.
- Lock and greeter vs `lock-*.png` / `greeter-*.png`: clock 96/100 Light with dimmed colon, date mono
  caps, 320×40 field with dots + accent caret + go button, footer row (accessibility, mark, colophon).
- Wizard vs `setup-look/profile/jackson/ai-*.png`: top strip (progress segments `text`/`textFaint`/
  `lineStrong`), 1040px column at 104px, cards with the neutral `text` ring, footer buttons 40px —
  «Дальше» is the only accent element. Small screens (1280×720) scale the whole wizard down.
- Reduce motion: panels appear without animation, scope static; Hyprland animations off.
- Paper theme everywhere (Theme hot reload from `~/.local/state/svoya/theme.json`).

## 3. Function

- Launcher: apps (DesktopEntries), fuzzy ranking + launch counts, groups, `?text` or Tab → Jackson,
  settings/modules/actions modes from the СОС menu.
- Notifications: `notify-send test body`; actions, history in the control center, DND and focus
  modes (presentation also inhibits idle). Timeouts: `notify-send -t 4000 a b` leaves after 4 s,
  default/`-t 0` after 6 s (clamped 3–20 s; the history keeps it).
- Control center: Wi-Fi list/connect (nmcli), Bluetooth, volume/brightness sliders, theme + the
  accent button → «Оформление», focus mode, AI & privacy block (the AI switch = `sos ai off|on`:
  jacksond stops, the bar chip disappears, the switch holds until `sos status` agrees; today's spend,
  cloud requests from `sos status`).
- Media keys → wpctl/brightnessctl, OSD appears (volume via PipeWire; brightness via IPC).
- Clipboard: Super+V lists `cliphist`, Enter pastes/copies, Delete removes.
- Screenshot: Super+Shift+S / Print → slurp → actions (ask Jackson with the image, copy, OCR with
  tesseract rus+eng).
- Session menu: log out (hyprshutdown or `hyprctl dispatch exit`), suspend (locks first), restart,
  shut down — each needs a second press.
- `sos status --json --watch 2` stream: GPU segment and job segment update; without `sos` nothing
  breaks (retry every 30 s).
- IPC: `quickshell -p /usr/share/svoya/shell ipc call launcher toggle` (targets: launcher, jackson
  [+ `customize`], clipboard, screenshot, controlcenter [+ `look`], session, cheatsheet, menu, lock,
  layout, system, osd, notifications). Super+J is `global, svoya:jackson`.

Generated assets: `tools/gen_icons.py` (Lucide + mockup glyphs → `assets/icons`, `core/Icons.qml`),
`tools/gen_textures.py` (grain, dots, scanlines), `tools/gen_previews.js` (wizard pictures from the
mockups, needs playwright). Re-run them after changing the mockups.

## 3a. Accent, theme and Jackson's look (DESIGN §10–§13, WORKFLOWS §2)

1. **Budget (§11).** On every surface at rest count accent-colored things: at most the one primary
   button + the live signal (scope, the Morse dashes while Jackson is active, the wallpaper burst,
   running job/tool/download meters), the caret, text selection and links. Selected tiles, toggles,
   radios, checkmarks, step bars, focus rings (`text` 70 %, 2px), active workspace, eyebrows
   (`textFaint`), panel edges (neutral light; accent only on Jackson's panel) must be neutral. Try
   `sos theme accent rose` — anything pink that is not in that list is a bug.
2. **Cross-fade.** Change theme or accent: bar, panels, windows, wallpaper glow and mascot fade in
   260 ms together; with reduce motion it is instant; logging in never fades from the defaults
   (`Theme.settled`).
3. **Control center → «Оформление».** Base theme segmented (Графит · Бумага · Авто · Фосфор). Hover a
   swatch → everything previews (nothing written, `sos theme current` unchanged); leave → back; click →
   `sos theme accent <id> --json` (toast/undo from the CLI, Super+Z). «Сигнал» is drawn split
   (night/day). «Свой…» → hex field: `d64fd8` on Graphite shows `✓ AA · 5,2 : 1` (against `surface`,
   like the CLI); `ffcc00` on Paper shows «поправили · 4,5 : 1» and the note names `#8c6e00` — both
   must equal `sos theme accent '#…' --dry-run --json` (`color`, `contrast`). Enter applies.
4. **Login screen.** Turn «Использовать на экране входа» on → nothing happens while the panel is open;
   closing it brings one polkit prompt (`pkexec sos theme system-write …`); `/etc/svoya/theme.json`
   gets the accent (dark base). Five quick accent clicks → still one prompt, after the panel closes
   (or 20 s later with no overlay open). Cancel the prompt on first enabling → the switch turns off
   and a toast says the login screen was not changed. Log out: the greeter caret and burst use the
   accent; the user ring, field border, power buttons (armed = `text` edge) and glow are neutral.
5. **Mascot.** 32 px in the Jackson panel head (surface3 backing, radius 8) with the 92×22 scope on the
   right; 32 px in Jackson's toasts (first action primary); 64 px in «Оформление»; 192 px in the
   customizer; 128 px in the wizard. Pixels crisp (integer scale), outfit in the accent's shades,
   horns/LEDs = the accent, updates with the hover preview. States: idle blinks every 3.6–6 s,
   listening (hold Super+J), thinking/working, talking (two frames, 140 ms) while speaking, happy for a
   beat after an answer, error; dimmed when jacksond is off. Without `assets/jackson/*.json` the scope
   stands in. On a fractional-scale output (1.25) check the pixel grid still looks even.
6. **Customizer.** Right-click the mascot (panel head) → «Настроить Джексона»; also «Настроить» in
   «Оформление», the launcher («Настроить Джексона») and `ipc call jackson customize`. Every control
   writes at once: `j avatar show --json` matches; jacksond's next state event carries the same look;
   «стань котом» said to Jackson updates the open customizer. Persona cards and humor run
   `j persona set …` / `j persona humor …`. «вернуть как было» restores what was there when the panel
   opened, «По умолчанию» = `j avatar reset` (unknown keys in avatar.json survive both). The preview
   walks through the six states; a thumbnail holds one; pause stops.
7. **Launcher.** «Оформление», «Акцент: Сирень» (search «сирень»/«акцент»), «Тема: …» — all through the
   same CLI calls (and the login-screen batching).
8. **POST.** Morse, wordmark and lines in `text`/`textFaint` only (DESIGN §12), on any accent.

## 4. Known gaps to settle with other components

- **Voice/PTT** is not in ARCHITECTURE §4.3; the shell sends `{"type":"listen","action":"start|stop"}`
  only when `welcome.capabilities` has `voice`.
- **NVIDIA gate** uses `__GLX_VENDOR_LIBRARY_NAME` (svoya-session); a dedicated `SVOYA_GPU=nvidia`
  would be cleaner.
- **Polkit agent**: module installs from the wizard need one; `hyprpolkitagent` is optional in
  `image/packages/desktop.list` (the config starts it if present).
- **Jackson key cache**: keys stored by the wizard are found only after jacksond re-reads the keyring.
- **QtQuick.Effects is only recommended.** `packages/svoya-shell` puts `${svoya:QmlDepends}`
  (→ `qml6-module-qtquick-effects`) in `Recommends`; `PanelFrame`, `SignalBurst`, `Toasts` and the
  wizard import `QtQuick.Effects`, so after an install with `--no-install-recommends` shell.qml
  and the wizard do not load at all ("module QtQuick.Effects is not installed"). Move it to `Depends`.
  `qml6-module-qtquick-controls` in `Depends` is unused (nothing imports QtQuick.Controls).
- **Login-screen prompts.** `sos theme … --system` goes through `pkexec`, whose polkit action is
  `org.freedesktop.policykit.exec`, not `org.svoya.*`, so `50-svoya.rules` (AUTH_ADMIN_KEEP) does not
  apply and every sync asks again. The shell batches changes into one sync per closed panel; a
  dedicated action for `sos theme system-write` (AUTH_ADMIN_KEEP, or YES for the first user) would
  make WORKFLOWS §2's "asks once" literally true (packages/cli).
- **`sos theme accent` has no `--quiet`** (`theme apply` has): the shell passes `--json` and ignores
  the output. **Auto switch times** are not in `theme.json`/`sos theme current --json`; «Оформление»
  says «Бумага днём · Графит ночью» instead of today's times.
- **Personas** are listed in the shell (`kent sysop dispatcher pirate`, as in jackson/persona.py);
  `welcome` could send the list with titles. `j persona set` should also push a `state` event so the
  panel updates without waiting for the next one (the shell shows the choice optimistically).
- **Jackson's look over the protocol**: the shell reads `~/.config/svoya/avatar.json` itself (watched)
  and ignores the `avatar` object in `welcome`/`state`.
- **Hyprland > 0.56** (Lua): `hypr/*.conf` and `greeter/hyprland.conf` need a port; `core/Hypr.qml`
  already dispatches Lua syntax when `Hyprland.usingLua`.
