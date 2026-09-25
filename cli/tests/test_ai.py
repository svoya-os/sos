"""`sos ai off|on|status` — the AI switch (design/WORKFLOWS.md §8)."""
import argparse
import contextlib
import io
import json

from svoya_cli import ai, session, status
from svoya_cli.models import cli as models_cli

from .helpers import FakeRunner, Result, SandboxTest, capture


def show(states: dict[str, str | None]) -> str:
    """Fake `systemctl show -p Id,LoadState,ActiveState …` output; None = unit not installed."""
    blocks = []
    for unit, active in states.items():
        blocks.append(f"Id={unit}\nLoadState={'loaded' if active else 'not-found'}\nActiveState={active or 'inactive'}")
    return "\n\n".join(blocks) + "\n"


def args(cmd, **kw):
    base = dict(ai_cmd=cmd, json=False, system=False, dry_run=False, root_only=False)
    base.update(kw)
    return argparse.Namespace(**base)


class AiSwitchTest(SandboxTest):
    def runner(self, user_states, system_states=None, **extra):
        responses = {"systemctl --user show": show(user_states), "systemctl show": show(system_states or {}),
                     "systemctl --user stop": Result(0), "systemctl --user start": Result(0), "kill": Result(0),
                     "systemctl stop": Result(0), "systemctl start": Result(0), "pkexec": Result(0)}
        responses.update(extra)
        return FakeRunner(responses, available={"systemctl", "pkexec"})

    def stray_server(self, pid=4242, uid=1000, name="llama-server"):
        self.sb.write(f"/proc/{pid}/comm", name + "\n")
        self.sb.write(f"/proc/{pid}/status", f"Name:\t{name}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")

    def test_off_stops_everything_and_on_brings_it_back(self):
        states = {"jacksond.service": "active", "svoya-llm.service": "active", "llama-swap.service": None,
                  "llama-server.service": None, "ollama.service": "inactive"}
        r = self.runner(states)
        ctx = self.sb.ctx(r)
        self.stray_server(4242)
        self.stray_server(4243, uid=0)                                     # someone else's: not ours to stop
        self.assertEqual(ai.main(args("off"), ctx), 0)
        self.assertTrue((self.sb.home / ".config/svoya/ai.off").exists())
        self.assertTrue(r.called("systemctl", "--user", "stop", "jacksond.service"))
        self.assertTrue(r.called("systemctl", "--user", "stop", "svoya-llm.service"))
        self.assertFalse(r.called("systemctl", "--user", "stop", "ollama.service"))    # was not running
        self.assertTrue(r.called("kill", "-TERM", "4242"))
        self.assertFalse(r.called("kill", "-TERM", "4243"))
        self.assertIn("AI off", self.output())
        # everyone sees it
        self.assertFalse(ai.enabled(ctx))
        self.assertEqual(status.collect(ctx, background=False)["ai"]["enabled"], False)
        self.assertEqual(status.collect(ctx, background=False)["ai"]["off"], "user")
        steps = {s["step"]: s for s in session.start(self.sb.ctx(FakeRunner(available={"systemctl"}),
                                                                 SVOYA_SHELL_DIR=str(self.sb.dir / "sh")))}
        self.assertIn("AI off", steps["jacksond"]["detail"])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            serve = argparse.Namespace(port=18080, status=False, stop=False, json=False, foreground=False, dry_run=False)
            self.assertEqual(models_cli.cmd_serve(serve, ctx), 3)
        self.assertIn("AI is switched off", err.getvalue())
        # on: jacksond + exactly what was stopped
        stopped_states = dict(states, **{"jacksond.service": "inactive", "svoya-llm.service": "inactive"})
        r2 = self.runner(stopped_states)
        ctx2 = self.sb.ctx(r2)
        self.assertEqual(ai.main(args("on"), ctx2), 0)
        self.assertFalse((self.sb.home / ".config/svoya/ai.off").exists())
        self.assertTrue(r2.called("systemctl", "--user", "start", "--no-block", "jacksond.service"))
        self.assertTrue(r2.called("systemctl", "--user", "start", "--no-block", "svoya-llm.service"))
        self.assertFalse(r2.called("systemctl", "--user", "start", "--no-block", "ollama.service"))
        self.assertTrue(ai.enabled(ctx2))
        self.assertTrue(status.collect(ctx2, background=False)["ai"]["enabled"])

    def test_status_json(self):
        r = self.runner({"jacksond.service": "active", "svoya-llm.service": None, "llama-swap.service": None,
                         "llama-server.service": None, "ollama.service": None},
                        {"svoya-ollama.service": "active", "ollama.service": None, "llama-swap.service": None})
        rc, out = capture(ai.main, args("status", json=True), self.sb.ctx(r))
        data = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertEqual((data["enabled"], data["off"], data["since"]), (True, None, None))
        self.assertEqual(data["services"], [{"unit": "jacksond.service", "scope": "user", "active": True},
                                            {"unit": "svoya-ollama.service", "scope": "system", "active": True}])

    def test_system_switch(self):
        r = self.runner({"jacksond.service": "inactive"}, {"svoya-ollama.service": "active"})
        ctx = self.sb.ctx(r)
        self.assertEqual(ai.main(args("off", system=True), ctx), 0)
        call = next(c for c in r.calls if c[0] == "pkexec")
        self.assertEqual(call[-5:], ["ai", "off", "--system", "--root-only", "--json"])
        # the root half (what pkexec runs): /etc marker + system units
        root = self.sb.ctx(r, uid=0)
        rc, out = capture(ai.main, args("off", system=True, root_only=True, json=True), root)
        self.assertEqual(rc, 0)
        self.assertTrue(self.sb.path("/etc/svoya/ai.off").exists())
        self.assertTrue(r.called("systemctl", "stop", "svoya-ollama.service"))
        self.assertEqual(ai.off_reason(ctx), "system")
        # a user cannot switch it back on alone
        self.assertEqual(ai.main(args("on"), self.sb.ctx(self.runner({}))), 1)
        self.assertIn("stays off for everyone", self.output())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ai.main(args("off", root_only=True), ctx), 2)            # root half refuses users
        r_on = self.runner({}, {"svoya-ollama.service": "inactive"})
        rc, _ = capture(ai.main, args("on", system=True, root_only=True, json=True), self.sb.ctx(r_on, uid=0))
        self.assertFalse(self.sb.path("/etc/svoya/ai.off").exists())
        self.assertTrue(r_on.called("systemctl", "start", "--no-block", "svoya-ollama.service"))

    def test_config_switch_and_dry_run(self):
        (self.sb.home / ".config/svoya").mkdir(parents=True)
        (self.sb.home / ".config/svoya/svoya.toml").write_text("[ai]\nenabled = false\n")
        ctx = self.sb.ctx(self.runner({}))
        self.assertEqual(ai.off_reason(ctx), "config")
        ai.main(args("on"), ctx)
        self.assertTrue(ai.enabled(ctx))
        dry = self.sb.ctx(self.runner({"jacksond.service": "active"}), dry_run=True)
        ai.main(args("off", dry_run=True), dry)
        self.assertFalse((self.sb.home / ".config/svoya/ai.off").exists())
        self.assertIn(["systemctl", "--user", "stop", "jacksond.service"], dry.runner.planned)


if __name__ == "__main__":
    import unittest
    unittest.main()
