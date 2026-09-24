# SPDX-License-Identifier: Apache-2.0
"""Calls into the `svoya` system CLI (owned by cli/), degrading gracefully when it is missing.

Assumed contract (see README "Contract notes"):

* ``svoya status --json``                       — ARCHITECTURE §4.2
* ``svoya snapshot create --reason TEXT --json`` → ``{"id": "<snapshot id>", ...}``
* ``svoya undo [<snapshot id>]``                 — revert to before that snapshot (default: last change)
* ``svoya theme apply <id|auto>``                — ARCHITECTURE §4.1

Fallback for snapshots when `svoya` is absent: ``snapper -c <snapshots.snapper_config>``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .paths import Paths
from .runner import Runner


@dataclass
class Snapshot:
    id: str
    tool: str      # "svoya" | "snapper"


class SvoyaCli:
    def __init__(self, runner: Runner, paths: Paths, snapper_config: str = "") -> None:
        self.runner = runner
        self.paths = paths
        self.snapper_config = snapper_config

    def available(self) -> bool:
        return self.runner.which("svoya") is not None

    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any] | None:
        if not self.available():
            return None
        res = self.runner.run(["svoya", "status", "--json"], timeout=4.0)
        if not res.ok:
            return None
        try:
            data = json.loads(res.out)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    def snapshot(self, reason: str) -> Snapshot | None:
        if self.available():
            res = self.runner.run(["svoya", "snapshot", "create", "--reason", reason, "--json"], timeout=30.0)
            if not res.ok:
                res = self.runner.run(["svoya", "snapshot", "create"], timeout=30.0)
            if res.ok:
                return Snapshot(_parse_snapshot_id(res.out) or "last", "svoya")
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
        if not self.available():
            return False, "the svoya CLI is not installed"
        argv = ["svoya", "undo"] + ([snapshot.id] if snapshot and snapshot.id not in ("", "last") else [])
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
        if not self.available():
            return False, "the svoya CLI is not installed"
        res = self.runner.run(["svoya", "theme", "apply", theme], timeout=20.0)
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
