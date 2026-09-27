# Coming from Windows

> SOS is pre-alpha; this describes the current test builds. `Super` is the Windows key.
>
> По-русски: [docs/ru/from-windows.md](../ru/from-windows.md).

Your hands already know most of SOS. The keys below work the way they do on Windows, the
touchpad does what a Windows laptop does, and the few real differences are at the end.
`Super+K` shows every shortcut at any time.

## The keys you know

| On Windows | In SOS |
|---|---|
| Tap `Win` | The launcher: apps, files, settings, and `?` to ask Jackson |
| `Win+Tab` | Every window at a glance, with live pictures. Type to filter, `Enter` to go, middle click to close |
| `Win+D` | Show the desktop. Press it again and the windows come back |
| `Win+←` / `Win+→` | Snap the window to the left or right half |
| `Win+↑` / `Win+↓` | Maximize / back to a normal size in the middle |
| `Alt+Tab` | The window you used before. Keep Alt down and press Tab again for the ones before it; hold Alt a moment and their pictures appear |
| `Alt+F4` | Close the window (`Super+Q` does the same) |
| `Win+E` | Files |
| `Win+I` | Settings |
| `Win+R` | Run: the launcher. It also counts: type `2+2*3`, `200*15%` or `sqrt(2)` and `Enter` copies the answer |
| `Win+L` | Lock the screen |
| `Win+V` | Clipboard history |
| `Win+Shift+S`, `Print Screen` | Screenshot of a region: copy it, save it, read its text or ask Jackson about it |
| `Win+.` or `Win+;` | Emoji. Type a word in English or Russian; `Enter` puts it where you were typing |
| `Win+A`, `Win+N` | The control center: Wi-Fi, Bluetooth, sound, what is playing, brightness, power mode, theme, focus, night light, notifications |
| `Win+G` | Game mode (see below) |
| `Ctrl+Shift+Esc` | What is running and what it takes (`btop`) |
| `Ctrl+Alt+Del` | Log out, restart, shut down |
| `Alt+Shift` | Switch the keyboard layout |
| The Copilot key | Jackson |

From PowerToys: `Win+Shift+T` copies the text of any region of the screen (Russian and
English), `Win+Shift+C` picks a color from anywhere and copies it as `#rrggbb`.

## The touchpad

| Gesture | What it does |
|---|---|
| Three fingers left or right (four too) | The next or previous desktop |
| Three fingers up | Every window at a glance (`Win+Tab`) |
| Three fingers down | Show the desktop (`Win+D`) |
| Two fingers | Scroll (content follows the fingers, like Windows' default) |
| Tap | Click; a two-finger tap is a right click |

## What is different

- **Desktops instead of a busy taskbar.** `Super+1` … `Super+9` switch desktops, `Super+Shift+1`
  … `Super+Shift+9` send the window to one. They are at the top left of the bar. Many people keep
  one desktop per task: the browser on 1, the code on 2, the chat on 3.
- **No minimize.** Hide everything with `Win+D`, or send the window to another desktop.
- **Windows float,** as on Windows. `Super+T` turns tiling on for the current desktop: windows
  share the screen side by side by themselves, and `Super+arrows` then move between them.
- **Installing apps.** Type the name in the launcher and pick «Install …», tell Jackson
  "install telegram", or run `sos install telegram`. No installers to download.
- **Games.** `sos install steam` sets up Steam with Proton (Windows games), GameMode, MangoHud and
  the 32-bit drivers. Minecraft and others are one word each: `sos apps` lists them.
- **`Win+Space`** opens the launcher here (as on a Mac); the layout switch is `Alt+Shift`, as on
  most Windows PCs in Russia.

## Game mode

`Win+G`, or *Focus → Game* in the control center: no animations, blur, shadows or gaps, the
power profile goes to performance, notifications wait, and a stray tap of the Windows key does not
cover the game with the launcher. `Win+G` again brings everything back. Fullscreen games keep the
screen awake in any mode.

## Talk to Jackson

With the voice module (`sos install voice`, part of the Creator profile), Jackson listens and
answers aloud, in Russian and English, all on this computer.

- **Hold `Super+J`** and speak, let go when you are done. Or press the microphone in his panel.
  On laptops with a Copilot key, that key opens him.
- **Keep talking:** after an answer he listens a few more seconds, so a conversation goes on by
  itself. "Thanks, that's all" (or «спасибо, всё») ends it; typing a question or pressing the
  microphone while he speaks stops him.
- **His voice:** pick one and hear it in his customizer (the «Голос» row), or `j voice set M3`.
- **Calmer in the evening:** from 20:00 to 07:00 he speaks with a softer voice, a little slower.
  `j voice evening 21:30-07:00` moves the hours, `j voice evening off` turns it off, `j voice`
  shows everything.
- The microphone is open only while you talk to him. Nothing is recorded or sent anywhere.

## Night light

*Night light* in the control center: *Off*, *Evenings* or *On*. The screen gets warmer (less
blue) in the evening hours, the same hours Jackson speaks calmer, so `j voice evening …`
moves both. Game mode switches it off while you play.

## The small things people usually set up by hand

Already there, nothing to install: clipboard history, emoji, text from the screen, the color
picker, a calculator in the launcher, play/pause and track buttons for the browser or Spotify in
the control center (and the media keys), the power mode, `Win+arrows` snapping, desktop gestures,
a warm screen in the evening, game mode, and undo for system changes (`Super+Z`).

More: [first steps](first-steps.md) · [FAQ](faq.md).
