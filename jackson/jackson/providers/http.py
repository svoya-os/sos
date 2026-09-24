# SPDX-License-Identifier: Apache-2.0
"""HTTP(S) with separate connect/read timeouts, env proxies for remote hosts,
Server-Sent Events parsing and cancellation that closes the socket."""

from __future__ import annotations

import base64
import http.client
import ipaddress
import json
import socket
import ssl
import urllib.parse
import urllib.request
from typing import Any, Iterator

from .base import CancelToken, Cancelled, ProviderError

USER_AGENT = "jackson/0.1 (Svoya OS)"
MAX_ERROR_BODY = 64 * 1024


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host in ("localhost", "localhost.localdomain") or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _proxy_for(url: urllib.parse.SplitResult) -> urllib.parse.SplitResult | None:
    if is_loopback_host(url.hostname):
        return None
    proxies = urllib.request.getproxies()
    proxy = proxies.get(url.scheme) or proxies.get("all")
    if not proxy:
        return None
    try:
        if urllib.request.proxy_bypass(url.hostname or ""):
            return None
    except Exception:
        pass
    if "://" not in proxy:
        proxy = "http://" + proxy
    return urllib.parse.urlsplit(proxy)


class Connection:
    """One HTTP request/response; ``abort()`` may be called from any thread."""

    def __init__(self, url: str, *, connect_timeout: float, read_timeout: float,
                 use_proxy: bool = True, provider: str = "") -> None:
        self.url = urllib.parse.urlsplit(url)
        if self.url.scheme not in ("http", "https"):
            raise ProviderError(f"unsupported URL scheme: {self.url.scheme!r}", kind="bad_request",
                                provider=provider)
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.provider = provider
        self.proxy = _proxy_for(self.url) if use_proxy else None
        self.conn: http.client.HTTPConnection | None = None
        self.resp: http.client.HTTPResponse | None = None
        self.aborted = False

    @property
    def host_label(self) -> str:
        return self.url.netloc

    def _make_conn(self) -> tuple[http.client.HTTPConnection, str]:
        host = self.url.hostname or ""
        port = self.url.port or (443 if self.url.scheme == "https" else 80)
        path = self.url.path or "/"
        if self.url.query:
            path += "?" + self.url.query
        if self.proxy is not None:
            p_host, p_port = self.proxy.hostname or "", self.proxy.port or 80
            auth_headers = {}
            if self.proxy.username:
                cred = f"{urllib.parse.unquote(self.proxy.username)}:{urllib.parse.unquote(self.proxy.password or '')}"
                auth_headers["Proxy-Authorization"] = "Basic " + base64.b64encode(cred.encode()).decode()
            if self.url.scheme == "https":
                conn: http.client.HTTPConnection = http.client.HTTPSConnection(
                    p_host, p_port, timeout=self.connect_timeout, context=ssl.create_default_context())
                conn.set_tunnel(host, port, headers=auth_headers)
                return conn, path
            conn = http.client.HTTPConnection(p_host, p_port, timeout=self.connect_timeout)
            return conn, urllib.parse.urlunsplit(self.url)
        if self.url.scheme == "https":
            return http.client.HTTPSConnection(host, port, timeout=self.connect_timeout,
                                               context=ssl.create_default_context()), path
        return http.client.HTTPConnection(host, port, timeout=self.connect_timeout), path

    def request(self, method: str, body: bytes | None, headers: dict[str, str],
                cancel: CancelToken | None = None) -> http.client.HTTPResponse:
        conn, path = self._make_conn()
        self.conn = conn
        if cancel is not None:
            cancel.on_cancel(self.abort)  # abort() is idempotent and thread-safe enough
        try:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            conn.connect()
            if conn.sock is not None:
                conn.sock.settimeout(self.read_timeout)
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            hdrs = {"User-Agent": USER_AGENT, **headers}
            conn.request(method, path, body=body, headers=hdrs)
            resp = conn.getresponse()
        except Cancelled:
            self.close()
            raise
        except (socket.timeout, TimeoutError) as exc:
            self.close()
            raise ProviderError(f"no answer from {self.host_label} (timeout)", kind="timeout",
                                retryable=True, provider=self.provider) from exc
        except ssl.SSLError as exc:
            self.close()
            raise ProviderError(f"TLS error with {self.host_label}: {exc.reason or exc}", kind="network",
                                retryable=False, provider=self.provider) from exc
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            self.close()
            if cancel is not None and cancel.is_set():
                raise Cancelled() from exc
            reason = getattr(exc, "strerror", None) or exc.__class__.__name__
            raise ProviderError(f"cannot connect to {self.host_label} ({reason})", kind="network",
                                retryable=True, provider=self.provider) from exc
        self.resp = resp
        if resp.status >= 400:
            try:
                raw = resp.read(MAX_ERROR_BODY)
            except Exception:
                raw = b""
            self.close()
            raise http_error(resp.status, raw, self.provider, self.host_label)
        return resp

    def abort(self) -> None:
        self.aborted = True
        conn = self.conn
        if conn is not None and conn.sock is not None:
            try:
                conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.close()

    def close(self) -> None:
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:
            pass


def http_error(status: int, raw: bytes, provider: str, host: str) -> ProviderError:
    detail = ""
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            detail = str(err.get("message") or err.get("type") or "")
        elif isinstance(err, str):
            detail = err
        elif isinstance(data, dict) and data.get("message"):
            detail = str(data["message"])
        elif isinstance(data, list) and data and isinstance(data[0], dict):  # Gemini sometimes wraps in a list
            inner = data[0].get("error") or {}
            detail = str(inner.get("message") or "")
    except (ValueError, AttributeError):
        detail = raw.decode("utf-8", "replace").strip()[:300]
    detail = detail[:500]
    if status in (401, 403):
        return ProviderError(f"access denied by {host} (HTTP {status}): check the API key. {detail}".strip(),
                             kind="auth", status=status, provider=provider)
    if status == 429:
        return ProviderError(f"rate limit or quota at {host} (HTTP 429). {detail}".strip(), kind="rate",
                             retryable=True, status=status, provider=provider)
    if status in (500, 502, 503, 504, 529):
        return ProviderError(f"{host} is unavailable (HTTP {status}). {detail}".strip(), kind="server",
                             retryable=True, status=status, provider=provider)
    return ProviderError(f"{host} rejected the request (HTTP {status}). {detail}".strip(), kind="bad_request",
                         status=status, provider=provider)


def iter_sse(resp: http.client.HTTPResponse, cancel: CancelToken, provider: str = ""
             ) -> Iterator[tuple[str, str]]:
    """Yield ``(event, data)`` pairs from a text/event-stream response."""
    event, data_lines = "", []
    while True:
        if cancel.is_set():
            raise Cancelled()
        try:
            raw = resp.readline(1 << 20)
        except (socket.timeout, TimeoutError) as exc:
            raise ProviderError("the stream stalled (read timeout)", kind="timeout", retryable=True,
                                provider=provider) from exc
        except (OSError, ValueError, http.client.HTTPException) as exc:
            if cancel.is_set():
                raise Cancelled() from exc
            raise ProviderError(f"the stream broke ({exc.__class__.__name__})", kind="network",
                                retryable=True, provider=provider) from exc
        if not raw:
            if cancel.is_set():
                raise Cancelled()
            if data_lines:
                yield event or "message", "\n".join(data_lines)
            return
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if data_lines:
                yield event or "message", "\n".join(data_lines)
            event, data_lines = "", []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event = value
        elif field == "data":
            data_lines.append(value)


def post_sse(url: str, payload: dict[str, Any], headers: dict[str, str], *, connect_timeout: float,
             read_timeout: float, use_proxy: bool, cancel: CancelToken, provider: str
             ) -> tuple[Connection, http.client.HTTPResponse]:
    conn = Connection(url, connect_timeout=connect_timeout, read_timeout=read_timeout,
                      use_proxy=use_proxy, provider=provider)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    resp = conn.request("POST", body, {"Content-Type": "application/json", "Accept": "text/event-stream",
                                        **headers}, cancel)
    return conn, resp


def get_json(url: str, headers: dict[str, str] | None = None, *, timeout: float = 2.0,
             use_proxy: bool = True, provider: str = "") -> tuple[int, Any]:
    conn = Connection(url, connect_timeout=timeout, read_timeout=timeout, use_proxy=use_proxy,
                      provider=provider)
    try:
        c, path = conn._make_conn()
        conn.conn = c
        c.connect()
        if c.sock is not None:
            c.sock.settimeout(timeout)
        c.request("GET", path, headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                                        **(headers or {})})
        resp = c.getresponse()
        raw = resp.read(4 << 20)
        try:
            data = json.loads(raw.decode("utf-8", "replace")) if raw else None
        except ValueError:
            data = None
        return resp.status, data
    except (socket.timeout, TimeoutError) as exc:
        raise ProviderError(f"no answer from {conn.host_label} (timeout)", kind="timeout", retryable=True,
                            provider=provider) from exc
    except (OSError, http.client.HTTPException) as exc:
        reason = getattr(exc, "strerror", None) or exc.__class__.__name__
        raise ProviderError(f"cannot connect to {conn.host_label} ({reason})", kind="network",
                            retryable=True, provider=provider) from exc
    finally:
        conn.close()
