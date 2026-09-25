# SOS — Architecture

> «СОС — Своя Операционная Система». English: **SOS — Svoya Operating System**.
> User-facing command: `sos` (alias `svoya`). Internal namespace: `svoya` (packages `svoya-*`, paths below).
> Jackson is a character in the UI; never call it a "daemon/демон" in user-facing text. Jackson CLI: `jackson`, short `j`.
> This document is the contract between components. If you change an interface here, update every consumer.

## 1. Layers

```
┌──────────────────────────────────────────────────────────────────────┐
│  SOS Shell (Quickshell/QML)      bar · launcher · Jackson panel ·     │
│                                 notifications · control center ·     │
│                                 lock · greeter · first-run · OSD     │
├──────────────────────────────────────────────────────────────────────┤
│  jacksond (Jackson, background) sos command (system tool)             │
│  router · tools/MCP · memory ·  gpu doctor · modules · models ·       │
│  permissions · audit · undo     theme engine · update/undo · new      │
├──────────────────────────────────────────────────────────────────────┤
│  Hyprland (compositor, pinned) · PipeWire · NetworkManager · greetd · │
│  xdg-desktop-portal-{hyprland,gtk} · snapper/btrfs · podman · flatpak │
├──────────────────────────────────────────────────────────────────────┤
│  Engine: Ubuntu 26.04 LTS packages (kernel, drivers, CUDA/ROCm        │
│  from the archive), never visible to the user, no Ubuntu branding.    │
└──────────────────────────────────────────────────────────────────────┘
```

Rule of thumb: **everything the user sees or touches is ours; everything below is a replaceable engine.**
All our parts ship as Debian packages from our own APT repository, so the engine can be swapped later.

## 2. Repository map (monorepo)

| Path | Owner component | Ships as |
|---|---|---|
| `image/` | ISO build (mmdebstrap → squashfs → hybrid ISO) | build tooling |
| `installer/` | Calamares settings + branding | `svoya-installer` |
| `packages/` | Debian packaging for every `svoya-*` package | `.deb` |
| `shell/` | SOS Shell QML (Quickshell config) | `svoya-shell` |
| `shell/greeter/` | login screen (greetd) | `svoya-shell` |
| `jackson/` | Jackson daemon + CLI (Python) | `svoya-jackson` |
| `cli/` | `sos` command (Python; alias `svoya`) | `svoya-cli` |
| `modules/` | module catalog (TOML) | `svoya-cli` |
| `themes/` | theme tokens (TOML) + templates | `svoya-theme` |
| `branding/` | logo, wallpapers, plymouth, grub, sounds, fonts manifest | `svoya-branding` |
| `design/` | mockups (HTML) and design docs | not shipped |
| `tests/` | unit + VM (QEMU/QMP) tests | CI |
| `.github/workflows/` | CI/CD | CI |
| `docs/` | vision, architecture, guides | website |

## 3. Filesystem layout on the installed system

| Path | Purpose |
|---|---|
| `/usr/bin/sos` | system CLI (`/usr/bin/svoya` is a symlink alias) |
| `/usr/bin/jackson`, `/usr/bin/j` | Jackson CLI client |
| `/usr/lib/svoya/jacksond` | Jackson daemon entry point (systemd **user** service `jacksond.service`) |
| `/usr/lib/svoya/` | helpers and private Python packages (`svoya_cli`, `jackson`) |
| `/usr/share/svoya/themes/<id>.toml` | theme tokens |
| `/usr/share/svoya/templates/` | theme templates (hyprland, kitty, gtk, qt, btop, fuzzel…) |
| `/usr/share/svoya/modules/<id>.toml` | module catalog |
| `/usr/share/svoya/shell/` | Quickshell config (`quickshell -p /usr/share/svoya/shell`) |
| `/usr/share/svoya/sounds/` | sound theme (freedesktop naming) |
| `/usr/share/svoya/wallpapers/` | wallpapers |
| `/etc/svoya/` | system config (`svoya.toml`, policies) |
| `~/.config/svoya/` | user config (`svoya.toml`, `jackson.toml`) |
| `~/.local/state/svoya/` | generated state (`theme.json`, `status.json`) |
| `~/.local/share/svoya/jackson/` | Jackson memory (Markdown + git), audit log, sqlite index |
| `/srv/ai/` | shared model & dataset store (group `ai`, excluded from snapshots) |
| `/var/lib/svoya/` | system state (installed modules, update history) |

Secrets (API keys) live in the Secret Service keyring (`secret-tool`), never in plain files.
Fallback for headless/test runs only: `~/.config/svoya/secrets.env` with mode `0600`.

## 4. Interfaces

### 4.1 Theme tokens → `theme.json`
Themes are TOML files in `themes/` — the canonical examples are `themes/graphite.toml`,
`themes/paper.toml` and `themes/phosphor.toml`. Sections: top-level `id`, `name.{en,ru}`, `mode` (`dark`|`light`),
`pair` (sibling for `auto`), `[color]` (wall, bar, surface, surface2, surface3, line, lineStrong, text, textDim,
textFaint, accent, accentSoft, accentInk, ok, warn, bad, cloud), `[font]` (sans, mono, pixel), `[shape]`
(radius, radiusSmall, radiusLarge, border), `[motion]` (fast, base, slow — ms, ease-out), `[effects]`
(grain, glow, scanlines).

`sos theme apply [<id>|auto]` renders every template and writes
`~/.local/state/svoya/theme.json` (flat JSON of the same keys). The shell watches that file
and hot-reloads colors. `auto` switches between `graphite` (night) and `paper` (day) by local sunset/sunrise
(fallback: 20:00 / 07:00).

### 4.2 `sos status --json` (polled by the shell every 2 s)

```json
{
  "gpu": [{"index":0,"vendor":"nvidia","name":"RTX 4090","tempC":64,"vramUsedMiB":11468,
           "vramTotalMiB":24564,"util":93,"powerW":301,"driver":"595.58","ok":true}],
  "jobs": [{"id":"train-1832","label":"обучение","progress":0.62,"etaSec":1080}],
  "ai": {"local":true,"cloudActiveSince":null},
  "updates": {"available":3,"security":1},
  "snapshots": {"last":"2026-09-24T18:02:11Z"}
}
```
Every field is optional; the shell must render gracefully when a field is missing.

### 4.3 Jackson socket protocol
Unix socket `$XDG_RUNTIME_DIR/svoya/jackson.sock`, **JSON Lines** (one JSON object per line, UTF-8).

Client → daemon:

| type | fields | meaning |
|---|---|---|
| `hello` | `client`, `version` | handshake; daemon answers `welcome` |
| `ask` | `id`, `text`, `context?` (`selection`, `clipboard`, `screenshot` path, `cwd`), `route?` (`auto`/`local`/`cloud`) | start a turn |
| `approve` | `id`, `callId`, `decision` (`once`/`always-project`/`deny`) | answer an approval request |
| `cancel` | `id` | stop a running turn |
| `status` | — | daemon state |
| `undo` | `actionId?` | revert last reversible action |

Daemon → client (events, all carry `id` of the turn when relevant):

| type | fields |
|---|---|
| `welcome` | `version`, `models`, `route` |
| `route` | `model`, `provider`, `local` (bool), `reason` |
| `token` | `text` (streamed answer chunk, Markdown) |
| `tool` | `callId`, `name`, `args`, `tier` (0–4), `state` (`running`/`done`/`failed`), `summary` |
| `approval` | `callId`, `name`, `preview` (exact action text/diff), `tier` |
| `done` | `usage` (`inTokens`,`outTokens`), `costEur`, `latencyMs`, `leftMachine` (bool), `actions` (list of undoable action ids) |
| `error` | `message`, `retryable` |
| `state` | `listening`/`thinking`/`working`/`speaking`/`idle` (drives the scope animation) |

### 4.4 Permission tiers (Jackson and every agent it runs)

| Tier | What | Policy |
|---|---|---|
| T0 | read-only (read files in allowed roots, system info, search) | runs freely |
| T1 | reversible local writes (files inside project/home, settings) | auto, **snapshot first** |
| T2 | external side effects (network send, post, email, install from network, new domain) | confirm against exact preview |
| T3 | root/system changes | polkit + snapshot |
| T4 | secrets (ssh keys, keyrings, browser profiles) | denied unless granted for one task |

Every tool call is appended to a hash-chained audit log (`audit.jsonl`: each line has `prev` = sha256 of previous line).
Untrusted content (web pages, files from the internet, tool output) taints the turn; tainted turns need T2 confirmation for anything that sends data out.

### 4.5 Module catalog (`modules/<id>.toml`)

```toml
id = "llm-local"
name = { en = "Local LLMs", ru = "Локальные модели" }
summary = { en = "...", ru = "..." }
category = "ai"                # ai | media | ml | agents | dev | system | cloud
profiles = ["creator", "ml", "agent", "hacker"]
requires = ["base-ai"]
apt = ["llama.cpp"]
flatpak = []
scripts = { install = "install.sh", remove = "remove.sh" }   # relative to modules/<id>/
disk_gb = 2.5
vram_gb_min = 0
license_note = { en = "...", ru = "..." }
```

`sos modules add <id>` (also `sos install <id>`) = snapshot → apt/flatpak/scripts → record in `/var/lib/svoya/modules.json`.
`sos modules remove <id>` reverses it. Everything is reversible (`sos undo`).

### 4.6 Model store
Single source of truth: Hugging Face cache layout under `/srv/ai/hub` (`HF_HOME=/srv/ai`).
Per-tool views are generated (llama.cpp models dir, Ollama import, ComfyUI `extra_model_paths.yaml`).
`/srv/ai/registry.db` (SQLite) tracks hash, source, license, EU/commercial flags, VRAM estimate, last use.

## 5. Session startup

```
greetd → svoya greeter (Hyprland + quickshell -p /usr/share/svoya/shell/greeter)
  → user session: Hyprland (config /usr/share/svoya/hypr/hyprland.conf + ~/.config/hypr/user.conf)
      exec-once: sos session-start
          → sos theme apply auto
          → systemctl --user start jacksond.service
          → quickshell -p /usr/share/svoya/shell      (the SOS Shell)
          → first login only: quickshell -p /usr/share/svoya/shell/setup (first-run wizard)
```

## 6. Keyboard map (defaults)

| Keys | Action |
|---|---|
| Super + Space | launcher / command palette (`?text` → Jackson) |
| Super + J (hold) | Jackson; hold to talk (push-to-talk) |
| Super + V | clipboard history |
| Super + Shift + S | region → ask Jackson / OCR / copy |
| Super + Enter | terminal |
| Super + E | files |
| Super + Q | close window |
| Super + F | fullscreen · Super + T toggle tiling for workspace |
| Super + 1…9 | workspaces |
| Super + K | shortcut cheat sheet |
| Super + Z | undo last system change |
| Super + Escape | System Doctor |
| Super + L | lock |

## 7. Conventions

* Python ≥ 3.12, **stdlib first** (runtime deps only from the Ubuntu archive), type hints, `unittest`.
* Shell scripts: `bash`, `set -euo pipefail`, shellcheck-clean.
* User-facing strings: English + Russian (`en`, `ru`); UI copy is short, calm, and never nags.
* No telemetry. No network call happens without the user having enabled the feature that needs it.
* Licenses: code Apache-2.0; artwork/docs CC BY-SA 4.0; fonts OFL/MIT (see `LICENSES/`).

## 8. Contract details agreed during v0.1 integration

These refine §3–§5; where they differ, this section wins.

**Secrets (§3).** API keys: `secret-tool store --label='SOS: <name>' service svoya provider <name>`,
read with `secret-tool lookup service svoya provider <name>`. The first-run wizard writes keys to the
keyring through stdin; Jackson re-reads the keyring when a key is missing.

**theme.json (§4.1).** Flat object: `id, mode, pair, nameEn, nameRu, choice, appliedAt`, every `[color]`
token as `#AARRGGBB`, every `[font] [shape] [motion] [effects]` key with its TOML type.
`sos theme apply` also writes `~/.config/hypr/svoya-colors.conf` (colors + hyprbars buttons).

**Status (§4.2).** Optional extras: `ts`, `updates.checkedAt`, `gpu[].integrated|gttUsedMiB|gttTotalMiB`,
`ai.enabled|todayCostEur|todayCloudRequests`. Jackson writes `$XDG_RUNTIME_DIR/svoya/ai.json`
`{local, cloudActiveSince}`. `sos status --json --watch 2` streams one JSON line per interval.
Jobs are `~/.local/state/svoya/jobs/<id>.json` (schema v1, see cli/README.md), updated with
`sos job progress <id> <0..1>`.

**Jackson protocol (§4.3).** Clients and the daemon ignore unknown message/event types and fields.
`status` is answered with a `status` event (route, spend, pending approvals, turns, models) and a
`state` event. `undo` may carry `id` and is answered with `tool`/`token`/`done {undone}` or `error`.
`ask` may carry `new: true` and `refines` (id of the turn being refined); `route` also accepts
`provider/model`. `approval` carries `decisions` (T3/T4 and tainted turns offer only `once`/`deny`).
`welcome` and `state` carry `persona`, `avatar`, `mood`. Voice (v0.2): when `welcome.capabilities`
contains `voice`, clients may send `listen {action: start|stop}`.

**Snapshots and undo.** `sos snapshot create --reason TEXT --json` prints `{"id": …}`;
`sos undo [<id>] --yes` reverts it non-interactively (callers without a TTY must pass `--yes`).
The snapper configs `root`/`home` set `ALLOW_GROUPS` so Jackson can snapshot without a password.

**Modules (§4.5).** Optional keys: `aliases`, `hardware`, `options.<name> = {en, ru, disk_gb}`,
`user_scripts`, `proprietary`; apt placeholders `{nvidia.branch}` `{nvidia.open}` `{kernel.flavor}`;
category `apps`; profiles live in `modules/profiles.toml` (`jackson_route` → the wizard runs
`jackson route set default <route>`), where `@gpu` means the driver module for this machine.
`sos modules profiles --json`, `sos models suggest --json`, `sos models pull <id> --yes --json` feed the wizard.

**Session (§5).** `/usr/bin/svoya-session` exports the session environment (incl.
`QT_QPA_PLATFORMTHEME=qt6ct`, NVIDIA hints when the proprietary driver is loaded), pre-creates every
file `hyprland.conf` sources (`svoya-colors.conf` via `sos theme apply auto`, `svoya-shell.conf`,
`user.conf`, `~/.local/state/svoya/hypr/input.conf`) and starts Hyprland. `sos session-start` runs
`dbus-update-activation-environment --systemd WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE`.
`/etc/svoya/live` marks the live session (show "Install", skip the wizard).

**Accent (§4.1).** `themes/accents.toml` + `[theme] accent = "<id>|#rrggbb"` in `~/.config/svoya/svoya.toml`
(default: the base theme's `accentDefault`). theme.json adds `accentStrong, accentId, accentNameEn, accentNameRu,
accentCustom (#rrggbb|null), accentAdjusted, accentContrast`; `accent accentSoft accentStrong accentInk` come from the
accent system. `sos theme accent <id|name|#hex> [--system] [--undo] [--dry-run] [--json]`;
`sos theme accents --json` → `[{id, name, note, dark, light, ink{dark,light}, gnome{dark,light}, default, current}]`
+ `custom`. `--system` writes `/etc/svoya/theme.json` (same keys, dark base, `choice: "system"`) through
`pkexec sos theme system-write`, which the polkit action `org.svoya.theme.system-write` allows for active local
sessions without a password (it only writes the login screen's colors).

**Undo of looks.** Explicit theme/accent changes are journaled in `~/.local/state/svoya/undo.json`; `sos undo`
reverts the newest change (journal or snapshot pair); ids `look-N`, `N`, `snap-N`; `--list --json` rows add `id`
and `kind: "look"`.

**AI switch.** AI is off while `~/.config/svoya/ai.off` or `/etc/svoya/ai.off` exists or `[ai] enabled = false`
(`sos ai off|on|status [--system] [--json]`). `sos status --json` always has `ai.enabled`, plus `ai.off`
(`user|system|config`) while off. AI units carry `ConditionPathExists=!%h/.config/svoya/ai.off` and
`ConditionPathExists=!/etc/svoya/ai.off`. Jackson then answers only fast-path commands; other turns end with
`error {aiOff: true, off: …}` explaining `sos ai on`. Jackson runs `sos ai off` only after its answer is sent.

**Jackson's look and name (DESIGN §13).** `~/.config/svoya/avatar.json` is shared by the shell and Jackson:
`character` (imp|cat), `skin`, `outfit`, `style`, `headphones`, `glasses`, `hood`, `name`. It may be sparse
(missing keys follow the character's defaults); writers keep unknown keys and replace the file atomically.
`welcome` carries `name`, `avatar` (the full resolved object), `ai {enabled, off}`, `capabilities` and
`personas`; every `state` carries the full `avatar`; when the file changes, Jackson re-sends
`state {detail: "avatar"}` to every client within 2 s. Sprites: `shell/assets/jackson/{imp,cat}.json`
(format `sos-jackson/1`, see `design/mascot/FORMAT.md`). Jackson changes the accent only via
`sos theme accent <word|#hex> --json` and verifies `theme.json` `accentId`.
Login screen copy: with «Использовать на экране входа», `sos theme … --system` also passes the look to
the root helper as `--avatar key=value;…` (values percent-encoded, validated again as root) and it writes
`/etc/svoya/avatar.json` (0644); an empty look removes it. The greeter reads only that copy and never
writes. The shell queues this sync after every avatar change (`Theme.queueSystemSync()`).
