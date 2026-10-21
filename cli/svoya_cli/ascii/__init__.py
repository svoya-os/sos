"""SOS ASCII: one small engine for Jackson's eye (``sos eye``), the screensavers (``sos art``) and,
later, the games (``sos play``). Everything is characters in a terminal: no images, no GPU.

The style rules every effect follows (``cli/tests/test_ascii.py`` checks the ones a test can see):

- four colors and no more: background #0a0a0a, phosphor #3cffd0, one hot accent #ff2e88 only for
  what is alive (the pupil, a heart, an error, a win) and grey #5a5a5a for noise;
- brightness is the density of the character: ``RAMP`` " .:-=+*#%@" (``BLOCKS`` " ░▒▓█" for solid
  shapes); one engine draws the eye, the planets and the letters;
- a hard monospace grid, frames from ─ │ ┌ ┐ └ ┘, headings in capitals, no rounding and no
  shadows; a glitch may break the grid for one or two frames, then everything is back in place;
- 30 frames a second, ease-in-out curves, a slow breathing of brightness, a little jitter at the
  edges; never more than three flashes a second;
- a weak laptop and SSH are fine: only the cells that changed are written, a narrow terminal
  (< 80 columns) gets a simpler picture rather than a broken one, and without a terminal (a pipe,
  ``--quiet``) it is one still frame.
"""
from .engine import ACCENT, ASPECT, BG, BLOCKS, FG, NOISE, PALETTE, RAMP, Canvas, Effect, run, still

__all__ = ["ACCENT", "ASPECT", "BG", "BLOCKS", "FG", "NOISE", "PALETTE", "RAMP", "Canvas", "Effect", "run",
           "still"]
