# First steps with SOS

> SOS is pre-alpha. This guide describes v0.1 as designed; commands may still change before
> the release. `svoya` works everywhere you see `sos`.
>
> По-русски: [docs/ru/first-steps.md](../ru/first-steps.md).

## The desktop in one minute

- **The bar** runs along the top. On the left: the Morse mark (it opens the SOS menu),
  workspaces and the window title. On the right: a running job with its progress, GPU
  temperature and memory, network, sound and battery, the keyboard layout, Jackson's small scope
  and the clock. Click the status icons to open the **control center**.
- Windows float, and the mouse works as you expect. `Super+T` turns tiling on or off for the
  current workspace.
- `Super+K` shows every shortcut.

| Keys | Action |
|---|---|
| `Super+Space` | Launcher: apps, files, settings; start with `?` to ask Jackson |
| `Super+J` | Jackson |
| `Super+V` | Clipboard history |
| `Super+Shift+S` | Select a screen region: ask Jackson, recognize text, or copy |
| `Super+Enter` | Terminal |
| `Super+E` | Files |
| `Super+Q` | Close the window |
| `Super+F` | Fullscreen |
| `Super+T` | Tiling on or off for this workspace |
| `Super+1` … `Super+9` | Workspaces |
| `Super+K` | Shortcut cheat sheet |
| `Super+Z` | Undo the last system change |
| `Super+Escape` | System Doctor |
| `Super+L` | Lock the screen |

## Meet Jackson

Jackson («Джексон») is a friendly guy from the 2000s internet. He jokes a bit, and he gets
things done. Talk to him in English or Russian.

- **Call him** with `Super+J`, or type `?` and your question in the launcher.
- **From a terminal,** use `j`:

  ```sh
  j find my datasets
  j what is using my GPU memory
  ```

- **The route chip** at the top of his panel shows which model answers and whether it runs
  locally or in the cloud. The footer of each answer shows the time, tokens, cost and whether
  any data left your machine.
- **He asks first.** Reading and searching are free. Changes to your files happen after a
  snapshot, so they can be undone. Anything that reaches outside your machine (sending,
  installing from the network, a website he has not visited before) or changes the system needs
  your approval. He shows the exact action with three buttons: *Allow once*, *Always in this
  project*, *Deny*.
- **Undo** anything he did with `Super+Z` or `sos undo`.
- **His memory** is Markdown files that you can read and edit: in
  `~/.local/share/svoya/jackson/memory/`, or in your Obsidian vault if you chose that in the
  first-run wizard.
- **Cloud models are off by default.** To use one, add the provider's API key (in the wizard, or
  later) and change the route policy. See [privacy.md](privacy.md#how-cloud-routing-is-shown).

## Your GPU

```sh
sos gpu      # check the driver, CUDA or ROCm, PyTorch, Secure Boot, suspend/resume, containers
sos fix      # apply the safe fixes; a snapshot is taken first
sos doctor   # the full check: GPU, storage and snapshots
```

In SOS the system owns the driver, and each project brings its own CUDA version, so projects do
not break each other.

## Add tools: modules

Modules add groups of tools: Local LLMs, Studio (image, video, voice), ML Lab, Agents, Dev and
Cloud burst. Nothing is installed that you did not ask for.

```sh
sos modules list              # what exists and what is installed
sos install comfyui           # install a module; a snapshot is taken first
sos modules remove comfyui    # remove it again (or: sos undo)
```

The profile you picked in the wizard is only a starting set. Change it any time.

## Models

All tools share one model store, `/srv/ai`, so a model is downloaded once.

```sh
sos models fit <model>     # will it fit my GPU? what does its license allow?
sos models pull <model>    # download it into the store
sos models list            # what you have
```

License checks use your region and whether you work commercially. Both are set in
`~/.config/svoya/svoya.toml`:

```toml
[models]
region = "EU"
commercial = true
```

## Look and feel

```sh
sos theme apply paper     # graphite | paper | phosphor | auto
```

Or use *Theme* in the control center. *Auto* switches to Graphite at sunset and to Paper at
sunrise, computed from the coordinates in your settings.

## Updates and undo

```sh
sos update          # takes a snapshot, then updates
sos undo            # undo the last change (same as Super+Z)
sos snapshot list   # all snapshots
```

If an update goes wrong badly enough that the desktop does not start, pick yesterday's system
in the boot menu.

## Where your things are

Settings, Jackson's memory, the audit log and models are plain files. The full list, and what
leaves your machine and when: [privacy.md](privacy.md).

## Getting help

- `Super+K` for shortcuts, `sos --help` for commands, or just ask Jackson.
- [FAQ](faq.md).
- Something broken? [Report a bug](https://github.com/svoya-os/sos/issues/new?template=bug.yml).
