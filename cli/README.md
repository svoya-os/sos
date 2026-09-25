# `sos` — the system tool of SOS

«СОС — Своя Операционная Система». The command is **`sos`** (`svoya` is a compatibility alias);
the internal namespace stays `svoya` (`svoya_cli`, `/usr/share/svoya`, `~/.config/svoya`, `/var/lib/svoya`).
Python ≥ 3.11, standard library only. Code: Apache-2.0.

```
sos                          interactive menu (arrows + Enter, digits, q) — numbered prompt without a TTY
sos install obsidian         a module, an app (Flathub) or a model — one verb for everything
sos remove obsidian          …and back
sos fix · sos gpu            GPU Doctor: repair safely (snapshot first) · check the graphics card
sos update · sos undo        update with a snapshot pair · undo the latest change (look or system)
sos theme night|day|auto     Graphite · Paper · by sunrise/sunset (also: phosphor, graphite, paper)
sos accent lilac             accent color: signal amber ink phosphor ice lilac rose mono · '#hex' · сирень, лёд…
sos ai off · sos ai on       the AI switch: Jackson and local model servers stop and stay off
sos models suggest           the best local model for this machine (+2 alternatives)
sos status · sos new · sos run
```

Russian verbs work everywhere: `sos установить`, `удалить`, `починить`, `видеокарта`, `обновить`,
`откатить`/`отменить`, `тема ночь|день|авто`, `акцент сирень` (also `тема сирень`, `акцент фиолетовым`),
`ии выкл|вкл`, `модели [подобрать]`, `модули`, `статус`. Typos get
"did you mean …?" (`sos modles` → `models`). Output language follows `$LANG` (override: `SVOYA_LANG=ru|en`);
colors follow the applied theme, truecolor when `COLORTERM=truecolor`, none with `NO_COLOR` or `--json`.

## Commands

| Command | What it does |
|---|---|
| `sos status [--json] [--write] [--watch N]` | GPU/jobs/AI/updates/snapshots for the bar (ARCHITECTURE §4.2). ~0.1 s; slow sources are cached and refreshed in the background. `--watch N` prints one JSON line every N s (cheaper than polling). |
| `sos doctor [--json] [--gpu] [--fix] [--dry-run] [--yes]` | 23 checks (below). `--fix` applies only *safe* fixes (local config, modules, services, groups; never downloads) after a snapshot; everything else is printed as an exact command. `sos fix` = `doctor --fix`, `sos gpu` = `doctor --gpu`. |
| `sos install|remove <thing>…` | Resolves, in order: module id/alias (`obsidian` → module `notes`) → app alias (`data/apps.toml` → `flatpak --user`) → model id from `models suggest` (`qwen3.5-9b[:Q4_K_M]`) → Hugging Face repo (`org/repo[/file.gguf]`). |
| `sos modules list|info|add|remove|profiles` | Module catalog (§4.5). `add`: snapshot → apt/flatpak/scripts → state → snapshot. `--dry-run`, `--with <option>`, `--profile <p> [--offline]`, `--show-scripts`, `--json`. |
| `sos models list [--catalog] [--all]` | Installed models (registry synced with `/srv/ai/hub`), or the curated catalog — by default only models usable **commercially in the EU** (`[models] region/commercial` in `svoya.toml`). |
| `sos models suggest [--json]` | One default + two alternatives from a license-safe ladder, checked with the fit estimator for this GPU/APU/CPU. |
| `sos models fit <path|org/repo/file.gguf> [--ctx 8192] [--gpu auto|<idx>|24gb] [--kv f16|q8_0]` | Will it fit? Reads only the GGUF header (HTTP Range for remote files). |
| `sos models pull <org/repo[/file]|ladder-id> [--yes] [--json]` | License + fit + disk check first, then download into the HF cache layout (`hf download` if present, else resumable urllib with sha256 verification). `--json` streams progress events. |
| `sos models serve [--stop|--status] [--foreground]` | Start the local OpenAI/Anthropic-compatible server Jackson uses: user unit `svoya-llm.service` (llama.cpp router over `/srv/ai/views/llama.cpp`, 127.0.0.1:8080), else `llama-server` directly. |
| `sos models rm <repo|path|sha256>` · `dedup [--apply]` · `views` | Remove · find duplicates, reflink them on btrfs · per-tool views (llama.cpp dir, ComfyUI yaml, Ollama imports). |
| `sos theme list|current|apply [<id>|auto] [--system]` | Render every template, write `theme.json`, reload Hyprland/kitty, set GTK color scheme and accent. An explicit choice is remembered in `~/.config/svoya/svoya.toml` and is undoable (`sos undo`). |
| `sos theme accent [<id|name|#hex>] [--undo] [--system] [--dry-run] [--json]` · `sos theme accents [--json]` | The accent color (below). One calm line: `› accent Lilac · undo: sos undo`. `--dry-run --json` previews (the swatch hover); `--system` also writes `/etc/svoya/theme.json` for the login screen (pkexec). `sos accent …` is short for it. |
| `sos ai off|on|status [--system] [--json]` | The AI switch (WORKFLOWS §8, below). |
| `sos new <name> [--template torch|llm-finetune|comfy-node|agent|upsil]` | uv project wired to the store, PyTorch index chosen by GPU Doctor; `upsil` is an UpsiL program with tests. |
| `sos run <script> [args]` · `sos job progress|done|start|list` | Environment header (as in the design mockup) + a job the bar shows; `.py`, `.sh` and UpsiL `.upl` (in the project's `.venv` when there is one). |
| `sos update [--dry-run]` · `sos undo [--list|<id>] [--yes]` · `sos snapshot create|list [--config root|home]` | snapper pre/post pairs (`--cleanup-algorithm number`, userdata `svoya=1`). `sos undo` takes the **newest change**: a look change (theme/accent, from the journal — instant, no password) or an sos snapshot pair. `undo <n>` reverts a pair (`pre..post`) or everything since a single snapshot (`n..0`; `7`, `#7`, `snap-7`); `undo look-3` a look change. Snapshot undos without a TTY need `--yes`. |
| `sos session-start` | Hyprland `exec-once` (§5): theme → export `WAYLAND_DISPLAY`/`HYPRLAND_INSTANCE_SIGNATURE` to systemd/D-Bus → jacksond → shell → first-run wizard. Idempotent, never blocks; log in `~/.local/state/svoya/session.log`. |

Privileged work re-executes **the same program** through `pkexec` (`pkexec /usr/bin/sos modules add … --yes`);
the elevated process re-reads the catalog from its install location and accepts module ids/options only —
never commands or scripts from the caller.

## Machine-readable interfaces

All `--json` outputs are UTF-8 JSON on stdout; human text goes to stdout only without `--json`.

**`sos status --json`** — exactly ARCHITECTURE §4.2, every field optional. Extra keys (ignorable):
`ts` (ISO time), `updates.checkedAt`, and for AMD APUs `gpu[].integrated`, `gpu[].gttUsedMiB`, `gpu[].gttTotalMiB`.
`gpu[]` lists NVIDIA GPUs (nvidia-smi order) then AMD (card order); `index` is the position in that list.
`gpu[].ok` is false when the GPU is ≥ 90 °C or the last `sos doctor` found a GPU failure.
`ai` merges three sources: jacksond's runtime state `$XDG_RUNTIME_DIR/svoya/ai.json`
(`local`, `cloudActiveSince`, anything else it adds), the AI switch → `ai.enabled` (always present) and `ai.off`
(`user` | `system` | `config`, only while off), and today's totals from Jackson's ledger
`~/.local/share/svoya/jackson/spend.json` → `ai.todayCostEur`, `ai.todayCloudRequests`.

**Job files** — `~/.local/state/svoya/jobs/<id>.json`, written atomically; anyone may create one:

```json
{"v": 1, "id": "train-1832", "label": "обучение", "state": "running", "progress": 0.62, "etaSec": 1080,
 "message": "эпоха 2/3", "pid": 12345, "command": ["uv", "run", "python", "train.py"], "cwd": "/…",
 "startedAt": "2026-09-24T18:32:00Z", "updatedAt": "…", "finishedAt": null, "exitCode": null}
```

`state`: running | done | failed | cancelled. `progress` 0..1 or null. `etaSec` is optional (valid at
`updatedAt`); without it status extrapolates from progress. Jobs whose `pid` died are not shown.
`sos run` exports `SVOYA_JOB_ID` and `SVOYA_JOB_FILE`; scripts call `sos job progress $SVOYA_JOB_ID 0.5`
(or the dependency-free `sos_progress.report()` that `sos new` puts in every project); UpsiL programs
report with `sys.progress(0.5)`, and `nn.fit` / `m.ask_all` do it themselves.

**`~/.local/state/svoya/theme.json`** — flat: `id`, `mode`, `pair`, `nameEn`, `nameRu`, `choice`
(`auto` or an id), every `[color]` token as `#AARRGGBB` (alpha first, QML-ready: `accent` `#ffffb547`,
`accentSoft` `#24ffb547`) — the four accent tokens `accent`, `accentSoft`, `accentStrong`, `accentInk` come from the
accent system — plus `accentId` (accent id, `custom`, or `theme` without accents.toml), `accentNameEn`, `accentNameRu`,
`accentCustom` (the user's `#rrggbb` or null), `accentAdjusted` (lightness moved for contrast), `accentContrast`
(vs `surface`), every key of `[font]`, `[shape]`, `[motion]`, `[effects]` with its TOML type, and `appliedAt`.
`/etc/svoya/theme.json` (login screen, `--system`) has the same keys with `choice` = `system`, always on a dark base.

**`sos theme accents --json`** — `[{id, name{en,ru}, note, dark, light, ink{dark,light}, gnome{dark,light}, default,
current}]`, last entry `id: "custom"` (with `custom`, the user's hex). **`sos theme accent X --json`** →
`{ok, accent{id, name, mode, color, soft, strong, ink, requested, adjusted, custom, contrast, inkContrast, gnome, clash,
fallback, note}, changed, visible, previous{theme, accent}, undo (journal id | null), system, theme, dryRun}`;
errors → `{ok: false, error, hint}` (exit 2).

**`sos ai status --json`** — `{enabled, off (user|system|config|null), since, services[{unit, scope, active}],
processes[{pid, name}]}`.

**`sos doctor --json`** — `{"checks":[{id,title{en,ru},status,message{en,ru},gpu,fix|null}], "summary":{ok,warn,fail,skip},
"gpu":{vendor,name,arch,archName,cuda,branch,openModules,packages,torchBackend,gfx}, "torchBackend", "gpuOk", "at"}`;
`fix` = `{safe, root, commands[[argv]], files[], userFiles[], display[], note}`. The summary (without checks) is cached
in `~/.local/state/svoya/doctor.json`.

**`sos modules list --json`**, **`sos modules profiles --json`** — for the first-run wizard: modules with
`installed`, `applicable` (+`reason`), `diskGb`, `vramGbMin`, `aliases`, `options`, `proprietary`; profiles with
the module list resolved for *this* machine (`@gpu` → `nvidia` | `rocm` | nothing), `layout`, `jacksonRoute`, `diskGb`.

**`sos models suggest --json`** — `{hardware, tier, tierName, ctx, default, alternatives[2]}`; each pick has
`id` (e.g. `qwen3.5-9b:Q4_K_M`), `name`, `repo`, `files`, `mmproj`, `quant`, `sizeBytes`, `memoryBytes8k`,
`verdict` (fits | offload | no), `nCpuMoe`, `speed` (fast | good | slow | very-slow), `tokensPerSecond`, `license`,
`vision`, `note`, `pull` (the one-click command). **`sos models pull <id> --yes --json`** prints one JSON object
per line: `plan`, `file`, `progress` (`bytes`, `totalBytes`, `fraction`, ≤ 2/s), `file-done`, `done`, or `error`.

**`sos undo --list --json`** — `[{id, n, pre, post, to, date, description, kind}]`, oldest first (`kind`: pair | single
for sos snapshots, `look` for journal entries, where `n`/`pre`/`post`/`to` are null; `sos undo <id> --yes` applies one).
The look journal is `~/.local/state/svoya/undo.json` (`{seq, entries[{id, kind, at, description{en,ru}, before{theme,
accent}, after{theme, accent}, system}]}`, 50 newest). **`sos snapshot create --reason TEXT [--config home] --json`** →
`{"id": "77", "number": 77, "config", "description", "dryRun"}` or `{"id": null, "error": …}` — no password prompt when
snapperd allows the user (ALLOW_USERS/ALLOW_GROUPS), which is what Jackson's T1 "snapshot first" path needs.

## GPU Doctor checks

gpu.detect · gpu.arch · nvidia.driver · nvidia.branch · nvidia.open · boot.secureboot · nvidia.kernel ·
nvidia.uvm · nvidia.modeset · nvidia.suspend · nvidia.resume · containers.gpu · vulkan.icd · compute.backend ·
cuda.compat · gpu.prime · amd.rocm · amd.gtt · user.groups · storage.ai · memory.zram · fs.snapper ·
snapshots.recent. Policy: R595 open modules for Turing+ (required on Blackwell), R580 for Maxwell/Pascal/Volta;
CUDA 13 needs driver ≥ 580 and Turing+; PyTorch backend `cu130` (Turing+), `cu126` (Maxwell–Volta; uv's `auto`
picks wheels that fail there), `rocmX.Y` (AMD, `[gpu] rocm_backend`, default `rocm7.2`), `xpu` (Intel Arc), else `cpu`.
Device IDs → architecture come from `hw/nvidia_db.py` (regenerate: `python3 cli/tools/gen_nvidia_arch.py pci.ids`).

## Model store

`/srv/ai` (`HF_HOME=/srv/ai`; overridable with `SVOYA_AI_ROOT`): `hub/` (HF cache layout — the single
source of truth), `datasets/`, `views/{llama.cpp,comfyui,ollama}`, `registry.db` (SQLite, `PRAGMA user_version=1`:
`models(path, sha256, size, source, repo, revision, filename, format, arch, quant, params, n_ctx_train, license,
commercial, eu_ok, regions_excluded, vram_bytes, vram_ctx, added_at, last_used, meta)` and a hash cache).

**VRAM estimate** (`models/estimate.py`):

```
weights = Σ tensor bytes (all shards)                     kv = n_ctx × Σ_layers n_kv_heads × (d_k + d_v) × b
        = 2 × n_layers × n_ctx × n_kv_heads × head_dim × b     (b: f16 2 · q8_0 34/32 · q4_0 18/32)
          hybrid models (full_attention_interval): only full-attention layers · MLA: (kv_lora_rank + rope_dim)
compute = max(A, S) + 0.1·min(A, S) + 32·n_vocab           A = n_ubatch·32·n_embd·4 · S = no-FA ? n_ubatch·n_ctx·n_head·4 : 0
runtime = 400 MiB (CUDA/ROCm) · 256 MiB (Vulkan)           total = weights + kv + compute + runtime
fits: total ≤ VRAM − used − max(256 MiB, 3 %) · offload: MoE experts to RAM (--n-cpu-moe N) or last k layers (-ngl k)
```

The compute term is a heuristic calibrated on llama.cpp's reported buffers; the KV term is exact for
standard attention and an upper bound with sliding windows.

**Licenses** (`data/model_catalog.toml`, `models/licenses.py`): curated facts win over the GGUF/model-card license
id. Encoded: Qwen-Image (Apache-2.0) vs Qwen-Image 2.1 (non-commercial) · Z-Image-Turbo 6B (Apache-2.0, 16 GB) ·
FLUX.2 klein 4B (Apache-2.0) vs 9B (non-commercial) · Wan 2.2 (Apache-2.0) · LTX-2.5 19B (free < $10M revenue) ·
HunyuanVideo 1.5 (excludes EU/UK/KR) · MiniMax-H3 (excludes EU/UK/KR/US) · Parakeet TDT v3 (CC-BY-4.0) ·
Chatterbox (MIT) · Qwen3-TTS (Apache-2.0) · Llama 4 multimodal (excludes EU users).

**Suggest ladder** (`data/model_ladder.toml`, verified on the Hub 2026-09-25, Apache-2.0 only): Qwen3.5 4B/9B/27B/
35B-A3B/122B-A10B (unsloth GGUF + vision projector) and gpt-oss 20B/120B, in tiers CPU · 6–8 · 10–12 · 16 · 24 ·
32–48 GB · 64 GB+/unified 96–128 GB.

## Themes

### Accent

`themes/accents.toml` (installed as `/usr/share/svoya/themes/accents.toml`) defines 8 accents with a dark-base and a
light-base variant; the choice is `[theme] accent = "<id>|#rrggbb"` in `~/.config/svoya/svoya.toml` (default: the base
theme's `accentDefault`; `signal` = amber on dark bases, ink blue on light ones). For the base theme in use sos derives
`accent` (a custom hex keeps its OKLCH hue and chroma; lightness moves just far enough for 4.5:1 against `surface`, and the
confirmation says so), `accentSoft` (14 % / 9 % alpha), `accentStrong` (OKLCH L +6 % dark, −6 % light) and `accentInk`
(`#141518` or `#ffffff`, whichever contrasts more). Names: ids, English and Russian names (`сирень`, `лёд`/`лед`), color
words with Russian inflections (`фиолетовым` → lilac, `голубой` → ice, `белый` → mono …); `red`/`красный` is refused
(red means errors). A custom color close to ok/warn/bad/cloud gets a note. Where it goes: the Hyprland active border
and hyprbars button glyphs (shown on hover), terminal cursor/selection/links (kitty, foot), GTK/libadwaita accent
(`@accent_color`, CSS variables) and GNOME `accent-color` (closest of blue, teal, green, yellow, orange, red, pink,
purple, slate), qt6ct Highlight/Link/Accent, btop meters, fuzzel prompt/matches, the ——— of the fastfetch mark.
Never: the 16 ANSI colors, warn/bad/ok/cloud, borders other than the focused window, headings.

### Templates

`themes/templates/manifest.toml` lists the targets: Hyprland colors (`~/.config/hypr/svoya-colors.conf`,
to be `source`d), kitty, foot, GTK 3/4 (`@define-color` + libadwaita CSS variables), qt6ct color scheme and
`qt6ct.conf` (merged), btop theme and `btop.conf` (merged), fastfetch, fuzzel. A pre-existing user file is kept
once as `<file>.pre-svoya` and included first (kitty/foot/fuzzel/GTK), so user settings survive and theme colors win.
Opt out per target: `[theme] skip = ["kitty"]`.

Template language (no code execution): `{{ color.accent }}` and filters `hex` (#rrggbb), `hexa` (#aarrggbb),
`rgb` ("r,g,b"), `rgba(0.5)`, `strip` (rrggbb), `stripa` (rrggbbaa), `ansi` (38;2;r;g;b), `mix(other, t)`,
`over(bg)`, `lighten(x)`, `darken(x)`, `opacity(a)`, `ink` (text color for that fill), `alpha`, `json`, `upper`,
`lower`, `round(n)`. Variables: `color.*` (incl. `accentStrong`), `accent.id|custom|adjusted|gnome|name.en|name.ru`,
`font.*`, `shape.*`, `motion.*`, `effects.*`, `name.en|ru`, `id`, `mode`, `pair`, `term.*` (16 ANSI colors derived from
the base theme's semantic tokens — never the accent), `icons`, `colorScheme`, `path.home|config|state`. Unknown names
are errors.
`auto`: NOAA sunrise/sunset for `[location] latitude/longitude` (default Tallinn 59.437 N 24.745 E); polar
day/night or a bad location → 07:00–20:00. `cli/systemd/sos-theme-auto.{service,timer}` re-checks every 15 min.

## The AI switch

`sos ai off` writes `~/.config/svoya/ai.off`, stops the user units `jacksond`, `svoya-llm`, `llama-swap`,
`llama-server`, `ollama` that are running and this user's stray `llama-server`/`llama-swap` processes, and remembers
what it stopped; `sos ai on` removes the file and starts jacksond plus exactly those again. `--system` does the same
for the machine through pkexec: `/etc/svoya/ai.off`, system units `svoya-ollama`, `ollama`, `llama-swap` — and a user
cannot switch that back on alone. While off: `sos status` reports `ai.enabled = false`, `sos session-start` skips
jacksond, `sos models serve` refuses, and `svoya-llm.service`/`svoya-ollama.service` have
`ConditionPathExists=!…/ai.off`. `[ai] enabled = false` in `svoya.toml` still works as a third way to say off.

## Modules

`modules/<id>.toml` + `modules/<id>/{install,remove}.sh`, shared helpers in `modules/lib/common.sh`.
14 modules: base-ai, nvidia, cuda-devel, rocm, llm-local, studio, voice, ml-lab, agents, dev, cloud-burst, codecs,
gaming, notes (Obsidian from Flathub — proprietary freeware, only on request). Profiles: `modules/profiles.toml`
(newcomer, creator, ml, agent, hacker + `offline` modifier). Extensions to §4.5: `aliases`, `hardware`,
`options` (`--with`), `user_scripts`, `proprietary`, and apt placeholders `{nvidia.branch}`, `{nvidia.open}`,
`{kernel.flavor}`. State: `/var/lib/svoya/modules.json` (`aptNew` = packages this module actually installed, so
`remove` never takes away what you had before or what another module needs).

Scripts run with a clean environment: `PATH`, `LANG=C.UTF-8`, `HOME`, `DEBIAN_FRONTEND=noninteractive` and
`SVOYA_MODULE`, `SVOYA_ACTION`, `SVOYA_MODULE_DIR`, `SVOYA_LIB`, `SVOYA_TARGET_USER/UID/HOME`, `SVOYA_AI_ROOT`,
`SVOYA_LANG`, `SVOYA_GPU_VENDOR`, `SVOYA_TORCH_BACKEND`, `SVOYA_KERNEL_FLAVOR`, `SVOYA_NVIDIA_ARCH/BRANCH/OPEN`,
`SVOYA_AMD_GFX`, `SVOYA_OPT_<OPTION>=1`. Rules: idempotent; no `curl | sh` — downloads go to a temp file and are
checked against a sha256 (publisher or the GitHub release `digest`) before use; every changing command is echoed;
AI services are installed, never auto-started.

## Development

```
python3 -m unittest discover -s cli/tests -t cli      # 211 tests, ~3 s, no network, no root (also run as non-root)
cli/bin/sos …                                         # runs from the checkout (uses ./themes, ./modules)
SVOYA_ROOT=/tmp/fake SVOYA_AI_ROOT=… SVOYA_VAR_LIB=…  # fake system root for experiments
```

Every external command goes through `runner.Runner` (tests use the table-driven `FakeRunner`; `--dry-run` prints
mutating commands instead of running them). Fixtures: `cli/tests/fixtures/` (lspci, nvidia-smi, snapper, apt,
/proc files); synthetic GGUF files are generated by `cli/tests/gguf_synth.py`; HTTP Range reads are tested against a
local server. Completions: `cli/completions/{sos.bash,_sos,sos.fish}` (all call `sos __complete …`).

Installed layout (for packaging): `/usr/bin/sos` + `/usr/bin/svoya` → `cli/bin/sos`; `/usr/lib/svoya/svoya_cli/`;
`/usr/share/svoya/{themes,templates,modules}`; completions in the usual vendor directories; user units in
`/usr/lib/systemd/user/`.
