# SPDX-License-Identifier: Apache-2.0
"""Permission tiers T0–T4 (docs/ARCHITECTURE.md §4.4), project grants and taint tracking.

| Tier | What                                   | Policy                                        |
|------|----------------------------------------|-----------------------------------------------|
| T0   | read-only                              | runs freely                                   |
| T1   | reversible local writes                | auto, snapshot first                          |
| T2   | external side effects                  | confirm against the exact preview             |
| T3   | root/system changes                    | confirm (once), polkit + snapshot             |
| T4   | secrets                                | denied unless granted for this one task       |

Taint: once untrusted content (web pages, downloaded files, network tool output, clipboard)
enters the conversation, any call with an external side effect needs a fresh T2 confirmation;
standing "always in this project" grants do not apply to tainted conversations.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .i18n import t
from .tools.base import Assessment

DECISIONS = ("once", "always-project", "deny")
PROJECT_MARKERS = (".git", ".svoya-project", "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
                   "pixi.toml", "Makefile", "CMakeLists.txt")


def project_root(cwd: Path | None, home: Path) -> Path:
    """Project for grants: nearest ancestor with a project marker, else *cwd*, else home."""
    if cwd is None:
        return home
    try:
        cwd = cwd.resolve()
        home_r = home.resolve()
    except OSError:
        return home
    for candidate in (cwd, *cwd.parents):
        if candidate == home_r or candidate == Path(candidate.anchor):
            break
        if any((candidate / m).exists() for m in PROJECT_MARKERS):
            return candidate
    return cwd


class Taint:
    """Untrusted-content sources seen in a conversation."""

    def __init__(self) -> None:
        self.sources: list[str] = []

    def add(self, label: str | None) -> bool:
        if label and label not in self.sources:
            self.sources.append(label)
            return True
        return False

    def clear(self) -> None:
        self.sources.clear()

    def __bool__(self) -> bool:
        return bool(self.sources)

    def label(self) -> str:
        shown = self.sources[:3]
        return ", ".join(shown) + ("…" if len(self.sources) > 3 else "")


@dataclass
class Verdict:
    action: str                     # allow | ask | deny
    tier: int
    reasons: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    grant: str | None = None        # which grant allowed it (for the audit log)


class Grants:
    """Standing "always in this project" grants — ~/.local/share/svoya/jackson/grants.json."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            grants = data.get("grants") if isinstance(data, dict) else None
            return [g for g in grants or [] if isinstance(g, dict)]
        except (OSError, ValueError):
            return []

    def _save(self, grants: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".grants-", dir=str(self.path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "grants": grants}, fh, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load()

    def has(self, project: Path, tool: str, scope: str) -> bool:
        proj = str(project)
        with self._lock:
            for g in self._load():
                if g.get("project") == proj and g.get("tool") == tool and g.get("scope") in (scope, "*"):
                    return True
        return False

    def add(self, project: Path, tool: str, scope: str, tier: int) -> dict[str, Any]:
        grant = {"project": str(project), "tool": tool, "scope": scope, "tier": tier,
                 "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        with self._lock:
            grants = [g for g in self._load()
                      if not (g.get("project") == grant["project"] and g.get("tool") == tool
                              and g.get("scope") == scope)]
            grants.append(grant)
            self._save(grants)
        return grant

    def revoke(self, project: str | None = None, tool: str | None = None) -> int:
        with self._lock:
            grants = self._load()
            keep = [g for g in grants
                    if not ((project is None or g.get("project") == project)
                            and (tool is None or g.get("tool") == tool))]
            self._save(keep)
        return len(grants) - len(keep)


class Permissions:
    def __init__(self, grants: Grants) -> None:
        self.grants = grants

    def evaluate(self, tool: str, a: Assessment, project: Path, taint: Taint,
                 task_grants: set[tuple[str, str]], lang: str = "ru") -> Verdict:
        reasons = list(a.reasons)
        if a.blocked:
            return Verdict("deny", a.tier, reasons + [a.blocked])
        tier = a.tier
        tainted_external = a.external and bool(taint)
        if tainted_external:
            reasons.append(t("approval.reason.taint", lang, sources=taint.label()))
        if tier >= 4:
            if (tool, a.scope) in task_grants:
                return Verdict("allow", tier, reasons, grant="task")
            return Verdict("ask", tier, reasons + [t("approval.reason.t4", lang)], ["once", "deny"])
        if tier == 3:
            return Verdict("ask", tier, reasons + [t("approval.reason.t3", lang)], ["once", "deny"])
        if tainted_external:
            return Verdict("ask", max(tier, 2), reasons, ["once", "deny"])
        if tier == 2:
            if self.grants.has(project, tool, a.scope):
                return Verdict("allow", tier, reasons, grant=f"project:{project}")
            return Verdict("ask", tier, reasons + [t("approval.reason.t2", lang)], list(DECISIONS))
        return Verdict("allow", tier, reasons)
