import argparse
import datetime as dt
import json
import os

from svoya_cli import jobs, status
from svoya_cli.util import write_json

from .helpers import NOW, FakeRunner, SandboxTest, capture, fixture

SCHEMA_GPU = {"index": int, "vendor": str, "name": str, "tempC": int, "vramUsedMiB": int, "vramTotalMiB": int,
              "util": int, "powerW": int, "driver": str, "ok": bool}


class StatusTest(SandboxTest):
    def nvidia_runner(self):
        return FakeRunner({"nvidia-smi --query-gpu": fixture("nvidia-smi/rtx4090.csv")}, available={"nvidia-smi"})

    def test_schema_matches_architecture_42(self):
        ctx = self.sb.ctx(self.nvidia_runner())
        j = jobs.create(ctx.paths.jobs_dir, label="обучение", command=["python", "train.py"], cwd="/tmp",
                        pid=os.getpid(), now=NOW - dt.timedelta(minutes=30), base="train")
        jobs.update(ctx.paths.jobs_dir, j["id"], NOW - dt.timedelta(minutes=10), progress=0.62)
        write_json(ctx.paths.cache_dir / "updates.json", {"available": 3, "security": 1, "checkedAt": "2026-09-24T18:00:00Z"})
        write_json(ctx.paths.cache_dir / "snapshots.json", {"last": "2026-09-24T18:02:11Z", "checkedAt": "2026-09-24T18:40:00Z"})
        write_json(ctx.paths.runtime_svoya / "ai.json", {"local": True, "cloudActiveSince": None})
        s = status.collect(ctx)
        self.assertEqual(set(s) - {"ts"}, {"gpu", "jobs", "ai", "updates", "snapshots"})
        g = s["gpu"][0]
        for k, t in SCHEMA_GPU.items():
            self.assertIsInstance(g[k], t, k)
        self.assertEqual((g["name"], g["vramUsedMiB"], g["driver"], g["ok"]), ("RTX 4090", 11468, "595.58", True))
        job = s["jobs"][0]
        self.assertEqual(set(job), {"id", "label", "progress", "etaSec"})
        self.assertEqual(job["label"], "обучение")
        self.assertAlmostEqual(job["progress"], 0.62)
        self.assertTrue(120 < job["etaSec"] < 150)   # 20 min for 62 % → 735 s left at that update, 600 s ago
        self.assertEqual(s["ai"], {"local": True, "cloudActiveSince": None, "enabled": True})
        self.assertEqual((s["updates"]["available"], s["updates"]["security"]), (3, 1))
        self.assertEqual(s["snapshots"]["last"], "2026-09-24T18:02:11Z")
        json.dumps(s)   # serialisable

    def test_graceful_without_anything(self):
        ctx = self.sb.ctx(FakeRunner())
        s = status.collect(ctx, background=False)
        self.assertEqual(s["jobs"], [])
        self.assertNotIn("gpu", s)
        self.assertNotIn("updates", s)

    def test_hot_gpu_and_doctor_failure_mark_not_ok(self):
        hot = fixture("nvidia-smi/rtx4090.csv").replace(", 64,", ", 93,")
        ctx = self.sb.ctx(FakeRunner({"nvidia-smi --query-gpu": hot}, available={"nvidia-smi"}))
        self.assertFalse(status.collect(ctx, background=False)["gpu"][0]["ok"])
        ctx = self.sb.ctx(self.nvidia_runner())
        write_json(ctx.paths.state_dir / "doctor.json", {"gpuOk": False})
        self.assertFalse(status.collect(ctx, background=False)["gpu"][0]["ok"])

    def test_nvidia_then_amd_indices(self):
        self.sb.amd_card("card1", "0000:03:00.0", 0x744C, vram_used=2**30, vram_total=24 * 2**30)
        s = status.collect(self.sb.ctx(self.nvidia_runner()), background=False)
        self.assertEqual([(g["index"], g["vendor"]) for g in s["gpu"]], [(0, "nvidia"), (1, "amd")])
        self.assertNotIn("card", s["gpu"][1])

    def test_stale_cache_spawns_one_refresh(self):
        r = FakeRunner()
        ctx = self.sb.ctx(r)
        status.collect(ctx)
        status.collect(ctx)
        refresh = [c for c in r.spawned if "--refresh-cache" in c]
        self.assertEqual(len(refresh), 1, "the backoff marker must prevent a second spawn")

    def test_fresh_cache_does_not_spawn(self):
        r = FakeRunner()
        ctx = self.sb.ctx(r)
        write_json(ctx.paths.cache_dir / "updates.json", {"available": 0, "security": 0, "checkedAt": "2026-09-24T18:40:00Z"})
        write_json(ctx.paths.cache_dir / "snapshots.json", {"last": None, "checkedAt": "2026-09-24T18:41:00Z"})
        status.collect(ctx)
        self.assertEqual(r.spawned, [])

    def test_refresh_cache_counts_updates(self):
        r = FakeRunner({"apt-get -s": fixture("apt/simulate.txt")}, available={"apt-get"})
        ctx = self.sb.ctx(r)
        status.refresh_cache(ctx)
        data = json.loads((ctx.paths.cache_dir / "updates.json").read_text())
        self.assertEqual((data["available"], data["security"]), (6, 2))

    def test_apt_check_is_preferred(self):
        self.sb.write("/usr/lib/update-notifier/apt-check", "", mode=0o755)
        path = str(self.sb.path("/usr/lib/update-notifier/apt-check"))
        r = FakeRunner({(path,): __import__("svoya_cli.runner", fromlist=["Result"]).Result(0, "", "12;4")})
        self.assertEqual(status.count_updates(self.sb.ctx(r)), {"available": 12, "security": 4})

    def test_main_json_and_write(self):
        ctx = self.sb.ctx(self.nvidia_runner())
        args = argparse.Namespace(json=True, write=True, watch=None, refresh_cache=False)
        rc, out = capture(status.main, args, ctx)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["gpu"][0]["name"], "RTX 4090")
        self.assertTrue(ctx.paths.status_json.exists())

    def test_history_snapshot_is_used_instantly(self):
        ctx = self.sb.ctx()
        write_json(ctx.paths.history_file, {"snapshots": [{"number": 50, "at": "2026-09-24T18:30:00Z"}]})
        write_json(ctx.paths.cache_dir / "snapshots.json", {"last": "2026-09-24T18:02:11Z", "checkedAt": "2026-09-24T18:40:00Z"})
        self.assertEqual(status.collect(ctx, background=False)["snapshots"]["last"], "2026-09-24T18:30:00Z")


class AiStateTest(SandboxTest):
    def test_ai_block_from_switch_and_spend_ledger(self):
        ctx = self.sb.ctx(FakeRunner())
        ctx.paths.user_config.parent.mkdir(parents=True)
        ctx.paths.user_config.write_text("[ai]\nenabled = true\n")
        today = NOW.astimezone().strftime("%Y-%m-%d")
        write_json(ctx.paths.data_home / "svoya/jackson/spend.json", {"version": 1, "days": {today: {"eur": 0.0421, "left": 3}}})
        write_json(ctx.paths.runtime_svoya / "ai.json", {"local": False, "cloudActiveSince": "2026-09-24T18:40:00Z"})
        ai = status.collect(ctx, background=False)["ai"]
        self.assertEqual(ai, {"local": False, "cloudActiveSince": "2026-09-24T18:40:00Z", "enabled": True,
                              "todayCostEur": 0.0421, "todayCloudRequests": 3})
