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

### Changed

- The system is called **SOS — Svoya Operating System** («СОС — Своя Операционная Система»),
  and its command is `sos`; `svoya` stays as an alias. Package names and paths keep the
  technical name `svoya`. Jackson has a short command too: `j`.

[Unreleased]: https://github.com/svoya-os/sos/commits/main
