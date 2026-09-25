# SOS sounds — listening sheet

Theme id `svoya` (freedesktop sound theme: `svoya/index.theme` + `svoya/stereo/*.oga`, Ogg Vorbis, 48 kHz
stereo). Everything is synthesized by [`generate.py`](generate.py) — no samples — so any change is a code
change: `python3 branding/sounds/generate.py` rewrites the files and `measurements.json`.

**Character.** Soft sine voices with a trace of 2nd/3rd harmonic that dies faster than the fundamental
(a small struck-glass/marimba feel), raised-cosine attacks, exponential releases, a gentle 7 kHz low-pass
and a short dark room with decorrelated left/right tails for subtle width. One pitch family, just
intonation on A: A4 440 · E5 660 · A5 880 · B5 990 · C♯6 1100 · E6 1320 Hz, so any two sounds that
overlap still agree. Rising intervals mean *something started/arrived*, falling ones *ended/left*.

**Levels.** K-weighted (ITU-R BS.1770) loudness, gated, measured on the decoded .oga that ships: −18 LUFS
(±0.3). Exceptions: `audio-volume-change` −21 (it repeats while dragging) and `jackson-thinking` −32
(meant to be barely there). Peaks (4× oversampled) are −5 dBFS or lower, far under the −3 dBFS ceiling.
For clips shorter than one 400 ms BS.1770 block the loudness uses 100 ms blocks with the same gates, so
treat the figures as a close approximation, not a certified measurement.

| sound | length | LUFS | peak dBFS | what you hear |
|---|---|---|---|---|
| `desktop-login` | 2.07 s | -17.9 | -11.7 | The mark in sound: ··· ——— ··· at 50 ms per Morse unit. First S on A5, the O as three warm E5 tones, the last S climbing A5–C♯6–E6 and ringing out: an A-major greeting, never a distress beep. |
| `desktop-logout` | 1.02 s | -17.9 | -12.4 | C♯6 · A5 · E5 — the greeting folded back down; the last note long and soft. |
| `message-new-instant` | 0.41 s | -18.0 | -8.6 | One soft tick on E6 with an E5 undertone. The only notification sound. |
| `bell` | 0.36 s | -17.9 | -8.4 | Terminal/console bell: a short, round E5, darker than a notification. |
| `complete` | 0.74 s | -17.9 | -11.0 | A job finished: E5–A5–E6, three quick rising notes. |
| `dialog-information` | 0.45 s | -17.9 | -9.2 | A single A5. Neutral. |
| `dialog-warning` | 0.50 s | -17.9 | -11.1 | Two even E5 blips: attention, not alarm. |
| `dialog-error` | 0.54 s | -17.9 | -11.2 | Two low, dark A4 blips. |
| `device-added` | 0.46 s | -17.9 | -11.1 | Plugged in: E5 → B5, a rising fifth. |
| `device-removed` | 0.46 s | -17.9 | -10.8 | Unplugged: B5 → E5, the same fifth falling. |
| `audio-volume-change` | 0.22 s | -21.0 | -7.7 | A 70 ms C♯6 tick that repeats cleanly while the volume moves; 3 dB quieter than the rest. |
| `camera-shutter` | 0.24 s | -18.3 | -5.2 | Two filtered noise clicks 75 ms apart with a soft body: a small leaf shutter. |
| `screen-capture` | 0.39 s | -18.0 | -10.2 | A short airy sweep and an E6 ping: the screen was captured. |
| `jackson-listen` | 0.42 s | -17.9 | -10.4 | Jackson starts listening: E5 → A5, rising fourth, quick. |
| `jackson-done` | 0.52 s | -17.9 | -9.5 | Jackson finished: A5 → E5, the listening motif turned down. |
| `jackson-error` | 0.53 s | -17.9 | -11.3 | Jackson could not do it: A4 → E4, a low, dark double. |
| `jackson-thinking` | 0.07 s | -31.9 | -25.6 | Optional: an almost inaudible A6 tick for long waits (−32 LUFS). |

**Checked:** each file starts and ends at silence (no clicks: no energy above 10 kHz, no
discontinuities), the login sound's audible length is 1.8 s. **Not checked:** listening on real speakers
and headphones. Please give them one pass on a laptop and on headphones before the release.

**Install.** Packaging installs `svoya/` as `/usr/share/sounds/svoya/` (where libcanberra looks for sound
themes) and links `/usr/share/svoya/sounds → /usr/share/sounds/svoya` (docs/ARCHITECTURE.md §3). Select it
with `gsettings set org.gnome.desktop.sound theme-name svoya` / `gtk-sound-theme-name = svoya`. The
`jackson-*` names are ours (not in the freedesktop naming spec); the shell plays them by name, e.g.
`canberra-gtk-play -i jackson-listen`. The startup sound can be turned off in the first-run wizard.

License: CC BY-SA 4.0 (the sounds), Apache-2.0 (the generator).
