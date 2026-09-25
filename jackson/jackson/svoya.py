# SPDX-License-Identifier: Apache-2.0
"""Calls into the system command (owned by cli/): ``sos``, with ``svoya`` as a fallback alias.
Degrades gracefully when neither is installed.

Assumed contract (see README "Contract notes"):

* ``sos status --json``                       — ARCHITECTURE §4.2
* ``sos snapshot create --reason TEXT --json`` → ``{"id": "<snapshot id>", ...}``
* ``sos undo [<snapshot id>]``                 — revert to before that snapshot (default: last change)
* ``sos theme apply <id|auto>``                — ARCHITECTURE §4.1
* ``sos theme accent <id|word|#hex> --json``   — DESIGN §10 (``{"ok", "accent", "previous", …}``)
* ``sos ai off`` / ``sos ai on``               — the AI switch (WORKFLOWS §8)
* ``sos apps --json`` → ``{"apps": [{"key", "name", "aliases", "installed", …}]}`` and
  ``sos modules list --json`` → ``{"modules": [{"id", "name", "aliases", "installed", …}]}``: what
  ``sos install <word>`` knows (Jackson opens that install in a terminal, the user confirms there)

Fallback for snapshots when neither command exists: ``snapper -c <snapshots.snapper_config>``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from .paths import Paths
from .runner import Runner


@dataclass
class Snapshot:
    id: str
    tool: str      # "sos" | "snapper"


BINARIES = ("sos", "svoya")


class SvoyaCli:
    """Wrapper around the ``sos`` system command (``svoya`` is accepted as a fallback)."""

    def __init__(self, runner: Runner, paths: Paths, snapper_config: str = "") -> None:
        self.runner = runner
        self.paths = paths
        self.snapper_config = snapper_config
        self._catalog: tuple[float, list[dict[str, Any]]] | None = None

    @property
    def binary(self) -> str | None:
        for name in BINARIES:
            if self.runner.which(name):
                return name
        return None

    def available(self) -> bool:
        return self.binary is not None

    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any] | None:
        exe = self.binary
        if exe is None:
            return None
        res = self.runner.run([exe, "status", "--json"], timeout=4.0)
        if not res.ok:
            return None
        try:
            data = json.loads(res.out)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    def snapshot(self, reason: str) -> Snapshot | None:
        exe = self.binary
        if exe is not None:
            res = self.runner.run([exe, "snapshot", "create", "--reason", reason, "--json"], timeout=30.0)
            if not res.ok:
                res = self.runner.run([exe, "snapshot", "create"], timeout=30.0)
            if res.ok:
                return Snapshot(_parse_snapshot_id(res.out) or "last", "sos")
            return None
        if self.snapper_config and self.runner.which("snapper"):
            res = self.runner.run(["snapper", "-c", self.snapper_config, "create", "--description",
                                   reason[:120], "--cleanup-algorithm", "number", "--print-number"],
                                  timeout=30.0)
            if res.ok and res.out.strip().isdigit():
                return Snapshot(res.out.strip(), "snapper")
        return None

    def undo(self, snapshot: Snapshot | None = None) -> tuple[bool, str]:
        if snapshot is not None and snapshot.tool == "snapper":
            if not self.runner.which("snapper"):
                return False, "snapper is not installed"
            res = self.runner.run(["snapper", "-c", self.snapper_config, "undochange", f"{snapshot.id}..0"],
                                  timeout=300.0)
            return res.ok, res.out.strip() or res.why()
        exe = self.binary
        if exe is None:
            return False, "the sos command is not installed"
        argv = [exe, "undo"] + ([snapshot.id] if snapshot and snapshot.id not in ("", "last") else []) + ["--yes"]
        res = self.runner.run(argv, timeout=300.0)
        return res.ok, (res.out.strip() or res.why()) if res.ok else res.why()

    # ------------------------------------------------------------------
    def theme_current(self) -> str | None:
        try:
            data = json.loads(self.paths.theme_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        for key in ("id", "theme", "name"):
            if isinstance(data.get(key), str):
                return data[key]
        return None

    def theme_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self.paths.theme_json.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def theme_apply(self, theme: str) -> tuple[bool, str]:
        exe = self.binary
        if exe is None:
            return False, "the sos command is not installed"
        res = self.runner.run([exe, "theme", "apply", theme], timeout=20.0)
        return res.ok, res.out.strip() if res.ok else res.why()

    # ------------------------------------------------------------------ accent (DESIGN.md §10)
    def accent_current(self) -> str | None:
        """The accent in effect: ``accentId`` from theme.json (``custom`` for a hex), if known."""
        value = self.theme_state().get("accentId")
        return str(value) if value else None

    def accent_set(self, choice: str) -> dict[str, Any]:
        """``sos theme accent <choice> --json`` — sos understands ids, RU/EN names and color words
        («фиолетовым» → lilac) and hex. Returns its JSON (``ok``, ``accent``, ``previous``, ``error``,
        ``hint``) or ``{"ok": False, "error": …}``."""
        exe = self.binary
        if exe is None:
            return {"ok": False, "error": "the sos command is not installed", "missing": True}
        res = self.runner.run([exe, "theme", "accent", *choice.split(), "--json"], timeout=30.0)
        try:
            data = json.loads(res.out) if res.out.strip() else {}
        except ValueError:
            data = {}
        if not isinstance(data, dict) or "ok" not in data:
            return {"ok": False, "error": res.why() if not res.ok else "unexpected output from sos theme accent"}
        return data

    # ------------------------------------------------------------------ the AI switch (WORKFLOWS.md §8)
    def ai_off_later(self) -> bool:
        """Run ``sos ai off`` detached: it stops jacksond itself, so it must outlive this process's turn."""
        exe = self.binary
        if exe is None:
            return False
        return self.runner.spawn([exe, "ai", "off"]) is not None

    # ------------------------------------------------------------------
    def catalog(self) -> list[dict[str, Any]]:
        """Apps and modules `sos install` knows, each with the words that name it (cached 30 s)."""
        exe = self.binary
        if exe is None:
            return []
        now = time.monotonic()
        if self._catalog is not None and now - self._catalog[0] < 30:
            return self._catalog[1]
        items: list[dict[str, Any]] = []
        for argv, key in (([exe, "apps", "--json"], "apps"), ([exe, "modules", "list", "--json"], "modules")):
            res = self.runner.run(argv, timeout=8.0)
            try:
                rows = json.loads(res.out).get(key, []) if res.ok else []
            except (ValueError, AttributeError):
                rows = []
            for r in rows if isinstance(rows, list) else []:
                if not isinstance(r, dict) or not (r.get("key") or r.get("id")):
                    continue
                name = r.get("name")
                names = list(name.values()) if isinstance(name, dict) else [str(name or "")]
                items.append({"key": str(r.get("key") or r.get("id")), "name": next((n for n in names if n), ""),
                              "names": {k: v for k, v in name.items()} if isinstance(name, dict) else {},
                              "kind": "app" if key == "apps" else "module", "installed": bool(r.get("installed")),
                              "proprietary": bool(r.get("proprietary")),
                              "words": [str(r.get("key") or r.get("id")), *names, *map(str, r.get("aliases") or [])]})
        self._catalog = (now, items)
        return items

    def find_installable(self, word: str) -> dict[str, Any] | None:
        w = " ".join(word.lower().replace("ё", "е").split())
        if not w:
            return None
        for item in self.catalog():
            if any(w == x.lower().replace("ё", "е") for x in item["words"] if x):
                return item
        return None

    def ai_on(self) -> tuple[bool, str]:
        exe = self.binary
        if exe is None:
            return False, "the sos command is not installed"
        res = self.runner.run([exe, "ai", "on"], timeout=60.0)
        return res.ok, res.out.strip() if res.ok else res.why()


def _parse_snapshot_id(out: str) -> str | None:
    out = out.strip()
    if not out:
        return None
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            for key in ("id", "snapshot", "number"):
                if data.get(key) is not None:
                    return str(data[key])
    except ValueError:
        pass
    last = out.splitlines()[-1].strip().split()
    return last[-1] if last else None
