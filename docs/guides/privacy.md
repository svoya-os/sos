# Privacy: what leaves your machine, and when

> SOS is pre-alpha. This page states the rules the code has to follow, and marks the parts that
> are not built yet. If SOS ever behaves differently from this page, that is a bug, and we treat
> it as a security bug: please report it as described in [SECURITY.md](../../SECURITY.md).

## The short version

- **By default, nothing leaves your machine.** No telemetry, no account, no crash reports, no
  "phoning home".
- Data goes out only when you use a feature that needs the network, and SOS shows you when it
  happens.
- Jackson answers with **local models** unless you add a cloud provider yourself and allow
  cloud routing.
- **One switch** turns every AI feature off, and every AI component can be removed.
- Your data is plain files in known places ([list below](#where-your-data-lives)).

## What never happens

- Telemetry, usage statistics, analytics or "anonymous" identifiers.
- An account or a sign-in to use the system.
- Ads, recommendations or upsells.
- AI acting on its own. Jackson runs in the background, but he does nothing until you call him:
  he does not look at your screen, files or clipboard, and he does not start tasks by himself.
- Network geolocation. The automatic day/night theme uses the coordinates in your settings
  (`[location]` in `~/.config/svoya/svoya.toml`; the default is Tallinn).

## When something does leave your machine

| Feature | When | Goes to | What is sent | How you see it |
|---|---|---|---|---|
| **Cloud AI** (Jackson) | Only after you add a provider key **and** change the route policy from `local-only` | The provider you set up, for example Anthropic, Google Gemini, DeepSeek or Mistral | Your message, the context you attach (selection, clipboard, screenshot), what Jackson's tools read in that turn, and a few snippets from his memory | Route chip names the provider; footer says the data left the machine and what it cost; counters in the control center; audit log |
| **Models** | When you click install: the wizard's suggested model, `sos models pull`, a module | Hugging Face, or the source shown before the download | Which files you download, your IP address, your Hugging Face token for gated models | Size, fit and license are shown before the download starts; progress in the bar |
| **Modules and apps** | When you install one: `sos install <module>`, the wizard, Obsidian | Our APT repository, the engine's package mirrors, Flathub | Which packages you download, your IP address | You start it; progress in the bar |
| **System updates** | When you run `sos update`, or after you turn on automatic update checks | Our APT repository and the engine's package mirrors | Package lists and versions | Update count in the bar |
| **Web pages for a task** | When Jackson or an agent opens a page for a task you gave | That website | The request for the page | Contacting a new domain needs your approval first (tier T2); audit log |
| **Agents** (Claude Code, Codex…) | When you run them | Their own cloud services | Whatever that agent sends; see its documentation | From v0.3, sandboxed: new destinations need your approval |
| **Crash reports** | Only if you opt in. **Not built yet** | To be decided | The report, shown to you before it is sent | You send it yourself |

### System services from the engine

Ubuntu, the engine underneath SOS, normally turns on a few background network services: clock
sync, network connectivity checks, firmware metadata downloads and periodic package list
updates. For v0.1, each of them is either off or offered as a choice in the first-run wizard.
**Status: in progress**, tracked in the [roadmap](../ROADMAP.md) together with a CI test that
checks that a fresh install makes no outbound connections.

### Obsidian

The first-run wizard can install [Obsidian](https://obsidian.md) with one click, from Flathub.
Obsidian is a separate application and it is not open source; its own privacy policy applies.
SOS does not turn on Obsidian Sync or Obsidian Publish. SOS works the same without Obsidian.

## How cloud routing is shown

- **Jackson's route chip** always names the model. Local answers say *local* next to a green
  dot; cloud answers name the provider next to a dot in the cloud color.
- **The footer** of every answer shows latency, tokens, cost in euros, and whether data left the
  machine.
- **The control center**, block *AI & privacy*: the current route, today's cloud spend, and how
  many requests left the machine today.
- **The audit log** records every request with its route (see [below](#where-your-data-lives)).

You decide where requests may go, in `~/.config/svoya/jackson.toml`:

```toml
[route]
policy = "local-only"     # local-only (default) | eu | any
offline = false           # true = nothing leaves the machine, even when you ask for it
daily_budget_eur = 1.0    # cloud spending limit per day
```

- `local-only`: cloud models are never used. This is the default.
- `eu`: only providers hosted in the EU.
- `any`: any provider you have added.

API keys are stored in your Secret Service keyring, never in plain files. A `secrets.env`
file (mode `0600`) is only a fallback for machines without a keyring.

Once a request reaches a cloud provider, that provider's data policy applies. SOS shows you when
that happens; it cannot control what the provider does afterwards.

## How to turn AI off

- **The switch:** control center → *AI & privacy*. It stops Jackson, his hotkeys and the
  background services of AI modules, and blocks cloud routing. **Status: planned for v0.1.**
- **From the terminal, today:** stop Jackson and keep him from starting with your session:

  ```sh
  systemctl --user disable --now jacksond.service
  ```

  Or set `jackson = false` under `[session]` in `~/.config/svoya/svoya.toml`.
- **Hard offline:** set `offline = true` under `[route]` in `~/.config/svoya/jackson.toml`.
  Jackson keeps working with local models only, even if you ask for a cloud model.
- **Remove it completely:** `sudo apt remove svoya-jackson` removes Jackson, and
  `sos modules remove <module>` removes an AI module. The rest of the system keeps working.

## Where your data lives

All of it is plain files you can read, move and delete.

| Path | What |
|---|---|
| `~/.config/svoya/svoya.toml`, `jackson.toml` | Your settings |
| `~/.local/share/svoya/jackson/memory/` | Jackson's memory: Markdown files in a git repository. If you choose it in the wizard, the memory lives in a folder of your Obsidian vault instead |
| `~/.local/share/svoya/jackson/audit.jsonl` | Audit log: every tool call Jackson made, with its tier and result. It can contain file names, commands and short excerpts |
| `~/.local/share/svoya/jackson/actions.jsonl`, `undo/` | What Jackson changed, and what is needed to undo it |
| `~/.local/share/svoya/jackson/grants.json` | Permissions you gave with "always in this project" |
| `~/.local/share/svoya/jackson/spend.json` | Cloud spend and "left the machine" counters for the last 90 days |
| `~/.local/share/svoya/jackson/index.sqlite`, `logs/` | Search index of the memory; logs |
| `~/.local/state/svoya/` | Generated state: current theme, bar status, jobs |
| `/srv/ai/` | Models and datasets shared by all tools, with `registry.db` (hashes, sources, licenses) |
| `/var/lib/svoya/` | Installed modules and update history |
| Secret Service keyring | API keys |
| Btrfs snapshots | Earlier versions of the system and your files, for undo |

Things to know:

- **Snapshots keep deleted files.** A file you delete stays in older snapshots until those
  snapshots are deleted too. To see and delete snapshots: `sudo snapper list-configs`, then
  `sudo snapper -c <config> list` and `sudo snapper -c <config> delete <number>`. The model
  store `/srv/ai` is not included in snapshots.
- **Synced vaults travel.** If Jackson's memory is in an Obsidian vault that you sync (Obsidian
  Sync, Syncthing, a cloud drive), his memory goes wherever the vault goes.
- **To make Jackson forget,** delete his memory folder. You may delete the audit log too: its
  tamper evidence exists to reveal changes you did not make, not to stop you from managing your
  own data.

## Found a connection you did not turn on?

That is a bug in SOS, and we treat it as a security issue. Please report it privately:
[SECURITY.md](../../SECURITY.md).
