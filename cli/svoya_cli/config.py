"""User and system configuration: ``/etc/svoya/svoya.toml`` then ``~/.config/svoya/svoya.toml``.

Keys svoya reads (all optional)::

    [location]            # sunrise/sunset for `sos theme apply auto`
    latitude = 59.437     # default: Tallinn
    longitude = 24.745

    [theme]
    id = "auto"           # auto | graphite | paper | phosphor | <user theme>
    skip = ["kitty"]      # template targets svoya must not touch

    [models]
    region = "EU"         # license checks: EU | UK | US | KR | ... (ISO-ish region code)
    commercial = true     # assume commercial use when judging licenses

    [gpu]
    rocm_backend = "rocm7.2"   # PyTorch wheel index for AMD GPUs
"""
from __future__ import annotations

import tomllib
from typing import Any

from .paths import Paths

DEFAULTS: dict[str, Any] = {
    "location": {"latitude": 59.437, "longitude": 24.745, "name": "Tallinn"},
    "theme": {"id": "auto", "skip": []},
    "models": {"region": "EU", "commercial": True},
    "gpu": {"rocm_backend": "rocm7.2"},
    "session": {"shell": True, "jackson": True},
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _load(path) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def load(paths: Paths | None = None) -> dict[str, Any]:
    paths = paths or Paths()
    cfg = _merge(DEFAULTS, _load(paths.system_config))
    cfg = _merge(cfg, _load(paths.user_config))
    loc = cfg.get("location", {})
    # accept lat/lon shorthands (defaults never contain them, so presence means the user set them)
    if "lat" in loc:
        loc["latitude"] = loc["lat"]
    if "lon" in loc:
        loc["longitude"] = loc["lon"]
    return cfg


def set_user_value(paths: Paths, section: str, key: str, value: str) -> None:
    """Set ``[section] key = "value"`` in ~/.config/svoya/svoya.toml, keeping comments and order."""
    import json
    import re
    from .util import atomic_write
    path = paths.user_config
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = ["# SOS user settings (see `sos help`)."]
    new = f"{key} = {json.dumps(value, ensure_ascii=False)}"
    cur, start, done = "", None, False
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", ln)
        if m:
            if cur == section and not done:
                lines.insert(i, new)
                done = True
                break
            cur = m.group(1).strip()
            if cur == section:
                start = i
            continue
        if cur == section and re.match(rf"^\s*{re.escape(key)}\s*=", ln):
            lines[i] = new
            done = True
            break
    if not done:
        if start is not None:
            lines.append(new)
        else:
            lines += ["", f"[{section}]", new]
    atomic_write(path, "\n".join(lines).strip("\n") + "\n")
