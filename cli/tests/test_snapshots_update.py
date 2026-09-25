import argparse
import json

from svoya_cli import update
from svoya_cli.runner import Result
from svoya_cli.snapshots import Guard, Snapper, parse_info_xml, parse_snapper_json

from .helpers import FakeRunner, SandboxTest, capture, fixture


class SnapperTest(SandboxTest):
    def runner(self, **extra):
        table = {"snapper --utc --jsonout": fixture("snapper/list.json")}
        table.update(extra)
        return FakeRunner(table, available={"snapper"})

    def test_parse_json(self):
        snaps = parse_snapper_json(fixture("snapper/list.json"))
        self.assertEqual([s.number for s in snaps], [1, 41, 42, 43, 44])      # 0 = "current" is not a snapshot
        s42 = snaps[2]
        self.assertEqual((s42.type, s42.pre_number, s42.is_svoya), ("post", 41, True))
        self.assertEqual(s42.date.isoformat(), "2026-09-24T18:02:11+00:00")

    def test_info_xml_fallback(self):
        s = parse_info_xml("<?xml version=\"1.0\"?><snapshot><type>post</type><num>12</num><date>2026-09-24 10:00:00</date>"
                           "<pre_num>11</pre_num><description>sos: update</description>"
                           "<userdata><key>svoya</key><value>1</value></userdata></snapshot>")
        self.assertEqual((s.number, s.pre_number, s.userdata, s.is_svoya), (12, 11, {"svoya": "1"}, True))

    def test_pairs_and_last(self):
        self.sb.write("/etc/snapper/configs/root", "")
        sn = Snapper(self.sb.ctx(self.runner()))
        self.assertTrue(sn.available())
        pairs = sn.pairs()
        self.assertEqual([(p.number, q.number) for p, q in pairs], [(41, 42)])     # only sos pairs
        self.assertEqual(len(sn.pairs(svoya_only=False)), 2)
        self.assertEqual(sn.last_date().isoformat(), "2026-09-24T18:11:00+00:00")

    def test_guard_creates_pre_post_and_history(self):
        self.sb.write("/etc/snapper/configs/root", "")
        numbers = iter(["50\n", "51\n"])
        r = self.runner(**{"snapper -c root create": lambda argv: Result(0, next(numbers))})
        ctx = self.sb.ctx(r, uid=0)
        with Guard(ctx, "sos: test") as g:
            pass
        self.assertEqual((g.pre, g.post), (50, 51))
        create = [c for c in r.calls if "create" in c]
        self.assertIn("--cleanup-algorithm", create[0])
        self.assertEqual(create[0][create[0].index("--cleanup-algorithm") + 1], "number")
        self.assertEqual(create[1][create[1].index("--pre-number") + 1], "50")
        hist = json.loads(ctx.paths.history_file.read_text())
        self.assertEqual([h["number"] for h in hist["snapshots"]], [50, 51])

    def test_guard_without_snapper_says_why(self):
        with Guard(self.sb.ctx(FakeRunner()), "sos: test") as g:
            pass
        self.assertIsNone(g.pre)
        self.assertIn("snapper", g.reason)


class UpdateTest(SandboxTest):
    def test_parse_simulation(self):
        plan = update.parse_simulation(fixture("apt/simulate.txt"))
        self.assertEqual((plan["count"], plan["security"]), (6, 2))
        self.assertEqual(plan["kernels"], ["6.17.0-10-generic"])
        self.assertIn("nvidia-driver-595-open", plan["nvidia"])
        self.assertEqual(plan["removed"], ["oldthing"])

    def test_update_dry_run_json(self):
        r = FakeRunner({"apt-get -s": fixture("apt/simulate.txt")}, available={"apt-get", "flatpak"}, dry_run=True)
        ctx = self.sb.ctx(r, dry_run=True)
        args = argparse.Namespace(yes=False, json=True, no_flatpak=False)
        rc, out = capture(update.main_update, args, ctx)
        data = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertEqual(data["plan"]["count"], 6)
        self.assertFalse(r.called("apt-get", "update"))                # dry run: lists untouched

    def test_undo_list_and_dry_run(self):
        self.sb.write("/etc/snapper/configs/root", "")
        r = FakeRunner({"snapper --utc --jsonout": fixture("snapper/list.json"),
                        "snapper -c root status 41..42": "+..... /usr/bin/llama-server\nc..... /var/lib/svoya/modules.json\n"},
                       available={"snapper"}, dry_run=True)
        ctx = self.sb.ctx(r, dry_run=True)
        rc, out = capture(update.main_undo, argparse.Namespace(list=True, json=True, n=None, yes=False), ctx)
        self.assertEqual(json.loads(out)[0]["pre"], 41)
        rc = update.main_undo(argparse.Namespace(list=False, json=False, n=41, yes=False), ctx)
        self.assertEqual(rc, 0)
        self.assertIn("undochange 41..42", self.output())
        self.assertFalse(r.called("snapper", "-c", "root", "undochange"))

    def test_undo_unknown_number(self):
        self.sb.write("/etc/snapper/configs/root", "")
        r = FakeRunner({"snapper --utc --jsonout": fixture("snapper/list.json")}, available={"snapper"})
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            rc = update.main_undo(argparse.Namespace(list=False, json=False, n=7, yes=True), self.sb.ctx(r))
        self.assertEqual(rc, 2)


class JacksonContractTest(SandboxTest):
    """What jackson/jackson/svoya.py relies on: snapshot create --reason --json → {"id"}, undo <id>."""

    def test_snapshot_create_reason_json(self):
        from svoya_cli import snapshots
        self.sb.write("/etc/snapper/configs/home", "")
        r = FakeRunner({"snapper -c home create": Result(0, "77\n"), "snapper --utc --jsonout": fixture("snapper/list.json")},
                       available={"snapper"})
        args = argparse.Namespace(snapshot_cmd="create", description="jackson: edit notes", config="home", json=True)
        rc, out = capture(snapshots.main, args, self.sb.ctx(r))
        data = json.loads(out)
        self.assertEqual((rc, data["id"], data["config"]), (0, "77", "home"))
        self.assertEqual(data["description"], "sos: jackson: edit notes")
        rc, out = capture(snapshots.main, args, self.sb.ctx(FakeRunner()))
        self.assertEqual(rc, 2)
        self.assertIsNone(json.loads(out)["id"])

    def test_undo_single_snapshot_needs_yes_when_not_interactive(self):
        import contextlib
        import io
        self.sb.write("/etc/snapper/configs/root", "")
        listing = json.loads(fixture("snapper/list.json"))
        listing["root"].append({"number": 45, "type": "single", "pre-number": None, "date": "2026-09-24 18:30:00",
                                "description": "sos: jackson: edit notes", "userdata": {"svoya": "1"}, "cleanup": "number"})
        numbers = iter(["46\n", "47\n"])
        r = FakeRunner({"snapper --utc --jsonout": json.dumps(listing), "snapper -c root status": "c... /home/x\n",
                        "snapper -c root create": lambda argv: Result(0, next(numbers)),
                        "snapper -c root undochange": Result(0)}, available={"snapper"})
        ctx = self.sb.ctx(r)
        with contextlib.redirect_stderr(io.StringIO()):
            rc = update.main_undo(argparse.Namespace(list=False, json=False, n=None, yes=False, config="root"), ctx)
        self.assertEqual(rc, 3)                                             # stdin is not a TTY in tests
        rc = update.main_undo(argparse.Namespace(list=False, json=False, n=None, yes=True, config="root"), ctx)
        self.assertEqual(rc, 0)
        self.assertTrue(r.called("snapper", "-c", "root", "undochange", "45..0"))   # newest change: the single one
