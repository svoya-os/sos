"""User and system configuration: ``/etc/svoya/svoya.toml`` then ``~/.config/svoya/svoya.toml``.

Keys svoya reads (all optional)::

    [location]            # sunrise/sunset for `svoya theme apply auto`
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
