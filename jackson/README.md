# Джексон / Jackson

The assistant of **СОС / SOS — «Своя Операционная Система»**. Jackson is a character — by default
«Кентафурик» / "Buddy" — and the OS layer that controls agents: it routes each request to a
local or cloud model, runs tools inside a sandbox, asks before anything risky with the exact preview,
keeps a tamper-evident log and can undo what it did.

```
j найди мои датасеты                 # ask (j is the short alias of jackson)
git diff | j "что тут не так?"       # stdin becomes the selected text
j -                                  # the question itself comes from stdin
j                                    # chat until Ctrl+D
jackson status | models | doctor     # what is going on
jackson undo                         # revert the last thing Jackson did (Super+Z does the same)
j avatar set персонаж кот            # his look and name (~/.config/svoya/avatar.json)
```

Stdlib-only Python (≥ 3.11; target 3.13 on Ubuntu 26.04). No LiteLLM, no pip dependencies.

## Layout

| Path | What |
|---|---|
| `bin/jackson`, `bin/j` | CLI (installed as `/usr/bin/jackson`, `/usr/bin/j`) |
| `bin/jacksond` | background service (installed as `/usr/lib/svoya/jacksond`) |
| `systemd/jacksond.service` | systemd **user** unit, `Type=notify`; started by `sos session-start`, never by itself |
| `jackson/daemon.py` | asyncio Unix-socket server, JSON Lines protocol (§4.3) |
| `jackson/engine.py` | one turn: fast path, or route → model → tool loop → done |
| `jackson/router.py` | provider/model choice with a human reason; health cache; circuit breaker |
| `jackson/providers/` | streaming clients: OpenAI-compatible (llama.cpp, Ollama, vLLM, LM Studio, DeepSeek, Mistral, Gemini's compat endpoint), Anthropic Messages, Gemini `streamGenerateContent`; SSE over `http.client`; pricing |
| `jackson/tools/` | built-in tools with tier metadata, MCP client (`mcp.py`), notes over an Obsidian vault |
| `jackson/permissions.py` | tiers T0–T4, approvals, project grants, taint |
| `jackson/audit.py` | hash-chained `audit.jsonl` + `audit.head` |
| `jackson/undo.py`, `trash.py` | undo registry, freedesktop Trash, `sos undo` / snapper |
| `jackson/memory.py`, `skills.py` | Markdown memory + FTS5 index; Agent Skills (`SKILL.md`) |
| `jackson/fastpath.py`, `osctl.py` | ~40 RU/EN commands without a model, each verified |
| `jackson/avatar.py`, `aiswitch.py` | look and name (`avatar.json`, DESIGN §13); the AI switch (`sos ai off`) |
| `jackson/persona.py`, `prompts/` | system prompts (RU/EN), personas, humor level |
| `jackson/voice.py`, `acp.py` | documented interfaces only (v0.2 voice, v0.3 external agents) |
| `tests/` | `python3 -m unittest discover -s jackson/tests -t jackson` (from the repo root) |

Files on the installed system (ARCHITECTURE §3): settings `~/.config/svoya/jackson.toml`
(optional `/etc/svoya/jackson.toml` underneath), data `~/.local/share/svoya/jackson/`
(`audit.jsonl`, `audit.head`, `actions.jsonl`, `grants.json`, `mcp-pins.json`, `spend.json`,
`index.sqlite`, `memory/`, `skills/`, `undo/`, `logs/`), socket `$XDG_RUNTIME_DIR/svoya/jackson.sock`
(directory 0700, socket 0600). Deleted and overwritten files go to `~/.local/share/Trash` (restorable
from the file manager too).

## How a turn works

```
ask ─► fast path? ──yes──► run + verify ─► token ─► done (0 tokens, 0 €)
          │no
          ▼
       router ─► route event (model, local?, human reason)
          ▼
       prompt = persona + safety rules + memory snippets + skills + taint note
          ▼
   ┌─► model stream ─► token events
   │      │ tool calls
   │      ▼
   │   assess (tier, exact preview) ─► permissions ─► approval? ─► snapshot (first write)
   │      ▼
   │   run tool (sandbox) ─► verify ─► undo record ─► audit ─► taint?
   └──────┘  (max_steps)
          ▼
       journal (if something changed) ─► done (usage, cost €, latency, leftMachine, actions)
```

If the chosen provider fails before any text was streamed, the turn falls back to the next
candidate that the policy allows and says so in a second `route` event.

## Socket protocol (ARCHITECTURE §4.3)

JSON Lines over `$XDG_RUNTIME_DIR/svoya/jackson.sock`. Implemented exactly as specified; extra fields
are additive and clients must ignore what they do not know.

Client → Jackson: `hello {client, version, lang?}` · `ask {id, text, context?{selection, clipboard,
screenshot, cwd}, route?, new?, refines?}` · `approve {id, callId, decision}` · `cancel {id}` · `status` ·
`undo {actionId?, id?}` · `ping`. Unknown message types are ignored.

Jackson → client:

| type | fields (additive ones in *italics*) |
|---|---|
| `welcome` | `version`, `models`, `route` (*mode, policy, offline, model, provider, local, reason*), *`protocol`, `persona` {id, name, humor}, `avatar` (full avatar.json object), `name`, `ai` {enabled, off}, `capabilities`, `client`, `lang`* |
| `route` | `model`, `provider`, `local`, `reason`, *`task`, `label`* |
| `token` | `text` |
| `tool` | `callId`, `name`, `args`, `tier`, `state`, `summary`, *`verified`, `actions`* |
| `approval` | `callId`, `name`, `preview`, `tier`, *`decisions` (allowed answers), `reasons`, `args`* |
| `done` | `usage`, `costEur`, `latencyMs`, `leftMachine`, `actions`, *`leftTo`, `costEstimated`, `model`, `provider`, `meta` (ready-made footer), `cancelled`, `undone`* |
| `error` | `message`, `retryable`, *`costEur`, `leftMachine`, `aiOff` + `off` (user/system/config) when the AI switch refused the turn* |
| `state` | `state`, *`persona`, `avatar` (full object), `mood` (calm/thinking/busy/talking/asking/sorry), `detail` (`approval`, `error`, `avatar`, `persona`), `client`* |
| *`status`* | *answer to `status`: route, spend today, requests that left today, pending approvals, turns, models, sandbox/sos availability, MCP servers* |
| *`pong`* | *answer to `ping`* |

Rules: every turn ends with exactly one `done` or `error`, then `state: idle`. When
`avatar.json` changes (the shell's customizer, `j avatar`, «стань котом»), every client gets a fresh
`state {detail: "avatar"}` within 2 s (one `stat()` per 2 s while clients are connected). `ask.refines`
continues the conversation of that turn, even from a new connection. Jackson keeps
`$XDG_RUNTIME_DIR/svoya/ai.json` = `{local, cloudActiveSince}` current for `sos status`. `state` events are
broadcast to all clients (the bar's mini-scope follows any turn); other events go to the client that
asked. An approval can be answered from any client (`jackson approve <callId> once`). A second
`ask` while a turn is running gets `error {retryable: true}`. A disconnect cancels the client's turn.
`cancel` ends the turn with `done {cancelled: true}` (tokens spent are still reported). `undo` answers
with `tool` → `token` → `done {undone: [...]}` (or `error`).

Example session:

```json
→ {"type":"hello","client":"svoya-shell","version":"0.1","lang":"ru"}
← {"type":"welcome","version":"0.1.0","models":[…],"route":{"mode":"auto","policy":"local-only","model":"qwen3.5-4b","local":true,…},"persona":{"id":"kent","name":"Кентафурик","humor":1},"avatar":"auto"}
→ {"type":"ask","id":"t1","text":"запиши план в ~/plan.md","context":{"cwd":"/home/u"}}
← {"type":"state","id":"t1","state":"thinking","persona":"kent","avatar":"auto","mood":"thinking"}
← {"type":"route","id":"t1","model":"qwen3.5-4b","provider":"local","local":true,"reason":"локально: политика «только локально», данные не покидают компьютер"}
← {"type":"tool","id":"t1","callId":"call_0","name":"fs.write","args":{…},"tier":1,"state":"done","summary":"~/plan.md · 32 Б · проверено","verified":true,"actions":["a-dc0c5f"]}
← {"type":"token","id":"t1","text":"Записал."}
← {"type":"done","id":"t1","usage":{"inTokens":200,"outTokens":24},"costEur":0,"latencyMs":812,"leftMachine":false,"actions":["a-8df087","a-dc0c5f"],"meta":"0,8 с · 224 токена · 0 € · данные не покидали компьютер"}
← {"type":"state","id":"t1","state":"idle",…}
```

## Settings (`~/.config/svoya/jackson.toml`)

Everything is optional; defaults are in `jackson/config.py`. `jackson route set …` and
`jackson persona …` edit this file in place (comments are kept) and the running service reloads it.

```toml
language = "ru"          # ru | en
address  = "ty"          # «ты» (default) | "vy"
persona  = "kent"        # kent («Кентафурик») | sysop | dispatcher («Диспетчер») | pirate («Пиратское радио»)
humor    = 1             # 0 none · 1 occasional · 2 more (never on errors or when you're stressed)
avatar   = "auto"        # mascot hint for the shell: auto | imp | cat | none
allowed_roots = ["~"]    # file tools work only here
max_steps = 8

[route]
policy = "local-only"    # local-only | eu | any   (an explicit per-turn route overrides it…)
default = "auto"         # auto | local | cloud
offline = false          # …unless this hard switch is on: then nothing ever leaves the machine
daily_budget_eur = 1.0   # cloud spend cap per day; exhausted → local only
[route.task]             # preferred models per task class ("provider/model", "provider/*")
code = ["local/*", "anthropic/claude-sonnet-5", "deepseek/deepseek-v4-pro"]

[providers.local]        # llama.cpp llama-server (router mode: --models-dir); models discovered via /v1/models
base_url = "http://127.0.0.1:8080/v1"
[providers.vllm]         # any OpenAI-compatible endpoint
kind = "openai"
base_url = "http://gpu-box:8000/v1"
local = true
models = ["qwen3.5-32b"]

[pricing]                # EUR per 1M tokens [input, output]; local is always 0
"anthropic/claude-sonnet-5" = [1.72, 8.60]

[memory]
dir = "~/Obsidian/SOS"   # default: ~/.local/share/svoya/jackson/memory
obsidian = "auto"        # auto (a parent has .obsidian/) | on | off
journal = true

[mcp]
on_change = "block"      # block | warn — what to do when a pinned tool definition changes
[mcp.servers.files]
command = ["mcp-server-filesystem", "/home/u/Documents"]
tier = 1                 # default tier of this server's tools (default 2 = confirm)
network = false          # sandbox without network
taint = true             # its output is untrusted (default)
rw = ["~/Documents"]     # writable inside the sandbox
env = { TOKEN = "keyring:files" }   # secrets come from the keyring, never from this file
```

Built-in providers: `local` (llama.cpp), `ollama`, `anthropic`, `gemini`, `deepseek` (region `cn`),
`mistral` (region `eu`, so the `eu` policy has a cloud option). Cloud providers are inert until a key
exists. Default models and EUR prices (converted at ≈ 0.86 €/$ on 2026-09-24; edit `[pricing]`):
Claude Haiku 4.5 / Sonnet 5 / Opus 5.5, Gemini 3.5 Flash-Lite / 3.8 Flash / 3.1 Pro (preview),
DeepSeek Flash / V4 Pro (peak, cache-miss), Mistral Small / Medium.

**Keys** — Secret Service first, then `~/.config/svoya/secrets.env` (must be 0600; Jackson warns
otherwise), then the environment variable (`ANTHROPIC_API_KEY`, …):

```
secret-tool store --label='SOS: anthropic' service svoya provider anthropic
```

Keys never reach a prompt, a client, the audit log or a sandbox.

## Routing

Precedence: **explicit route > privacy policy > task class > budget > availability**; local first.

* explicit: `ask.route` (`local`, `cloud`, or `provider/model`) — overrides the policy, never `offline`;
* policy: `local-only` (default), `eu` (local + EU-region providers), `any`;
* task class: `chat`, `code` (bigger local model), `vision` (screenshot attached; needs a vision
  model), `long` (context larger than the local window);
* budget: cloud candidates whose estimated cost would exceed today's budget are dropped;
* availability: local servers are probed (`/v1/models`, cached 15 s, refreshed in the background);
  cloud providers need a key and are skipped for 60 s after a failure.

Every decision has a reason in plain words («локально: быстрый ответ, данные не покидают компьютер»,
«облако: нужна модель со зрением, локальной такой нет — Anthropic»). When nothing fits, the error says
exactly why and what to do (`sos models serve`, `jackson route set policy any`, add a key).

## Security model

| Tier | What | Policy |
|---|---|---|
| T0 | read files in allowed roots, system info, search, GET a web page | runs freely (logged) |
| T1 | reversible local writes: files, notes, memory, theme, volume… | auto; snapshot first (`sos snapshot create`) + own undo record |
| T2 | external side effects: POST/PUT, network commands, local-network services, notes outside Jackson's vault folder, MCP tools (default) | confirm against the exact preview; "always in this project" allowed |
| T3 | root/system changes (`sudo`, `pkexec`, `apt install`, `systemctl` system units…) | confirm once, snapshot, polkit asks; runs outside the sandbox because escalation cannot work inside it |
| T4 | secrets (`~/.ssh`, keyrings, browser profiles, cloud credentials, `.env`) | denied unless granted for this one task |

* **Previews are exact**: unified diffs for writes, the full command and sandbox layout for
  `shell.run`, method + URL + body for sends, JSON arguments for MCP tools.
* **Taint / lethal trifecta**: web pages, downloaded files (`user.xdg.origin.url` xattr or
  `~/Downloads`), clipboard/selection, network command output and MCP output mark the conversation
  untrusted. From then on every call with an external effect (even a plain GET) needs a fresh
  confirmation, and standing grants do not apply. Untrusted text is wrapped as data in the prompt.
* **Sandbox** (`bwrap`): everything read-only, the project folder writable, private `/tmp`, secrets
  hidden behind empty tmpfs, `$XDG_RUNTIME_DIR` hidden (no D-Bus/Wayland/keyring), scrubbed
  environment, no network unless approved. Without bwrap every command needs confirmation.
* **Own state is off-limits**: file tools refuse to write Jackson's settings, grants, audit log,
  undo store or the trash; the default memory folder (inside Jackson's data) is changed only through
  memory/notes tools.
* **MCP**: servers only from the settings file (never installed from chat); dual-era client —
  2026-07-28 stateless requests with `_meta` (probe `server/discover`), falls back to the legacy
  `initialize` handshake; each server under bwrap; tools namespaced `mcp.<server>.<tool>`; every tool
  definition (name + description + input schema) pinned by SHA-256 on first sight — a changed
  definition is blocked until `jackson mcp trust <server>`; descriptions with injected instructions or
  mentions of other tools (shadowing) are blocked; output taints by default.
* **Skills** (`~/.local/share/svoya/jackson/skills/*/SKILL.md`, plus system skills from packages in
  `/usr/share/svoya/jackson/skills`, e.g. UpsiL's; a user skill of the same name wins): catalogue in the
  prompt, bodies of the best matches added per turn (the name or an `aliases:` spelling in the request
  counts extra); they are guidance only and grant nothing.
* **Audit**: `audit.jsonl`, one JSON object per line, `prev` = SHA-256 of the previous line's bytes,
  plus `audit.head` (last seq + hash) to catch truncation; `flock`-serialized across processes,
  fsync'ed; long values stored as digests, secret-looking keys masked. `jackson audit verify`.
* **Honesty**: tools verify their effect (re-read hashes, re-query volume, `theme.json`, process
  list…); results carry `verified`, and the prompt forbids claiming success without it.

## Undo

Every reversible action gets an id (`a-3f9c2e`) in `actions.jsonl`; `done.actions` lists them.
File writes keep the previous version in the trash and content hashes; undo refuses to clobber a
file you edited afterwards. Moves go back, trashed files are restored, settings are reset, volume /
brightness / Wi-Fi return to the previous value, timers are stopped, memory edits are rolled back.
A snapshot taken before the first write of a turn is recorded too (`sos undo <id>` or
`snapper undochange`). `jackson undo` (or Super+Z in the shell) reverts the last non-bookkeeping
action; `jackson undo --list` shows them all.

## Memory and Obsidian

`USER.md` (facts about you), `MEMORY.md` (notes), `journal/YYYY-MM-DD.md` (what Jackson did, written
only when a turn changed something). Plain Markdown, indexed by SQLite FTS5 with light RU/EN stemming;
the relevant snippets and `USER.md` go into the prompt, clearly marked as data. Each write is
announced (`tool` event) and undoable; outside Obsidian the folder is also a git repository.

Point `memory.dir` into an Obsidian vault and Jackson writes Obsidian-friendly notes (YAML front
matter with `created`/`updated`/`tags`, `[[wikilinks]]`, no HTML), indexes the whole vault for
`notes.search`/`notes.read`, and writes only inside its own subfolder (`notes.write`/`notes.append`
are T1 there, T2 anywhere else in the vault — the same guard applies to `fs.*`). Pointing it at the
vault root makes Jackson use `<vault>/Jackson/`. No nested git repository inside a vault.

`jackson memory show | search <q> | forget <text> [--yes] | path`, `jackson notes search | read | where`.

## Fast path (no model, verified)

Volume up/down/set/query, mute/unmute, brightness up/down/set, open app (desktop entries + aliases
like «браузер», «терминал»), open folder, lock screen, screenshot, theme dark/light/auto/phosphor,
timer / «напомни через …», GPU/VRAM, disk space, battery, RAM, CPU, uptime, time, date, local IP,
Wi-Fi on/off, Bluetooth on/off, «что ты умеешь», «отмени», «новый разговор», models, «только
локально» / «можно облако». Matching is anchored to the whole utterance, so «как сделать тёмную тему
в VS Code?» goes to a model. Measured 110–140 ms wall (CLI start included) with the background
service running, 3–8 ms inside Jackson.

## Look, name and the AI switch

`~/.config/svoya/avatar.json` (DESIGN §13, shared with the shell): `character` imp|cat, `skin`,
`outfit`, `style`, `headphones`, `glasses`, `hood`, `name`. The file may be sparse; missing keys follow
the character's defaults, unknown keys are kept, writes are atomic, every change is undoable. `name`
(default «Джексон» / "Jackson") is used everywhere he talks about himself — the system prompt, CLI
texts, `welcome.name` — and also works as a wake word («Макс, громче»).

```
j avatar                                  # show
j avatar set персонаж кот                 # keys and values in Russian or English:
j avatar set окрас рыжий                  #   персонаж/character кот|чёрт · окрас/skin · одежда/outfit
j avatar set очки круглые                 #   стиль/style худи|куртка|футболка · наушники да|нет
j avatar set имя Макс                     #   очки нет|круглые|тёмные · капюшон да|нет · имя/name
j avatar reset
```

Or ask: «стань котом» / «стань рыжим котом», «надень очки», «сними наушники», «капюшон долой»,
«надень худи», «тебя теперь зовут Макс» (he confirms with the new name). Accent: «сделай акцент
фиолетовым», «акцент сирень», «верни оранжевый», «без цвета» → `sos theme accent … --json` (sos
resolves the color words), verified against `theme.json.accentId`, undoable; red is refused (errors
own it). Base theme: «тёмная/светлая/авто тема», «включи бумагу/графит/фосфор».

**AI switch** (WORKFLOWS §8): with `~/.config/svoya/ai.off`, `/etc/svoya/ai.off` or
`[ai] enabled = false` in `svoya.toml`, Jackson answers only fast-path commands; everything else gets a
calm `error {aiOff: true}` explaining `sos ai on` (and `j` prints it without alarm). «выключи ИИ»
answers first and then runs `sos ai off` detached (it stops Jackson too); `jackson undo` turns it back
on. While off, no model servers are probed and no MCP servers start.

## Personas

«Кентафурик» (default, id `kent`): a laid-back dude who grew up on the ICQ-and-forums internet and
knows today's memes too, warm and a little goofy, straight to the point. He calls you «кентафурик»
(also «кент», «чувак», «братишка»), says «здарова», «базар» / «базару нет» to agree, «это база» for
the obviously right thing, «имба», «пушка», «жиза», «чётко», «лови», «погнали», and stretches one word
when happy («чуваааак», «красаааава») — in most answers at `humor` 1, almost every answer at 2, never
at 0. No swearing or prison slang, and no jokes when something broke, you are stressed, or it is about
security or money. The shell's fixed lines (greeter, lock screen, setup) use the same voice, or a plain
one for the other personas and humor 0 (`Strings.kentVoice`; the greeter gets it with the exported
look). Alternatives: SYSOP (log-line terse), «Диспетчер» (checklists, GO/NO-GO), «Пиратское радио»
(late-night 90s DJ, drops the act on errors). The safety rules are identical for every persona and
come after it in the prompt. `welcome`/`state` carry `persona`, `avatar` and `mood` for the mascot.

## Voice roadmap (v0.2 «Голос») and external agents (v0.3)

See `jackson/voice.py`: push-to-talk on Super+J; Wyoming services on the CPU — Silero VAD (MIT),
STT Parakeet-TDT-0.6B-v3 (CC-BY-4.0, RU/EN/ET) or GigaAM-v3 (MIT) via onnx-asr, TTS Silero
v5_cis_base (MIT) or Piper (GPL-3.0, dmitri/denis), Qwen3-TTS (Apache-2.0) on GPU; optional wake word
«Джексон» with livekit-wakeword. Protocol additions: `listen`/`listen-stop`, `transcript`, `state`
with `level`. External agents (Claude Code, Codex CLI, OpenCode, goose) will run over ACP inside the
same sandbox/tier/audit/undo machinery — interface in `jackson/acp.py`.

## Contract notes

Implemented as agreed in ARCHITECTURE §8 (unknown types ignored, `status`/`undo` answers, `new`,
`refines`, `provider/model` routes, `decisions`, `capabilities`, `ai.json`, `sos undo … --yes`).
Proposed addition to §8 (look, name, AI switch):

> **Jackson's look and name (DESIGN §13).** `~/.config/svoya/avatar.json` is shared by the shell and
> Jackson: `character` (imp|cat), `skin`, `outfit`, `style`, `headphones`, `glasses`, `hood`, `name`.
> It may be sparse (missing keys follow the character's defaults); writers keep unknown keys and replace
> the file atomically. `welcome` carries `name`, `avatar` (the full resolved object), `ai {enabled, off}`
> and `capabilities`; every `state` carries the full `avatar`; when the file changes, Jackson re-sends
> `state {detail: "avatar"}` to every client within 2 s.
> **AI switch.** With `/etc/svoya/ai.off`, `~/.config/svoya/ai.off` or `[ai] enabled = false`, Jackson
> answers only fast-path commands; other turns end with `error {aiOff: true, off: system|user|config}`
> whose message explains `sos ai on`. Jackson runs `sos ai off` only after its answer has been sent.
> **Accent.** Jackson changes the accent only via `sos theme accent <word|#hex> --json` and verifies
> `theme.json` `accentId`.

## Tests

```
python3 -m unittest discover -s jackson/tests -t jackson
```

Fake OpenAI-compatible, Anthropic and Gemini streaming servers (`http.server` in a thread), a fake OS
(`tests/fakes.py` simulates wpctl, brightnessctl, nmcli, bluetoothctl, loginctl, sos, systemd-run…),
a fake stdio MCP server that speaks both protocol eras. Covered: providers and SSE parsing,
thinking/signature replay, router policies, tiers and taint, audit tampering, undo, memory and
Obsidian, ~30 fast-path intents in RU/EN, the tool loop with approvals and fallbacks, socket
round-trips with two clients, MCP pinning/rug-pull/poisoning, and the CLI as a real subprocess.

Needs a real system to verify: bwrap namespaces (Ubuntu's AppArmor userns rules), secret-tool,
snapper/`sos snapshot`, llama-server router mode and real cloud APIs, PipeWire/brightnessctl/nmcli/
loginctl LockedHint/grim/gtk-launch behaviour, systemd `Type=notify` readiness.
