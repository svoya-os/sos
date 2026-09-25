import hashlib
import json
import os
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from svoya_cli.models import gguf, remote
from svoya_cli.models.cli import load_remote

from .gguf_synth import llama_like
from .helpers import Sandbox


class HubHandler(BaseHTTPRequestHandler):
    files: dict[str, bytes] = {}
    seen_auth: dict[str, str | None] = {}
    commit = "c0ffee" * 6 + "abcd"

    def log_message(self, *a):
        pass

    def _send_bytes(self, data: bytes, head_only: bool = False):
        rng = self.headers.get("Range")
        if rng:
            start_s, _, end_s = rng.removeprefix("bytes=").partition("-")
            start = int(start_s)
            end = min(int(end_s) if end_s else len(data) - 1, len(data) - 1)
            if start >= len(data):
                self.send_response(416)
                self.end_headers()
                return
            body = data[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        else:
            body = data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_HEAD(self):
        self._route(head=True)

    def do_GET(self):
        self._route(head=False)

    def _route(self, head: bool):
        path = self.path
        self.seen_auth[path.split("?")[0]] = self.headers.get("Authorization")
        if path.startswith("/api/models/"):
            body = json.dumps({"sha": self.commit, "siblings": [
                {"rfilename": name, "size": len(data), "lfs": {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}}
                for name, data in self.files.items()], "cardData": {"license": "apache-2.0"}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if "/resolve/main/" in path:
            name = path.split("/resolve/main/", 1)[1]
            data = self.files.get(name)
            if data is None:
                self.send_response(404)
                self.end_headers()
                return
            sha = hashlib.sha256(data).hexdigest()
            # like the Hub: redirect to a CDN host (different hostname) with metadata headers
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{self.server.server_port}/cdn/{sha}")
            self.send_header("X-Repo-Commit", self.commit)
            self.send_header("X-Linked-Etag", f'"{sha}"')
            self.send_header("X-Linked-Size", str(len(data)))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path.startswith("/cdn/"):
            sha = path[5:]
            data = next((d for d in self.files.values() if hashlib.sha256(d).hexdigest() == sha), None)
            if data is None:
                self.send_response(404)
                self.end_headers()
                return
            self._send_bytes(data, head_only=head)
            return
        self.send_response(404)
        self.end_headers()


class RemoteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sb = Sandbox()
        p = cls.sb.path("/src/model-Q4_K_M.gguf")
        p.parent.mkdir(parents=True)
        llama_like(p, n_layers=4, n_embd=512, vocab=2048)
        cls.model = p.read_bytes()
        HubHandler.files = {"model-Q4_K_M.gguf": cls.model}
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), HubHandler)
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.env = mock.patch.dict(os.environ, {"HF_ENDPOINT": cls.base, "no_proxy": "127.0.0.1,localhost",
                                               "NO_PROXY": "127.0.0.1,localhost"})
        cls.env.start()

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.sb.cleanup()

    def test_header_over_range_requests_reads_little(self):
        ref = remote.HFRef("org/repo", "model-Q4_K_M.gguf")
        rd = remote.HttpRangeReader(ref.url(), None, block=64 * 1024)
        h = gguf.read_header(rd)
        self.assertEqual(h.arch_get("block_count"), 4)
        self.assertEqual(rd.size, len(self.model))
        self.assertLess(rd.fetched, len(self.model) / 4)

    def test_load_remote_shape(self):
        shape, hdr, fetched = load_remote(remote.HFRef("org/repo", "model-Q4_K_M.gguf"), None)
        local = gguf.read_file(self.sb.path("/src/model-Q4_K_M.gguf"))
        self.assertEqual(shape.weights, local.tensor_bytes())
        self.assertGreater(fetched, 0)

    def test_head_metadata(self):
        info = remote.head(remote.HFRef("org/repo", "model-Q4_K_M.gguf").url())
        self.assertEqual(info.etag, hashlib.sha256(self.model).hexdigest())
        self.assertEqual(info.size, len(self.model))
        self.assertEqual(info.commit, HubHandler.commit)

    def test_token_is_stripped_on_cross_host_redirect(self):
        url = remote.HFRef("org/repo", "model-Q4_K_M.gguf").url()
        req = urllib.request.Request(url, headers={"Authorization": "Bearer secret", "Range": "bytes=0-99"})
        with remote.opener().open(req, timeout=10) as r:
            self.assertEqual(len(r.read()), 100)
        self.assertEqual(HubHandler.seen_auth["/org/repo/resolve/main/model-Q4_K_M.gguf"], "Bearer secret")
        cdn = "/cdn/" + hashlib.sha256(self.model).hexdigest()
        self.assertIsNone(HubHandler.seen_auth[cdn])

    def test_download_resumes_and_verifies(self):
        sb = Sandbox()
        try:
            dest = sb.path("/hub/blob")
            dest.parent.mkdir(parents=True)
            sha = hashlib.sha256(self.model).hexdigest()
            part = dest.with_name(dest.name + ".incomplete")
            part.write_bytes(self.model[:1000])
            url = remote.HFRef("org/repo", "model-Q4_K_M.gguf").url()
            seen = []
            remote.download(url, dest, expected_size=len(self.model), expected_sha256=sha,
                            progress=lambda d, t: seen.append(d))
            self.assertEqual(dest.read_bytes(), self.model)
            self.assertTrue(seen and seen[0] > 1000)          # continued, not restarted
            bad = sb.path("/hub/bad")
            with self.assertRaises(remote.RemoteError):
                remote.download(url, bad, expected_size=len(self.model), expected_sha256="0" * 64)
            self.assertFalse(Path(str(bad) + ".incomplete").exists())
        finally:
            sb.cleanup()

    def test_api_model(self):
        info = remote.api_model("org/repo")
        self.assertEqual(info["sha"], HubHandler.commit)
        self.assertEqual(info["siblings"][0]["rfilename"], "model-Q4_K_M.gguf")


class RefTest(unittest.TestCase):
    def test_parse_ref(self):
        r = remote.parse_ref("unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf")
        self.assertEqual((r.repo, r.filename, r.revision), ("unsloth/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf", "main"))
        r = remote.parse_ref("https://huggingface.co/org/repo/resolve/v1.0/sub/dir/f.gguf")
        self.assertEqual((r.repo, r.filename, r.revision), ("org/repo", "sub/dir/f.gguf", "v1.0"))
        r = remote.parse_ref("hf://org/repo")
        self.assertEqual((r.repo, r.filename), ("org/repo", None))
        self.assertIsNone(remote.parse_ref("./local.gguf"))
        self.assertIsNone(remote.parse_ref("/abs/local.gguf"))
        self.assertEqual(remote.HFRef("o/r", "a b.gguf").url("https://hf.example"), "https://hf.example/o/r/resolve/main/a%20b.gguf")

    def test_token_precedence(self):
        sb = Sandbox()
        try:
            (sb.home / ".cache/huggingface").mkdir(parents=True)
            (sb.home / ".cache/huggingface/token").write_text("from-file\n")
            self.assertEqual(remote.hf_token({}, None, sb.home), "from-file")
            self.assertEqual(remote.hf_token({"HF_TOKEN": "env"}, None, sb.home), "env")
            self.assertIsNone(remote.hf_token({}, None, None))
        finally:
            sb.cleanup()


if __name__ == "__main__":
    unittest.main()
