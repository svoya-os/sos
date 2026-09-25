# SOS Shell — VM checklist

Nothing in `shell/` has run on a real compositor yet: the build machine has no Qt 6.10/Quickshell.
What *was* checked: `python3 shell/tools/qmlcheck.py` (brackets, imports, singleton members, ids,
qmldir, icon names, ambiguous types, and — with `node` — the JavaScript of every function, handler and
binding) and the Hyprland option/dispatcher names against the 0.53 wiki and the 0.56.2 source.
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
   and shows the taskbar, Hacker tiles, hides title bars, accent border. Super+T on workspace 2 flips it
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
   choice applies live: language (UI flips), layouts (Hyprland reload, try field), theme (whole
   screen recolors; `sos theme current`), preset, profile + Obsidian (nothing installs yet), AI (one
   model from `sos models suggest --json`, «Установить» shows progress and survives going
   forward/back; cloud key → `secret-tool lookup service svoya provider anthropic`), privacy
   (snapshot). «Начать работу» hides the wizard, writes `first-run-done`, a polkit prompt appears for
   `sos modules add … --yes`, and a notification reports the result. Super+Alt+A later → only the
   accessibility step.
8. **NVIDIA.** On an NVIDIA box `hyprctl getoption cursor:no_hardware_cursors` → 2 from
   `nvidia.conf` (gated on `__GLX_VENDOR_LIBRARY_NAME`, exported by svoya-session); no flicker in
   Electron apps; cursor visible on all outputs.

## 2. Look (compare with design/out/*.png at 1440×900, scale 1)

- Bar 30px: Morse mark (dashes accent), workspaces 19×19 radius 5, title `app / detail`, job meter,
  `GPU 64° · 11,2/24 ГБ`, icons 15px, layout code, Jackson mini-scope, `Чт 24 сен 18:42`.
- Wallpaper per theme: Graphite glow + horizon + Morse burst + grain; Paper 22px dot grid; Phosphor
  scanlines. Colophon `SOS 26.10 · первый сигнал` bottom right.
- Jackson panel 704px at 118px, launcher 640px, control center 380px from the right, toasts 330px
  (right 18, top 44), OSD pill, session menu, clipboard, cheat sheet, screenshot actions.
- Lock and greeter vs `lock-*.png` / `greeter-*.png`: clock 96/100 Light with dimmed colon, date mono
  caps, 320×40 field with dots + accent caret + go button, footer row (accessibility, mark, colophon).
- Wizard vs `setup-look/profile/ai-*.png`: top strip, 1040px column at 104px, cards with the accent
  ring, footer buttons 40px. Small screens (1280×720) scale the whole wizard down.
- Reduce motion: panels appear without animation, scope static; Hyprland animations off.
- Paper theme everywhere (Theme hot reload from `~/.local/state/svoya/theme.json`).

## 3. Function

- Launcher: apps (DesktopEntries), fuzzy ranking + launch counts, groups, `?text` or Tab → Jackson,
  settings/modules/actions modes from the СОС menu.
- Notifications: `notify-send test body`; actions, history in the control center, DND and focus
  modes (presentation also inhibits idle).
- Control center: Wi-Fi list/connect (nmcli), Bluetooth, volume/brightness sliders, theme, focus
  mode, AI & privacy block (today's spend, cloud requests from `sos status`).
- Media keys → wpctl/brightnessctl, OSD appears (volume via PipeWire; brightness via IPC).
- Clipboard: Super+V lists `cliphist`, Enter pastes/copies, Delete removes.
- Screenshot: Super+Shift+S / Print → slurp → actions (ask Jackson with the image, copy, OCR with
  tesseract rus+eng).
- Session menu: log out (hyprshutdown or `hyprctl dispatch exit`), suspend (locks first), restart,
  shut down — each needs a second press.
- `sos status --json --watch 2` stream: GPU segment and job segment update; without `sos` nothing
  breaks (retry every 30 s).
- IPC: `quickshell -p /usr/share/svoya/shell ipc call launcher toggle` (targets: launcher, jackson,
  clipboard, screenshot, controlcenter, session, cheatsheet, menu, lock, layout, system, osd,
  notifications). Super+J is `global, svoya:jackson`.

Generated assets: `tools/gen_icons.py` (Lucide + mockup glyphs → `assets/icons`, `core/Icons.qml`),
`tools/gen_textures.py` (grain, dots, scanlines), `tools/gen_previews.js` (wizard pictures from the
mockups, needs playwright). Re-run them after changing the mockups.

## 4. Known gaps to settle with other components

- **Voice/PTT** is not in ARCHITECTURE §4.3; the shell sends `{"type":"listen","action":"start|stop"}`
  only when `welcome.capabilities` has `voice`.
- **NVIDIA gate** uses `__GLX_VENDOR_LIBRARY_NAME` (svoya-session); a dedicated `SVOYA_GPU=nvidia`
  would be cleaner.
- **Polkit agent**: module installs from the wizard need one; `hyprpolkitagent` is optional in
  `image/packages/desktop.list` (the config starts it if present).
- **Jackson key cache**: keys stored by the wizard are found only after jacksond re-reads the keyring.
- **Hyprland > 0.56** (Lua): `hypr/*.conf` and `greeter/hyprland.conf` need a port; `core/Hypr.qml`
  already dispatches Lua syntax when `Hyprland.usingLua`.
