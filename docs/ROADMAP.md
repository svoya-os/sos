# Roadmap

SOS is pre-alpha. This roadmap turns [VISION.md](VISION.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
into checklists. There are no dates: a milestone ships when its checklist is done and its
"done when" criteria pass on real hardware. A box is ticked when the work is merged on `main`.

Last reviewed: 2026-10-25.

- [v0.1 «Первый сигнал» / First Signal](#v01-первый-сигнал--first-signal): bootable system, shell, text Jackson, the `sos` command
- [v0.2 «Голос» / Voice](#v02-голос--voice): voice, model store UI, Studio
- [v0.3 «Поводок» / Leash](#v03-поводок--leash): agents in sandboxes, computer use, signed skills
- [v1.0](#v10): stable channel, documentation, hardware certification

---

## v0.1 «Первый сигнал» / First Signal

**Goal:** an ISO you can install on a real machine with an NVIDIA or AMD GPU. You get Svoya
Shell, Jackson in text mode and the `sos` command, and nothing leaves the machine until you
turn something on.

### Foundations

- [x] Vision, architecture contract and design system
- [x] Theme tokens: Graphite, Paper, Phosphor
- [x] Desktop and launcher mockups in all three themes
- [x] Project documents: README (EN/RU), contributing guide, Code of Conduct, security policy,
      governance, trademark policy draft, guides, issue forms, per-file licensing (REUSE)

### Image and installer

- [x] Hybrid ISO built from `image/`: mmdebstrap → squashfs → ISO
- [ ] Boots and installs with Secure Boot on, through the engine's signed boot chain (boots: a CI
      test every build; installing with Secure Boot on: not tested yet)
- [x] Driver pool on the NVIDIA ISO: NVIDIA current branch (open kernel modules) and the 580
      legacy branch for GTX 900/1000; installs offline. The standard ISO stays one file under
      2 GiB and downloads the driver during the install
- [x] Calamares installer with SOS branding: Btrfs with a subvolume layout ready for snapshots,
      optional disk encryption
- [ ] No Ubuntu branding visible anywhere
- [ ] Engine defaults reviewed for network silence: clock sync, connectivity checks, firmware
      metadata, periodic package list updates, crash reporters. Each one is off, or asked in the
      first-run wizard (see [privacy.md](guides/privacy.md))
- [ ] ISO published with SHA-256 checksums and a signature (checksums with every test build; the
      signature waits for `SOS_RELEASE_SIGNING_KEY`)

### Packages

- [x] Debian packages: `svoya-shell`, `svoya-jackson`, `svoya-cli`, `svoya-session`,
      `svoya-base`, `svoya-fonts`, `svoya-branding`, `svoya-installer` (there is no `svoya-theme`:
      the theme tokens ship in `svoya-cli`, the GTK theme, icons and cursors in `svoya-branding`)
- [x] Our own signed APT repository (flat, on the `test` release; `sos update` reads it)
- [x] The `sos` command installed, with `svoya` as a compatibility alias, and no file conflict
      with the engine's unrelated `sos` support-tool package (sosreport)

### Svoya Shell

- [x] Bar: Morse mark, workspaces, window title, job meter, GPU, status icons, keyboard layout,
      Jackson's mini-scope, clock; segments hide when data is missing
- [x] Launcher (`Super+Space`); `?` or `Tab` hands the query to Jackson
- [x] Jackson panel (`Super+J`): route chip, streamed answers, approval cards
      (once · always in this project · deny), footer with latency, tokens, cost and
      local/cloud
- [x] Notifications and a notification center
- [x] Control center: Wi-Fi, Bluetooth, sound, brightness, theme, focus modes, and **AI &
      privacy**: route, today's spend, requests that left the machine, and the one switch that
      turns every AI feature off
- [x] Lock screen and greeter (greetd)
- [x] On-screen display and the POST screen
- [x] First-run wizard, at most seven steps, each skippable and reversible: accessibility,
      language and keyboard, look, layout, profile, AI (detected GPU; **one suggested local model
      that fits the GPU and memory, installed with one click**; **Obsidian** from Flathub with one
      click, for Jackson's memory; optional cloud keys), privacy summary with the first snapshot
      and the shortcut cheat sheet
- [x] Keyboard map from [ARCHITECTURE.md §6](ARCHITECTURE.md#6-keyboard-map-defaults)
- [x] Reduce-motion and high-contrast variants; all copy in Russian and English

### Jackson (text)

- [x] Runs in the background as a user service; socket protocol from
      [ARCHITECTURE.md §4.3](ARCHITECTURE.md#43-jackson-socket-protocol)
- [x] `j` in the terminal (`j найди мои датасеты`), `jackson` as the long name
- [x] Character and voice: a friendly guy from the 2000s internet, cheeky but useful; «ты» by
      default, «вы» as a setting; Russian and English
- [x] Router: local (llama.cpp, Ollama) and cloud providers; route policy `local-only` by
      default; daily budget; cost and "left the machine" counters
- [x] Tools and MCP servers under permission tiers T0–T4; approval cards with the exact preview;
      taint tracking for untrusted content
- [x] Hash-chained audit log; undo through snapshots
- [x] Memory as Markdown in git, optionally inside the user's Obsidian vault
- [x] API keys in the Secret Service keyring, never in files or prompts
- [x] Honest by rule, in every persona: no flattery, «это неверно» when the user is wrong, «не
      знаю» instead of a guess
- [x] The Arena («арена: …»): the Advocate, the Critic and the Checker answer on their own, then
      Jackson sums up what they agree on, where they disagree and what is left to check
- [x] «Кто сделал, тот не проверяет»: after changes, a separate request that did not do the work
      compares the request, the tools' results and the answer

### The `sos` command

- [x] `sos gpu` (GPU Doctor): driver ↔ CUDA ↔ PyTorch, ROCm, Secure Boot, suspend/resume,
      GPU access from containers
- [x] `sos fix`: safe fixes, snapshot first
- [x] `sos install <module>` and module add, remove, list, profiles; first module: Local LLMs
- [x] Model store in `/srv/ai`: fit check, license flags (EU, commercial use), duplicates,
      per-tool views (llama.cpp, Ollama, ComfyUI)
- [x] `sos theme`: Graphite, Paper, Phosphor, auto (sunrise and sunset); templates for Hyprland,
      kitty, GTK, Qt, btop, fuzzel
- [x] `sos update` with a snapshot first; `sos undo` and `Super+Z`; yesterday's system in the
      boot menu
- [x] `sos status --json` for the bar

### Quality

- [x] CI builds every commit, boots the ISO in QEMU and takes screenshots
- [ ] Unit tests, shellcheck, qmllint and `reuse lint` in CI
- [ ] Network silence test: a fresh install opens no outbound connection until the user turns a
      feature on
- [ ] Tested on at least one NVIDIA RTX machine, one AMD RDNA 3 or RDNA 4 machine and a
      CPU-only VM

### Project

- [ ] Repository `svoya-os/sos` public; private vulnerability reporting on; issue labels and the
      maintainers team created
- [ ] Contact addresses working: security, conduct, trademarks
- [ ] Trademark policy reviewed by a lawyer

**Done when:** the ISOs install offline with Secure Boot on; `sos gpu` is clean on the NVIDIA
and AMD test machines; Jackson answers with a local model, asks before any T2 action and undoes
a file change; and the network silence test passes.

---

## v0.2 «Голос» / Voice

**Goal:** talk to Jackson, and make models and creative tools easy.

- [ ] Push-to-talk: hold `Super+J`, speak Russian or English; local speech-to-text and
      text-to-speech; voice stays off until you turn it on
- [ ] Jackson's scope follows the microphone and his voice (listening, speaking states)
- [ ] Installer polish
- [ ] Model store in the shell: search, will-it-fit, license, disk use, remove
- [ ] Studio module: image, video and voice tools such as ComfyUI (`sos install comfyui`),
      wired to the shared model store
- [ ] Job queue: start a download or a render after the current job finishes
- [ ] Night rule: heavy jobs (renders, training, big downloads) wait for the morning unless you
      say yes; a quiet GPU mode (power limit) for long renders
- [ ] Spoken approvals: Jackson asks «разрешаешь?» out loud and takes a spoken yes or no; an
      agent's work is checked by the Checker before he reports it
- [ ] Dictation: hold a key, speak, the text appears where the cursor is (local speech-to-text,
      like OpenWhispr)
- [ ] «Окей, Джексон»: a local wake phrase, off until you turn it on
- [ ] Summaries to Telegram as a voice message, with your own bot (bots cannot call)
- [ ] Focus mode: the apps you pick open after a pause screen or a few squats in front of the
      webcam (MediaPipe Pose, local, nothing recorded)
- [ ] Local models on modest cards: a 27B model on 8–16 GB with a 4-bit KV cache and threads =
      physical cores; regular models only (no "abliterated"), every download checked by its hash
- [ ] Model cascade: a small local model answers simple questions, the big one only hard ones

**Done when:** a Russian and an English speaker can do a full task by voice without touching
the network, and a new user can install Studio and generate an image from the wizard's
suggestions alone.

---

## v0.3 «Поводок» / Leash

**Goal:** agents do real work, on a leash.

- [ ] Agent sandboxes in containers (podman) and microVMs for Claude Code, Codex, OpenCode,
      goose and others, with per-project grants
- [ ] Every network destination of a sandbox visible, and new ones approved (tier T2)
- [ ] Computer use in a separate session, never on your main desktop
- [ ] Signed skill registry: reviewed, signed skills; unsigned skills off by default; the source
      of every skill shown
- [ ] Sandbox and permission code reviewed by someone outside the core team
- [ ] Jackson sees the system as text (windows, the focused app, network, battery, jobs): cheaper
      than screenshots, the base for computer use
- [ ] Three coding agents on one task in their sandboxes, their results compared (the Arena for
      code); local MoE models with few active parameters for code
- [ ] A light headless browser for agents (MCP inside), evaluated against Firefox in a sandbox
- [ ] Offline radio: a Meshtastic module (LoRa mesh, 868 MHz in Europe), a map of the nodes, and
      Jackson relaying short messages without internet; an RTL-SDR module (scan, record, hints,
      receive only)
- [ ] Tor, said honestly: Tor Browser in one word, never "100 % anonymity"

**Done when:** a coding agent can work on a project for an hour inside its sandbox, every
action is in the audit log, and a documented escape attempt suite fails.

---

## v1.0

**Goal:** stable enough to recommend to people who are not enthusiasts.

- [ ] Stable update channel and a published support period for each release
- [ ] Complete documentation in English and Russian; website
- [ ] Hardware certification list
- [ ] All modules from the vision: Local LLMs, Studio, ML Lab, Agents, Dev, Cloud burst
- [ ] At least two key holders for every signing key ([GOVERNANCE.md](../GOVERNANCE.md#signing-keys))
- [ ] Final trademark policy, reviewed by a lawyer
- [ ] External security audit of Jackson's permissions and sandboxes
- [ ] Accessibility review: WCAG AA, full keyboard use, reduce motion
- [ ] An assistive mode for blind users: a screen reader that works in the shell and spoken
      descriptions of what is on the screen
- [ ] A start screen like an operator's console: the system, jobs, network and AI use at a glance
- [ ] A dark theme in the mood of "Wired" (Serial Experiments Lain), with our own art, and one live
      detail on every empty screen
- [ ] Gestures through the webcam (local)
- [ ] A software bill of materials (SBOM) for every ISO; Cyber Resilience Act steward duties in
      place before 11 December 2027 ([SECURITY.md](../SECURITY.md#eu-cyber-resilience-act))
- [ ] Maintainer council formed ([GOVERNANCE.md](../GOVERNANCE.md#towards-a-maintainer-council))

---

## Not planned

From [VISION.md §5](VISION.md#5-what-we-deliberately-do-not-do): our own kernel or package
manager; CUDA, cuDNN or model weights inside the ISO; anything that requires a cloud service, an
account or an internet connection; dark patterns, including AI buttons where you did not ask
for them.

Looked at and left out (from the saved videos, 2026-11): proxies that promise "Claude Code for
free", tools that share other people's OAuth logins, models from torrents without checked hashes,
jailbreak prompts, "abliterated" models in the model store, closed apps as the base of a feature
(Beeper, LM Studio: SOS keeps llama.cpp). Sensing people through walls with Wi-Fi (ESP32) stays an
experiment, only with the consent of everyone at home.
