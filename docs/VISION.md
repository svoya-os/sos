# SOS — Vision

**СОС — Своя Операционная Система. SOS — Svoya Operating System: your own operating system for AI.**
Local-first. Under your control.

`··· ——— ···` — the mark is the Morse code for «СОС». It reads the same in Russian and international Morse.

---

## 1. Why this exists

In 2025–2026 every major OS decided to "add AI". The results made people angry rather than productive:

* Windows announced an "agentic OS"; users answered with a wave of criticism, asked for reliability,
  and Recall still stores screenshots that malware can read.
* Ubuntu 26.04 added AI features and got a backlash because there is no single switch to turn them off.
* The hottest open-source agents of 2026 (OpenClaw and friends) shipped with tens of thousands of exposed
  instances and more than a thousand malicious "skills".
* Enthusiasts who run models locally still fight drivers, CUDA versions, duplicated 30 GB model files,
  broken suspend/resume and environments that a single ComfyUI node can brick.

Nobody ships the two things people actually want: **a workstation that sets up local AI by itself** and
**an assistant that is safe by design** — sandboxed, logged, undoable, and one key away from "off".
SOS is exactly that.

## 2. Who it is for

1. **Local-AI creators and enthusiasts** (first): NVIDIA RTX 20–50 or AMD RDNA3+/Strix Halo, running
   LLMs, image, video and voice models at home. They switch systems, make videos, and measure results.
2. **ML engineers and researchers**: reproducible project environments, CUDA/ROCm that never fight each other,
   experiment tracking, painless burst to cloud GPUs.
3. **People leaving Windows** who want modern AI tools without ads, accounts and telemetry.

## 3. The promise (published, binding)

* No ads, no upsells, no account, no telemetry. Crash reports only if you opt in.
* AI never starts by itself. One switch turns every AI feature off; every AI component can be removed.
* Local by default. Every request that leaves the machine is visible, and you can see what it cost.
* Everything is reversible: updates, modules, settings and every action Jackson takes.
* Your data is plain files you can read, move and delete.

## 4. Five pillars

### 4.1 A GPU that just works
Signed drivers from the engine archive, a driver pool on the ISO for offline installs, and **GPU Doctor**
(`sos doctor`) that checks driver ↔ CUDA ↔ PyTorch compatibility, Secure Boot, suspend/resume fixes and
container GPU access. The OS owns the driver; **each project owns its CUDA** (uv/pixi/containers), so
version hell disappears.

### 4.2 Jackson — the assistant that controls agents
Jackson is not one more chatbot. It is the OS layer that routes requests to local or cloud models,
runs tools and other agents (Claude Code, Codex, OpenCode, goose…) inside sandboxes, asks before anything
risky with an exact preview, keeps a tamper-evident log, and undoes its own actions through filesystem
snapshots. Instant by hotkey, push-to-talk voice in Russian and English, memory stored as plain Markdown.

### 4.3 The AI toolbox as modules
Nothing is forced. In the first-run wizard you pick a profile (Newcomer, Creator, ML Engineer,
Agent Builder, Hacker, plus "offline only") and add or remove modules any time:
Local LLMs · Studio (image/video/voice) · ML Lab · Agents · Dev · Cloud burst.
One **model store** (`/srv/ai`) is shared by every tool — no duplicates. Before anything downloads,
SOS tells you whether it fits your GPU and whether its license allows your use (the EU matters).

### 4.4 SOS Shell — minimal, matte, ours
A desktop built from scratch on Quickshell and Hyprland. Graphite by night, Paper by day, Phosphor for the
nostalgic. Matte surfaces instead of glass, IBM Plex typography, one signal color, the Morse mark,
Jackson's oscilloscope. Old internet and hacker culture live in the details — never in your way.

### 4.5 Undo everything
Btrfs snapshots before every update, module change and Jackson action. `Super+Z` undoes the last change;
yesterday's system is one entry in the boot menu.

## 5. What we deliberately do not do

* We do not write our own kernel or package manager: NVIDIA ships drivers and CUDA only for Linux and
  Windows, and we would rather spend our time on what makes SOS different. The engine (Ubuntu 26.04 LTS
  packages) is invisible and replaceable.
* We do not ship CUDA, cuDNN or model weights inside the ISO (licenses), and never a model whose license
  excludes the user's region without saying so.
* We do not require a cloud service, an account, or an internet connection to work.
* We do not use dark patterns — including "AI" buttons in places you did not ask for.

## 6. How we compare

| | SOS | Omarchy | Ubuntu 26.04 | Bluefin GDX | Pop!_OS |
|---|---|---|---|---|---|
| Local AI ready out of the box | ✔ modules + fit check | manual | snaps (partial) | CLI tools | — |
| Assistant with sandbox, audit, undo | ✔ Jackson | coding agents only | voice typing (26.10) | — | — |
| One switch to turn AI off | ✔ | — | — | — | n/a |
| Driver + Secure Boot without key enrollment | ✔ (signed) | — | ✔ | enroll key | disable SB |
| Rollback of updates | ✔ snapshots | ✔ snapshots | — | ✔ image | — |
| Newcomer-friendly (floating windows, mouse) | ✔ + tiling preset | tiling only | ✔ | ✔ | ✔ |

## 7. Milestones

* **v0.1 «Первый сигнал» / First Signal** — bootable ISO, SOS Shell (bar, launcher, Jackson panel,
  notifications, lock, greeter), Jackson text MVP (local + cloud routing, tools, tiers, audit, undo),
  `sos` command (doctor, modules, models, theme, update/undo), Graphite/Paper/Phosphor, CI that boots and
  screenshots every build.
* **v0.2 «Голос» / Voice** — push-to-talk RU/EN, installer polish, model store UI, Studio module.
* **v0.3 «Поводок» / Leash** — agent sandboxes (containers/microVMs), computer use in a separate session,
  signed skill registry.
* **v1.0** — stable channel, documentation, hardware certification list.

## 8. Name and brand

* Russian: **СОС — Своя Операционная Система**. English: **SOS — Svoya Operating System** («svoya» = "one's own").
* Command: `sos` (`sos install comfyui`, `sos fix`, `sos gpu`, `sos undo`); `svoya` remains an alias.
* Internal namespace `svoya` (packages `svoya-*`, paths `/usr/share/svoya`, `~/.config/svoya`) — it avoids clashes with the
  unrelated `sos`/sosreport tool. Code lives at github.com/svoya-os/sos.
* The assistant is **Джексон / Jackson** — a character, a cool guy from the 2000s internet, not a "daemon". Short command: `j`.
* The mark: Morse `··· ——— ···`. Colors: amber signal on graphite; ink blue on paper.
