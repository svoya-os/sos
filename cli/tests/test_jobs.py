import argparse
import datetime as dt
import json
import os

from svoya_cli import jobs, run

from .helpers import NOW, SandboxTest


class JobsTest(SandboxTest):
    def test_lifecycle(self):
        d = self.sb.path("/jobs")
        j = jobs.create(d, label="обучение", command=["python", "train.py"], cwd="/p", pid=os.getpid(), now=NOW, base="train")
        self.assertRegex(j["id"], r"^train-\d{4}$")
        self.assertEqual(jobs.load(d, j["id"])["state"], "running")
        jobs.update(d, j["id"], NOW, progress=0.25, message="эпоха 1/4")
        self.assertEqual(jobs.load(d, j["id"])["message"], "эпоха 1/4")
        jobs.finish(d, j["id"], NOW, 0)
        done = jobs.load(d, j["id"])
        self.assertEqual((done["state"], done["progress"], done["exitCode"]), ("done", 1.0, 0))
        self.assertEqual(jobs.for_status(d, NOW), [])

    def test_unique_ids_and_validation(self):
        d = self.sb.path("/jobs")
        a = jobs.create(d, label="x", command=[], cwd="/", pid=1, now=NOW, base="train")
        b = jobs.create(d, label="x", command=[], cwd="/", pid=1, now=NOW, base="train")
        self.assertNotEqual(a["id"], b["id"])
        with self.assertRaises(ValueError):
            jobs.job_path(d, "../etc/passwd")
        with self.assertRaises(ValueError):
            jobs.update(d, a["id"], NOW, progress=1.5)

    def test_dead_owner_is_not_running(self):
        d = self.sb.path("/jobs")
        jobs.create(d, label="x", command=[], cwd="/", pid=424242, now=NOW)
        self.assertEqual(jobs.running(d, NOW, check_pid=lambda p: False), [])
        self.assertEqual(len(jobs.running(d, NOW, check_pid=lambda p: True)), 1)

    def test_explicit_eta_ages(self):
        d = self.sb.path("/jobs")
        j = jobs.create(d, label="x", command=[], cwd="/", pid=os.getpid(), now=NOW)
        jobs.update(d, j["id"], NOW, etaSec=600)
        self.assertEqual(jobs.eta(jobs.load(d, j["id"]), NOW + dt.timedelta(seconds=100)), 500)

    def test_cleanup_old_finished(self):
        d = self.sb.path("/jobs")
        j = jobs.create(d, label="x", command=[], cwd="/", pid=1, now=NOW - dt.timedelta(days=3))
        jobs.finish(d, j["id"], NOW - dt.timedelta(days=2), 1)
        self.assertEqual(jobs.cleanup(d, NOW), 1)

    def test_default_labels(self):
        self.assertEqual(jobs.default_label("train.py"), "training")
        self.assertEqual(jobs.default_label("scripts/generate_video.py"), "generation")

    def test_job_cli(self):
        ctx = self.sb.ctx()
        j = jobs.create(ctx.paths.jobs_dir, label="x", command=[], cwd="/", pid=os.getpid(), now=NOW)
        ns = argparse.Namespace(job_cmd="progress", id=j["id"], progress=0.4, eta=90, message="m", label=None)
        self.assertEqual(run.main_job(ns, ctx), 0)
        data = json.loads(jobs.job_path(ctx.paths.jobs_dir, j["id"]).read_text())
        self.assertEqual((data["progress"], data["etaSec"], data["message"]), (0.4, 90, "m"))
        ns = argparse.Namespace(job_cmd="progress", id="nope", progress=0.4, eta=None, message=None, label=None)
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run.main_job(ns, ctx), 1)
