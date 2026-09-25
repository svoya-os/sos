#!/usr/bin/env python3
"""SOS sound theme «svoya»: every sound is synthesized here (no samples), so it is reproducible.

    python3 branding/sounds/generate.py          # → branding/sounds/svoya/stereo/*.oga + index.theme

Palette: soft sine voices with a little 2nd/3rd harmonic, raised-cosine attacks, exponential decays,
a gentle low-pass and a short, decorrelated room for width. Pitches come from one just-intonation
family on A: 440 · 550 · 660 · 880 · 990 · 1100 · 1320 Hz (the «880/660» signal pair and its friends).
Loudness is measured with ITU-R BS.1770 K-weighting over the audible part of each sound and normalized
to −18 LUFS (quiet UI ticks lower, see TARGETS), with the 4× oversampled peak kept ≤ −3 dBFS.
Rendered as 48 kHz stereo WAV, then Ogg Vorbis (.oga) with ffmpeg.

SPDX-License-Identifier: Apache-2.0
The sounds it produces are licensed CC BY-SA 4.0.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import wave

import numpy as np
from scipy import signal

HERE = pathlib.Path(__file__).resolve().parent
THEME_DIR = HERE / "svoya"
OUT = THEME_DIR / "stereo"
SR = 48000
RNG = np.random.default_rng(26_10)

A4, CS5, E5, A5, B5, CS6, E6 = 440.0, 550.0, 660.0, 880.0, 990.0, 1100.0, 1320.0


# ───────────────────────────── voices ─────────────────────────────

def env(n_attack: int, n_sustain: int, n_release: int, sustain_drop_db: float = 0.0) -> np.ndarray:
    """Raised-cosine attack, gently falling sustain, exponential-feel release ending at exactly 0."""
    a = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, max(n_attack, 1), endpoint=False))
    s = 10 ** (np.linspace(0, -sustain_drop_db, max(n_sustain, 1)) / 20)
    r_t = np.linspace(0, 1, max(n_release, 2))
    r = s[-1] * (np.exp(-5.0 * r_t) - np.exp(-5.0)) / (1 - np.exp(-5.0))
    return np.concatenate([a, s, r])


def tone(freq: float, dur: float, attack: float = 0.006, release: float = 0.18, drop_db: float = 3.0,
         harmonics=((2, -20.0), (3, -32.0)), detune_cents: float = 0.0, lp: float | None = None) -> np.ndarray:
    """A blip: `dur` is the keyed length (attack + sustain); the release rings after it."""
    na, nr = int(attack * SR), int(release * SR)
    ns = max(int(dur * SR) - na, 1)
    e = env(na, ns, nr, drop_db)
    t = np.arange(len(e)) / SR
    f = freq * 2 ** (detune_cents / 1200)
    x = np.sin(2 * np.pi * f * t)
    for k, db in harmonics:
        # upper partials die away faster, as in struck or plucked things
        x += 10 ** (db / 20) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * 6 * k)
    y = x * e
    if lp:
        y = signal.sosfiltfilt(signal.butter(2, lp, fs=SR, output="sos"), y)
    return y


def noise_burst(dur: float, lo: float, hi: float, attack: float = 0.002, release: float = 0.05) -> np.ndarray:
    n = int(dur * SR)
    x = RNG.standard_normal(n + int(release * SR))
    x = signal.sosfiltfilt(signal.butter(2, [lo, hi], btype="band", fs=SR, output="sos"), x)
    e = env(int(attack * SR), n - int(attack * SR), int(release * SR), 6.0)
    return x[: len(e)] * e / (np.abs(x).max() + 1e-9)


def place(events, tail: float = 0.6) -> np.ndarray:
    """events: [(start_s, mono, pan −1..1)] → stereo (constant-power pan)."""
    end = max(s + len(m) / SR for s, m, _ in events) + tail
    out = np.zeros((int(end * SR) + 1, 2))
    for start, mono, pan in events:
        i = int(start * SR)
        th = (pan + 1) * np.pi / 4
        out[i:i + len(mono), 0] += mono * np.cos(th)
        out[i:i + len(mono), 1] += mono * np.sin(th)
    return out


def room(x: np.ndarray, wet_db: float = -17.0, length: float = 0.55, lp: float = 5200.0) -> np.ndarray:
    """A short, dark, decorrelated room: early reflections + a smooth tail; subtle stereo."""
    n = int(length * SR)
    t = np.arange(n) / SR
    out = x.copy()
    for ch in range(2):
        ir = RNG.standard_normal(n) * np.exp(-t / (length / 6.5))
        ir = signal.sosfilt(signal.butter(1, lp, fs=SR, output="sos"), ir)
        for delay, gain in ((0.011 + 0.004 * ch, 0.5), (0.023 - 0.003 * ch, 0.35), (0.037 + 0.002 * ch, 0.25)):
            ir[int(delay * SR)] += gain * 4
        ir *= 10 ** (wet_db / 20) / np.sqrt(np.sum(ir ** 2))
        out[:, ch] += signal.fftconvolve(x[:, ch], ir)[: len(x)]
    return out


def finish(x: np.ndarray, lp: float = 7000.0, hp: float = 90.0) -> np.ndarray:
    sos = np.vstack([signal.butter(2, lp, fs=SR, output="sos"), signal.butter(1, hp, btype="high", fs=SR, output="sos")])
    y = signal.sosfiltfilt(sos, x, axis=0)
    # 3 ms fade-in guard and a 25 ms fade-out so the file starts and ends at true silence
    fi, fo = int(0.003 * SR), int(0.025 * SR)
    y[:fi] *= (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fi)))[:, None]
    y[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo)))[:, None]
    # trim the silent end of the tail (below −70 dBFS), keep 20 ms
    level = np.max(np.abs(y), axis=1)
    last = np.nonzero(level > 10 ** (-70 / 20))[0]
    end = min(len(y), (last[-1] if len(last) else len(y)) + int(0.02 * SR))
    y = y[:end]
    fo = min(fo, len(y))
    y[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo)))[:, None]
    return y


# ───────────────────────────── loudness (BS.1770) ─────────────────────────────

def k_weight(x: np.ndarray) -> np.ndarray:
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)


def loudness(x: np.ndarray) -> float:
    """Gated K-weighted loudness. For sounds shorter than one 400 ms block, BS.1770 is undefined; we use
    100 ms blocks (75 % overlap) with the same absolute (−70) and relative (−10 LU) gates."""
    z = k_weight(x)
    blk, hop = int(0.1 * SR), int(0.025 * SR)
    ms = [np.sum(np.mean(z[i:i + blk] ** 2, axis=0)) for i in range(0, max(1, len(z) - blk + 1), hop)]
    ms = np.array(ms)
    lk = -0.691 + 10 * np.log10(ms + 1e-20)
    ms = ms[lk > -70]
    rel = -0.691 + 10 * np.log10(np.mean(ms)) - 10
    ms = ms[-0.691 + 10 * np.log10(ms) > rel]
    return float(-0.691 + 10 * np.log10(np.mean(ms)))


def true_peak_db(x: np.ndarray) -> float:
    up = signal.resample_poly(x, 4, 1, axis=0)
    return float(20 * np.log10(np.max(np.abs(up)) + 1e-12))


def normalize(x: np.ndarray, target_lufs: float, ceiling_db: float = -3.0):
    g = 10 ** ((target_lufs - loudness(x)) / 20)
    y = x * g
    tp = true_peak_db(y)
    if tp > ceiling_db:                      # never limit: lower the whole sound instead
        y *= 10 ** ((ceiling_db - tp) / 20)
    return y, loudness(y), true_peak_db(y)


# ───────────────────────────── the sounds ─────────────────────────────

def morse_login() -> np.ndarray:
    """··· ——— ··· in real Morse timing (unit 50 ms): the first S neutral, the O warm and low,
    the last S climbing A–C♯–E so the signal resolves into a major chord — hello, not help."""
    u = 0.05
    ev, t = [], 0.0
    s1 = [A5, A5, A5]
    o = [E5, E5, E5]
    s2 = [A5, CS6, E6]
    for li, (letter, pitches) in enumerate((("...", s1), ("---", o), ("...", s2))):
        for si, (sym, f) in enumerate(zip(letter, pitches)):
            last = li == 2 and si == 2
            if sym == ".":
                v = tone(f, u, attack=0.005, release=0.55 if last else 0.16, drop_db=2, detune_cents=+1.5)
            else:
                v = tone(f, 3 * u, attack=0.012, release=0.22, drop_db=4, harmonics=((2, -18.0), (3, -30.0), (4, -40.0)))
            pan = (-0.18 if sym == "." else 0.12) * (1 if li != 2 else -0.6)
            ev.append((t, v * (0.9 if sym == "-" else 1.0), pan))
            t += (1 if sym == "." else 3) * u + (u if si < 2 else 0)
        t += 3 * u
    # a whisper of the chord under the last S
    ev.append((t - 3 * u - 2 * u, tone(A4, 0.1, attack=0.03, release=0.5, drop_db=6, harmonics=()) * 0.18, 0.0))
    return room(place(ev, tail=0.2), wet_db=-16)


def logout() -> np.ndarray:
    ev = [(0.0, tone(CS6, 0.05, release=0.16), -0.15), (0.11, tone(A5, 0.05, release=0.16), 0.0),
          (0.22, tone(E5, 0.15, attack=0.012, release=0.45, drop_db=5), 0.12)]
    return room(place(ev, 0.2), wet_db=-16)


def single(freq: float, dur: float = 0.04, release: float = 0.22, under: float | None = None, pan: float = 0.0,
           lp: float | None = None) -> np.ndarray:
    v = tone(freq, dur, attack=0.004, release=release, drop_db=2, lp=lp)
    ev = [(0.0, v, pan)]
    if under:
        ev.append((0.0, tone(under, dur, attack=0.004, release=release * 0.8, drop_db=2, harmonics=()) * 0.3, -pan))
    return room(place(ev, 0.15), wet_db=-19)


def pair(f1: float, f2: float, gap: float = 0.085, dur: float = 0.045, release: float = 0.2, lp=None,
         level2: float = 1.0) -> np.ndarray:
    ev = [(0.0, tone(f1, dur, release=release * 0.8, lp=lp), -0.12),
          (gap, tone(f2, dur, release=release, lp=lp) * level2, 0.12)]
    return room(place(ev, 0.15), wet_db=-18)


def shutter() -> np.ndarray:
    a = noise_burst(0.012, 1200, 5200, attack=0.0015, release=0.03)
    b = noise_burst(0.018, 700, 3800, attack=0.002, release=0.05) * 0.8
    body = tone(220.0, 0.01, attack=0.002, release=0.05, harmonics=()) * 0.35
    return room(place([(0.0, a, -0.1), (0.0, body, 0.0), (0.075, b, 0.1)], 0.1), wet_db=-20, length=0.3)


def screen_capture() -> np.ndarray:
    sweep = noise_burst(0.05, 2200, 7000, attack=0.01, release=0.08) * 0.55
    ping = tone(E6, 0.03, attack=0.004, release=0.2, drop_db=2) * 0.7
    return room(place([(0.0, sweep, -0.2), (0.04, ping, 0.15)], 0.12), wet_db=-18)


def thinking_tick() -> np.ndarray:
    v = tone(1760.0, 0.008, attack=0.002, release=0.04, drop_db=0, harmonics=())
    return place([(0.0, v, 0.0)], 0.03)


SOUNDS = {
    # name: (builder, target LUFS, note for the listening sheet)
    "desktop-login": (morse_login, -18.0, "The mark in sound: ··· ——— ··· at 50 ms per Morse unit. First S on A5, "
                      "the O as three warm E5 tones, the last S climbing A5–C♯6–E6 and ringing out: an A-major "
                      "greeting, never a distress beep."),
    "desktop-logout": (logout, -18.0, "C♯6 · A5 · E5 — the greeting folded back down; the last note long and soft."),
    "message-new-instant": (lambda: single(E6, under=E5, pan=0.1), -18.0,
                            "One soft tick on E6 with an E5 undertone. The only notification sound."),
    "bell": (lambda: single(E5, dur=0.03, release=0.18, lp=3800), -18.0,
             "Terminal/console bell: a short, round E5, darker than a notification."),
    "complete": (lambda: room(place([(0.0, tone(E5, 0.04, release=0.12), -0.15), (0.07, tone(A5, 0.04, release=0.14), 0.0),
                                     (0.14, tone(E6, 0.05, release=0.4, drop_db=2), 0.15)], 0.15), wet_db=-17), -18.0,
                 "A job finished: E5–A5–E6, three quick rising notes."),
    "dialog-information": (lambda: single(A5, dur=0.05, release=0.25), -18.0, "A single A5. Neutral."),
    "dialog-warning": (lambda: pair(E5, E5, gap=0.12, dur=0.05, release=0.18, level2=0.85), -18.0,
                       "Two even E5 blips: attention, not alarm."),
    "dialog-error": (lambda: pair(A4, A4, gap=0.13, dur=0.06, release=0.2, lp=2600, level2=0.9), -18.0,
                     "Two low, dark A4 blips."),
    "device-added": (lambda: pair(E5, B5, gap=0.07), -18.0, "Plugged in: E5 → B5, a rising fifth."),
    "device-removed": (lambda: pair(B5, E5, gap=0.07), -18.0, "Unplugged: B5 → E5, the same fifth falling."),
    "audio-volume-change": (lambda: single(CS6, dur=0.012, release=0.06), -21.0,
                            "A 70 ms C♯6 tick that repeats cleanly while the volume moves; 3 dB quieter than the rest."),
    "camera-shutter": (shutter, -18.0, "Two filtered noise clicks 75 ms apart with a soft body: a small leaf shutter."),
    "screen-capture": (screen_capture, -18.0, "A short airy sweep and an E6 ping: the screen was captured."),
    "jackson-listen": (lambda: pair(E5, A5, gap=0.075, dur=0.04, release=0.16), -18.0,
                       "Jackson starts listening: E5 → A5, rising fourth, quick."),
    "jackson-done": (lambda: pair(A5, E5, gap=0.085, dur=0.045, release=0.24), -18.0,
                     "Jackson finished: A5 → E5, the listening motif turned down."),
    "jackson-error": (lambda: pair(A4, E5 / 2, gap=0.12, dur=0.06, release=0.2, lp=2400), -18.0,
                      "Jackson could not do it: A4 → E4, a low, dark double."),
    "jackson-thinking": (thinking_tick, -32.0, "Optional: an almost inaudible A6 tick for long waits (−32 LUFS)."),
}


def write_wav(path: pathlib.Path, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.rint(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


INDEX_THEME = """[Sound Theme]
Name=SOS
Name[ru]=СОС
Comment=Soft synthesized sounds of SOS (Svoya Operating System)
Comment[ru]=Мягкие синтезированные звуки СОС (Своя Операционная Система)
Inherits=freedesktop
Directories=stereo

[stereo]
OutputProfile=stereo
"""


def main(argv) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (THEME_DIR / "index.theme").write_text(INDEX_THEME, encoding="utf-8")
    report = {}
    wav_dir = pathlib.Path(tempfile.mkdtemp(prefix="sos-sounds-"))
    for name, (build, target, note) in SOUNDS.items():
        x = finish(build())
        y, lufs, tp = normalize(x, target)
        wav = wav_dir / f"{name}.wav"
        write_wav(wav, y)
        oga = OUT / f"{name}.oga"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "6",
                        "-metadata", f"title={name}", "-metadata", "artist=SOS design team",
                        "-metadata", "copyright=CC BY-SA 4.0", str(oga)], check=True)
        # measure what actually ships (decoded Vorbis)
        dec = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(oga), "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                             check=True, capture_output=True).stdout
        z = np.frombuffer(dec, "<i2").reshape(-1, 2) / 32768.0
        report[name] = {"seconds": round(len(z) / SR, 3), "lufs": round(loudness(z), 1),
                        "truePeakDb": round(true_peak_db(z), 1), "target": target, "note": note}
        print(f"{name:22s} {len(z) / SR:5.2f} s  {loudness(z):6.1f} LUFS  peak {true_peak_db(z):5.1f} dBFS")
    for f in wav_dir.glob("*.wav"):
        f.unlink()
    wav_dir.rmdir()
    (HERE / "measurements.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
