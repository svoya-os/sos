"""SOS ASCII (svoya_cli/ascii): golden frames of every effect at 80×24 and 160×48, the style rules a
test can see, the renderer, input parsing, photosensitivity and the frame rate.

Golden frames: SOS_UPDATE_GOLDEN=1 python3 -m unittest tests.test_ascii rewrites them; look at the
diff (and at scripts/ascii-demo.py --sheet) before committing new ones.
"""
import contextlib
import io
import os
import pathlib
import re
import statistics
import time
import unittest
from unittest import mock

from svoya_cli.ascii.engine import ACCENT, Ansi, Canvas, Effect, parse_input, render, still
from svoya_cli.ascii.eye import STORY_LEN, Eye
from svoya_cli.ascii.planets import Planets

GOLDEN = pathlib.Path(__file__).parent / "golden" / "ascii"
UPDATE = os.environ.get("SOS_UPDATE_GOLDEN") == "1"

CASES = [
    ("eye-idle", lambda: Eye(night=False, clock=lambda: "21:47"), 2.2, [(80, 24), (160, 48)]),
    ("eye-thinking", lambda: Eye(state="thinking", night=False), 3.0, [(80, 24)]),
    ("eye-done", lambda: Eye(state="done", night=False), 1.1, [(80, 24)]),
    ("eye-error", lambda: Eye(state="error", night=False), 1.5, [(80, 24)]),
    ("eye-story", lambda: Eye(story=True, night=False), 7.3, [(80, 24), (160, 48)]),
    ("planets", lambda: Planets(), 5.6, [(80, 24), (160, 48)]),
]


def frame_text(cv: Canvas) -> str:
    return "\n".join(cv.lines()) + "\n--\n" + "\n".join(cv.color_lines()) + "\n"


def apply_ansi(screen: list[list[str]], data: str) -> None:
    """A tiny terminal: cursor moves (ESC [ r ; c H) and text; colors and modes are ignored."""
    r = c = 0
    for m in re.finditer(r"\x1b\[(\d+);(\d+)H|\x1b\[[0-9;?]*[A-Za-z]|([^\x1b])", data):
        if m.group(1):
            r, c = int(m.group(1)) - 1, int(m.group(2)) - 1
        elif m.group(3):
            screen[r][c] = m.group(3)
            c += 1


class GoldenFrames(unittest.TestCase):
    def test_every_effect_at_both_sizes(self):
        for name, make, t, sizes in CASES:
            for w, h in sizes:
                with self.subTest(effect=name, size=f"{w}x{h}"):
                    got = frame_text(render(make(), w, h, t))
                    path = GOLDEN / f"{name}-{w}x{h}.txt"
                    if UPDATE:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(got, encoding="utf-8")
                    self.assertTrue(path.exists(), f"no golden frame {path.name}: run with SOS_UPDATE_GOLDEN=1")
                    want = path.read_text(encoding="utf-8")
                    # a different libm may round one sine the other way: a handful of cells may move
                    # one step, a real change moves hundreds
                    diff = sum(1 for x, y in zip(want, got) if x != y) + abs(len(want) - len(got))
                    self.assertLessEqual(diff, max(3, w * h // 400), f"{path.name}: {diff} cells differ")

    def test_same_time_same_frame(self):
        a, b = render(Eye(night=False), 120, 40, 3.3), render(Eye(night=False), 120, 40, 3.3)
        self.assertEqual(frame_text(a), frame_text(b))


class StyleRules(unittest.TestCase):
    def test_four_colors_and_pink_only_for_what_is_alive(self):
        for name, make, t, sizes in CASES:
            cv = render(make(), *sizes[0], t)
            self.assertLessEqual(set(cv.co), {0, 1, 2, 3}, name)
        self.assertNotIn(ACCENT, render(Planets(), 120, 40, 5.6).co)          # planets are not alive
        self.assertIn(ACCENT, render(Eye(night=False), 120, 40, 2.2).co)       # the pupil's rim is

    def test_narrow_and_tiny_terminals_simplify(self):
        for w, h in ((79, 24), (60, 20), (40, 12), (23, 8), (10, 5), (1, 1)):
            for make in (lambda: Eye(night=False), lambda: Eye(story=True, night=False), Planets):
                cv = render(make(), w, h, 2.0)
                self.assertEqual((cv.w, cv.h, len(cv.ch)), (w, h, w * h))
        wide, narrow = render(Eye(night=False), 120, 30, 2.2), render(Eye(night=False), 70, 30, 2.2)
        self.assertIn("\\", "".join(wide.ch))                   # lashes on a wide terminal...
        self.assertNotIn("\\", "".join(narrow.ch))              # ...none on a narrow one

    def test_still_frame_for_a_pipe(self):
        text = still(Eye(night=False), 80, 24, color=False)
        self.assertEqual(len(text.splitlines()), 24)
        self.assertNotIn("\x1b", text)
        self.assertIn("\x1b[0;38;2;60;255;208;48;2;10;10;10m", still(Planets(), 80, 24, env={"COLORTERM": "truecolor"}))

    def test_story_is_a_short_film(self):
        self.assertTrue(12.0 <= STORY_LEN <= 15.0)
        eye = Eye(story=True, night=False)
        text = {t: "".join(render(eye, 100, 30, t).ch) for t in (0.5, 3.0, 7.5)}
        self.assertIn("LOOK", text[0.5])                       # the one line, at the start only
        self.assertNotIn("LOOK", text[3.0])
        self.assertIn("●", text[7.5])                           # cat-Jackson's eyes inside the pupil


class Photosensitivity(unittest.TestCase):
    def test_no_more_than_three_flashes_a_second(self):
        eye = Eye(night=False)
        for n in range(60):                                    # someone holds Enter: 20 a second
            eye.trigger("done" if n % 2 else "error", n * 0.05)
        times = sorted(te for kind, te in eye.events if kind in ("done", "error"))
        for t0 in times:
            self.assertLessEqual(sum(1 for t in times if t0 <= t < t0 + 1.0), 3)


class Renderer(unittest.TestCase):
    def test_diff_frames_rebuild_the_screen(self):
        eye = Eye(state="thinking", night=False)
        eye.resize(100, 30)
        a, b = Canvas(100, 30), Canvas(100, 30)
        eye.draw(a, 2.0)
        eye.draw(b, 2.0 + 1 / 30)
        ansi = Ansi(mode="truecolor")
        screen = [[" "] * 100 for _ in range(30)]
        full = ansi.frame(a)
        apply_ansi(screen, full)
        self.assertEqual(["".join(r) for r in screen], a.lines())
        diff = ansi.frame(b, a)
        apply_ansi(screen, diff)
        self.assertEqual(["".join(r) for r in screen], b.lines())
        self.assertLess(len(diff), len(full) / 3)              # only what changed goes over SSH

    def test_color_modes(self):
        for mode, needle in (("truecolor", "38;2;255;46;136"), ("256", "38;5;198"), ("16", "95")):
            self.assertIn(needle, Ansi(mode=mode).sgr[ACCENT])
        self.assertEqual(Ansi(mode="none").sgr[ACCENT], "\x1b[0m")


class Input(unittest.TestCase):
    def test_keys_and_mouse(self):
        self.assertEqual(parse_input("q"), [("key", "q")])
        self.assertEqual(parse_input("\x1b"), [("key", "esc")])
        self.assertEqual(parse_input("\x1b[A\x1b[D"), [("key", "up"), ("key", "left")])
        self.assertEqual(parse_input("\x1b[<35;10;5M"), [("mouse", 9, 4)])
        self.assertEqual(parse_input("\x1b[<64;10;5M"), [])     # the wheel is not a look
        self.assertEqual(parse_input("\x1b[1;5Ax"), [("key", "x")])

    def test_eye_keys(self):
        eye = Eye(night=False)
        self.assertTrue(eye.key("2", 1.0))
        self.assertEqual(eye.mode, "thinking")
        self.assertTrue(eye.key("4", 1.0))
        self.assertAlmostEqual(eye.last_event("done", 1.2), 0.2)
        self.assertFalse(eye.key("q", 1.5))
        self.assertFalse(Effect().key("esc", 0.0))

    def test_the_pupil_follows_the_mouse(self):
        eye = Eye(night=False)
        eye.resize(120, 40)
        eye.pointer(119, 20, 1.0)
        gx, _ = eye.gaze(1.0)
        self.assertGreater(gx, eye.gmax[0] * 0.9)
        eye2 = Eye(night=False)
        eye2.resize(120, 40)
        self.assertNotEqual(eye2.gaze(1.0), eye2.gaze(5.0))   # without a mouse it looks around


class FrameRate(unittest.TestCase):
    def test_at_least_24_fps_at_160x48(self):
        for name, make, t0 in (("eye", lambda: Eye(state="thinking", night=False), 1.0),
                               ("eye error", lambda: Eye(state="error", night=False), 1.1),
                               ("story", lambda: Eye(story=True, night=False), 5.0),
                               ("planets", Planets, 1.0)):
            eff = make()
            eff.resize(160, 48)
            ansi, prev, times = Ansi(), None, []
            for n in range(30):
                cv = Canvas(160, 48)
                start = time.perf_counter()
                eff.draw(cv, t0 + n / 30)
                ansi.frame(cv, prev)
                times.append(time.perf_counter() - start)
                prev = cv
            with self.subTest(effect=name):
                self.assertLess(statistics.median(times), 1 / 24)


class Command(unittest.TestCase):
    def test_sos_eye_quiet_prints_one_frame(self):
        from svoya_cli import main
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"COLUMNS": "80", "LINES": "24", "LANG": "en_US.UTF-8"}), \
                contextlib.redirect_stdout(out):
            self.assertEqual(main.main(["eye", "--quiet"]), 0)
            self.assertEqual(main.main(["art", "planets", "--quiet"]), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 48)
        self.assertIn("JACKSON::EYE", lines[0])
        self.assertIn("PLANETS", lines[24])


if __name__ == "__main__":
    unittest.main()
