"""The night rule (night.py) and the quiet graphics card (hw/quiet.py)."""
import argparse
import datetime as dt
import json

from svoya_cli import commands, night
from svoya_cli import run as run_mod
from svoya_cli.hw import quiet
from svoya_cli.models import cli as mcli
from svoya_cli.runner import Result

from .helpers import FakeRunner, SandboxTest, capture

ALWAYS_NIGHT = '[night]\nhours = "00:00-23:59"\n'      # whatever the time zone of the test machine


class NightRulesTest(SandboxTest):
    def test_hours(self):
        self.assertEqual(night.parse_hours("23:00-07:00"), (dt.time(23), dt.time(7)))
        self.assertEqual(night.parse_hours(" 1:30 - 6:05 "), (dt.time(1, 30), dt.time(6, 5)))
        for off in ("", "off", "25:00-07:00", "07:00-07:00", None):
            self.assertIsNone(night.parse_hours(off))
        self.assertEqual(night.hours({}), (dt.time(23), dt.time(7)))           # on by default
        self.assertIsNone(night.hours({"night": {"hours": ""}}))

    def test_is_night_and_the_morning(self):
        span = (dt.time(23), dt.time(7))
        at = lambda h, m=0: dt.datetime(2026, 11, 6, h, m)                   # noqa: E731
        self.assertTrue(night.is_night(at(23, 30), span))
        self.assertTrue(night.is_night(at(3), span))
        self.assertFalse(night.is_night(at(7), span))
        self.assertFalse(night.is_night(at(22, 59), span))
        self.assertEqual(night.morning(at(23, 30), span), dt.datetime(2026, 11, 7, 7))
        self.assertEqual(night.morning(at(3), span), dt.datetime(2026, 11, 6, 7))
        day = (dt.time(1), dt.time(5))                                         # a night inside one day
        self.assertTrue(night.is_night(at(2), day))
        self.assertFalse(night.is_night(at(23), day))
        self.assertFalse(night.is_night(at(3), None))

    def test_who_waits(self):
        self.sb.write("/etc/svoya/svoya.toml", ALWAYS_NIGHT)
        ctx = self.sb.ctx(FakeRunner())
        from svoya_cli import config
        cfg = config.load(ctx.paths)
        self.assertIsNotNone(night.should_wait(ctx, cfg, now=False, attended=False))   # nobody at the keyboard
        self.assertIsNone(night.should_wait(ctx, cfg, now=False, attended=True))       # you are here
        self.assertIsNone(night.should_wait(ctx, cfg, now=True, attended=False))       # --now
        self.assertIsNone(night.should_wait(ctx, {"night": {"hours": "off"}}, now=False, attended=False))

    def test_put_off_with_a_user_timer(self):
        r = FakeRunner({"systemd-run": ""}, available={"systemd-run"})
        ctx = self.sb.ctx(r, LANG="ru_RU.UTF-8")
        when = dt.datetime(2026, 11, 7, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        res = night.put_off(ctx, ["run", "--now", "train.py", "--epochs", "3"], when, "train.py", self.sb.home)
        self.assertTrue(res["ok"])
        argv = r.calls[-1]
        self.assertEqual(argv[:2], ["systemd-run", "--user"])
        self.assertIn("--on-calendar=2026-11-07 07:00:00", argv)
        self.assertIn("--timer-property=Persistent=true", argv)                 # a sleeping laptop catches up
        self.assertIn(f"--working-directory={self.sb.home}", argv)
        self.assertIn("--setenv=LANG=ru_RU.UTF-8", argv)
        self.assertEqual(argv[argv.index("--") + 1:][-5:], ["run", "--now", "train.py", "--epochs", "3"])
        self.assertTrue(res["unit"].startswith("sos-later-train-py-"))
        failed = night.put_off(self.sb.ctx(FakeRunner()), ["run", "--now", "x.py"], when, "x.py")
        self.assertFalse(failed["ok"])                                          # no systemd-run here


class NightCommandsTest(SandboxTest):
    def setUp(self):
        super().setUp()
        self.sb.write("/etc/svoya/svoya.toml", ALWAYS_NIGHT)
        self._interactive = night.interactive
        night.interactive = lambda: False                                       # as Jackson or a timer

    def tearDown(self):
        night.interactive = self._interactive
        super().tearDown()

    def test_run_waits_for_the_morning(self):
        r = FakeRunner({"systemd-run": ""}, available={"systemd-run"})
        ctx = self.sb.ctx(r)
        args = argparse.Namespace(script="train.py", args=["--lr", "1e-4"], label=None, no_job=False,
                                  no_header=False, now=False)
        rc, out = capture(run_mod.main, args, ctx)
        self.assertEqual(rc, 0)
        cmd = r.calls[-1][r.calls[-1].index("--") + 1:]
        self.assertEqual(cmd[-5:], ["run", "--now", "train.py", "--lr", "1e-4"])   # --now before the script
        said = self.output()
        self.assertIn("--now", said)
        self.assertIn(".timer", said)
        self.assertFalse(any(ctx.paths.jobs_dir.glob("*.json")) if ctx.paths.jobs_dir.exists() else False)

    def test_a_big_download_waits_and_says_so_in_json(self):
        self.sb.write("/proc/meminfo", "MemTotal: 33554432 kB\nMemAvailable: 30000000 kB\n")
        self.sb.mkdir("/srv/ai")
        r = FakeRunner({"systemd-run": ""}, available={"systemd-run"})
        ctx = self.sb.ctx(r)
        args = argparse.Namespace(repo="qwen3.5-9b:Q4_K_M", files=[], revision="main", include=[], ctx=8192, yes=True,
                                  accept_license=False, allow_uncensored=False, now=False, dry_run=False, json=True)
        rc, out = capture(mcli.cmd_pull, args, ctx)
        events = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(rc, 0)
        self.assertEqual([e["event"] for e in events], ["plan", "scheduled", "done"])
        self.assertTrue(events[-1]["scheduled"])
        cmd = r.calls[-1][r.calls[-1].index("--") + 1:]
        self.assertEqual(cmd[-5:], ["models", "pull", "qwen3.5-9b:Q4_K_M", "--yes", "--now"])


NVSMI = "0, NVIDIA GeForce RTX 4070, 200.00, 200.00, 100.00, 220.00\n"
Q = ("nvidia-smi", "--query-gpu=index,name,power.limit,power.default_limit,power.min_limit,power.max_limit")


class QuietTest(SandboxTest):
    def test_reading_and_the_target(self):
        g = quiet.parse_nvidia(NVSMI + "1, Tesla, [N/A], [N/A], [N/A], [N/A]\n")
        self.assertEqual(g[0]["name"], "RTX 4070")
        self.assertEqual((g[0]["limit"], g[0]["default"], g[0]["min"]), (200.0, 200.0, 100.0))
        self.assertIsNone(g[1]["limit"])
        self.assertEqual(quiet.target(g[0], True), 140)
        self.assertEqual(quiet.target(g[0], True, 40), 100)                     # never below the card's minimum
        self.assertEqual(quiet.target(g[0], False), 200)

    def test_status_lists_cards_that_can_do_it(self):
        ctx = self.sb.ctx(FakeRunner({Q: NVSMI.replace("200.00, 200.00", "140.00, 200.00")}, available={"nvidia-smi"}))
        rc, out = capture(quiet.main, argparse.Namespace(state="status", percent=70, json=True, root_only=False), ctx)
        card = json.loads(out)["cards"][0]
        self.assertEqual((rc, card["quiet"], card["limitW"]), (0, True, 140.0))

    def test_on_asks_polkit_for_the_exact_command(self):
        answer = json.dumps({"cards": [{"vendor": "nvidia", "name": "RTX 4070", "limitW": 200.0, "defaultW": 200.0,
                                        "setW": 140, "ok": True}]})
        r = FakeRunner({Q: NVSMI, "pkexec": Result(0, answer, "")}, available={"nvidia-smi", "pkexec"})
        rc, out = capture(quiet.main, argparse.Namespace(state="on", percent=70, json=False, root_only=False),
                          self.sb.ctx(r))
        self.assertEqual(rc, 0)
        pk = next(c for c in r.calls if c[0] == "pkexec")
        self.assertEqual(pk[-5:], ["quiet", "on", "--percent", "70", "--root-only"])
        self.assertIn("140", self.output())

    def test_root_sets_nvidia_and_amd(self):
        hw = "/sys/class/drm/card1/device/hwmon/hwmon3"
        self.sb.write("/sys/class/drm/card1/device/vendor", "0x1002\n")
        self.sb.write("/sys/class/drm/card1/device/device", "0x744c\n")
        for name, uw in (("power1_cap", 300_000_000), ("power1_cap_default", 300_000_000),
                         ("power1_cap_min", 150_000_000), ("power1_cap_max", 330_000_000)):
            self.sb.write(f"{hw}/{name}", f"{uw}\n")
        r = FakeRunner({Q: NVSMI, "nvidia-smi -i": ""}, available={"nvidia-smi"})
        ctx = self.sb.ctx(r, uid=0)
        rc, out = capture(quiet.main, argparse.Namespace(state="on", percent=70, json=False, root_only=True), ctx)
        self.assertEqual(rc, 0)
        self.assertIn(["nvidia-smi", "-i", "0", "-pl", "140"], r.calls)
        self.assertEqual(self.sb.path(f"{hw}/power1_cap").read_text(), "210000000")
        done = json.loads(out)["cards"]
        self.assertEqual([d["setW"] for d in done], [140, 210])

    def test_no_card_that_can(self):
        rc, out = capture(quiet.main, argparse.Namespace(state="on", percent=70, json=False, root_only=False),
                          self.sb.ctx(FakeRunner()))
        self.assertEqual(rc, 2)

    def test_words(self):
        self.assertEqual(commands.normalize(["тихо", "вкл"]), ["quiet", "on"])
        self.assertEqual(commands.normalize(["gpu", "quiet", "off"]), ["quiet", "off"])
        self.assertEqual(commands.normalize(["видеокарта", "тихо"]), ["quiet"])
        self.assertEqual(commands.normalize(["gpu"]), ["doctor", "--gpu"])
