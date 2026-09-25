# Frequently asked questions

> По-русски: [docs/ru/faq.md](../ru/faq.md).

**Contents:** [The project](#the-project) · [Privacy and AI](#privacy-and-ai) ·
[Hardware and models](#hardware-and-models) · [Using SOS](#using-sos) ·
[Getting involved](#getting-involved)

## The project

### What does SOS stand for?

**Svoya Operating System**: in Russian, «СОС — Своя Операционная Система», "your own operating
system" («своя» means "one's own"). In Morse code «СОС» is `··· ——— ···`, the same signal as SOS
in international Morse. That is our mark.

### Is SOS related to the `sos` support tool (sosreport)?

No. That is a different project, which collects diagnostic reports on many Linux systems. To
avoid clashes, SOS keeps its internal files under the name `svoya`: packages `svoya-*`,
settings in `/etc/svoya/` and `~/.config/svoya/`.

### Is SOS just Ubuntu with a theme?

No. SOS uses Ubuntu 26.04 LTS packages as its engine: the kernel, drivers, CUDA and ROCm come
from the Ubuntu archive. Everything you see and use is ours: the Svoya Shell desktop, Jackson,
the `sos` command, the module system and the model store. SOS is not affiliated with or
endorsed by Canonical.

We chose this engine because NVIDIA supports it first, because its archive ships signed NVIDIA
kernel modules (so Secure Boot keeps working) together with CUDA and ROCm packages, and because
an LTS release gets security updates for years. We would rather spend our time on what makes SOS
different than on a kernel or a package manager.

### Is it free? Is there a paid edition?

SOS is free and open source (Apache-2.0 for code). There is no paid edition, no account and no
upsell inside the system.

### Is it ready to use?

Not for daily work yet: SOS is pre-alpha, and v0.1 «Первый сигнал» is being built (see the
[roadmap](../ROADMAP.md)). But you can try it: every build from `main` is boot-tested in CI, and the
[install guide](install.md) shows how to download a test build and run it in a virtual machine.

### Who is behind it?

SOS is an independent open-source project, led by Maksim and maintained through LIFKURU OÜ, a
small company in Estonia (EU). How decisions are made: [GOVERNANCE.md](../../GOVERNANCE.md).

## Privacy and AI

### Does SOS collect any data?

No. There is no telemetry and no account, and crash reports are sent only if you opt in. What
leaves your machine, and when: [privacy.md](privacy.md).

### Who is Jackson?

Jackson («Джексон») is the assistant built into SOS: a friendly guy from the 2000s internet,
cheeky but useful. He is more than a chat window. He can use tools and run other agents, but
he asks before anything risky, shows exactly what he is going to do, logs every action and can
undo it. Call him with `Super+J`, or type `j` in a terminal.

### Can I turn AI off completely?

Yes. One switch in the control center turns every AI feature off. You can also remove Jackson
(`sudo apt remove svoya-jackson`) and any AI module. The rest of the system works without them.
Details: [privacy.md](privacy.md#how-to-turn-ai-off).

### Does Jackson send my data to the cloud?

Not unless you set it up. By default, Jackson uses only local models (route policy
`local-only`). If you add a cloud provider and allow cloud routing, every request that leaves
the machine is marked, and its cost is shown.

### Which cloud providers can Jackson use?

Out of the box: Anthropic, Google Gemini, DeepSeek and Mistral, plus any OpenAI-compatible
endpoint you configure. Local models run through llama.cpp or Ollama. The `eu` route policy
limits Jackson to providers hosted in the EU.

### Do I need Obsidian?

No. The first-run wizard offers [Obsidian](https://obsidian.md) as an optional app, and Jackson
can keep his memory in your Obsidian vault. Obsidian is not open source. Without it, Jackson's
memory is the same kind of Markdown files, in `~/.local/share/svoya/jackson/memory/`.

## Hardware and models

### Do I need a GPU?

No. Without a GPU the whole system works, and small local models run on the processor. For
larger models, image and video generation, an NVIDIA RTX card (20 series or newer) or a recent
AMD card is what SOS is built around. See the [hardware table](../../README.md#hardware).

### My card is a GTX 1060 / 1080. Will it work?

The desktop, yes. The driver comes from NVIDIA's 580 branch, the last one for these cards, and
CUDA is limited to version 12.x. Many current AI tools no longer support these cards, so expect
limits. `sos gpu` tells you what works.

### Does SOS work without internet?

Yes. The image carries the drivers, and there is an "offline only" profile. Models have to be
downloaded once, or copied into `/srv/ai` from another machine.

### Can I use models I already have?

Yes. Put them into the shared store `/srv/ai`. SOS creates views of it for llama.cpp, Ollama and
ComfyUI, and `sos models dedup` finds duplicate files.

### Why does SOS talk about licenses before a download?

Some model licenses exclude the EU or forbid commercial use. SOS reads the license information
and compares it with your settings before anything is downloaded, so you do not find out later.

## Using SOS

### Hyprland sounds hard. Is SOS only for tiling fans?

No. Windows float and the mouse works by default. Tiling is a preset you can turn on in the
first-run wizard or with `Super+T`.

### What about the `svoya` command I saw in older docs?

It is the same tool. `sos` is the name to use; `svoya` stays as an alias so old scripts keep
working.

### Can I run Windows apps and games?

That is not what SOS focuses on. Steam and other apps from Flathub should work as on other Linux
systems, but we do not test them yet.

### Snap packages?

SOS modules install from APT and Flatpak. Snap is not part of the module system.

### ARM, Apple Silicon?

Not supported for now. SOS targets 64-bit x86 PCs (amd64).

## Getting involved

### How can I help?

Hardware reports are the most useful thing right now, followed by testing, translations and
documentation. Start with [CONTRIBUTING.md](../../CONTRIBUTING.md).

### Can I build my own distribution on top of SOS?

Yes, the code is Apache-2.0. Give your system its own name and logo; you may say it is "based on
SOS". Details: [TRADEMARKS.md](../../TRADEMARKS.md).
