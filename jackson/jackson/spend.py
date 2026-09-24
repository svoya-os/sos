# SPDX-License-Identifier: Apache-2.0
"""Daily cloud spend and "data left the machine" counters (control center: AI & privacy)."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

KEEP_DAYS = 90


class SpendLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    @staticmethod
    def today_key(now: dt.datetime | None = None) -> str:
        return (now or dt.datetime.now()).strftime("%Y-%m-%d")

    def _load(self) -> dict[str, Any]:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("days"), dict):
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "days": {}}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".spend-", dir=str(self.path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def add(self, cost_eur: float, left_machine: bool, now: dt.datetime | None = None) -> None:
        if cost_eur <= 0 and not left_machine:
            return
        with self._lock:
            data = self._load()
            day = data["days"].setdefault(self.today_key(now), {"eur": 0.0, "left": 0})
            day["eur"] = round(float(day.get("eur", 0.0)) + max(0.0, cost_eur), 6)
            day["left"] = int(day.get("left", 0)) + (1 if left_machine else 0)
            for key in sorted(data["days"])[:-KEEP_DAYS]:
                del data["days"][key]
            self._save(data)

    def today(self, now: dt.datetime | None = None) -> dict[str, float]:
        with self._lock:
            day = self._load()["days"].get(self.today_key(now), {})
        return {"eur": float(day.get("eur", 0.0)), "left": int(day.get("left", 0))}
