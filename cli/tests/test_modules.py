import argparse
import json
import os
import subprocess

from svoya_cli import modules as M
from svoya_cli.paths import REPO_ROOT
from svoya_cli.runner import Result

from .helpers import FakeRunner, SandboxTest, capture, fixture

MODDIR = REPO_ROOT / "modules"
EXPECTED = {"base-ai", "nvidia", "cuda-devel", "rocm", "llm-local", "studio", "voice", "ml-lab", "agents", "dev",
            "cloud-burst", "codecs", "gaming", "notes", "upsil"}
NV_FACTS = {"vendors": ["nvidia"], "vendor": "nvidia", "kernel.flavor": "generic", "torch": "cu130",
            "nvidia.arch": "ada", "nvidia.branch": "595", "nvidia.open": "-open"}


class CatalogTest(SandboxTest):
    def test_catalog_is_complete_and_valid(self):
        cat = M.load_catalog(MODDIR)
        self.assertEqual(set(cat), EXPECTED)
        for m in cat.values():
            self.assertIn(m["category"], M.CATEGORIES, m["id"])
            for key in ("name", "summary"):
                self.assertTrue(m[key].get("en") and m[key].get("ru"), f"{m['id']}.{key}")
            self.assertIn("license_note", m, m["id"])
            self.assertIsInstance(m.get("disk_gb"), (int, float))
            self.assertIsInstance(m.get("vram_gb_min"), (int, float))
            for dep in m["requires"]:
                self.assertIn(dep, cat)
            for fn in (m.get("scripts") or {}).values():
                self.assertTrue((MODDIR / m["id"] / fn).is_file(), f"{m['id']}/{fn}")
            for o, d in (m.get("options") or {}).items():
                self.assertTrue(d.get("en") and d.get("ru"), f"{m['id']} option {o}")

    def test_scripts_are_valid_bash_and_never_pipe_to_shell(self):
        scripts = sorted(MODDIR.glob("*/*.sh")) + [MODDIR / "lib/common.sh", MODDIR / "studio/files/sos-studio",
                                                   MODDIR / "nvidia/files/svoya-nvidia-uvm"]
        self.assertGreaterEqual(len(scripts), 20)
        for s in scripts:
            r = subprocess.run(["bash", "-n", str(s)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{s}: {r.stderr}")
            text = s.read_text()
            code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
            self.assertNotRegex(code, r"curl[^\n|]*\|\s*(ba|z)?sh\b", str(s))
            self.assertNotRegex(code, r"wget[^\n|]*\|\s*(ba|z)?sh\b", str(s))
            if s.parent.name != "files" and s.name != "common.sh":
                self.assertIn('source "${SVOYA_LIB:?}/common.sh"', text, str(s))

    def test_notes_module_is_obsidian_on_request(self):
        cat = M.load_catalog(MODDIR)
        n = M.find(cat, "obsidian")
        self.assertEqual(n["id"], "notes")
        self.assertEqual(n["flatpak"], ["md.obsidian.Obsidian"])
        self.assertTrue(n["proprietary"])
        self.assertEqual(n["profiles"], [])
        self.assertIn("proprietary", n["license_note"]["en"])

    def test_upsil_module_counts_the_image_copy(self):
        cat = M.load_catalog(MODDIR)
        self.assertEqual(M.find(cat, "упсиль")["id"], "upsil")
        ctx = self.sb.ctx(FakeRunner())
        state = M.with_shipped(ctx, cat, M.load_state(ctx))
        self.assertNotIn("upsil", state["modules"])
        bin_ = ctx.sys("/usr/bin/upsil")
        bin_.parent.mkdir(parents=True, exist_ok=True)
        bin_.write_text("#!/usr/bin/python3\n")
        state = M.with_shipped(ctx, cat, M.load_state(ctx))
        self.assertTrue(state["modules"]["upsil"]["shipped"])
        plan = M.plan_remove(cat, ["upsil"], state)                 # removable like any module
        self.assertEqual(plan.apt, ["upsil"])
        plan = M.plan_add(cat, ["upsil"], state, {})                # and re-adding is harmless
        self.assertEqual(plan.apt, ["upsil"])
        self.assertTrue(any("upsil" in n for n in plan.notes))

    def test_profiles(self):
        prof = M.load_profiles(MODDIR)
        self.assertEqual(set(prof["profiles"]), {"newcomer", "creator", "ml", "agent", "hacker"})
        for p in prof["profiles"].values():
            self.assertIn(p["layout"], ("clean", "classic", "hacker"))
            self.assertIn(p["jackson_route"], ("local", "auto", "cloud"))
        creator = M.resolve_profile_modules(prof["profiles"]["creator"], NV_FACTS, prof)
        self.assertEqual(creator[:2], ["base-ai", "nvidia"])
        amd = M.resolve_profile_modules(prof["profiles"]["newcomer"], {"vendor": "amd"}, prof)
        self.assertIn("rocm", amd)
        ml_off = M.resolve_profile_modules(prof["profiles"]["ml"], {"vendor": "none"}, prof, offline=True)
        self.assertNotIn("cloud-burst", ml_off)
        self.assertNotIn("@gpu", ml_off)


class PlanTest(SandboxTest):
    def setUp(self):
        super().setUp()
        self.cat = M.load_catalog(MODDIR)
        self.state = {"v": 1, "modules": {}, "history": []}

    def test_dependencies_first_and_options(self):
        p = M.plan_add(self.cat, ["llm-local"], self.state, NV_FACTS, ["ollama"])
        self.assertEqual([m["id"] for m in p.modules], ["base-ai", "llm-local"])
        self.assertIn("llama.cpp", p.apt)
        self.assertEqual(p.options, {"llm-local": ["ollama"]})
        self.assertAlmostEqual(p.disk_gb, 0.6 + 1.2 + 4.0)
        with self.assertRaises(M.ModuleError):
            M.plan_add(self.cat, ["llm-local"], self.state, NV_FACTS, ["no-such-option"])

    def test_driver_packages_expand_per_gpu(self):
        p = M.plan_add(self.cat, ["nvidia"], self.state, NV_FACTS)
        self.assertEqual(p.apt, ["nvidia-driver-595-open", "linux-modules-nvidia-595-open-generic"])
        legacy = dict(NV_FACTS, **{"nvidia.branch": "580", "nvidia.open": "", "nvidia.arch": "pascal"})
        self.assertEqual(M.plan_add(self.cat, ["nvidia"], self.state, legacy).apt,
                         ["nvidia-driver-580", "linux-modules-nvidia-580-generic"])
        with self.assertRaises(M.ModuleError):                        # no NVIDIA GPU
            M.plan_add(self.cat, ["nvidia"], self.state, {"vendors": ["amd"], "vendor": "amd"})

    def test_remove_keeps_shared_packages(self):
        self.state["modules"] = {
            "dev": {"apt": ["podman", "gh"], "aptNew": ["podman", "gh"]},
            "agents": {"apt": ["podman", "bubblewrap"], "aptNew": ["bubblewrap"]},
            "base-ai": {"apt": ["git"], "aptNew": []}}
        p = M.plan_remove(self.cat, ["dev"], self.state)
        self.assertEqual(p.apt, ["gh"])                                  # podman is still used by agents
        with self.assertRaises(M.ModuleError):
            M.plan_remove(self.cat, ["base-ai"], dict(self.state, modules={**self.state["modules"], "llm-local": {}}))

    def test_script_env_is_clean(self):
        ctx = self.sb.ctx(FakeRunner(), SECRET_TOKEN="x", PKEXEC_UID=str(os.getuid()))
        env = M.script_env(ctx, self.cat["llm-local"], "install", NV_FACTS, ["open-webui"], as_user=False)
        self.assertNotIn("SECRET_TOKEN", env)
        self.assertEqual(env["PATH"], M.CLEAN_PATH)
        self.assertEqual(env["SVOYA_OPT_OPEN_WEBUI"], "1")
        self.assertEqual((env["SVOYA_NVIDIA_BRANCH"], env["SVOYA_TORCH_BACKEND"]), ("595", "cu130"))
        self.assertTrue(env["SVOYA_LIB"].endswith("/modules/lib"))


class ApplyTest(SandboxTest):
    def test_dry_run_changes_nothing(self):
        cat = M.load_catalog(MODDIR)
        r = FakeRunner({"dpkg-query": ""}, available={"snapper"}, dry_run=True)
        ctx = self.sb.ctx(r, dry_run=True)
        plan = M.plan_add(cat, ["llm-local"], M.load_state(ctx), NV_FACTS)
        res = M.apply_root(ctx, plan, NV_FACTS)
        self.assertFalse(ctx.paths.modules_state.exists())
        cmds = [" ".join(c) for c in r.planned]
        self.assertTrue(any(c.startswith("apt-get install -y") and "llama.cpp" in c for c in cmds))
        self.assertTrue(any(c.endswith("base-ai/install.sh") for c in cmds))
        self.assertTrue(res["ok"])

    def test_real_run_records_state_and_snapshots(self):
        cat = M.load_catalog(MODDIR)
        self.sb.write("/etc/snapper/configs/root", "")
        numbers = iter(["41\n", "42\n"])
        r = FakeRunner({"dpkg-query": Result(0, "git\tii \npython3-venv\tii \n"),
                        "snapper -c root create": lambda argv: Result(0, next(numbers)),
                        "apt-get": Result(0), "bash": Result(0)}, available={"snapper"})
        ctx = self.sb.ctx(r, uid=0)
        plan = M.plan_add(cat, ["base-ai"], M.load_state(ctx), NV_FACTS)
        res = M.apply_root(ctx, plan, NV_FACTS)
        self.assertTrue(res["ok"])
        self.assertEqual(res["snapshot"], {"pre": 41, "post": 42})
        state = json.loads(ctx.paths.modules_state.read_text())
        rec = state["modules"]["base-ai"]
        self.assertIn("git", rec["apt"])
        self.assertNotIn("git", rec["aptNew"])                           # was already installed
        self.assertIn("aria2", rec["aptNew"])
        self.assertEqual(state["history"][-1]["action"], "add")
        streamed = [" ".join(c) for c in r.streamed]
        self.assertTrue(any(c.startswith("apt-get install -y") and "git " not in c + " " for c in streamed))

    def test_cli_list_json_and_info(self):
        ctx = self.sb.ctx(FakeRunner({"lspci -Dnnk": fixture("lspci/rx7900xtx.txt")}, available={"lspci"}))
        rc, out = capture(M.main, argparse.Namespace(modules_cmd="list", json=True), ctx)
        rows = {r["id"]: r for r in json.loads(out)["modules"]}
        self.assertFalse(rows["nvidia"]["applicable"])
        self.assertTrue(rows["rocm"]["applicable"])
        self.assertIn("obsidian", rows["notes"]["aliases"])
        rc = M.main(argparse.Namespace(modules_cmd="info", module="llm", json=False, show_scripts=False), ctx)
        self.assertEqual(rc, 0)
        self.assertIn("llama.cpp", self.output())
