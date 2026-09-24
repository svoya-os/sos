# SPDX-License-Identifier: Apache-2.0
"""API keys: Secret Service keyring first, ``secrets.env`` (0600) as a headless fallback.

Keys are stored with::

    secret-tool store --label='Svoya: anthropic' service svoya provider anthropic

and read with ``secret-tool lookup service svoya provider <name>``.
Keys are never logged, never sent to a client and never put in a prompt.
"""

from __future__ import annotations

import os
import stat
import threading
from dataclasses import dataclass
from typing import Mapping

from .config import ProviderConfig
from .paths import Paths
from .runner import Runner


@dataclass
class KeyLookup:
    key: str | None
    source: str            # "keyring" | "secrets.env" | "env" | "none"
    warning: str | None = None

    @property
    def found(self) -> bool:
        return bool(self.key)


class KeyStore:
    def __init__(self, paths: Paths, runner: Runner | None = None,
                 env: Mapping[str, str] | None = None, use_keyring: bool = True) -> None:
        self.paths = paths
        self.runner = runner or Runner()
        self.env = os.environ if env is None else env
        self.use_keyring = use_keyring
        self._cache: dict[str, KeyLookup] = {}
        self._lock = threading.Lock()
        self.warnings: list[str] = []

    def refresh(self) -> None:
        with self._lock:
            self._cache.clear()

    def lookup(self, provider: ProviderConfig) -> KeyLookup:
        with self._lock:
            cached = self._cache.get(provider.name)
            if cached is not None:
                return cached
        result = self._lookup(provider)
        with self._lock:
            self._cache[provider.name] = result
        return result

    # ------------------------------------------------------------------
    def _lookup(self, provider: ProviderConfig) -> KeyLookup:
        if self.use_keyring and self.runner.which("secret-tool"):
            res = self.runner.run(["secret-tool", "lookup", "service", "svoya", "provider", provider.name],
                                  timeout=3.0)
            if res.ok and res.out.strip():
                return KeyLookup(res.out.strip(), "keyring")
        names = [n for n in (provider.api_key_env, f"{provider.name.upper()}_API_KEY", provider.name) if n]
        values, warning = self._read_secrets_env()
        for n in names:
            if values.get(n):
                return KeyLookup(values[n], "secrets.env", warning)
        if provider.api_key_env and self.env.get(provider.api_key_env):
            return KeyLookup(self.env[provider.api_key_env], "env", warning)
        return KeyLookup(None, "none", warning)

    def _read_secrets_env(self) -> tuple[dict[str, str], str | None]:
        path = self.paths.secrets_file
        try:
            st = os.stat(path)
        except OSError:
            return {}, None
        warning = None
        if stat.S_IMODE(st.st_mode) & 0o077 or st.st_uid != os.getuid():
            warning = (f"{path} is readable by other users (mode {stat.S_IMODE(st.st_mode):04o}); "
                       f"run: chmod 600 {path} — better, move keys to the keyring (secret-tool)")
            if warning not in self.warnings:
                self.warnings.append(warning)
        values: dict[str, str] = {}
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    if line.startswith("export "):
                        line = line[7:]
                    name, _, value = line.partition("=")
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                        value = value[1:-1]
                    values[name.strip()] = value
        except OSError:
            return {}, warning
        return values, warning
