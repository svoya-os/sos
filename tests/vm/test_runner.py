# SPDX-License-Identifier: Apache-2.0
"""Runner end to end against a fake QEMU that answers screendump by writing PPM files."""
from __future__ import annotations

import json
import pathlib
import socket
import sys
import tempfile
import threading
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run  # noqa: E402
from qmp import QMPClient  # noqa: E402


class ScreenQEMU(threading.Thread):
    def __init__(self, sock: socket.socket, frames: list[bytes]):
        super().__init__(daemon=True)
        self.sock, self.frames, self.keys, self.commands = sock, list(frames), [], []

    def send(self, obj: dict) -> None:
        self.sock.sendall((json.dumps(obj) + "\n").encode())

    def run(self) -> None:
        self.send({"QMP": {"version": {}, "capabilities": []}})
        buf = b""
        while True:
            try:
                chunk = self.sock.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = json.loads(line)
                if msg["execute"] == "screendump":
                    frame = self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]
                    pathlib.Path(msg["arguments"]["filename"]).write_bytes(frame)
                elif msg["execute"] == "send-key":
                    self.keys.append([k["data"] for k in msg["arguments"]["keys"]])
                self.commands.append((msg["execute"], msg.get("arguments")))
                self.send({"return": {}, "id": msg.get("id")})


def frame(color: tuple[int, int, int], w: int = 40, h: int = 30, stripe: bool = False) -> bytes:
    px = bytearray(bytes(color) * (w * h))
    if stripe:
        for i in range(0, w * h, 2):
            px[i * 3:i * 3 + 3] = b"\xff\xb5\x47"
    return f"P6\n{w} {h}\n255\n".encode() + bytes(px)


class RunnerTests(unittest.TestCase):
    def test_plan_with_screens_keys_and_serial(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "serial.log").write_text("...\nSOS-MARK 42.00 desktop-ready\n")
            a, b = socket.socketpair()
            fake = ScreenQEMU(b, [frame((0, 0, 0)), frame((12, 13, 15), stripe=True),
                                  frame((12, 13, 15), stripe=True), frame((20, 20, 20), stripe=True)])
            fake.start()
            qmp = QMPClient(a, timeout=2)
            qmp.negotiate()
            runner = run.Runner(qmp, out, scale=0.01, proc=None)
            steps = [
                {"id": "menu", "action": "wait_screen", "timeout_s": 50},
                {"id": "menu", "action": "screenshot", "name": "01-menu", "assert": "not_blank"},
                {"id": "desk", "action": "wait_serial", "pattern": r"SOS-MARK \S+ desktop-ready", "timeout_s": 5},
                {"id": "launch", "action": "key", "keys": ["meta_l", "spc"]},
                {"id": "launch", "action": "screenshot", "name": "02-launch", "expect_change_from": "01-menu"},
            ]
            self.assertTrue(runner.run(steps), runner.results)
            self.assertEqual(fake.keys, [["meta_l", "spc"]])
            self.assertTrue((out / "screens" / "01-menu.png").exists())
            self.assertIn("changed vs 01-menu", runner.results[-1]["detail"])
            run.write_reports(out, {"plan": "t", "firmware": "uefi", "accel": "tcg", "iso": "x"},
                              runner.results, True)
            self.assertIn("passed", (out / "report.md").read_text())
            qmp.close()

    def test_failure_stops_and_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "serial.log").write_text("SOS-MARK 900.0 desktop-timeout\n")
            a, b = socket.socketpair()
            ScreenQEMU(b, [frame((0, 0, 0))]).start()
            qmp = QMPClient(a, timeout=2)
            qmp.negotiate()
            runner = run.Runner(qmp, out, scale=0.01, proc=None)
            ok = runner.run([
                {"id": "desk", "action": "wait_serial", "pattern": "desktop-ready",
                 "fail_pattern": "desktop-timeout", "timeout_s": 5},
                {"id": "never", "action": "screenshot", "name": "x"},
            ])
            self.assertFalse(ok)
            self.assertEqual([r["status"] for r in runner.results], ["failed"])
            self.assertTrue(any(p.name.startswith("fail-01") for p in (out / "screens").iterdir()))
            qmp.close()

    def test_the_nth_serial_event_decides(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "serial.log").write_text("jackson.engine: turn done in 900 ms\n"
                                            "jackson.engine: turn failed after 20000 ms: no_local_model\n"
                                            "jackson.engine: turn done in 1200 ms\n")
            a, b = socket.socketpair()
            ScreenQEMU(b, [frame((0, 0, 0))]).start()
            qmp = QMPClient(a, timeout=2)
            qmp.negotiate()
            runner = run.Runner(qmp, out, scale=0.01, proc=None)
            turn = {"id": "answer", "action": "wait_serial", "pattern": "turn done", "fail_pattern": "turn failed",
                    "timeout_s": 5, "continue_on_failure": True}
            ok = runner.run([{**turn, "count": 1}, {**turn, "count": 2}, {**turn, "count": 3},
                             {**turn, "count": 4, "timeout_s": 0.2}])
            self.assertFalse(ok)
            self.assertEqual([r["status"] for r in runner.results], ["ok", "failed", "ok", "failed"])
            self.assertIn("no_local_model", runner.results[1]["detail"])       # the 2nd answer failed
            self.assertIn("(#3)", runner.results[2]["detail"])
            self.assertIn("timed out", runner.results[3]["detail"])
            qmp.close()

    def test_click_eject_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "serial.log").write_text("")
            a, b = socket.socketpair()
            fake = ScreenQEMU(b, [frame((12, 13, 15), w=400, h=300, stripe=True)])
            fake.start()
            qmp = QMPClient(a, timeout=2)
            qmp.negotiate()
            runner = run.Runner(qmp, out, scale=0.01, proc=None)
            ok = runner.run([
                {"id": "c", "action": "click", "at": [720, 450]},              # before any screenshot: 1440x900
                {"id": "s", "action": "screenshot", "name": "x"},
                {"id": "c", "action": "click", "at": [399, 0]},                # now the 400x300 frame
                {"id": "e", "action": "eject"},
                {"id": "r", "action": "reset"},
            ])
            self.assertTrue(ok, runner.results)
            events = [args["events"] for cmd, args in fake.commands if cmd == "input-send-event"]
            self.assertEqual(events[0], [{"type": "abs", "data": {"axis": "x", "value": 16395}},
                                         {"type": "abs", "data": {"axis": "y", "value": 16402}}])
            self.assertEqual([e[0]["data"] for e in events[1:3]], [{"down": True, "button": "left"},
                                                                   {"down": False, "button": "left"}])
            self.assertEqual(events[3][0]["data"]["value"], 32767)          # the right edge
            self.assertIn(("eject", {"id": "cdrom", "force": True}), fake.commands)
            self.assertIn(("system_reset", None), fake.commands)
            qmp.close()

    def test_journey_goes_on_after_a_failed_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "serial.log").write_text("")
            a, b = socket.socketpair()
            ScreenQEMU(b, [frame((0, 0, 0))]).start()
            qmp = QMPClient(a, timeout=2)
            qmp.negotiate()
            runner = run.Runner(qmp, out, scale=0.01, proc=None)
            ok = runner.run([
                {"id": "blank", "action": "screenshot", "name": "a", "assert": "not_blank", "continue_on_failure": True},
                {"id": "pause", "action": "sleep", "seconds": 0.1},
                {"id": "next", "action": "screenshot", "name": "b"},
            ])
            self.assertFalse(ok)                                       # the failure is still reported
            self.assertEqual([r["status"] for r in runner.results], ["failed", "ok", "ok"])
            qmp.close()


if __name__ == "__main__":
    unittest.main()
