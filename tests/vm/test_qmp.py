# SPDX-License-Identifier: Apache-2.0
"""QMP client tests against an in-process fake QEMU (socketpair)."""
from __future__ import annotations

import json
import pathlib
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from qmp import QMPClient, QMPError, QMPTimeout, encode_command, key_events  # noqa: E402

GREETING = {"QMP": {"version": {"qemu": {"major": 8, "minor": 2, "micro": 2}}, "capabilities": ["oob"]}}


class FakeQEMU(threading.Thread):
    """Speaks just enough QMP: greeting, capabilities, scripted replies, events in between."""

    def __init__(self, sock: socket.socket, replies: dict):
        super().__init__(daemon=True)
        self.sock = sock
        self.replies = replies
        self.received: list[dict] = []

    def send(self, obj: dict) -> None:
        self.sock.sendall((json.dumps(obj) + "\r\n").encode())

    def run(self) -> None:
        self.send(GREETING)
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
                self.received.append(msg)
                cmd, cid = msg["execute"], msg.get("id")
                if cmd == "qmp_capabilities":
                    self.send({"return": {}, "id": cid})
                elif cmd in self.replies:
                    kind, payload = self.replies[cmd]
                    if kind == "event-then-return":
                        self.send({"event": "RESUME", "timestamp": {"seconds": 1, "microseconds": 0}})
                        self.send({"return": payload, "id": "stale-id"})
                        self.send({"return": payload, "id": cid})
                    elif kind == "error":
                        self.send({"error": payload, "id": cid})
                    elif kind == "silent":
                        pass
                    else:
                        self.send({"return": payload, "id": cid})


def pair(replies: dict) -> tuple[QMPClient, FakeQEMU]:
    a, b = socket.socketpair()
    fake = FakeQEMU(b, replies)
    fake.start()
    return QMPClient(a, timeout=2.0), fake


class EncodingTests(unittest.TestCase):
    def test_encode_command_with_arguments_and_id(self):
        raw = encode_command("screendump", {"filename": "/tmp/x.ppm"}, "sos-7")
        self.assertTrue(raw.endswith(b"\r\n"))
        self.assertEqual(json.loads(raw), {"execute": "screendump", "arguments": {"filename": "/tmp/x.ppm"},
                                           "id": "sos-7"})

    def test_encode_command_without_arguments(self):
        self.assertEqual(json.loads(encode_command("qmp_capabilities")), {"execute": "qmp_capabilities"})

    def test_key_events_are_qcodes(self):
        self.assertEqual(key_events(["meta_l", "spc"]),
                         [{"type": "qcode", "data": "meta_l"}, {"type": "qcode", "data": "spc"}])


class ClientTests(unittest.TestCase):
    def test_negotiate_reads_greeting_and_sends_capabilities(self):
        client, fake = pair({})
        greeting = client.negotiate()
        self.assertEqual(greeting["version"]["qemu"]["major"], 8)
        self.assertEqual(fake.received[0]["execute"], "qmp_capabilities")
        client.close()

    def test_execute_skips_events_and_stale_replies(self):
        client, _ = pair({"query-status": ("event-then-return", {"status": "running", "running": True})})
        client.negotiate()
        self.assertEqual(client.status(), "running")
        self.assertEqual(client.events[0]["event"], "RESUME")
        client.close()

    def test_error_reply_raises(self):
        client, _ = pair({"screendump": ("error", {"class": "GenericError", "desc": "no surface"})})
        client.negotiate()
        with self.assertRaises(QMPError) as ctx:
            client.screendump("/tmp/nope.ppm")
        self.assertIn("no surface", str(ctx.exception))
        client.close()

    def test_send_key_payload(self):
        client, fake = pair({"send-key": ("return", {})})
        client.negotiate()
        client.send_key(["meta_l", "j"], hold_ms=150)
        sent = fake.received[-1]
        self.assertEqual(sent["execute"], "send-key")
        self.assertEqual(sent["arguments"]["hold-time"], 150)
        self.assertEqual([k["data"] for k in sent["arguments"]["keys"]], ["meta_l", "j"])
        client.close()

    def test_timeout(self):
        client, _ = pair({"query-status": ("silent", None)})
        client.negotiate()
        client.timeout = 0.3
        with self.assertRaises(QMPTimeout):
            client.execute("query-status", timeout=0.3)
        client.close()

    def test_connect_unix_times_out_without_socket(self):
        with self.assertRaises(QMPTimeout):
            QMPClient.connect_unix("/nonexistent/qmp.sock", wait=0.3)


if __name__ == "__main__":
    unittest.main()
