import argparse
import hashlib
import json
import os

from svoya_cli.models import cli as mcli
from svoya_cli.models import dedup, hfcache, licenses, suggest, views
from svoya_cli.models.registry import Registry

from .gguf_synth import llama_like
from .helpers import FakeRunner, SandboxTest, capture, fixture

GiB = 2**30


def cache_file(sb, repo: str, filename: str, content: bytes, commit: str = "a" * 40):
    hub = sb.path("/srv/ai/hub")
    src = sb.dir / "tmp-src"
    src.write_bytes(content)
    etag = hashlib.sha256(content).hexdigest()
    return hfcache.add_file(hub, repo, commit, filename, src, etag)


class HfCacheTest(SandboxTest):
    def test_layout_and_scan(self):
        snap = cache_file(self.sb, "unsloth/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf", b"x" * 100)
        self.assertTrue(snap.is_symlink())
        self.assertEqual(os.readlink(snap), f"../../blobs/{hashlib.sha256(b'x' * 100).hexdigest()}")
        cache_file(self.sb, "unsloth/Qwen3.5-9B-GGUF", "sub/dir/file.gguf", b"y" * 10)
        files = hfcache.scan(self.sb.path("/srv/ai/hub"))
        self.assertEqual(sorted(f.filename for f in files), ["Qwen3.5-9B-Q4_K_M.gguf", "sub/dir/file.gguf"])
        self.assertTrue(all(f.sha256 for f in files))
        self.assertEqual(files[0].repo, "unsloth/Qwen3.5-9B-GGUF")
        nested = next(f for f in files if f.filename.startswith("sub/"))
        self.assertTrue(nested.blob_path.exists())
        self.assertEqual((self.sb.path("/srv/ai/hub/models--unsloth--Qwen3.5-9B-GGUF/refs/main")).read_text(), "a" * 40)

    def test_remove_file_keeps_shared_blob(self):
        cache_file(self.sb, "o/r", "a.gguf", b"same")
        cache_file(self.sb, "o/r", "b.gguf", b"same")
        files = hfcache.scan(self.sb.path("/srv/ai/hub"))
        removed = hfcache.remove_file(self.sb.path("/srv/ai/hub"), files[0], files)
        self.assertEqual(len(removed), 1)         # the blob is still used by b.gguf
        self.assertTrue(files[1].blob_path.exists())


class ViewsTest(SandboxTest):
    def test_llama_cpp_layout(self):
        cache_file(self.sb, "unsloth/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf", b"a")
        cache_file(self.sb, "unsloth/Qwen3.5-9B-GGUF", "mmproj-F16.gguf", b"b")
        cache_file(self.sb, "ggml-org/gpt-oss-120b-GGUF", "gpt-oss-120b-MXFP4-00001-of-00002.gguf", b"c")
        cache_file(self.sb, "ggml-org/gpt-oss-120b-GGUF", "gpt-oss-120b-MXFP4-00002-of-00002.gguf", b"d")
        cache_file(self.sb, "ggml-org/gpt-oss-20b-GGUF", "gpt-oss-20b-MXFP4.gguf", b"e")
        files = hfcache.scan(self.sb.path("/srv/ai/hub"))
        out = self.sb.path("/srv/ai/views/llama.cpp")
        rep = views.apply(views.llama_plan(files, out), out)
        self.assertTrue((out / "gpt-oss-20b-MXFP4.gguf").is_symlink())                        # single file
        self.assertTrue((out / "Qwen3.5-9B-Q4_K_M" / "mmproj-F16.gguf").is_symlink())         # vision sidecar
        self.assertTrue((out / "gpt-oss-120b-MXFP4" / "gpt-oss-120b-MXFP4-00001-of-00002.gguf").exists())
        self.assertEqual(rep["links"], 5)
        # idempotent; stale links disappear when a model is removed
        hfcache.remove_repo(self.sb.path("/srv/ai/hub"), "ggml-org/gpt-oss-20b-GGUF")
        rep2 = views.apply(views.llama_plan(hfcache.scan(self.sb.path("/srv/ai/hub")), out), out)
        self.assertFalse((out / "gpt-oss-20b-MXFP4.gguf").exists())
        self.assertEqual(len(rep2["stale"]), 1)

    def test_comfyui_folders_and_yaml(self):
        cache_file(self.sb, "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors", b"1")
        cache_file(self.sb, "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/vae/wan2.2_vae.safetensors", b"2")
        cache_file(self.sb, "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/text_encoders/umt5_xxl_fp8.safetensors", b"3")
        cache_file(self.sb, "Tongyi-MAI/Z-Image-Turbo", "z_image_turbo_lora_style.safetensors", b"4")
        cache_file(self.sb, "Qwen/Qwen3.5-9B", "model-00001-of-00004.safetensors", b"5")   # an LLM: not for ComfyUI
        files = hfcache.scan(self.sb.path("/srv/ai/hub"))
        out = self.sb.path("/srv/ai/views/comfyui")
        views.apply(views.comfy_plan(files, out), out)
        self.assertTrue((out / "diffusion_models" / "wan2.2_ti2v_5B_fp16.safetensors").is_symlink())
        self.assertTrue((out / "vae" / "wan2.2_vae.safetensors").is_symlink())
        self.assertTrue((out / "text_encoders" / "umt5_xxl_fp8.safetensors").is_symlink())
        self.assertTrue((out / "loras" / "z_image_turbo_lora_style.safetensors").is_symlink())
        self.assertFalse(any("model-00001" in str(p) for p in out.rglob("*")))
        y = (out / "extra_model_paths.yaml").read_text()
        self.assertIn(f"base_path: {out}/", y)
        self.assertIn("diffusion_models: diffusion_models/", y)

    def test_ollama_commands(self):
        cache_file(self.sb, "unsloth/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf", b"a")
        cache_file(self.sb, "unsloth/Qwen3.5-9B-GGUF", "mmproj-F16.gguf", b"b")
        files = hfcache.scan(self.sb.path("/srv/ai/hub"))
        out = self.sb.path("/srv/ai/views/ollama")
        rep = views.apply(views.ollama_plan(files, out), out)
        self.assertEqual(len(rep["commands"]), 1)
        self.assertTrue(rep["commands"][0].startswith("ollama create qwen3.5-9b:q4_k_m -f "))
        self.assertIn("FROM ", (out / "qwen3.5-9b--q4_k_m.Modelfile").read_text())
        self.assertEqual(views.ollama_name("gpt-oss-20b-MXFP4.gguf"), "gpt-oss-20b-mxfp4:latest")


class DedupTest(SandboxTest):
    def test_find_and_reflink_plan(self):
        a = self.sb.write("/srv/ai/hub/x/blob", b"z" * 4096)
        b = self.sb.write("/home/u/.ollama/models/blobs/sha256-abc", b"z" * 4096)
        self.sb.write("/srv/ai/hub/y/other", b"q" * 4096)
        os.link(a, self.sb.path("/srv/ai/hub/x/hardlink"))                  # same inode: not a duplicate
        groups = dedup.find([self.sb.path("/srv/ai"), self.sb.path("/home/u/.ollama")], min_size=1024)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].wasted, 4096)
        self.assertEqual(set(groups[0].files), {a, b})
        r = FakeRunner(dry_run=True)
        res = dedup.reflink_group(groups[0], r, dry_run=True)
        self.assertTrue(res[0][1])
        self.assertTrue(r.planned[0][:2] == ["cp", "--reflink=always"])

    def test_hash_cache_in_registry(self):
        reg = Registry(self.sb.path("/srv/ai/registry.db"))
        p = self.sb.write("/f", b"hello")
        st = p.stat()
        self.assertIsNone(reg.cached_hash(p, st))
        reg.put_hash(p, st, "abc")
        self.assertEqual(reg.cached_hash(p, st), "abc")
        reg.close()


class LicensesTest(SandboxTest):
    def test_catalog_facts(self):
        eu = lambda **kw: licenses.classify(**kw).allows("EU", commercial=True)[0]  # noqa: E731
        self.assertEqual(eu(repo="Qwen/Qwen-Image"), "ok")
        self.assertEqual(eu(repo="Qwen/Qwen-Image-2.1"), "no")                 # non-commercial
        self.assertEqual(eu(repo="black-forest-labs/FLUX.2-klein-4B"), "ok")
        self.assertEqual(eu(repo="black-forest-labs/FLUX.2-klein-9B"), "no")
        self.assertEqual(eu(repo="tencent/HunyuanVideo-1.5"), "no")            # excludes the EU
        self.assertEqual(licenses.classify(repo="tencent/HunyuanVideo-1.5").allows("US")[0], "warn")
        self.assertEqual(eu(repo="MiniMaxAI/MiniMax-H3"), "no")
        self.assertEqual(licenses.classify(repo="MiniMaxAI/MiniMax-H3").allows("US")[0], "no")
        self.assertEqual(eu(repo="Lightricks/LTX-2.5"), "warn")                # revenue threshold
        self.assertEqual(eu(repo="Wan-AI/Wan2.2-TI2V-5B"), "ok")
        self.assertEqual(eu(repo="nvidia/parakeet-tdt-0.6b-v3"), "ok")         # attribution note
        self.assertIn("attribution", licenses.classify(repo="nvidia/parakeet-tdt-0.6b-v3").allows("EU")[1])
        self.assertEqual(licenses.classify(repo="meta-llama/Llama-4-Scout").allows("EU", multimodal=True)[0], "no")
        self.assertEqual(licenses.classify(repo="meta-llama/Llama-4-Scout").allows("EU", commercial=False)[0], "warn")
        self.assertEqual(eu(repo="ResembleAI/chatterbox"), "ok")

    def test_generic_license_ids(self):
        self.assertEqual(licenses.classify(license_id="apache-2.0").allows("EU")[0], "ok")
        self.assertEqual(licenses.classify(license_id="cc-by-nc-4.0").allows("EU")[0], "no")
        self.assertEqual(licenses.classify(license_id="cc-by-nc-4.0").allows("EU", commercial=False)[0], "ok")
        self.assertEqual(licenses.classify(license_id="weird-license").allows("EU")[0], "warn")
        self.assertEqual(licenses.classify().allows("EU")[0], "warn")

    def test_default_catalog_view_hides_restricted(self):
        ctx = self.sb.ctx(FakeRunner())
        args = argparse.Namespace(catalog=True, all=False, kind=None, json=True)
        _, out = capture(mcli.cmd_list, args, ctx)
        ids = {m["id"] for m in json.loads(out)["models"]}
        self.assertIn("wan2.2-ti2v-5b", ids)
        self.assertNotIn("hunyuanvideo-1.5", ids)
        self.assertNotIn("qwen-image-2.1", ids)
        args.all = True
        _, out = capture(mcli.cmd_list, args, ctx)
        self.assertIn("hunyuanvideo-1.5", {m["id"] for m in json.loads(out)["models"]})


class RegistryTest(SandboxTest):
    def test_upsert_roundtrip(self):
        reg = Registry(self.sb.path("/srv/ai/registry.db"))
        reg.upsert({"path": "/srv/ai/hub/x", "sha256": "ab", "repo": "o/r", "license": "Apache-2.0",
                    "commercial": True, "eu_ok": True, "regions_excluded": ["UK"], "meta": {"k": 1}})
        reg.upsert({"path": "/srv/ai/hub/x", "commercial": "conditional"})
        row = reg.find("o/r")[0]
        self.assertEqual((row["sha256"], row["commercial"], row["regions_excluded"], row["meta"]),
                         ("ab", "conditional", ["UK"], {"k": 1}))
        self.assertEqual(reg.delete_paths(["/srv/ai/hub/x"]), 1)
        reg.close()


class FitCliTest(SandboxTest):
    def test_fit_local_file_json(self):
        p = self.sb.path("/m/Synth-Q4_K_M.gguf")
        p.parent.mkdir(parents=True)
        llama_like(p, n_layers=8, n_embd=512)
        ctx = self.sb.ctx(FakeRunner())
        self.sb.write("/proc/meminfo", "MemTotal: 16000000 kB\nMemAvailable: 12000000 kB\n")
        args = argparse.Namespace(model=str(p), ctx=8192, gpu="24gb", kv="f16", no_flash_attn=False,
                                  revision="main", json=True)
        rc, out = capture(mcli.cmd_fit, args, ctx)
        data = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertEqual(data["fit"]["verdict"], "fits")
        self.assertEqual(data["gpu"]["totalBytes"], 24 * GiB)
        self.assertEqual(data["license"]["license"], "Apache-2.0")
        self.assertEqual(data["usable"]["status"], "ok")
        self.assertEqual(data["estimate"]["totalBytes"], sum(data["estimate"][k] for k in
                                                            ("weightsBytes", "kvBytes", "computeBytes", "runtimeBytes")))

    def test_fit_uses_live_gpu(self):
        p = self.sb.path("/m/Synth-Q4_K_M.gguf")
        p.parent.mkdir(parents=True)
        llama_like(p, n_layers=8, n_embd=512)
        r = FakeRunner({"nvidia-smi --query-gpu": fixture("nvidia-smi/rtx4090.csv")}, available={"nvidia-smi"})
        args = argparse.Namespace(model=str(p), ctx=4096, gpu="auto", kv="q8_0", no_flash_attn=True,
                                  revision="main", json=False)
        rc, _ = capture(mcli.cmd_fit, args, self.sb.ctx(r))
        self.assertEqual(rc, 0)
        text = self.output()
        self.assertIn("✓ fits", text)
        self.assertIn("RTX 4090", text)


class SuggestTest(SandboxTest):
    def hw(self, gib: float | None, *, unified=False, ram=32, backend="cuda"):
        return {"gpu": "GPU" if gib else None, "vendor": "nvidia", "memoryBytes": int(gib * GiB) if gib else None,
                "unified": unified, "usedBytes": int(0.5 * GiB) if gib else 0, "ramTotalBytes": ram * GiB,
                "ramAvailableBytes": int(ram * 0.8 * GiB), "diskFreeBytes": 500 * GiB,
                "backend": backend if gib else "cpu"}

    def test_ladder_is_license_safe_and_resolvable(self):
        lad = suggest.load_ladder()
        for m in lad["models"].values():
            self.assertIn(m["license"], ("Apache-2.0", "MIT"), m["id"])
        for t in lad["tiers"]:
            self.assertEqual(len(t["picks"]), 3, t["id"])
            for pk in t["picks"]:
                self.assertIsNotNone(suggest.resolve(pk, lad), pk)

    def test_tiers(self):
        ctx = self.sb.ctx()
        cases = [(None, "cpu", "qwen3.5-4b:Q4_K_M"), (8, "gpu6", "qwen3.5-9b:Q4_K_M"),
                 (12, "gpu10", "qwen3.5-9b:Q8_0"), (10, "gpu10", "qwen3.5-9b:Q6_K"),
                 (16, "gpu16", "qwen3.5-27b:Q3_K_M"), (24, "gpu24", "qwen3.5-27b:Q4_K_M"),
                 (32, "gpu32", "qwen3.5-27b:Q8_0"), (96, "big64", "qwen3.5-122b-a10b:UD-Q4_K_XL")]
        for gib, tier, default in cases:
            res = suggest.suggest(ctx, self.hw(gib, unified=gib == 96, ram=128 if gib == 96 else 32))
            self.assertEqual(res["tier"], tier, gib)
            self.assertEqual(res["default"]["id"], default, gib)
            self.assertEqual(res["default"]["verdict"], "fits", gib)
            self.assertEqual(len(res["alternatives"]), 2, gib)
            self.assertTrue(res["default"]["pull"].startswith("sos models pull "))

    def test_unified_memory_speed_class_and_json_fields(self):
        res = suggest.suggest(self.sb.ctx(), self.hw(96, unified=True, ram=128))
        d = res["default"]
        for k in ("id", "repo", "files", "quant", "sizeBytes", "memoryBytes8k", "verdict", "speed", "tokensPerSecond",
                  "license", "vision", "mmproj"):
            self.assertIn(k, d)
        self.assertEqual(len(d["files"]), 3)                  # split GGUF
        self.assertIn(d["speed"], ("fast", "good", "slow", "very-slow"))

    def test_suggest_yes_downloads_the_default_in_one_step(self):
        ctx = self.sb.ctx(FakeRunner(), dry_run=True)
        self.sb.write("/proc/meminfo", "MemTotal: 33554432 kB\nMemAvailable: 30000000 kB\n")
        self.sb.mkdir("/srv/ai")
        from unittest import mock
        def run(**kw):
            self.buf.seek(0)
            self.buf.truncate()
            rc, _ = capture(mcli.cmd_suggest, argparse.Namespace(json=False, **kw), ctx)
            return rc, self.output()

        with mock.patch.object(suggest, "hardware", return_value=self.hw(None)):
            rc, out = run(yes=True)
            self.assertEqual(rc, 0, out)
            self.assertIn("unsloth/Qwen3.5-4B-GGUF", out)          # the pull ran (as a dry run here)
            self.assertIn("dry run: nothing downloaded", out)
            # without --yes and without a terminal it only lists
            rc, out = run(yes=False)
            self.assertNotIn("nothing downloaded", out)
            # a live session never downloads into RAM from here
            self.sb.write("/etc/svoya/live", "")
            rc, out = run(yes=True)
            self.assertIn("install SOS first", out)
            self.assertNotIn("nothing downloaded", out)

    def test_pull_alias_dry_run_emits_json_events(self):
        ctx = self.sb.ctx(FakeRunner(), dry_run=True)
        self.sb.write("/proc/meminfo", "MemTotal: 33554432 kB\nMemAvailable: 30000000 kB\n")
        self.sb.mkdir("/srv/ai")
        args = argparse.Namespace(repo="qwen3.5-9b:Q4_K_M", files=[], revision="main", include=[], ctx=8192, yes=True,
                                  accept_license=False, dry_run=True, json=True)
        rc, out = capture(mcli.cmd_pull, args, ctx)
        events = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(rc, 0)
        self.assertEqual(events[0]["event"], "plan")
        self.assertEqual(events[0]["repo"], "unsloth/Qwen3.5-9B-GGUF")
        self.assertEqual(events[0]["files"], ["Qwen3.5-9B-Q4_K_M.gguf", "mmproj-F16.gguf"])
        self.assertEqual(events[0]["usable"]["status"], "ok")
        self.assertEqual(events[-1], {"event": "done", "ok": True, "dryRun": True})


class ListCliTest(SandboxTest):
    def test_list_installed_syncs_registry(self):
        p = self.sb.dir / "m.gguf"
        llama_like(p, n_layers=2)
        cache_file(self.sb, "unsloth/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf", p.read_bytes())
        ctx = self.sb.ctx(FakeRunner())
        args = argparse.Namespace(catalog=False, all=False, kind=None, json=True)
        _, out = capture(mcli.cmd_list, args, ctx)
        m = json.loads(out)["models"][0]
        self.assertEqual((m["repo"], m["format"], m["arch"], m["quant"]), ("unsloth/Qwen3.5-9B-GGUF", "gguf", "llama", "Q4_K_M"))
        self.assertTrue(ctx.paths.registry_db.exists())

    def test_rm_repo(self):
        cache_file(self.sb, "o/r", "a.gguf", b"a")
        ctx = self.sb.ctx(FakeRunner())
        args = argparse.Namespace(target="o/r", dry_run=False, yes=True)
        self.assertEqual(mcli.cmd_rm(args, ctx), 0)
        self.assertEqual(hfcache.scan(self.sb.path("/srv/ai/hub")), [])


class ServeTest(SandboxTest):
    def test_serve_uses_the_user_unit(self):
        r = FakeRunner({"systemctl --user cat": "", "systemctl --user start": ""}, available={"systemctl"})
        args = argparse.Namespace(port=18080, stop=False, status=False, foreground=False, json=False)
        self.assertEqual(mcli.cmd_serve(args, self.sb.ctx(r)), 0)
        self.assertTrue(r.called("systemctl", "--user", "start", "svoya-llm.service"))
        self.assertIn("127.0.0.1:18080/v1", self.output())

    def test_serve_limits_the_context_window(self):
        # llama.cpp's default context (the model's training context, 262k for Qwen3.5) ran the model
        # bot's 12 GB machine out of memory before the first answer
        from svoya_cli.paths import REPO_ROOT
        unit = (REPO_ROOT / "modules/llm-local/files/svoya-llm.service").read_text()
        self.assertIn(f"Environment=LLAMA_ARG_CTX_SIZE={mcli.SERVE_CTX}", unit)
        self.assertIn("EnvironmentFile=-%h/.config/svoya/llm.env", unit)
        self.assertLess(unit.index("Environment=LLAMA_ARG_CTX_SIZE"), unit.index("EnvironmentFile="))  # yours wins
        seen = {}

        class Spawning(FakeRunner):
            def spawn(self, argv, *, env=None, cwd=None, mutating=True):
                seen["env"], seen["argv"] = env, list(argv)
                return super().spawn(argv, env=env, cwd=cwd, mutating=mutating)

        r = Spawning(available={"llama-server"})
        args = argparse.Namespace(port=18080, stop=False, status=False, foreground=False, json=False)
        self.assertEqual(mcli.cmd_serve(args, self.sb.ctx(r)), 0)
        self.assertEqual(seen["env"]["LLAMA_ARG_CTX_SIZE"], "16384")
        # llama.cpp lists the store (a Hugging Face cache) by repository name and, online, asked
        # Hugging Face before loading: the model bot's answers timed out. Only the views, offline.
        self.assertEqual(seen["env"]["LLAMA_ARG_OFFLINE"], "1")
        self.assertIn("--offline", seen["argv"])
        for var in ("LLAMA_CACHE", "HF_HUB_CACHE", "HF_HOME"):
            self.assertNotIn("/srv/ai", seen["env"][var])
            self.assertRegex(unit, rf"(?m)^Environment=.*\b{var}=%t/svoya-llm/")
        self.assertRegex(unit, r"(?m)^ExecStart=/usr/bin/llama-server .*--models-dir /srv/ai/views/llama.cpp .*--offline$")
        # a cancelled request stops after 512 tokens, not 2048 (minutes on a slow CPU)
        self.assertIn("--batch-size 512", unit)
        self.assertEqual(seen["argv"][seen["argv"].index("--batch-size") + 1], "512")

    def test_serve_without_server_explains(self):
        import contextlib
        import io
        args = argparse.Namespace(port=18080, stop=False, status=False, foreground=False, json=False)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(mcli.cmd_serve(args, self.sb.ctx(FakeRunner())), 2)
        self.assertIn("llm-local", err.getvalue())
