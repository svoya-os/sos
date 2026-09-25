import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from svoya_cli import i18n, new, run
from svoya_cli.paths import REPO_ROOT
from svoya_cli.util import write_json

from .helpers import FakeRunner, SandboxTest, strip_ansi


class NewTest(SandboxTest):
    def make(self, template: str, backend: str = "cu130"):
        ctx = self.sb.ctx(FakeRunner())
        write_json(ctx.paths.state_dir / "doctor.json", {"torchBackend": backend})
        args = argparse.Namespace(name="tts-finetune", template=template, dir=str(self.sb.dir), no_git=True, json=False)
        self.assertEqual(new.main(args, ctx), 0)
        return self.sb.dir / "tts-finetune", ctx

    def test_torch_project(self):
        p, ctx = self.make("torch")
        for rel in ("pyproject.toml", "svoya.toml", "README.md", ".gitignore", ".python-version", ".env", ".envrc",
                    "src/tts_finetune/__init__.py", "src/tts_finetune/train.py", "src/tts_finetune/sos_progress.py",
                    "tests/test_smoke.py", "notebooks/explore.py", "configs/default.toml", "scripts/setup.sh",
                    ".devcontainer/devcontainer.json", "Containerfile", "sky.yaml"):
            self.assertTrue((p / rel).is_file(), rel)
        py = tomllib.loads((p / "pyproject.toml").read_text())
        self.assertEqual(py["project"]["name"], "tts-finetune")
        self.assertIn("torch", py["project"]["dependencies"])
        self.assertEqual(py["tool"]["uv"]["index"][0]["url"], "https://download.pytorch.org/whl/cu130")
        self.assertTrue(py["tool"]["uv"]["index"][0]["explicit"])
        self.assertEqual(py["tool"]["uv"]["sources"]["torch"], [{"index": "pytorch-cu130"}])
        man = tomllib.loads((p / "svoya.toml").read_text())
        self.assertEqual((man["gpu"]["backend"], man["gpu"]["required"]), ("cu130", "optional"))
        self.assertEqual(man["tracking"]["tool"], "trackio")
        self.assertIn("UV_TORCH_BACKEND=cu130", (p / ".env").read_text())
        dc = json.loads((p / ".devcontainer/devcontainer.json").read_text())
        self.assertEqual(dc["hostRequirements"]["gpu"], "optional")
        self.assertEqual(os.readlink(p / "data"), f"{ctx.paths.ai_root}/datasets")
        self.assertEqual(os.readlink(p / "models"), str(ctx.paths.ai_root))
        compile(( p / "src/tts_finetune/train.py").read_text(), "train.py", "exec")

    def test_legacy_gpu_gets_cu126_and_rocm_index(self):
        p, _ = self.make("llm-finetune", backend="cu126")
        py = tomllib.loads((p / "pyproject.toml").read_text())
        self.assertEqual(py["tool"]["uv"]["index"][0]["url"], "https://download.pytorch.org/whl/cu126")
        self.assertIn("trl>=1.13", py["project"]["dependencies"])
        tomllib.loads((p / "configs/sft.toml").read_text())
        self.assertEqual(new.index_url("rocm7.2"), "https://download.pytorch.org/whl/rocm7.2")

    def test_comfy_node_and_agent(self):
        p, _ = self.make("comfy-node")
        self.assertTrue((p / "__init__.py").is_file() and (p / "nodes.py").is_file())
        py = tomllib.loads((p / "pyproject.toml").read_text())
        self.assertEqual(py["tool"]["comfy"]["DisplayName"], "tts-finetune")
        self.assertEqual(py["project"]["dependencies"], [])
        compile((p / "nodes.py").read_text(), "nodes.py", "exec")
        sb2 = self.sb.dir / "agent"
        sb2.mkdir()
        ctx = self.sb.ctx(FakeRunner())
        args = argparse.Namespace(name="helper", template="agent", dir=str(sb2), no_git=True, json=False)
        self.assertEqual(new.main(args, ctx), 0)
        compile((sb2 / "helper/src/helper/agent.py").read_text(), "agent.py", "exec")

    def test_refuses_non_empty_dir_and_bad_names(self):
        (self.sb.dir / "x").mkdir()
        (self.sb.dir / "x" / "f").write_text("")
        import contextlib
        import io
        ctx = self.sb.ctx(FakeRunner())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(new.main(argparse.Namespace(name="x", template="torch", dir=str(self.sb.dir), no_git=True, json=False), ctx), 2)
            self.assertEqual(new.main(argparse.Namespace(name="../evil", template="torch", dir=str(self.sb.dir), no_git=True, json=False), ctx), 2)
        self.assertEqual(new.package_name("2d-diffusion"), "p_2d_diffusion")


class RunHeaderTest(SandboxTest):
    lang = "ru"

    def test_header_like_the_mockup(self):
        manifest = {"run": {"model": "qwen3-tts-0.6b", "adapter": "LoRA r16", "dataset": "ru-voice"},
                    "datasets": [{"name": "ru-voice", "examples": 48213}],
                    "tracking": {"tool": "trackio", "url": "http://localhost:7860"}}
        rows = run.header("train.py", manifest, ("2.13", "CUDA 13.0"), {"name": "RTX 4090", "vramTotalMiB": 24564})
        text = [(strip_ansi(a), strip_ansi(b)) for a, b in rows]
        self.assertEqual(text, [
            ("среда", "torch 2.13 · CUDA 13.0 · RTX 4090 24 ГБ"),
            ("модель", "qwen3-tts-0.6b + LoRA r16"),
            ("данные", f"ru-voice · 48{i18n.NNBSP}213 примеров"),
            ("трекинг", "localhost:7860 (trackio)"),
        ])

    def test_torch_info_from_dist_info(self):
        proj = self.sb.dir / "p"
        (proj / ".venv/lib/python3.12/site-packages/torch-2.13.0+cu130.dist-info").mkdir(parents=True)
        self.assertEqual(run.torch_info(proj), ("2.13", "CUDA 13.0"))
        proj2 = self.sb.dir / "q"
        (proj2 / ".venv/lib/python3.12/site-packages/torch-2.10.1+rocm7.2.dist-info").mkdir(parents=True)
        self.assertEqual(run.torch_info(proj2), ("2.10", "ROCm 7.2"))
        self.assertEqual(run.torch_info(self.sb.dir / "none"), (None, None))

    def test_build_command(self):
        proj = self.sb.dir / "p"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname='p'\n")
        which = lambda n: f"/usr/bin/{n}" if n in ("uv", "python3") else None  # noqa: E731
        self.assertEqual(run.build_command("train.py", ["--x"], proj, which), ["uv", "run", "python", "train.py", "--x"])
        self.assertEqual(run.build_command("go.sh", [], proj, which), ["bash", "go.sh"])
        self.assertEqual(run.build_command("train.py", [], None, which), ["python3", "train.py"])


class RunEndToEndTest(SandboxTest):
    def test_sos_run_registers_a_job_and_reports_progress(self):
        proj = self.sb.dir / "proj"
        proj.mkdir()
        (proj / "svoya.toml").write_text('[run]\nmodel = "m"\n[gpu]\nbackend = "cu126"\n')
        (proj / "go.py").write_text(
            "import os, subprocess, sys\n"
            "assert os.environ['UV_TORCH_BACKEND'] == 'cu126'\n"
            "subprocess.run([sys.executable, '-m', 'svoya_cli', 'job', 'progress', os.environ['SVOYA_JOB_ID'], '0.5'], check=True)\n"
            "print('ok')\n")
        env = dict(self.sb.env(), PYTHONPATH=str(REPO_ROOT / "cli"), NO_COLOR="1", SVOYA_LANG="en")
        r = subprocess.run([sys.executable, "-m", "svoya_cli", "run", "go.py"], cwd=proj, env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("› sos run go.py", r.stdout)
        self.assertIn("model    m", r.stdout)
        jobs_dir = Path(env["HOME"]) / ".local/state/svoya/jobs"
        job = json.loads(next(jobs_dir.glob("go-*.json")).read_text())
        self.assertEqual((job["state"], job["exitCode"], job["progress"]), ("done", 0, 1.0))
