# Contributing to SOS

Thank you for helping. SOS is pre-alpha, so everything is still moving, and early help
counts a lot.

Issues and pull requests are welcome in English or Russian. Если тебе удобнее по-русски,
пиши по-русски; краткая версия этого документа — [в конце](#кратко-по-русски).

**Contents:** [Ways to help](#ways-to-help) · [Before you start](#before-you-start) ·
[How the repository is organized](#how-the-repository-is-organized) ·
[Development setup](#development-setup) · [Coding standards](#coding-standards) ·
[Commits and sign-off (DCO)](#commits-and-sign-off-dco) ·
[AI-assisted contributions](#ai-assisted-contributions) ·
[Design contributions](#design-contributions) · [Translations](#translations-ru--en) ·
[Security-sensitive areas](#security-sensitive-areas-two-reviews) ·
[Pull requests](#pull-requests) · [Кратко по-русски](#кратко-по-русски)

## Ways to help

You do not need to write code to make a difference.

- **Hardware reports.** Tell us how SOS runs on your machine, especially GPUs, laptops,
  suspend/resume and multi-monitor setups. Use the
  [hardware report form](https://github.com/svoya-os/sos/issues/new?template=hardware.yml).
- **Testing and bug reports.** Try development builds and report what breaks, using the
  [bug form](https://github.com/svoya-os/sos/issues/new?template=bug.yml).
- **Translations.** Every user-facing string exists in Russian and English. Natural wording in
  both languages matters as much as correct code.
- **Documentation.** Guides live in [`docs/guides/`](docs/guides/) (English) and
  [`docs/ru/`](docs/ru/) (Russian).
- **Design.** See [Design contributions](#design-contributions).
- **Code.** Look for issues labeled `good first issue` or `help wanted`.

Security vulnerabilities are the exception: never report them in public issues. See
[SECURITY.md](SECURITY.md).

## Before you start

- **Small fixes** (typos, clear bugs, small docs changes): open a pull request directly.
- **Larger changes** (a new feature, a new dependency, a change to an interface in
  [ARCHITECTURE.md](docs/ARCHITECTURE.md), anything that touches the promise): open an issue
  first so we can agree on the approach before you spend time on it.
- Read the three documents that define the project:
  - [docs/VISION.md](docs/VISION.md): what we build, the promise, and what we deliberately do not do.
  - [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the contract between components. If you change
    an interface there, update every consumer in the same pull request.
  - [design/DESIGN.md](design/DESIGN.md): the design system.
- Decisions that change the architecture, the promise, licensing or the security model are
  recorded as decision records in `docs/decisions/` (see [GOVERNANCE.md](GOVERNANCE.md)).

## How the repository is organized

**Names.** Users see **SOS** in English and **«СОС»** in Russian (Svoya Operating System, «Своя
Операционная Система»), the `sos` command and Jackson's `j` command. The internal namespace stays
`svoya`: package names (`svoya-*`), paths (`/usr/share/svoya/`, `/etc/svoya/`, `~/.config/svoya/`),
Python modules (`svoya_cli`) and the `svoya` compatibility command. Do not rename internals, and do
not use `/etc/sos/`, which belongs to the unrelated `sos` support tool (sosreport).

SOS is one monorepo. Each top-level directory is one component with one owner package:

| Path | Component | Ships as |
|---|---|---|
| `image/` | ISO build (mmdebstrap → squashfs → hybrid ISO) | build tooling |
| `installer/` | Calamares settings and branding | `svoya-installer` |
| `packages/` | Debian packaging for every `svoya-*` package | `.deb` |
| `shell/` | Svoya Shell (Quickshell/QML); `shell/greeter/` is the login screen | `svoya-shell` |
| `jackson/` | Jackson: the background service and the `j` command (Python) | `svoya-jackson` |
| `cli/` | the `sos` command, also installed as `svoya` (Python) | `svoya-cli` |
| `modules/` | module catalog (TOML) and install/remove scripts | `svoya-cli` |
| `themes/` | theme tokens (TOML) and templates | `svoya-theme` |
| `branding/` | logo, wallpapers, Plymouth, GRUB, sounds | `svoya-branding` |
| `design/` | design system, HTML mockups, fonts | not shipped |
| `tests/` | unit and VM (QEMU/QMP) tests | CI |
| `docs/` | vision, architecture, roadmap, guides (EN, RU) | website |
| `.github/` | CI workflows, issue forms, templates | — |

The interfaces between components are defined in
[ARCHITECTURE.md §4](docs/ARCHITECTURE.md#4-interfaces): theme tokens and `theme.json`,
`sos status --json`, the Jackson socket protocol, permission tiers, the module catalog and
the model store. The filesystem layout of an installed system is in §3.

## Development setup

- **A Linux machine** with Python 3.12 or newer. Ubuntu 26.04 is closest to the real thing.
- **No package installs from PyPI.** Runtime code uses the Python standard library first, and
  any other runtime dependency must come from the Ubuntu 26.04 archive.
- **Python tests** run with `unittest`. Each component documents its exact commands in its own
  README; the usual shape is:

  ```sh
  cd cli && python3 -m unittest discover -s tests -v
  ```

- **Shell scripts** must pass `shellcheck`.
- **QML** must pass `qmllint` (from the Qt 6 development tools). To try Svoya Shell from a
  checkout inside a Hyprland session: `quickshell -p shell/`.
- **VM tests** boot images in QEMU; see `tests/`.
- **Licensing** is checked with [`reuse lint`](https://reuse.software). New files need an SPDX
  header, or a matching entry in [REUSE.toml](REUSE.toml) for files that cannot carry one.

Full instructions, including building the ISO, are in
[docs/guides/build-from-source.md](docs/guides/build-from-source.md).

## Coding standards

### Python (`jackson/`, `cli/`, tools)

- Python ≥ 3.12, **standard library first.** A new runtime dependency must be packaged in the
  Ubuntu 26.04 archive (main or universe), and the pull request must say why it is needed.
  Never install packages from the network at runtime.
- Type hints on public functions; docstrings on modules and public API.
- Tests use `unittest`. Unit tests never touch the network, the real `$HOME` or root. Use
  temporary directories and fakes. Jackson and the CLI send every external command through a
  `Runner`, so tests can fake the operating system.
- Every user-facing string comes in English and Russian, through the component's i18n helper
  (for example `tr("English", "Русский")` in `svoya_cli.i18n`).
- Error messages are calm and specific, and say what to do next. No "Oops!".
- Secrets never appear in logs, prompts, config files or test fixtures. API keys live in the
  Secret Service keyring.
- **No network call** unless the user has turned on the feature that needs it. A pull request
  that adds a network call updates [docs/guides/privacy.md](docs/guides/privacy.md) in the same
  change.

### Shell scripts

- `bash` with `set -euo pipefail`; shellcheck-clean with no blanket disables.
- Quote every expansion; use `local` in functions; prefer long options in scripts.
- No `curl … | sh`. Downloads are verified against a checksum or signature.
- Module scripts (`modules/<id>/install.sh`, `remove.sh`) run with root privileges. They must be
  idempotent, and `remove.sh` must fully undo `install.sh`.

### QML (Svoya Shell)

- Follow the [Qt QML coding conventions](https://doc.qt.io/qt-6/qml-codingconventions.html).
  Attribute order: `id`, property declarations, signals, JavaScript functions, object
  properties, child objects, states, transitions.
- 4-space indentation; one component per file; component files in `PascalCase.qml`.
- No hard-coded colors, fonts, radii or durations. Everything comes from the theme tokens in
  `theme.json`, which `shell/core/Theme.qml` hot-reloads.
- Honor the reduce-motion setting (all durations 0). No blur and no translucency.
- Every field of `sos status --json` is optional. When data is missing, the segment hides.
- Keyboard-first, mouse-complete: every action has a shortcut and can be clicked.
- No raw user-facing strings: all copy lives in Russian and English in `shell/core/Strings.qml`.

### Everything else

- TOML, JSON, YAML: 2-space indentation where nesting is needed; see [.editorconfig](.editorconfig).
- Keep lines under 100 characters where the language allows it.
<!-- REUSE-IgnoreStart -->
- New files get an SPDX header, for example `# SPDX-License-Identifier: Apache-2.0`. Put
  nothing else on that line: explanations go on the next line, or `reuse lint` fails.
<!-- REUSE-IgnoreEnd -->

## Commits and sign-off (DCO)

We use the [Developer Certificate of Origin](https://developercertificate.org/) (DCO) instead of
a Contributor License Agreement. There is **no CLA**: you keep the copyright on your work, and
your contribution is licensed under the license of the files you change (Apache-2.0 for code,
CC BY-SA 4.0 for documentation and artwork; see [REUSE.toml](REUSE.toml)).

By adding a `Signed-off-by` line to a commit, you certify the following (DCO 1.1):

```text
Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

How to sign off:

```sh
git commit -s -m "jackson: show the exact diff in approval cards"
# forgot? fix the last commit, or every commit on your branch:
git commit --amend -s --no-edit
git rebase --signoff main
```

Sign off with a name you are known by in the community. Anonymous contributions cannot be
accepted.

Commit messages:

- Subject: `component: short imperative summary`, at most 72 characters. For example
  `cli: explain why a model does not fit` or `docs: add Intel Arc notes`.
- Body: what changed and **why**. Link issues (`Fixes #123`).
- One logical change per commit. Keep your branch rebased on `main`.
- If AI tools did a meaningful part of the work, add a trailer such as
  `Assisted-by: <tool or model name>` (see the next section).

## AI-assisted contributions

You may use AI tools, including coding agents, to contribute. The rules are about
responsibility, not about tools:

1. **You are responsible for everything you submit.** Read, understand and test every line
   before you open the pull request. "The AI wrote it" is not an answer to a review question.
2. **Only a human can sign off.** The DCO is a statement you make personally. AI tools must
   not add `Signed-off-by` lines; you add yours after reviewing the work.
3. **Disclose substantial AI generation** in the pull request: which parts, and which tool.
   The template has a field for it. Add an `Assisted-by:` trailer to the commits concerned.
   Autocomplete, spelling fixes and formatting do not need disclosure.
4. **Respect licenses.** Do not submit output that you know reproduces code under an
   incompatible license. If your tool flags a match with existing code, check it.
5. **No unreviewed bulk submissions.** Pull requests or issues opened by agents without a person
   who has checked them, and bug or security reports that nobody has reproduced, will be closed.
6. **Translations:** machine translation is a first draft. A fluent speaker reviews it before
   merge, and the Russian must read as if written in Russian.

This policy follows the approach of the Linux kernel's
[guidance for AI coding assistants](https://github.com/torvalds/linux/blob/master/Documentation/process/coding-assistants.rst).

## Design contributions

- Follow [design/DESIGN.md](design/DESIGN.md). Colors, fonts, radii and durations come only from
  the theme tokens in `themes/*.toml`.
- One signal color per theme; matte surfaces, 1px hairlines, no blur or glass; motion 120, 180
  or 260 ms with no bounce.
- Show user-interface changes in **all three themes** (Graphite, Paper, Phosphor), and with
  reduce-motion if the change animates. Mockups in `design/mockups/` render to PNG with
  `design/render.py`.
- Contrast meets WCAG AA; focus rings are a 2px accent outline.
- New icons follow the Lucide stroke rules: 1.5px stroke, round caps and joins.
- Artwork you contribute is licensed under CC BY-SA 4.0. Material you did not create needs a
  compatible license and its source stated in the pull request.

## Translations (RU / EN)

Both languages are first-class. A pull request that adds a user-facing string adds it in both.

Style (see [DESIGN.md §8](design/DESIGN.md#8-copy-ruen)):

- Short, calm and concrete. Sentence case; lowercase labels in the bar (`обучение 62%`).
- Never nag and never blame the user.
- Jackson is a character: a friendly guy from the 2000s internet, cheeky but useful. In
  user-facing text he is never a "daemon" («демон»); if the background service must be
  mentioned, say that Jackson runs in the background («Джексон работает в фоне»).
- Russian: informal «ты» by default (Jackson has a setting for «вы»), «ёлочки» for quotes,
  «ё» where it belongs, a decimal comma and a narrow no-break space in numbers
  (`11,2 ГБ`, `48 213`).

Starting glossary (extend it in pull requests):

| English | Русский |
|---|---|
| Jackson | Джексон |
| snapshot | снимок |
| undo | отменить, отмена |
| rollback | откат |
| module | модуль |
| model store | хранилище моделей |
| sandbox | песочница |
| permission tier | уровень разрешений |
| approval | подтверждение |
| audit log | журнал действий |
| local · cloud | локально · облако |
| first-run wizard | мастер первого запуска |
| lock screen · greeter | экран блокировки · экран входа |
| control center | центр управления |

## Security-sensitive areas (two reviews)

Pull requests that touch these areas need **two approving reviews from maintainers**, neither of
them the author:

- **Jackson permissions:** tiers T0–T4, approval cards, taint tracking, grants, the audit log
  and undo.
- **Sandboxing:** containers, microVMs, portals, the separate computer-use session.
- **Secrets:** keyring access and `secrets.env` handling.
- **Packaging:** `packages/` (including maintainer scripts), APT repository configuration and
  keyrings, module install/remove scripts in `modules/`.
- **Image, installer and boot chain:** `image/`, `installer/`, Secure Boot.
- **Release and signing:** workflows that build or publish, signing keys, checksums.

For these pull requests:

- Describe the effect on the threat model in the description.
- Add tests for the bypass you are preventing, not only for the happy path.
- Nobody merges their own change.
- Until the project has a second maintainer, the project lead asks a trusted outside reviewer
  and records the review in the pull request.

## Pull requests

- Keep them small and focused on one topic.
- Fill in the [template](.github/PULL_REQUEST_TEMPLATE.md): what, why, how it was tested,
  screenshots for UI changes, AI assistance.
- Update the docs and the `Unreleased` section of [CHANGELOG.md](CHANGELOG.md) if users will
  notice the change.
- CI must pass. A maintainer will try to give a first response within a week. If you hear
  nothing for two weeks, a polite ping is welcome.

## Code of Conduct

Everyone who takes part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Кратко по-русски

- **Как помочь без кода:** отчёты о железе ([форма](https://github.com/svoya-os/sos/issues/new?template=hardware.yml)),
  тестирование, переводы, документация. Issue и pull request можно писать по-русски.
- **Названия.** Пользователь видит «СОС» (по-английски SOS), команды `sos` и `j`. Внутри всё
  по-прежнему называется `svoya` (пакеты `svoya-*`, пути `/usr/share/svoya/`, `~/.config/svoya/`),
  это не переименовываем. Джексон — персонаж, в текстах для пользователя он не «демон», а
  «работает в фоне».
- **Перед большой работой** открой issue и договорись о подходе. Сначала прочитай
  [VISION.md](docs/VISION.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md) и
  [DESIGN.md](design/DESIGN.md).
- **DCO вместо CLA.** Каждый коммит подписывай: `git commit -s`. Авторские права остаются за
  тобой, а вклад распространяется под лицензией файлов, которые ты меняешь.
- **Код:** Python ≥ 3.12, сначала стандартная библиотека, тесты на `unittest`; скрипты на bash
  с `set -euo pipefail` без замечаний shellcheck; QML по соглашениям Qt, цвета и размеры
  только из токенов темы. Никаких сетевых запросов, пока пользователь сам не включил нужную
  функцию.
- **ИИ-помощники разрешены**, но за результат отвечаешь ты: прочитай, пойми и проверь каждую
  строку. Подписывает коммит только человек. Если ИИ сделал заметную часть работы, напиши об
  этом в pull request и добавь в коммит строку `Assisted-by:`.
- **Дизайн** — строго по [DESIGN.md](design/DESIGN.md), скриншоты во всех трёх темах.
- **Переводы:** каждая строка интерфейса — на двух языках. По-русски на «ты», кавычки «ёлочки»,
  буква «ё», числа вида `11,2 ГБ`. Машинный перевод — только черновик.
- **Два ревью** обязательны для изменений в разрешениях и песочницах Джексона, секретах,
  пакетах, сборке образа и установщике, подписях и выпуске релизов.
- **Об уязвимостях** — только закрыто, см. [SECURITY.md](SECURITY.md).
