#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A microphone that says what is in a file: raw 16 kHz mono int16 on stdout, in real time, with
quiet before and after — what the voice service reads from `pw-record` (SVOYA_VOICE_RECORD)."""

import sys
import time

RATE, FRAME = 16000, 512


def main() -> int:
    speech = open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else b""
    lead = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    tail = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    audio = b"\0\0" * int(RATE * lead) + speech + b"\0\0" * int(RATE * tail)
    out = sys.stdout.buffer
    t0 = time.monotonic()
    step = FRAME * 2
    for i in range(0, len(audio), step):
        due = t0 + (i // 2) / RATE
        wait = due - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            out.write(audio[i:i + step].ljust(step, b"\0"))
            out.flush()
        except BrokenPipeError:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
