import argparse
import json
import os
import subprocess
import sys
import tomllib
import unittest
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

    def test_upsil_program(self):
        p, ctx = self.make("upsil", backend="cu126")
        for rel in ("main.upl", "prompts.upl", "tests/test_prompts.upl", "README.md", "pyproject.toml",
                    ".gitignore", ".env", "svoya.toml"):
            self.assertTrue((p / rel).is_file(), rel)
        for rel in ("src", "sky.yaml", "Containerfile", ".python-version", "notebooks"):
            self.assertFalse((p / rel).exists(), rel)       # not a Python project tree
        py = tomllib.loads((p / "pyproject.toml").read_text())
        self.assertEqual(py["project"]["dependencies"], [])  # torch only when `uv add torch`
        self.assertEqual(py["tool"]["uv"]["index"][0]["url"], "https://download.pytorch.org/whl/cu126")
        self.assertNotIn("build-system", py)                 # uv never builds or installs it
        man = tomllib.loads((p / "svoya.toml").read_text())
        self.assertEqual(man["run"]["entry"], "main.upl")
        self.assertEqual(man["project"]["template"], "upsil")
        for key in ("tracking", "cloud", "datasets", "models"):
            self.assertNotIn(key, man)
        self.assertEqual(man["run"]["model"], "—")          # UpsiL asks the server's model
        self.assertIn("UV_TORCH_BACKEND=cu126", (p / ".env").read_text())
        for rel in ("main.upl", "prompts.upl", "tests/test_prompts.upl", "README.md"):
            text = (p / rel).read_text()
            self.assertNotIn("{{", text, rel)
        self.assertIn("tts-finetune", (p / "main.upl").read_text())
        self.assertEqual(os.readlink(p / "models"), str(ctx.paths.ai_root))

    @unittest.skipUnless(run.upsil_home(), "UpsiL is not installed")
    def test_upsil_program_compiles_and_its_tests_pass(self):
        p, _ = self.make("upsil")
        env = dict(os.environ, UPSIL_LANG="en")
        r = subprocess.run([sys.executable, "-m", "upsil", "check", "main.upl", "prompts.upl"], cwd=p, env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, "-m", "upsil", "test"], cwd=p, env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("4 tests: 4 passed", r.stdout)

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

    def test_upsil_command(self):
        proj = self.sb.dir / "u"
        proj.mkdir()
        (proj / "svoya.toml").write_text("[run]\nentry = 'main.upl'\n")
        on_path = lambda n: f"/usr/bin/{n}" if n == "upsil" else None  # noqa: E731
        nowhere = lambda n: None  # noqa: E731
        shim = "/usr/lib/upsil/path"
        self.assertEqual(run.upsil_command("main.upl", ["a"], proj, on_path, shim), ["upsil", "run", "main.upl", "a"])
        self.assertEqual(run.upsil_command("main.upl", [], proj, nowhere, shim), [sys.executable, "-m", "upsil", "run", "main.upl"])
        self.assertIsNone(run.upsil_command("main.upl", [], proj, nowhere, None))
        (proj / ".venv/bin").mkdir(parents=True)
        (proj / ".venv/bin/python").write_text("")
        self.assertEqual(run.upsil_command("main.upl", [], proj, on_path, shim),
                         [str(proj / ".venv/bin/python"), "-m", "upsil", "run", "main.upl"])
        # without a way to put upsil on the venv's path, the system upsil runs it
        self.assertEqual(run.upsil_command("main.upl", [], proj, on_path, None), ["upsil", "run", "main.upl"])
        self.assertEqual(run.build_command("main.upl", [], None, on_path), ["upsil", "run", "main.upl"])

    def test_upsil_pythonpath_exposes_only_upsil(self):
        site = self.sb.dir / "site"
        (site / "upsil").mkdir(parents=True)
        (site / "upsil" / "__init__.py").write_text('__version__ = "0.3.0"\n')
        (site / "numpy").mkdir()
        self.assertEqual(run.upsil_version(site / "upsil"), "0.3.0")
        self.assertIsNone(run.upsil_version(None))
        cache = self.sb.dir / "cache"
        path = Path(run.upsil_pythonpath(site / "upsil", cache))
        self.assertEqual(sorted(x.name for x in path.iterdir()), ["upsil"])
        self.assertEqual((path / "upsil").resolve(), (site / "upsil").resolve())
        self.assertEqual(run.upsil_pythonpath(site / "upsil", cache), str(path))   # reused
        other = self.sb.dir / "other" / "upsil"
        other.mkdir(parents=True)
        self.assertEqual((Path(run.upsil_pythonpath(other, cache)) / "upsil").resolve(), other.resolve())

    def test_header_names_upsil(self):
        rows = run.header("main.upl", {}, (None, None), None, None, upsil="0.3.0")
        self.assertEqual([(strip_ansi(a), strip_ansi(b)) for a, b in rows], [("среда", "upsil 0.3.0")])
        rows = run.header("main.upl", {}, ("2.13", "CUDA 13.0"), None, None, upsil="0.3.0")
        self.assertEqual(strip_ansi(rows[0][1]), "upsil 0.3.0 · torch 2.13 · CUDA 13.0")


FAKE_UPSIL_MAIN = """import os, sys
import upsil
job = os.environ.get("SVOYA_JOB_FILE", "")
print("upsil", upsil.__version__, sys.argv[1:], "via", "shim" if "upsil-path" in upsil.__file__ else "site",
      "job" if job.endswith(".json") else "no-job")
"""


class RunEndToEndTest(SandboxTest):
    def run_upl(self, proj: Path, site: Path, *args: str):
        env = dict(self.sb.env(), PYTHONPATH=os.pathsep.join([str(REPO_ROOT / "cli"), str(site)]),
                   NO_COLOR="1", SVOYA_LANG="en", PATH="/usr/bin:/bin")
        return subprocess.run([sys.executable, "-m", "svoya_cli", "run", *args], cwd=proj, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_sos_run_upl(self):
        site = self.sb.dir / "site"
        (site / "upsil").mkdir(parents=True)
        (site / "upsil" / "__init__.py").write_text('__version__ = "0.3.0"\n')
        (site / "upsil" / "__main__.py").write_text(FAKE_UPSIL_MAIN)
        proj = self.sb.dir / "prog"
        proj.mkdir()
        (proj / "svoya.toml").write_text('[run]\nentry = "main.upl"\n')
        (proj / "main.upl").write_text('print("hi")\n')
        (proj / ".env").write_text("UPSIL_LLM_MODEL=qwen3.5-4b\n")
        r = self.run_upl(proj, site, "main.upl", "rust")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("› sos run main.upl rust", r.stdout)
        self.assertIn("env      upsil 0.3.0", r.stdout)
        self.assertIn("model    qwen3.5-4b", r.stdout)
        self.assertIn("upsil 0.3.0 ['run', 'main.upl', 'rust'] via", r.stdout)
        self.assertIn("job", r.stdout.split("['run', 'main.upl', 'rust'] via")[1])
        # with a project venv the program runs there, seeing upsil through a folder that holds only it
        (proj / ".venv/bin").mkdir(parents=True)
        (proj / ".venv/bin/python").symlink_to(sys.executable)
        r = self.run_upl(proj, site, "--no-job", "main.upl")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("upsil 0.3.0 ['run', 'main.upl'] via shim no-job", r.stdout)

    def test_sos_run_upl_without_upsil(self):
        proj = self.sb.dir / "prog"
        proj.mkdir()
        (proj / "main.upl").write_text('print("hi")\n')
        r = self.run_upl(proj, self.sb.dir / "empty", "main.upl")
        if run.upsil_home() is not None or subprocess.run(["which", "upsil"], capture_output=True).returncode == 0:
            self.skipTest("UpsiL is installed here")
        self.assertEqual(r.returncode, 127, r.stderr + r.stdout)
        self.assertIn("UpsiL is not installed: sudo apt install upsil", r.stderr)

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
