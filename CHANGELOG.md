# Changelog

Notable changes to SOS. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Releases follow the milestones in the
[roadmap](docs/ROADMAP.md): v0.1 «Первый сигнал» (First Signal), v0.2 «Голос» (Voice),
v0.3 «Поводок» (Leash), v1.0.

How to add an entry:

- Write for people who use SOS: what changed for them, not how the code changed.
- Add it under **Unreleased**, in one of the groups Added, Changed, Deprecated, Removed, Fixed,
  Security.
- Start the entry with **Privacy:** if it changes what leaves the machine or adds a network
  request, and update [docs/guides/privacy.md](docs/guides/privacy.md) in the same pull request.

## [Unreleased]

Work towards v0.1 «Первый сигнал».

### Added

- Vision: the promise, five pillars and milestones ([docs/VISION.md](docs/VISION.md)).
- Architecture contract: layers, repository map, filesystem layout, and the interfaces between
  components (theme tokens, `sos status --json`, the Jackson socket protocol, permission tiers
  T0–T4, the module catalog, the model store) ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).
- Design system, with desktop and launcher mockups rendered in Graphite, Paper and Phosphor
  ([design/](design/)).
- Theme tokens for Graphite, Paper and Phosphor ([themes/](themes/)).
- First code for Jackson, the `sos` command and the branding tools. Work in progress, not usable yet.
- Project documents: README in English and Russian, contributing guide with DCO sign-off and a
  policy for AI-assisted contributions, Code of Conduct (Contributor Covenant 2.1), security
  policy, governance, trademark policy draft, roadmap.
- Guides: install, build from source, first steps, privacy, FAQ; install, first steps and FAQ
  in Russian.
- Licensing recorded per file with [REUSE.toml](REUSE.toml): Apache-2.0 for code, CC BY-SA 4.0
  for artwork and documentation, fonts under OFL-1.1 and MIT.
- Issue forms for bugs, feature requests and hardware reports; pull request template.
- While a local model reads a request before it answers (minutes on a computer without a graphics
  card), the Jackson panel and `j` show how far it got: «читаю запрос… 45%». A long read no longer
  counts as a model that stopped answering.
- **Privacy:** voice (`sos install voice`, v0.2 «Голос»): press the microphone in Jackson's panel
  or hold Super+J, speak Russian or English, and Jackson answers out loud, starting with his first
  sentence while the rest is still being written. After an answer he listens a few seconds more, so
  you can go on talking; «спасибо, всё» or the button ends it. Speech is recognized and spoken on
  your computer (Silero VAD, Parakeet TDT 0.6B v3, a local voice); nothing is recorded or sent.
  Installing the module downloads these models from Hugging Face.

### Changed

- The system is called **SOS — Svoya Operating System** («СОС — Своя Операционная Система»),
  and its command is `sos`; `svoya` stays as an alias. Package names and paths keep the
  technical name `svoya`. Jackson has a short command too: `j`.
- Jackson greets and confirms differently every time («йоу», «здарова», «салют»…) and does not
  repeat a joke or a quip until the others had their turn; the login and lock screens vary his
  lines too.

- A local model answers much sooner after the first question: Jackson's system prompt no longer
  changes from one request to the next (the time, route and folder come with the request, memory
  and skills only with the request they match), so llama.cpp reuses what it has already read of
  the prompt and the conversation instead of reading some 3,000 tokens again every time.
- Local models answer without thinking first: Qwen3.5's template thinks by default, minutes on a CPU
  of text nobody sees (`thinking = true` under `[providers.local]` brings it back).

### Fixed

- Wired Ethernet works out of the box: NetworkManager manages every network device, as on Ubuntu
  Desktop (a computer on a cable, or a virtual machine, stayed offline).
- The console welcome, `/etc/issue` and `lsb_release` name SOS again: the build lost these files.
- After `sos install steam` the launcher and the top bar call Steam «Steam», not Debian's «Install
  Steam».
- In the live session Steam, Flatpak apps and Jackson's sandbox start: no AppArmor profile is
  loaded there, and Ubuntu's restriction of user namespaces denied every one («Steam now
  requires user namespaces to be enabled»). Installed systems keep the restriction and Ubuntu's
  profiles, which allow these programs.
- Jackson no longer runs half of a request as a quick command: «скинь скриншот в телеграм» or
  «запиши видео с экрана» is not just a screenshot, the price of a battery is not its charge; such
  requests go to the model.
- When the local model does not answer, Jackson says what to check (`sos models serve --status`)
  or how to start it, instead of an address and a socket error.
- **Privacy:** the local model server (`sos models serve`, the llm-local module) serves the models
  in `/srv/ai` once each and never asks Hugging Face about them. It listed the store a second time
  under repository names, asked Hugging Face before loading those, and ran two copies of one
  model: Jackson's local answers timed out. Jackson now waits up to five minutes for a local
  answer (a CPU reads his whole prompt first) and does not load another model after a timeout.

[Unreleased]: https://github.com/svoya-os/sos/commits/main
