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
  in Russian. A short introduction (what SOS is, how to try it) in German, Spanish, French,
  Portuguese, Ukrainian and Estonian ([docs/i18n](docs/i18n/)).
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
  your computer (Silero VAD, Parakeet TDT 0.6B v3 and GigaAM v3 for Russian; a Supertonic 3 voice,
  fast on any processor, one per character); nothing is recorded or sent, and the system log never
  gets your words. Installing the module downloads these models from Hugging Face.
  In the evening (20:00–07:00) Jackson speaks calmer: a softer voice, a little slower. The
  customizer's «Голос» row plays a voice when you pick it and turns the calm evenings off;
  `j voice` sets the hours and the voices. "Thanks, that's all" ends a conversation in English
  too. Music (a browser tab, Spotify, a player) pauses while you talk to him and goes on after.
- **Privacy:** Jackson's own voice on an NVIDIA graphics card (`sos install voice-gpu`, part of the
  Creator profile there): Кентафурик by day and the calm one in the evening, Russian and English in
  the same voice (Qwen3-TTS 0.6B, made on your computer). Installing it downloads PyTorch with the
  CUDA libraries and the model (about 6 GB) from PyPI and Hugging Face. Without a card, or if it
  fails to load, he speaks with Supertonic as before.
- The keys people bring from Windows: `Alt+Tab` goes to the window used before (Tab again with Alt
  held goes further back, and holding Alt shows the windows' pictures), a tap of `Win` opens the
  launcher, `Win+Tab` shows every
  window with live pictures (type to filter), `Win+D` shows the desktop and brings the windows
  back, `Win+arrows` snap a window to a half, maximize and restore it, and `Alt+F4`,
  `Ctrl+Shift+Esc`, `Win+I`, `Win+R`, `Win+N` and the Copilot key (Jackson) work as expected.
  Three fingers up and down on the touchpad do what `Win+Tab` and `Win+D` do; four fingers switch
  desktops like three. A guide: [docs/guides/from-windows.md](docs/guides/from-windows.md), in
  Russian [docs/ru/from-windows.md](docs/ru/from-windows.md).
- The things people usually set up by hand: an emoji picker (`Win+.`, words in Russian and
  English, the recent ones first), text from any part of the screen (`Win+Shift+T`), a color
  picker (`Win+Shift+C`), what is playing with its buttons in the control center, game mode
  (`Win+G` or Focus → Game: no effects, the performance power profile, notifications wait, a
  stray `Win` does not cover the game), and a night light: the screen gets warmer in the
  evening, in the hours Jackson speaks calmer. The launcher counts too (`2+2*3`, `200*15%`,
  `sqrt(2)`: Enter copies the answer), and the control center switches the power mode (power
  saver, balanced, performance). The cheat sheet (`Super+K`) lists them all.
- **Privacy:** Jackson draws. «Нарисуй кота в шляпе», "draw a coloring page with a dragon", «сделай
  обои с горами»: FLUX.2 [klein] 4B (Apache-2.0, so what you make is yours to sell) in the Studio, a
  picture in seconds on a graphics card with 8 GB, minutes on a processor. It lands in
  `~/Pictures/Jackson` and in his panel, with buttons to open it, copy it or make it the wallpaper;
  Enter draws another one. Words for the shape pick the size («для телефона», «обои»,
  «вертикальную»), and a short request in any language first becomes a detailed description,
  written by the model's own text encoder. Set up once with «установи рисование» or
  `sos install draw`: it downloads about 12 GB of models from Hugging Face and builds the Studio's
  container once (Python, PyTorch and ComfyUI, about 9 GB); drawing itself stays on the computer.
  The Studio starts when he draws and stops after ten idle minutes. Qwen-Image 2.1 draws text and
  2K pictures better but needs about 16 GB of video memory and has a non-commercial license: on
  request only (`sos install qwen-image-2.1 --accept-license`, then «нарисуй … через квен»).
  `sos models kits` lists these model kits; `sos-studio up` and `down` run the Studio in the
  background.
- Jackson's eye in the terminal, `sos eye` (`sos глаз`): an ASCII eye across the whole screen, drawn
  only with characters (lids of slashes and dashes, lashes, an iris of fibers, a pink rim around the
  pupil), that blinks every 4–7 seconds, follows the mouse (or looks around by itself) and opens its
  pupil wider at night. Keys 1–5 show Jackson's states: thinking, listening, done (a pink flash),
  error (the eye falls apart into symbols and comes back). `sos eye --story` is a 14-second film into
  the pupil, where Jackson himself (the imp or the cat in his hoodie, in symbols) blinks, talks and
  smiles; `sos eye --idle` is a screensaver. `sos art planets` is the first of the ASCII screensavers.
  Four colors, 30 frames a second, never more than three flashes a second; over SSH only the cells
  that changed are sent, a narrow terminal gets a simpler picture, a pipe or `--quiet` one still frame.
  Settings in `[ascii]` of svoya.toml (fps, speed, quiet, timezone, colors).
- Three more ASCII screensavers (`sos art` lists them). `sos art rain`: rain at night over still
  water, near drops slanted by the wind and ringing on the water, far ones grey; every eighteen
  seconds the rain writes the signal ··· ——— ··· into the water. `sos art logo`: the letters SOS
  gather out of noise, a glint passes over them, the boot line grows under them and the signal types
  itself into it; once a loop the picture glitches for two frames and flies apart. `sos art heart`:
  a heart beats seventy-two times a minute, lub-dub, with a monitor line that spikes on every beat.
  The desktop's live wallpaper can be the rain (Control center → Appearance), and
  `qs ipc call ascii rain`, `logo` or `heart` shows one over everything.
- `sos hardware` (`sos железо`): is this computer ready for daily work? The model and its firmware
  (UEFI or BIOS, Secure Boot), the processor and memory, the graphics and the driver in use, the
  screens, Wi-Fi and Ethernet with their drivers and radio switches, Bluetooth, the sound cards,
  the battery's health, the sleep states, touchpad, camera and disks, and from the kernel log the
  firmware it could not load and its last errors. Problems first, each with what to do; `--save`
  writes a report to send (no serial numbers, no MAC addresses).
- For real computers: CPU microcode, the Wi-Fi regulatory database, ALSA's use-case maps (sound on
  many laptops), Intel's video decoder (cooler and longer on battery) and mpv for video and music
  files, which also gives Firefox H.264 and AAC.
- **Privacy:** an installed SOS keeps itself up to date. `sos update` (or «Update system», new in
  the launcher) now also brings new builds of SOS itself (the shell, Jackson, the `sos` command,
  the branding) from a signed package repository that every good build of `main` publishes next to
  the test ISO. A snapshot comes first and `sos undo` rolls back. Nothing checks for updates by
  itself: the repository is read only when you update (GitHub then sees your IP address, as a
  download would).
- Printing and scanning in one word: `sos install printing` (`sos установить принтер`). Printers
  on the network and modern USB ones work without drivers, Gutenprint and HP's drivers cover older
  ones, and a window adds the rest; scanners too. Printer discovery stays off until you install it.
- Estonian, Latvian, Lithuanian and Finnish keyboard layouts in the first-run wizard, which now
  also shows the layouts picked in the installer instead of always English and Russian.
- Spelling in Russian, English and Estonian: the dictionaries come with SOS, and Firefox uses them.
- Laptop and multimedia keys: keyboard backlight up and down, the touchpad switch (it says
  whether the touchpad is now on or off), Stop, and the Search, Calculator, Files, Browser and
  Mail keys.
- SOS ASCII in the interface, not only in the terminal. The lock screen has a screensaver in every
  theme: after 30 seconds without input the face fades, Jackson turns from where he stands into his
  eye, the eye looks around and follows the pointer, and every few minutes it looks closer (the
  film); a key or a click brings the face back (Control center → Appearance: 30 s, 2 min or off).
  Jackson can be drawn in symbols instead of pixels (his customizer: Auto, Pixels, Symbols; Auto
  follows the symbol style; from 120 px up, smaller he stays in pixels). With Phosphor the
  wallpaper is alive: the planet or Jackson's eye (Control center → Appearance), moving only while
  you can see it (an empty workspace or Super+D) and still in game mode or with reduced motion.
  Jackson's right-click menu calls up his eye over everything (also `qs ipc call ascii eye`, `story`,
  `planets`, `saver`). Firefox with Phosphor: the new tab and the home page are Jackson's eye and the
  time, and the browser's frame is near-black with phosphor text and the mono font; other themes
  leave Firefox as it is (a theme change shows when Firefox starts again).
- The symbol style is one setting with parts (Control center → Appearance → Symbol style): With
  Phosphor (the default), Always or Off, and what it covers. Buttons and switches: square corners,
  switches as [x], choices in brackets, sliders as [=====|-----], a terminal's block caret, «[1] 2 3»
  workspaces in the bar, «+» on the corners of panels. Folders: an icon theme where folders are
  drawn with box-drawing characters and a pink mark ([ ~ ] home, [ ↓ ] downloads, [doc], [img],
  [mp3]…), over Papirus. The cursor: an arrow with a phosphor edge, pink over links, the [|] [/] [-]
  [\] spinner while something loads (the shell and Hyprland at once, GTK apps through their
  settings, every other app from the next login). And Firefox. Jackson in symbols and the live
  wallpaper follow the style; GTK apps such as Files wear the theme's own colors (adw-gtk3, the
  libadwaita look for GTK 3, comes with SOS now). The lock
  screensaver also wakes on a decisive move of the mouse; a slow one only gets looked at.
- SOS downloads like any other Linux: the newest test build is one file,
  [sos-26.10-amd64.iso](https://github.com/svoya-os/sos/releases/download/test/sos-26.10-amd64.iso)
  (about 1.7 GB), on the [test build](https://github.com/svoya-os/sos/releases/tag/test) page of
  GitHub Releases, with no GitHub account. Every build of `main` that boots, installs and passes
  the bots replaces it. As with Pop!_OS there is a second image, `sos-26.10-amd64-nvidia.iso`
  (about 2.4 GB), with the NVIDIA drivers for installing without internet; it comes in two parts,
  and `sos-join.bat` (Windows) or `sos-join.sh` (Linux, macOS) joins and checks them. The standard
  image downloads the NVIDIA driver during the install when the computer is online.

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

- The Studio (`sos install studio`) starts: in the rootless container your Studio folder belonged
  to root, so ComfyUI's user could not write its settings there. `sos-studio build` now fetches the
  newest ComfyUI (PyTorch stays cached), and stopping the Studio no longer waits ten seconds.
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
- Jackson's quick answers come in the language of the question, as the model's do: «Который час?»
  in an English session got "It's 07:32." The interface keeps its language; "what time is it now"
  is a quick question too. A language asked for by name ("answer in Russian") wins, and the model
  is told so (the model bot's Qwen3.5 4B answered "answer in Russian: what is 17*23?" in English).
- **Privacy:** the local model server (`sos models serve`, the llm-local module) serves the models
  in `/srv/ai` once each and never asks Hugging Face about them. It listed the store a second time
  under repository names, asked Hugging Face before loading those, and ran two copies of one
  model: Jackson's local answers timed out. Jackson now waits up to five minutes for a local
  answer (a CPU reads his whole prompt first) and does not load another model after a timeout.
- The symbol cursor shows: Hyprland took every shape the theme shared with Adwaita, its parent,
  from Adwaita, so the cursor stayed Adwaita's everywhere. The theme now draws every shape itself,
  with a + for copying or zooming in and a - for zooming out.
- SOS ASCII costs a third of the processor time it did: the eye's white, the planet and its ring
  are worked out once and only what moves is drawn again. The lock screen no longer draws at the
  display's rate under its screensaver (the blinking caret and Jackson on the line stood still
  only when you could see them), and the live wallpaper stops while the screen is locked.
- Firefox with the symbol style: the new tab leaves the address bar empty instead of showing a long
  file:// address, and the frame keeps the theme's colors over a built-in theme's gradient.
- A boot that hung now and then before the desktop (about one in seventy in the test bots): the
  boot splash took over the console for its log, and when it stopped reading, the system's first
  process stopped too, on its next console message. The splash no longer takes the console, and a
  splash that does not end is ended after 30 seconds, so the login screen comes anyway.

[Unreleased]: https://github.com/svoya-os/sos/commits/main
