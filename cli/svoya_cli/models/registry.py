"""``/srv/ai/registry.db`` — what is in the store: hash, source, license, EU/commercial flags,
VRAM estimate, last use (ARCHITECTURE §4.6). Plain SQLite, schema versioned by ``PRAGMA user_version``.

Tables::

    models(id, path UNIQUE, sha256, size, source, repo, revision, filename, format, arch, quant,
           params, n_ctx_train, license, commercial, eu_ok, regions_excluded, vram_bytes, vram_ctx,
           added_at, last_used, meta)
    hashes(path PRIMARY KEY, size, mtime_ns, ino, sha256)       -- hash cache for dedup
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  sha256 TEXT,
  size INTEGER,
  source TEXT,
  repo TEXT,
  revision TEXT,
  filename TEXT,
  format TEXT,
  arch TEXT,
  quant TEXT,
  params INTEGER,
  n_ctx_train INTEGER,
  license TEXT,
  commercial INTEGER,
  eu_ok INTEGER,
  regions_excluded TEXT,
  vram_bytes INTEGER,
  vram_ctx INTEGER,
  added_at TEXT,
  last_used TEXT,
  meta TEXT
);
CREATE INDEX IF NOT EXISTS models_sha256 ON models(sha256);
CREATE INDEX IF NOT EXISTS models_repo ON models(repo);
CREATE TABLE IF NOT EXISTS hashes (
  path TEXT PRIMARY KEY,
  size INTEGER,
  mtime_ns INTEGER,
  ino INTEGER,
  sha256 TEXT
);
"""
COLUMNS = ("path", "sha256", "size", "source", "repo", "revision", "filename", "format", "arch", "quant",
           "params", "n_ctx_train", "license", "commercial", "eu_ok", "regions_excluded", "vram_bytes",
           "vram_ctx", "added_at", "last_used", "meta")


class Registry:
    def __init__(self, path: str | os.PathLike, readonly: bool = False):
        self.path = Path(path)
        self.readonly = readonly
        if readonly:
            self.db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=5)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.path, timeout=10)
            self.db.execute("PRAGMA journal_mode=WAL")
            self._migrate()
        self.db.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: str | os.PathLike) -> "Registry | None":
        """Writable if possible, read-only otherwise, None if it does not exist and cannot be made."""
        try:
            return cls(path)
        except (sqlite3.OperationalError, OSError):
            try:
                return cls(path, readonly=True) if Path(path).exists() else None
            except sqlite3.OperationalError:
                return None

    def _migrate(self) -> None:
        v = self.db.execute("PRAGMA user_version").fetchone()[0]
        if v < 1:
            self.db.executescript(SCHEMA)
            self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.db.commit()
            try:
                os.chmod(self.path, 0o664)   # shared store (group ai)
            except OSError:
                pass

    def close(self) -> None:
        self.db.close()

    # ---- models ----
    def upsert(self, rec: dict[str, Any]) -> None:
        rec = dict(rec)
        if isinstance(rec.get("meta"), (dict, list)):
            rec["meta"] = json.dumps(rec["meta"], ensure_ascii=False)
        if isinstance(rec.get("regions_excluded"), (list, tuple)):
            rec["regions_excluded"] = ",".join(rec["regions_excluded"])
        for k in ("commercial", "eu_ok"):
            if isinstance(rec.get(k), bool):
                rec[k] = int(rec[k])
            elif rec.get(k) == "conditional":
                rec[k] = 2
        cols = [c for c in COLUMNS if c in rec]
        placeholders = ",".join("?" for _ in cols)
        updates = ",".join(f"{c}=COALESCE(excluded.{c},{c})" for c in cols if c != "path")
        sql = f"INSERT INTO models ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(path) DO UPDATE SET {updates}"
        self.db.execute(sql, [rec[c] for c in cols])
        self.db.commit()

    def all(self) -> list[dict]:
        return [self._row(r) for r in self.db.execute("SELECT * FROM models ORDER BY repo, filename, path")]

    def find(self, term: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM models WHERE path=? OR sha256=? OR repo=? OR filename=?",
                               (term, term, term, term))
        return [self._row(r) for r in rows]

    def delete_paths(self, paths: Iterable[str]) -> int:
        n = 0
        for p in paths:
            n += self.db.execute("DELETE FROM models WHERE path=?", (str(p),)).rowcount
            self.db.execute("DELETE FROM hashes WHERE path=?", (str(p),))
        self.db.commit()
        return n

    def touch(self, path: str, when: str) -> None:
        self.db.execute("UPDATE models SET last_used=? WHERE path=?", (when, path))
        self.db.commit()

    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        d = dict(r)
        if d.get("meta"):
            try:
                d["meta"] = json.loads(d["meta"])
            except ValueError:
                pass
        if isinstance(d.get("regions_excluded"), str):
            d["regions_excluded"] = [x for x in d["regions_excluded"].split(",") if x]
        for k in ("commercial", "eu_ok"):
            if d.get(k) == 2:
                d[k] = "conditional"
            elif d.get(k) is not None:
                d[k] = bool(d[k])
        return d

    # ---- hash cache ----
    def cached_hash(self, path: Path, st: os.stat_result) -> str | None:
        row = self.db.execute("SELECT size, mtime_ns, ino, sha256 FROM hashes WHERE path=?", (str(path),)).fetchone()
        if row and row["size"] == st.st_size and row["mtime_ns"] == st.st_mtime_ns and row["ino"] == st.st_ino:
            return row["sha256"]
        return None

    def put_hash(self, path: Path, st: os.stat_result, sha: str) -> None:
        if self.readonly:
            return
        self.db.execute("INSERT OR REPLACE INTO hashes (path, size, mtime_ns, ino, sha256) VALUES (?,?,?,?,?)",
                        (str(path), st.st_size, st.st_mtime_ns, st.st_ino, sha))
        self.db.commit()
