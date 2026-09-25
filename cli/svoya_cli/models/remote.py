"""Hugging Face access with urllib only: header-only reads via HTTP Range, metadata, resumable downloads.

* ``HttpRangeReader`` is a lazy file object: the GGUF parser reads a few MB of header instead of
  a 20 GB file. Blocks are fetched on demand; a hard cap stops runaway reads.
* The token (``HF_TOKEN`` or the hf CLI token file) is sent only to the Hub host: it is stripped when a
  redirect leaves that host (the CDN URLs are pre-signed).
* No network call happens unless the user ran a command that needs it (fit on a remote file, pull).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .. import __version__

UA = f"svoya/{__version__} (+https://github.com/svoya-os)"
DEFAULT_ENDPOINT = "https://huggingface.co"


class RemoteError(Exception):
    pass


def hub_endpoint() -> str:
    """``HF_ENDPOINT`` (as honoured by huggingface_hub, e.g. for mirrors) or huggingface.co."""
    return (os.environ.get("HF_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")


@dataclass
class HFRef:
    repo: str
    filename: str | None
    revision: str = "main"

    def url(self, endpoint: str | None = None) -> str:
        if not self.filename:
            raise RemoteError("no file in reference")
        endpoint = endpoint or hub_endpoint()
        return (f"{endpoint.rstrip('/')}/{self.repo}/resolve/{urllib.parse.quote(self.revision, safe='')}/"
                f"{urllib.parse.quote(self.filename)}")


_REPO = r"[A-Za-z0-9][\w.-]*/[\w.-]+"


def parse_ref(ref: str, revision: str = "main") -> HFRef | None:
    """``org/repo/file.gguf`` · ``hf://org/repo/sub/file.gguf`` · ``org/repo`` ·
    ``https://huggingface.co/org/repo/(resolve|blob)/rev/path``."""
    ref = ref.strip()
    m = re.match(rf"^https?://[^/]+/({_REPO})/(?:resolve|blob)/([^/]+)/(.+)$", ref)
    if m:
        return HFRef(m.group(1), urllib.parse.unquote(m.group(3)), urllib.parse.unquote(m.group(2)))
    m = re.match(rf"^https?://[^/]+/({_REPO})/?$", ref)
    if m:
        return HFRef(m.group(1), None, revision)
    if ref.startswith("hf://"):
        ref = ref[5:]
    if ref.startswith(("/", ".", "~")):
        return None
    m = re.match(rf"^({_REPO})(?:/(.+))?$", ref)
    if not m:
        return None
    return HFRef(m.group(1), m.group(2), revision)


def hf_token(env: Mapping[str, str], ai_root: Path | None = None, home: Path | None = None) -> str | None:
    for k in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if env.get(k):
            return env[k].strip()
    cands = []
    if env.get("HF_TOKEN_PATH"):
        cands.append(Path(env["HF_TOKEN_PATH"]))
    if env.get("HF_HOME"):
        cands.append(Path(env["HF_HOME"]) / "token")
    if ai_root:
        cands.append(ai_root / "token")
    if home:
        cands.append(home / ".cache" / "huggingface" / "token")
    for c in cands:
        try:
            t = c.read_text().strip()
            if t:
                return t
        except OSError:
            continue
    return None


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            if urllib.parse.urlparse(newurl).hostname != urllib.parse.urlparse(req.full_url).hostname:
                new.remove_header("Authorization")
                new.unredirected_hdrs.pop("Authorization", None)
        return new


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def opener(no_proxy: bool = False, follow_redirects: bool = True) -> urllib.request.OpenerDirector:
    handlers: list = [_StripAuthOnRedirect() if follow_redirects else _NoRedirect()]
    if no_proxy:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def _headers(token: str | None, extra: dict | None = None) -> dict:
    h = {"User-Agent": UA}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if extra:
        h.update(extra)
    return h


class HttpRangeReader:
    """Read-only, seekable file over HTTP Range requests."""

    def __init__(self, url: str, token: str | None = None, *, op: urllib.request.OpenerDirector | None = None,
                 block: int = 1 << 20, max_bytes: int = 256 << 20, timeout: float = 30):
        self.url, self.token, self.op = url, token, op or opener()
        self.block, self.max_bytes, self.timeout = block, max_bytes, timeout
        self.pos = 0
        self.size: int | None = None
        self.fetched = 0
        self.requests = 0
        self._buf = b""
        self._start = 0

    def _fetch(self, start: int, length: int) -> bytes:
        if self.fetched + length > self.max_bytes:
            raise RemoteError(f"header larger than {self.max_bytes >> 20} MB — refusing to read further")
        req = urllib.request.Request(self.url, headers=_headers(self.token, {"Range": f"bytes={start}-{start + length - 1}"}))
        try:
            with self.op.open(req, timeout=self.timeout) as r:
                data = r.read(length)
                cr = r.headers.get("Content-Range")
                if r.status == 206 and cr:
                    m = re.search(r"/(\d+)\s*$", cr)
                    if m:
                        self.size = int(m.group(1))
                elif r.status == 200:
                    if start != 0:
                        raise RemoteError("server ignores Range requests")
                    cl = r.headers.get("Content-Length")
                    self.size = int(cl) if cl and cl.isdigit() else None
        except urllib.error.HTTPError as e:
            if e.code == 416:
                return b""
            if e.code in (401, 403):
                raise RemoteError(f"HTTP {e.code}: gated or private — accept the license on the Hub and set HF_TOKEN") from None
            if e.code == 404:
                raise RemoteError("HTTP 404: no such file") from None
            raise RemoteError(f"HTTP {e.code}") from None
        except urllib.error.URLError as e:
            raise RemoteError(f"network: {e.reason}") from None
        self.fetched += len(data)
        self.requests += 1
        return data

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            raise RemoteError("unbounded read on a remote file")
        end = self.pos + n
        buf_end = self._start + len(self._buf)
        if not (self._start <= self.pos and end <= buf_end):
            if self._start <= self.pos < buf_end:
                keep = self._buf[self.pos - self._start:]
                start = buf_end
            else:
                keep = b""
                start = self.pos
            need = end - start
            chunk = self._fetch(start, max(self.block, need))
            self._buf, self._start = keep + chunk, self.pos
            # grow block size geometrically for long sequential reads (tokenizer arrays)
            self.block = min(self.block * 2, 16 << 20)
        off = self.pos - self._start
        out = self._buf[off: off + n]
        self.pos += len(out)
        return out

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        else:
            if self.size is None:
                raise RemoteError("size unknown")
            self.pos = self.size + offset
        return self.pos

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos


@dataclass
class FileInfo:
    url: str
    size: int | None
    etag: str | None          # sha256 for LFS/Xet files
    commit: str | None


def head(url: str, token: str | None = None, *, op: urllib.request.OpenerDirector | None = None,
         timeout: float = 30) -> FileInfo:
    """Hub metadata without downloading: X-Repo-Commit, X-Linked-Etag (sha256), X-Linked-Size."""
    op = op or opener(follow_redirects=False)
    req = urllib.request.Request(url, method="HEAD", headers=_headers(token, {"Accept-Encoding": "identity"}))
    try:
        r = op.open(req, timeout=timeout)
        hdrs, status = r.headers, r.status
        r.close()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            hdrs, status = e.headers, e.code
        elif e.code in (401, 403):
            raise RemoteError(f"HTTP {e.code}: gated or private — accept the license on the Hub and set HF_TOKEN") from None
        else:
            raise RemoteError(f"HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise RemoteError(f"network: {e.reason}") from None
    etag = hdrs.get("X-Linked-Etag") or hdrs.get("ETag")
    if etag:
        etag = etag.strip().removeprefix("W/").strip('"')
    size = hdrs.get("X-Linked-Size") or (hdrs.get("Content-Length") if status == 200 else None)
    return FileInfo(url=url, size=int(size) if size and str(size).isdigit() else None, etag=etag,
                    commit=hdrs.get("X-Repo-Commit"))


def api_model(repo: str, revision: str = "main", token: str | None = None, *, endpoint: str | None = None,
              op: urllib.request.OpenerDirector | None = None, timeout: float = 30) -> dict:
    """``/api/models/{repo}/revision/{rev}?blobs=true`` → commit sha, files (size, lfs.sha256), card data."""
    endpoint = endpoint or hub_endpoint()
    url = f"{endpoint.rstrip('/')}/api/models/{repo}/revision/{urllib.parse.quote(revision, safe='')}?blobs=true"
    req = urllib.request.Request(url, headers=_headers(token))
    try:
        with (op or opener()).open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RemoteError(f"HTTP {e.code} for {repo}") from None
    except (urllib.error.URLError, ValueError) as e:
        raise RemoteError(f"{repo}: {e}") from None


def download(url: str, dest: Path, *, token: str | None = None, expected_size: int | None = None,
             expected_sha256: str | None = None, op: urllib.request.OpenerDirector | None = None,
             progress: Callable[[int, int | None], None] | None = None, timeout: float = 60,
             chunk: int = 1 << 20) -> Path:
    """Resumable download to ``dest`` (via ``dest.incomplete``), verified by sha256 when known."""
    part = dest.with_name(dest.name + ".incomplete")
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    if expected_size is not None and have > expected_size:
        part.unlink()
        have = 0
    if expected_size is None or have < expected_size:
        extra = {"Range": f"bytes={have}-"} if have else {}
        req = urllib.request.Request(url, headers=_headers(token, extra))
        try:
            with (op or opener()).open(req, timeout=timeout) as r:
                mode = "ab" if have and r.status == 206 else "wb"
                if mode == "wb":
                    have = 0
                total = expected_size
                with open(part, mode) as f:
                    while True:
                        b = r.read(chunk)
                        if not b:
                            break
                        f.write(b)
                        have += len(b)
                        if progress:
                            progress(have, total)
        except urllib.error.HTTPError as e:
            if e.code != 416:
                raise RemoteError(f"HTTP {e.code} while downloading") from None
        except urllib.error.URLError as e:
            raise RemoteError(f"network: {e.reason} (run again to resume)") from None
    if expected_size is not None and part.stat().st_size != expected_size:
        raise RemoteError(f"size mismatch: got {part.stat().st_size}, expected {expected_size} (run again to resume)")
    if expected_sha256 and re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        got = sha256_file(part)
        if got != expected_sha256:
            part.unlink()
            raise RemoteError(f"sha256 mismatch ({got[:12]}… ≠ {expected_sha256[:12]}…); partial file removed")
    os.replace(part, dest)
    return dest


def sha256_file(path: Path, chunk: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()
