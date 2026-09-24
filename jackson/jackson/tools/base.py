# SPDX-License-Identifier: Apache-2.0
"""Tool registry with permission-tier metadata (docs/ARCHITECTURE.md §4.4)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..providers.base import CancelToken, ToolSpec

if TYPE_CHECKING:  # pragma: no cover
    from ..config import Config
    from ..memory import Memory
    from ..paths import Paths
    from ..runner import Runner
    from ..sandbox import Sandbox
    from ..svoya import SvoyaCli
    from ..undo import UndoLog

T0, T1, T2, T3, T4 = 0, 1, 2, 3, 4

# Effects vocabulary: read, write, exec, network (talks to the outside), send (pushes data out),
# system (root/system change), secret.
EXTERNAL_EFFECTS = frozenset({"network", "send"})


@dataclass
class Assessment:
    """How risky one concrete call is (the tier can depend on the arguments)."""

    tier: int
    preview: str = ""
    scope: str = "*"            # grant scope for "always in this project"
    external: bool = False      # has an external side effect (data may leave the machine)
    reasons: list[str] = field(default_factory=list)
    blocked: str | None = None  # never allowed, not even with approval


@dataclass
class UndoSpec:
    kind: str
    summary: str
    data: dict[str, Any]
    auto: bool = False          # bookkeeping entries are skipped by "undo last"


@dataclass
class ToolResult:
    ok: bool
    content: str                     # what the model sees
    summary: str = ""                # what the user sees in the `tool` event
    data: Any = None
    undo: list[UndoSpec] = field(default_factory=list)
    verified: bool | None = None     # the effect was checked after the action
    taint: str | None = None         # label of untrusted content that entered the turn
    left_to: str | None = None       # where data went (host/provider)


@dataclass
class ToolContext:
    paths: "Paths"
    config: "Config"
    lang: str
    cwd: Path
    project: Path | None
    runner: "Runner"
    svoya: "SvoyaCli"
    undo: "UndoLog"
    memory: "Memory | None"
    sandbox: "Sandbox"
    cancel: CancelToken
    turn_id: str = ""
    client: str = ""
    tainted: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed_roots(self) -> list[Path]:
        return self.config.allowed_root_paths(self.paths.home)


ToolFn = Callable[[ToolContext, dict[str, Any]], ToolResult]
AssessFn = Callable[[ToolContext, dict[str, Any]], Assessment]

_WIRE_RE = re.compile(r"[^A-Za-z0-9_-]")


def wire_name(name: str) -> str:
    """Tool names on the wire: ``fs.read`` → ``fs__read``; ≤ 64 chars, [A-Za-z0-9_-]."""
    wire = _WIRE_RE.sub("_", name.replace(".", "__"))
    if len(wire) > 64:
        digest = hashlib.sha256(name.encode()).hexdigest()[:8]
        wire = wire[:55] + "_" + digest
    return wire


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: ToolFn
    tier: int = T0
    effects: frozenset[str] = frozenset({"read"})
    assess: AssessFn | None = None
    title: dict[str, str] = field(default_factory=dict)
    timeout: float = 60.0
    source: str = "builtin"

    @property
    def wire(self) -> str:
        return wire_name(self.name)

    def assessment(self, ctx: ToolContext, args: dict[str, Any]) -> Assessment:
        if self.assess is not None:
            a = self.assess(ctx, args)
        else:
            a = Assessment(tier=self.tier)
        if not a.preview:
            a.preview = f"{self.name} {json.dumps(args, ensure_ascii=False, indent=2, sort_keys=True)}"
        if self.effects & EXTERNAL_EFFECTS:
            a.external = True
        return a

    def spec(self) -> ToolSpec:
        return ToolSpec(self.wire, self.description, self.parameters)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def by_wire(self, wire: str) -> Tool | None:
        for tool in self._tools.values():
            if tool.wire == wire or tool.name == wire:
                return tool
        return None

    def names(self) -> list[str]:
        return sorted(self._tools)

    def tools(self) -> list[Tool]:
        return [self._tools[n] for n in sorted(self._tools)]

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self.tools()]


# ---------------------------------------------------------------------------
# Minimal JSON-schema argument check (types, required, enum) — enough to give
# the model an actionable error instead of a crash.

_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,), "integer": (int,), "number": (int, float), "boolean": (bool,),
    "array": (list,), "object": (dict,),
}


def validate_args(schema: dict[str, Any], args: Any) -> str | None:
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    for req in schema.get("required") or []:
        if req not in args:
            return f"missing required argument {req!r}"
    props = schema.get("properties") or {}
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            if schema.get("additionalProperties") is False:
                return f"unknown argument {key!r}"
            continue
        expected = spec.get("type")
        if isinstance(expected, str) and expected in _TYPES:
            ok = isinstance(value, _TYPES[expected])
            if expected in ("integer", "number") and isinstance(value, bool):
                ok = False
            if not ok:
                return f"argument {key!r} must be of type {expected}"
        if "enum" in spec and value not in spec["enum"]:
            return f"argument {key!r} must be one of {spec['enum']}"
    return None


def obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """Shorthand for an object schema."""
    return {"type": "object", "properties": properties, "required": required or [],
            "additionalProperties": False}
