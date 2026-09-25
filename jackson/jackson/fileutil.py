# SPDX-License-Identifier: Apache-2.0
"""Small file helpers shared by tools and the undo registry (no internal imports: no cycles)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IsADirectoryError):
        return None
