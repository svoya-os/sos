# SPDX-License-Identifier: Apache-2.0
"""Composition root: builds every component once, for the background service and for the
CLI's in-process mode alike."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Mapping

from . import aiswitch
from . import avatar as avatar_mod
from .audit import AuditLog
from .config import Config, load_config
from .engine import Engine
from .keys import KeyStore
from .memory import Memory
from .osctl import OsControl
from .paths import Paths
from .permissions import Grants, Permissions
from .persona import persona_info
from .providers import Provider, make_provider
from .router import HealthCache, RouteError, Router
from .runner import Runner
from .sandbox import Sandbox
from .skills import Skills
from .spend import SpendLedger
from .svoya import SvoyaCli
from .tools import default_registry
from .tools.mcp import McpManager, key_lookup_from
from .tools.notes import notes_tools
from .trash import Trash
from .undo import UndoLog

log = logging.getLogger("jackson")


class Jackson:
    def __init__(self, paths: Paths | None = None, config: Config | None = None, runner: Runner | None = None,
                 providers: dict[str, Provider] | None = None, env: Mapping[str, str] | None = None,
                 use_keyring: bool = True) -> None:
        self.paths = paths or Paths.from_env(env)
        self.config = config or load_config(self.paths)
        self.runner = runner or Runner()
        self.keys = KeyStore(self.paths, self.runner, env, use_keyring=use_keyring)
        self.audit = AuditLog(self.paths.audit_file, self.paths.audit_head)
        self.svoya = SvoyaCli(self.runner, self.paths, self.config.snapshots.snapper_config)
        self.trash = Trash(self.paths.trash_dir)
        self.undo = UndoLog(self.paths.actions_file, self.trash, self.svoya, self.audit)
        self.memory: Memory | None = (Memory(self.paths, self.config.memory, self.runner, self.config.language)
                                      if self.config.memory.enabled else None)
        self.sandbox = Sandbox(self.paths, self.runner)
        self.registry = default_registry(self.config)
        if self.memory is not None:
            for tool in notes_tools():
                self.registry.register(tool)
        if providers is None:
            providers = {name: make_provider(pc) for name, pc in self.config.providers.items() if pc.enabled}
        self.providers = providers
        self.health = HealthCache(self.providers)
        self.spend = SpendLedger(self.paths.spend_file)
        self._local_start_at = -1e9
        self.router = Router(self.config, self.providers, self.health, self.spend, key_check=self.key_check,
                             local_starter=self.start_local_models, local_installed=self.has_local_model)
        self.grants = Grants(self.paths.grants_file)
        self.permissions = Permissions(self.grants)
        self.skills = Skills(self.paths.skills_dir, self.config.skills_max_active)
        self.osc = OsControl(self.runner, self.paths, self.svoya)
        self.mcp = McpManager(self.config, self.paths, self.sandbox, self.registry, self.audit,
                              key_lookup_from(self.keys))
        self.avatar = avatar_mod.load(self.paths.avatar_file)
        self._avatar_stamp = avatar_mod.stamp(self.paths.avatar_file)
        self.engine = Engine(self)
        self._stamp = self._config_stamp()

    # ------------------------------------------------------------------
    def key_check(self, name: str) -> bool:
        """Is the provider usable key-wise? Looks the key up lazily (keyring → secrets.env → env)."""
        prov = self.providers.get(name)
        if prov is None:
            return False
        if prov.api_key:
            return True
        if not prov.cfg.needs_key:
            return True
        found = self.keys.lookup(prov.cfg)
        if found.key:
            prov.api_key = found.key
        return bool(found.key)

    def has_local_model(self) -> bool:
        """Is a GGUF model in the shared store (``$HF_HOME/hub``, default /srv/ai)?"""
        hub = Path(os.environ.get("HF_HOME") or "/srv/ai") / "hub"
        try:
            return any(True for _ in hub.glob("models--*/snapshots/*/*.gguf"))
        except OSError:
            return False

    def start_local_models(self) -> bool:
        """The router found every local model server down: `sos models serve`, if a model is installed
        — at most once in 2 minutes."""
        now = time.monotonic()
        if now - self._local_start_at < 120:
            return False
        sos = shutil.which("sos") or shutil.which("svoya")
        if not sos or not self.has_local_model():
            return False
        self._local_start_at = now
        log.info("starting the local model server (sos models serve)")
        res = self.runner.run([sos, "models", "serve"], timeout=60)
        return res.ok

    def local_provider_names(self) -> list[str]:
        return [n for n, p in self.providers.items() if p.cfg.local and p.cfg.enabled]

    def refresh_health(self, timeout: float = 0.8) -> None:
        self.health.refresh(self.local_provider_names(), timeout=timeout)

    def route_preview(self, lang: str | None = None) -> dict[str, Any]:
        rc = self.config.route
        info: dict[str, Any] = {"mode": rc.default, "policy": rc.policy, "offline": rc.offline}
        try:
            d = self.router.decide("", {}, None, lang or self.config.language)
            info.update({"model": d.chosen.model, "provider": d.chosen.provider, "local": d.chosen.local,
                         "label": d.chosen.label, "reason": d.reason})
        except RouteError as exc:
            info.update({"model": None, "provider": None, "local": True, "reason": exc.message})
        return info

    def persona(self, lang: str | None = None) -> dict[str, Any]:
        return persona_info(self.config, lang or self.config.language)

    # --- look and name (~/.config/svoya/avatar.json) -------------------------------------------
    def name(self, lang: str | None = None) -> str:
        return self.avatar.display_name(lang or self.config.language)

    def avatar_changed(self) -> bool:
        return avatar_mod.stamp(self.paths.avatar_file) != self._avatar_stamp

    def reload_avatar(self) -> bool:
        """Re-read avatar.json; True when the look or name actually changed."""
        self._avatar_stamp = avatar_mod.stamp(self.paths.avatar_file)
        new = avatar_mod.load(self.paths.avatar_file)
        changed = new.data != self.avatar.data
        self.avatar = new
        return changed

    def state_extra(self) -> dict[str, Any]:
        """Fields every `state` event carries for the shell's mascot."""
        return {"persona": self.config.persona, "avatar": self.avatar.to_event()}

    # --- the AI switch -------------------------------------------------------------------------
    def ai_state(self) -> dict[str, Any]:
        return aiswitch.state(self.paths)

    def start_background(self) -> list[str]:
        """Things the long-running service does once at start (MCP servers, index)."""
        warnings = list(self.config.warnings)
        if aiswitch.off_reason(self.paths):
            return warnings + ["AI is switched off (sos ai off): not starting MCP servers"]
        if self.memory is not None:
            try:
                self.memory.ensure()
                self.memory.reindex()
            except OSError as exc:
                warnings.append(f"memory: {exc}")
        try:
            warnings += self.mcp.start_all()
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(f"mcp: {exc}")
        for w in self.keys.warnings:
            warnings.append(w)
        return warnings

    def _config_stamp(self) -> tuple[float, ...]:
        stamps = []
        for path in (self.paths.system_config_file, self.paths.config_file):
            try:
                stamps.append(path.stat().st_mtime)
            except OSError:
                stamps.append(0.0)
        return tuple(stamps)

    def config_changed(self) -> bool:
        stamp = self._config_stamp()
        if not hasattr(self, "_stamp"):
            self._stamp = stamp
            return False
        return stamp != self._stamp

    def reload_config(self) -> list[str]:
        """Apply edited settings without a restart (route, persona, language, pricing, tools)."""
        self._stamp = self._config_stamp()
        new = load_config(self.paths)
        changed = []
        for attr in ("language", "address", "persona", "humor", "max_steps", "route", "pricing",
                     "tools", "snapshots", "skills_enabled", "skills_max_active", "mcp_on_change"):
            if getattr(self.config, attr) != getattr(new, attr):
                setattr(self.config, attr, getattr(new, attr))
                changed.append(attr)
        self.config.warnings = new.warnings
        if new.memory != self.config.memory or new.mcp_servers != self.config.mcp_servers \
                or new.providers != self.config.providers:
            changed.append("restart needed for memory/mcp/providers changes")
        return changed

    def close(self) -> None:
        self.mcp.stop_all()
