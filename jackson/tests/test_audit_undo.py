# SPDX-License-Identifier: Apache-2.0
import json
import threading
import unittest

from jackson.audit import GENESIS, AuditLog, sha256_hex
from jackson.memory import Memory
from jackson.config import MemoryConfig
from jackson.paths import Paths
from jackson.svoya import SvoyaCli
from jackson.trash import Trash
from jackson.undo import UndoLog
from tests.fakes import FakeRunner, make_app, rmtree, short_tmpdir
from tests.test_permissions import ctx_for


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.log = AuditLog(self.root / "audit.jsonl")

    def tearDown(self):
        rmtree(self.root)

    def test_chain_and_verify(self):
        for i in range(5):
            self.log.append("tool", tool="fs.read", n=i)
        lines = (self.root / "audit.jsonl").read_bytes().splitlines()
        self.assertEqual(json.loads(lines[0])["prev"], GENESIS)
        for prev, line in zip(lines, lines[1:]):
            self.assertEqual(json.loads(line)["prev"], sha256_hex(prev))
        res = self.log.verify()
        self.assertTrue(res.ok)
        self.assertEqual(res.count, 5)

    def test_tamper_is_detected(self):
        for i in range(4):
            self.log.append("approval", decision="deny", n=i)
        path = self.root / "audit.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[1] = lines[1].replace('"deny"', '"once"')
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        res = self.log.verify()
        self.assertFalse(res.ok)
        self.assertEqual(res.bad_line, 3)
        self.assertIn("line 2", res.reason)

    def test_removed_line_and_truncation_are_detected(self):
        for i in range(4):
            self.log.append("tool", n=i)
        path = self.root / "audit.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8")
        self.assertFalse(self.log.verify().ok)
        path.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")   # drop the last line
        res = self.log.verify()
        self.assertFalse(res.ok)
        self.assertIn("head", res.reason)

    def test_concurrent_appends_keep_the_chain(self):
        other = AuditLog(self.root / "audit.jsonl")  # a second writer (e.g. the CLI)
        threads = [threading.Thread(target=lambda lg=lg: [lg.append("x", i=i) for i in range(25)])
                   for lg in (self.log, other, self.log, other)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        res = self.log.verify()
        self.assertTrue(res.ok, res.reason)
        self.assertEqual(res.count, 100)

    def test_secrets_and_long_values_are_compacted(self):
        entry = self.log.append("tool", args={"api_key": "sk-123", "content": "x" * 5000})
        self.assertEqual(entry["args"]["api_key"], "***")
        self.assertEqual(entry["args"]["content"]["len"], 5000)
        self.assertNotIn("sk-123", (self.root / "audit.jsonl").read_text())


class UndoTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.app = make_app(self.root)
        self.home = self.app.paths.home
        (self.home / "docs").mkdir(parents=True)
        self.ctx = ctx_for(self.app, self.home / "docs")

    def tearDown(self):
        rmtree(self.root)

    def run_tool(self, name, args):
        res = self.app.registry.get(name).fn(self.ctx, args)
        ids = [self.app.undo.register(spec).id for spec in res.undo]
        return res, ids

    def test_create_then_undo_moves_to_trash(self):
        res, ids = self.run_tool("fs.write", {"path": "new.md", "content": "# hi\n"})
        self.assertTrue(res.verified)
        out = self.app.undo.undo(ids[0], "ru")
        self.assertTrue(out.ok, out.message)
        self.assertFalse((self.home / "docs" / "new.md").exists())
        self.assertTrue(any((self.app.paths.trash_dir / "files").iterdir()))
        self.assertTrue(any((self.app.paths.trash_dir / "info").glob("*.trashinfo")))

    def test_overwrite_undo_restores_previous_version(self):
        f = self.home / "docs" / "plan.md"
        f.write_text("v1\n")
        _, ids = self.run_tool("fs.write", {"path": "plan.md", "content": "v2\n"})
        self.assertEqual(f.read_text(), "v2\n")
        out = self.app.undo.undo(None, "ru")   # "undo last"
        self.assertTrue(out.ok, out.message)
        self.assertEqual(f.read_text(), "v1\n")
        self.assertIn("Отменил", out.message)
        again = self.app.undo.undo(ids[0], "ru")
        self.assertFalse(again.ok)

    def test_undo_refuses_to_clobber_user_edits(self):
        f = self.home / "docs" / "plan.md"
        f.write_text("v1\n")
        _, ids = self.run_tool("fs.write", {"path": "plan.md", "content": "v2\n"})
        f.write_text("user edit\n")
        out = self.app.undo.undo(ids[0], "ru")
        self.assertFalse(out.ok)
        self.assertIn("изменился", out.message)
        self.assertEqual(f.read_text(), "user edit\n")

    def test_move_and_trash_undo(self):
        (self.home / "docs" / "a.txt").write_text("A")
        _, ids = self.run_tool("fs.move", {"src": "a.txt", "dst": "b.txt"})
        self.assertTrue((self.home / "docs" / "b.txt").exists())
        self.assertTrue(self.app.undo.undo(ids[0], "en").ok)
        self.assertTrue((self.home / "docs" / "a.txt").exists())
        _, ids = self.run_tool("fs.trash", {"path": "a.txt"})
        self.assertFalse((self.home / "docs" / "a.txt").exists())
        self.assertTrue(self.app.undo.undo(ids[0], "en").ok)
        self.assertEqual((self.home / "docs" / "a.txt").read_text(), "A")

    def test_snapshot_undo_calls_sos(self):
        runner = FakeRunner(self.app.paths)
        undo = UndoLog(self.root / "actions.jsonl", Trash(self.root / "Trash"), SvoyaCli(runner, self.app.paths))
        from jackson.tools.base import UndoSpec
        a = undo.register(UndoSpec("snapshot", "снимок", {"id": "snap-7", "tool": "sos"}, auto=True))
        self.assertIsNone(undo.last())  # bookkeeping entries are not "the last action"
        self.assertTrue(undo.undo(a.id).ok)
        self.assertIn(["sos", "undo", "snap-7", "--yes"], runner.calls)

    def test_listing(self):
        self.run_tool("fs.write", {"path": "x.md", "content": "x"})
        items = self.app.undo.list()
        self.assertEqual(items[0].kind, "fs.create")
        self.assertTrue(items[0].id.startswith("a-"))


if __name__ == "__main__":
    unittest.main()
