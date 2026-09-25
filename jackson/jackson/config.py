# SPDX-License-Identifier: Apache-2.0
"""Configuration: built-in defaults < /etc/svoya/jackson.toml < ~/.config/svoya/jackson.toml.

Secrets never live here — see :mod:`jackson.keys`.
"""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import Paths

POLICIES = ("local-only", "eu", "any")
ROUTES = ("auto", "local", "cloud")
PERSONAS = ("kent", "sysop", "dispatcher", "pirate")
AVATARS = ("auto", "imp", "cat", "none")
TASKS = ("chat", "code", "vision", "long")

# Prices are EUR per 1M tokens (input, output), converted at ≈0.86 €/$ on 2026-09-24
# from the providers' public price lists. Override any of them in [pricing].
DEFAULT_PRICING: dict[str, list[float]] = {
    "anthropic/claude-haiku-4-5": [0.86, 4.30],
    "anthropic/claude-sonnet-5": [1.72, 8.60],
    "anthropic/claude-opus-5-5": [3.44, 17.20],
    "anthropic/claude-fable-5-1": [8.60, 43.00],
    "gemini/gemini-3.5-flash-lite": [0.26, 2.15],
    "gemini/gemini-3.8-flash": [0.65, 3.23],
    "gemini/gemini-3.1-pro-preview": [1.72, 10.32],
    "deepseek/deepseek-flash": [0.26, 1.03],      # peak-hour, cache-miss rates
    "deepseek/deepseek-v4-pro": [1.14, 3.41],
    "mistral/mistral-small-latest": [0.09, 0.26],
    "mistral/mistral-medium-latest": [0.34, 1.72],
}

# Fallback price for a cloud model missing from the table (reported as an estimate).
FALLBACK_PRICE = [2.0, 10.0]

DEFAULTS: dict[str, Any] = {
    "language": "ru",
    "address": "ty",            # ty | vy — informal «ты» by default (DESIGN.md §8)
    "persona": "kent",          # kent («Кент из нулевых») | sysop | dispatcher | pirate
    "humor": 1,                 # 0 none · 1 occasional (default) · 2 more
    "avatar": "auto",           # mascot hint for the shell: auto | imp | cat | none
    "allowed_roots": ["~"],
    "max_steps": 8,
    "route": {
        "policy": "local-only",  # local-only | eu | any
        "default": "auto",       # auto | local | cloud
        "offline": False,        # hard switch: nothing leaves the machine, even on explicit request
        "daily_budget_eur": 1.0,
        "prefer_local": True,
        "task": {
            "chat": ["local/*", "ollama/*", "anthropic/claude-haiku-4-5", "mistral/mistral-small-latest",
                     "gemini/gemini-3.5-flash-lite", "deepseek/deepseek-flash"],
            "code": ["local/*", "ollama/*", "anthropic/claude-sonnet-5", "mistral/mistral-medium-latest",
                     "deepseek/deepseek-v4-pro", "gemini/gemini-3.8-flash"],
            "vision": ["local/*", "ollama/*", "anthropic/claude-sonnet-5", "mistral/mistral-medium-latest",
                       "gemini/gemini-3.8-flash", "deepseek/deepseek-flash"],
            "long": ["local/*", "ollama/*", "gemini/gemini-3.8-flash", "anthropic/claude-sonnet-5",
                     "mistral/mistral-medium-latest", "deepseek/deepseek-flash"],
        },
    },
    "providers": {
        # llama.cpp `llama-server` (router mode: --models-dir), OpenAI-compatible.
        "local": {
            "kind": "openai", "label": "llama.cpp", "base_url": "http://127.0.0.1:8080/v1",
            "local": True, "region": "local", "needs_key": False, "models": [],
            "context": {"*": 32768}, "timeout": 180.0, "connect_timeout": 1.0,
        },
        # Ollama (OpenAI-compatible endpoint).
        "ollama": {
            "kind": "openai", "label": "Ollama", "base_url": "http://127.0.0.1:11434/v1",
            "local": True, "region": "local", "needs_key": False, "models": [],
            "context": {"*": 32768}, "timeout": 180.0, "connect_timeout": 1.0,
        },
        "anthropic": {
            "kind": "anthropic", "label": "Anthropic", "base_url": "https://api.anthropic.com",
            "local": False, "region": "us", "needs_key": True, "api_key_env": "ANTHROPIC_API_KEY",
            "models": ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5-5"],
            "vision_models": ["*"], "context": {"*": 200000, "claude-sonnet-5": 1000000,
                                                "claude-opus-5-5": 1000000},
        },
        "gemini": {
            "kind": "gemini", "label": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com",
            "local": False, "region": "us", "needs_key": True, "api_key_env": "GEMINI_API_KEY",
            "models": ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-pro-preview"],
            "vision_models": ["*"], "context": {"*": 1000000},
        },
        "deepseek": {
            "kind": "openai", "label": "DeepSeek", "base_url": "https://api.deepseek.com",
            "local": False, "region": "cn", "needs_key": True, "api_key_env": "DEEPSEEK_API_KEY",
            "models": ["deepseek-flash", "deepseek-v4-pro"], "vision_models": ["deepseek-flash"],
            "context": {"*": 1000000},
        },
        # EU-hosted provider, so that the `eu` policy has a cloud option.
        "mistral": {
            "kind": "openai", "label": "Mistral", "base_url": "https://api.mistral.ai/v1",
            "local": False, "region": "eu", "needs_key": True, "api_key_env": "MISTRAL_API_KEY",
            "models": ["mistral-small-latest", "mistral-medium-latest"],
            "vision_models": ["mistral-medium-latest", "mistral-small-latest"], "context": {"*": 128000},
        },
    },
    "pricing": {},
    # dir: where USER.md / MEMORY.md / journal/ live. Point it into an Obsidian vault (e.g. "~/Obsidian/SOS")
    # and Jackson writes Obsidian-friendly notes there and never touches the rest of the vault unless allowed.
    "memory": {"enabled": True, "dir": "", "obsidian": "auto", "journal": True, "git": True, "snippets": 4,
               "max_chars": 1500},
    "tools": {
        "web_fetch": True, "shell": True, "shell_timeout": 60, "max_read_bytes": 200_000,
        "approval_timeout": 600,
    },
    "snapshots": {"enabled": True, "snapper_config": ""},
    "skills": {"enabled": True, "max_active": 2},
    "mcp": {"on_change": "block", "servers": {}},
    "voice": {"enabled": False},  # v0.2, see jackson/voice.py
}

_TOP_KEYS = set(DEFAULTS)


@dataclass
class ProviderConfig:
    name: str
    kind: str = "openai"
    label: str = ""
    base_url: str = ""
    local: bool = False
    region: str = "other"
    enabled: bool = True
    needs_key: bool = False
    api_key_env: str = ""
    models: list[str] = field(default_factory=list)
    vision_models: list[str] = field(default_factory=list)
    context: dict[str, int] = field(default_factory=dict)
    timeout: float = 60.0
    connect_timeout: float = 5.0
    headers: dict[str, str] = field(default_factory=dict)
    max_tokens: int = 4096
    stream_usage: bool = True

    @property
    def display(self) -> str:
        return self.label or self.name

    def context_for(self, model: str) -> int:
        return int(self.context.get(model) or self.context.get("*") or 8192)

    def has_vision(self, model: str) -> bool:
        if "*" in self.vision_models or model in self.vision_models:
            return True
        if self.local:  # common local VLM naming
            return bool(re.search(r"(^|[-_.])(vl|vision|llava|pixtral|gemma-?3|minicpm-v)([-_.]|$)", model.lower()))
        return False


@dataclass
class RouteConfig:
    policy: str = "local-only"
    default: str = "auto"
    offline: bool = False
    daily_budget_eur: float | None = 1.0
    prefer_local: bool = True
    task: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class McpServerConfig:
    name: str
    command: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    enabled: bool = True
    tier: int = 2
    tool_tiers: dict[str, int] = field(default_factory=dict)
    network: bool = False
    taint: bool = True
    sandbox: bool = True
    rw: list[str] = field(default_factory=list)
    timeout: float = 30.0


@dataclass
class MemoryConfig:
    enabled: bool = True
    dir: str = ""              # empty = ~/.local/share/svoya/jackson/memory
    obsidian: str = "auto"     # auto | on | off
    journal: bool = True
    git: bool = True
    snippets: int = 4
    max_chars: int = 1500


@dataclass
class ToolsConfig:
    web_fetch: bool = True
    shell: bool = True
    shell_timeout: float = 60.0
    max_read_bytes: int = 200_000
    approval_timeout: float = 600.0


@dataclass
class SnapshotConfig:
    enabled: bool = True
    snapper_config: str = ""


@dataclass
class Config:
    language: str = "ru"
    address: str = "ty"
    persona: str = "kent"
    humor: int = 1
    avatar: str = "auto"
    allowed_roots: list[str] = field(default_factory=lambda: ["~"])
    max_steps: int = 8
    route: RouteConfig = field(default_factory=RouteConfig)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    pricing: dict[str, tuple[float, float]] = field(default_factory=dict)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    snapshots: SnapshotConfig = field(default_factory=SnapshotConfig)
    skills_enabled: bool = True
    skills_max_active: int = 2
    mcp_on_change: str = "block"
    mcp_servers: dict[str, McpServerConfig] = field(default_factory=dict)
    voice: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def allowed_root_paths(self, home: Path) -> list[Path]:
        roots = []
        for r in self.allowed_roots:
            if r == "~":
                p = home
            elif r.startswith("~/"):
                p = home / r[2:]
            else:
                p = Path(r)
            if not p.is_absolute():
                continue
            try:
                roots.append(p.resolve())
            except OSError:
                roots.append(p)
        return roots


# ---------------------------------------------------------------------------

def deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_toml(path: Path, warnings: list[str]) -> dict[str, Any] | None:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warnings.append(f"{path}: {exc}")
        return None


def load_config(paths: Paths, override: dict[str, Any] | None = None) -> Config:
    """Load and validate the configuration; problems become ``warnings``, never crashes."""
    warnings: list[str] = []
    sources: list[str] = []
    merged = copy.deepcopy(DEFAULTS)
    for path in (paths.system_config_file, paths.config_file):
        data = _read_toml(path, warnings)
        if data is None:
            continue
        sources.append(str(path))
        for key in data:
            if key not in _TOP_KEYS:
                warnings.append(f"{path}: unknown key {key!r}")
        merged = deep_merge(merged, data)
    if override:
        merged = deep_merge(merged, override)
    return build_config(merged, warnings, sources)


def _as_bool(v: Any, default: bool) -> bool:
    return v if isinstance(v, bool) else default


def _as_num(v: Any, default: float, lo: float | None = None, hi: float | None = None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return default
    if lo is not None and v < lo:
        return default
    if hi is not None and v > hi:
        return default
    return float(v)


def _as_str_list(v: Any) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [str(x) for x in v if isinstance(x, (str, int, float))]
    return []


def _choice(v: Any, allowed: tuple[str, ...], default: str, what: str, warnings: list[str]) -> str:
    if isinstance(v, str) and v in allowed:
        return v
    if v is not None:
        warnings.append(f"{what}: {v!r} is not one of {', '.join(allowed)}; using {default!r}")
    return default


def build_config(data: dict[str, Any], warnings: list[str] | None = None,
                 sources: list[str] | None = None) -> Config:
    warnings = [] if warnings is None else warnings
    cfg = Config(warnings=warnings, sources=sources or [], raw=data)
    lang = str(data.get("language", "ru"))[:2].lower()
    cfg.language = lang if lang in ("ru", "en") else "en"
    cfg.address = _choice(data.get("address"), ("ty", "vy"), "ty", "address", warnings)
    cfg.persona = _choice(data.get("persona"), PERSONAS, "kent", "persona", warnings)
    cfg.humor = int(_as_num(data.get("humor"), 1, 0, 2))
    cfg.avatar = _choice(data.get("avatar"), AVATARS, "auto", "avatar", warnings)
    cfg.allowed_roots = _as_str_list(data.get("allowed_roots")) or ["~"]
    cfg.max_steps = int(_as_num(data.get("max_steps"), 8, 1, 64))

    r = data.get("route") or {}
    budget = r.get("daily_budget_eur", 1.0)
    cfg.route = RouteConfig(
        policy=_choice(r.get("policy"), POLICIES, "local-only", "route.policy", warnings),
        default=_choice(r.get("default"), ROUTES, "auto", "route.default", warnings),
        offline=_as_bool(r.get("offline"), False),
        daily_budget_eur=None if budget is None or (isinstance(budget, (int, float)) and budget < 0)
        else _as_num(budget, 1.0, 0),
        prefer_local=_as_bool(r.get("prefer_local"), True),
        task={k: _as_str_list(v) for k, v in (r.get("task") or {}).items() if k in TASKS},
    )
    for task in TASKS:
        cfg.route.task.setdefault(task, [])

    for name, p in (data.get("providers") or {}).items():
        if not isinstance(p, dict):
            warnings.append(f"providers.{name}: must be a table")
            continue
        kind = _choice(p.get("kind", "openai"), ("openai", "anthropic", "gemini"), "openai",
                       f"providers.{name}.kind", warnings)
        pc = ProviderConfig(
            name=name, kind=kind, label=str(p.get("label", "")),
            base_url=str(p.get("base_url", "")).rstrip("/"),
            local=_as_bool(p.get("local"), False), region=str(p.get("region", "other")),
            enabled=_as_bool(p.get("enabled"), True), needs_key=_as_bool(p.get("needs_key"), not p.get("local")),
            api_key_env=str(p.get("api_key_env", "")), models=_as_str_list(p.get("models")),
            vision_models=_as_str_list(p.get("vision_models")),
            context={str(k): int(v) for k, v in (p.get("context") or {}).items()
                     if isinstance(v, int) and not isinstance(v, bool)},
            timeout=_as_num(p.get("timeout"), 60.0, 1), connect_timeout=_as_num(p.get("connect_timeout"), 5.0, 0.1),
            headers={str(k): str(v) for k, v in (p.get("headers") or {}).items()},
            max_tokens=int(_as_num(p.get("max_tokens"), 4096, 16)),
            stream_usage=_as_bool(p.get("stream_usage"), True),
        )
        if pc.local:
            pc.region = "local"
        if not pc.base_url:
            warnings.append(f"providers.{name}: base_url is empty; provider disabled")
            pc.enabled = False
        cfg.providers[name] = pc

    pricing = dict(DEFAULT_PRICING)
    pricing.update(data.get("pricing") or {})
    for key, value in pricing.items():
        if isinstance(value, dict):
            value = [value.get("input"), value.get("output")]
        if (isinstance(value, list) and len(value) == 2
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value)):
            cfg.pricing[key] = (float(value[0]), float(value[1]))
        else:
            warnings.append(f"pricing.{key}: expected [input, output] EUR per 1M tokens")

    m = data.get("memory") or {}
    obsidian = m.get("obsidian", "auto")
    if isinstance(obsidian, bool):
        obsidian = "on" if obsidian else "off"
    cfg.memory = MemoryConfig(
        enabled=_as_bool(m.get("enabled"), True), dir=str(m.get("dir") or ""),
        obsidian=_choice(obsidian, ("auto", "on", "off"), "auto", "memory.obsidian", warnings),
        journal=_as_bool(m.get("journal"), True),
        git=_as_bool(m.get("git"), True), snippets=int(_as_num(m.get("snippets"), 4, 0, 20)),
        max_chars=int(_as_num(m.get("max_chars"), 1500, 0, 20000)),
    )
    t = data.get("tools") or {}
    cfg.tools = ToolsConfig(
        web_fetch=_as_bool(t.get("web_fetch"), True), shell=_as_bool(t.get("shell"), True),
        shell_timeout=_as_num(t.get("shell_timeout"), 60, 1, 3600),
        max_read_bytes=int(_as_num(t.get("max_read_bytes"), 200_000, 1024)),
        approval_timeout=_as_num(t.get("approval_timeout"), 600, 1),
    )
    s = data.get("snapshots") or {}
    cfg.snapshots = SnapshotConfig(enabled=_as_bool(s.get("enabled"), True),
                                   snapper_config=str(s.get("snapper_config", "")))
    sk = data.get("skills") or {}
    cfg.skills_enabled = _as_bool(sk.get("enabled"), True)
    cfg.skills_max_active = int(_as_num(sk.get("max_active"), 2, 0, 10))

    mcp = data.get("mcp") or {}
    cfg.mcp_on_change = _choice(mcp.get("on_change"), ("block", "warn"), "block", "mcp.on_change", warnings)
    for name, sv in (mcp.get("servers") or {}).items():
        if not isinstance(sv, dict):
            continue
        command = _as_str_list(sv.get("command"))
        if not command:
            warnings.append(f"mcp.servers.{name}: command is empty; server disabled")
        tier = int(_as_num(sv.get("tier"), 2, 0, 4))
        cfg.mcp_servers[name] = McpServerConfig(
            name=name, command=command, env={str(k): str(v) for k, v in (sv.get("env") or {}).items()},
            cwd=str(sv.get("cwd", "")), enabled=_as_bool(sv.get("enabled"), True) and bool(command),
            tier=tier,
            tool_tiers={str(k): int(v) for k, v in (sv.get("tools") or {}).items()
                        if isinstance(v, int) and 0 <= v <= 4},
            network=_as_bool(sv.get("network"), False), taint=_as_bool(sv.get("taint"), True),
            sandbox=_as_bool(sv.get("sandbox"), True), rw=_as_str_list(sv.get("rw")),
            timeout=_as_num(sv.get("timeout"), 30, 1, 3600),
        )
    cfg.voice = dict(data.get("voice") or {})
    return cfg


# ---------------------------------------------------------------------------
# Minimal, comment-preserving TOML editor used by `jackson route set`.

def _toml_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_literal(v) for v in value) + "]"
    raise TypeError(f"unsupported TOML value: {value!r}")


_HEADER = re.compile(r"^\s*\[([^\[\]]+)\]\s*(#.*)?$")


def set_toml_value(path: Path, table: str, key: str, value: Any) -> None:
    """Set ``[table] key = value`` in *path*, keeping comments and layout.

    The result is re-parsed and verified before it replaces the file atomically.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    lines = text.splitlines()
    literal = f"{key} = {_toml_literal(value)}"
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    start = None
    if not table:  # top-level key: lives before the first [table] header
        first = next((i for i, line in enumerate(lines) if _HEADER.match(line) or line.lstrip().startswith("[[")),
                     len(lines))
        for j in range(first):
            if key_re.match(lines[j]):
                lines[j] = literal
                break
        else:
            insert_at = first
            while insert_at > 0 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines.insert(insert_at, literal)
            if insert_at < len(lines) - 1 and lines[insert_at + 1].strip():
                lines.insert(insert_at + 1, "")
        start = -1
    else:
        for i, line in enumerate(lines):
            m = _HEADER.match(line)
            if m and m.group(1).strip() == table:
                start = i
                break
    if start == -1:
        pass
    elif start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"[{table}]", literal]
    else:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if _HEADER.match(lines[j]) or lines[j].lstrip().startswith("[["):
                end = j
                break
        for j in range(start + 1, end):
            if key_re.match(lines[j]):
                lines[j] = literal
                break
        else:
            insert_at = end
            while insert_at > start + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines.insert(insert_at, literal)
    new_text = "\n".join(lines) + "\n"
    parsed = tomllib.loads(new_text)  # raises on a broken result
    node: Any = parsed
    for part in [p for p in table.split(".") if p]:
        node = node.get(part, {}) if isinstance(node, dict) else {}
    if not isinstance(node, dict) or node.get(key) != value:
        raise ValueError(f"could not set {table}.{key} in {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".jackson-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(new_text)
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o777)
        except FileNotFoundError:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
