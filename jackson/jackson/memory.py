# SPDX-License-Identifier: Apache-2.0
"""Memory as plain Markdown: USER.md, MEMORY.md and journal/YYYY-MM-DD.md in
~/.local/share/svoya/jackson/memory/, indexed with SQLite FTS5.

Every write is reversible (the previous content is kept in a content-addressed store) and
announced to the client by the caller. When `git` is available the directory is also a git
repository with one commit per change, so the history is readable with ordinary tools.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import sqlite3
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import MemoryConfig
from .paths import Paths
from .runner import Runner

JOURNAL_RE = re.compile(r"^journal/\d{4}-\d{2}-\d{2}\.md$")
FILES = ("USER.md", "MEMORY.md")

HEADERS = {
    "USER.md": {"ru": "# Обо мне\n\n<!-- Что Джексон знает о тебе. Файл можно править руками. -->\n",
                "en": "# About me\n\n<!-- What Jackson knows about you. Edit freely. -->\n"},
    "MEMORY.md": {"ru": "# Память\n\n<!-- Долгосрочные заметки Джексона. Файл можно править руками. -->\n",
                  "en": "# Memory\n\n<!-- Jackson's long-term notes. Edit freely. -->\n"},
}

STOPWORDS = set("""
что как это мне меня мой моя мое моё мои для про или где когда какой какая какое какие есть был была были
ты вы я он она оно они мы и в во на с со у о об по за из от до не ни ли же бы то а но да нет пожалуйста
джексон скажи расскажи покажи можешь надо нужно очень тебя тебе твой твоя свой
the a an is are was were what how my me you your for and or of to in on with it this that please jackson
do does did can could would should tell show about from have has had be been
""".split())


def normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def _stem(word: str) -> str:
    if re.search(r"[а-я]", word):
        if len(word) > 5:
            return word[:max(4, len(word) - 2)]
        return word
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def fts_query(text: str) -> str | None:
    terms: list[str] = []
    for word in re.findall(r"\w+", normalize(text)):
        if len(word) < 3 or word in STOPWORDS or (word.isdigit() and len(word) < 4):
            continue
        stem = _stem(word).replace('"', "")
        if stem:
            terms.append(f'"{stem}"*')
    terms = list(dict.fromkeys(terms))[:16]
    return " OR ".join(terms) if terms else None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Snippet:
    file: str
    line: int
    text: str
    score: float = 0.0


@dataclass
class MemoryChange:
    file: str
    prev_sha256: str
    new_sha256: str
    summary: str
    lines: list[str] = field(default_factory=list)

    def undo_data(self) -> dict[str, Any]:
        return {"file": self.file, "prev": self.prev_sha256, "sha256": self.new_sha256}


class MemoryFileError(Exception):
    pass


class Memory:
    def __init__(self, paths: Paths, config: MemoryConfig | None = None, runner: Runner | None = None,
                 lang: str = "ru") -> None:
        self.paths = paths
        self.config = config or MemoryConfig()
        self.runner = runner or Runner()
        self.lang = lang
        self.dir = paths.memory_dir
        self.blobs = paths.undo_store / "memory"
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    def ensure(self) -> None:
        with self._lock:
            self.paths.ensure_data_dir()
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / "journal").mkdir(exist_ok=True)
            for name in FILES:
                p = self.dir / name
                if not p.exists():
                    p.write_text(HEADERS[name].get(self.lang, HEADERS[name]["en"]), encoding="utf-8")
            if self.config.git:
                self._git_init()

    def path_of(self, name: str) -> Path:
        if name in FILES or JOURNAL_RE.match(name):
            return self.dir / name
        raise MemoryFileError(f"not a memory file: {name}")

    def read(self, name: str) -> str:
        try:
            return self.path_of(name).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def files(self) -> list[str]:
        names = [n for n in FILES if (self.dir / n).exists()]
        jdir = self.dir / "journal"
        if jdir.is_dir():
            names += [f"journal/{p.name}" for p in sorted(jdir.glob("*.md")) if JOURNAL_RE.match(f"journal/{p.name}")]
        return names

    # ------------------------------------------------------------------
    def _store_blob(self, text: str) -> str:
        digest = sha256_text(text)
        self.blobs.mkdir(parents=True, exist_ok=True)
        blob = self.blobs / f"{digest}.md"
        if not blob.exists():
            blob.write_text(text, encoding="utf-8")
        return digest

    def _write(self, name: str, text: str, message: str) -> MemoryChange:
        path = self.path_of(name)
        prev = self.read(name)
        prev_sha = self._store_blob(prev)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".mem-", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        self._git_commit(message)
        self.reindex()
        return MemoryChange(name, prev_sha, sha256_text(text), message)

    def remember(self, text: str, target: str = "memory", today: dt.date | None = None) -> MemoryChange:
        text = " ".join(text.split())
        if not text:
            raise MemoryFileError("empty memory")
        name = "USER.md" if target == "user" else "MEMORY.md"
        with self._lock:
            self.ensure()
            current = self.read(name)
            line = f"- {(today or dt.date.today()).isoformat()} · {text}"
            if line.split(" · ", 1)[1] in current:
                return MemoryChange(name, sha256_text(current), sha256_text(current), "already known", [])
            new = current.rstrip("\n") + "\n" + line + "\n"
            change = self._write(name, new, f"remember: {text[:60]}")
            change.lines = [line]
            return change

    def forget(self, query: str) -> list[MemoryChange]:
        needle = normalize(query.strip())
        if len(needle) < 2:
            raise MemoryFileError("query too short")
        changes = []
        with self._lock:
            for name in FILES:
                current = self.read(name)
                kept, removed = [], []
                for line in current.splitlines():
                    if line.lstrip().startswith(("- ", "* ")) and needle in normalize(line):
                        removed.append(line)
                    else:
                        kept.append(line)
                if removed:
                    change = self._write(name, "\n".join(kept) + "\n", f"forget: {query[:60]}")
                    change.lines = removed
                    changes.append(change)
        return changes

    def journal(self, entry: str, when: dt.datetime | None = None) -> MemoryChange:
        when = when or dt.datetime.now()
        name = f"journal/{when.strftime('%Y-%m-%d')}.md"
        entry = " ".join(entry.split())
        with self._lock:
            self.ensure()
            current = self.read(name) or f"# {when.strftime('%Y-%m-%d')}\n\n"
            line = f"- {when.strftime('%H:%M')} · {entry}"
            change = self._write(name, current.rstrip("\n") + "\n" + line + "\n", f"journal: {entry[:60]}")
            change.lines = [line]
            return change

    def restore(self, name: str, prev_sha256: str, expected_sha256: str | None = None) -> None:
        """Undo: put back the content with hash *prev_sha256* (if the file was not edited since)."""
        from .undo import UndoError
        with self._lock:
            current = self.read(name)
            if expected_sha256 and sha256_text(current) != expected_sha256:
                raise UndoError("undo.changed", path=str(self.path_of(name)))
            blob = self.blobs / f"{prev_sha256}.md"
            try:
                prev = blob.read_text(encoding="utf-8")
            except FileNotFoundError:
                raise UndoError("undo.prev_gone", name=name) from None
            self._write(name, prev, f"undo: {name}")

    def undo_handler(self, action: Any) -> str:
        self.restore(action.data["file"], action.data["prev"], action.data.get("sha256"))
        return f"{action.data['file']} restored"

    # ------------------------------------------------------------------
    # FTS5 index

    def _db(self) -> sqlite3.Connection:
        self.paths.ensure_data_dir()
        db = sqlite3.connect(str(self.paths.index_db), timeout=5.0)
        db.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER)")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5("
                   "path UNINDEXED, line UNINDEXED, text, tokenize='unicode61 remove_diacritics 2')")
        return db

    @staticmethod
    def _chunks(text: str) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        para: list[str] = []
        start = 0
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("<!--", "#")):
                if para:
                    out.append((start, " ".join(para)))
                    para = []
                continue
            if stripped.startswith(("- ", "* ")) or re.match(r"^\d+[.)] ", stripped):
                if para:
                    out.append((start, " ".join(para)))
                    para = []
                out.append((i, stripped))
                continue
            if not para:
                start = i
            para.append(stripped)
        if para:
            out.append((start, " ".join(para)))
        return [(n, c[:1000]) for n, c in out]

    def reindex(self, force: bool = False) -> int:
        """Re-index changed files; returns the number of files indexed."""
        if not self.dir.is_dir():
            return 0
        with self._lock:
            db = self._db()
            try:
                known = {row[0]: (row[1], row[2]) for row in db.execute("SELECT path, mtime, size FROM files")}
                present = set()
                count = 0
                for name in self.files():
                    p = self.dir / name
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    present.add(name)
                    if not force and known.get(name) == (st.st_mtime, st.st_size):
                        continue
                    db.execute("DELETE FROM chunks WHERE path = ?", (name,))
                    text = p.read_text(encoding="utf-8", errors="replace")
                    db.executemany("INSERT INTO chunks(path, line, text) VALUES (?, ?, ?)",
                                   [(name, n, normalize(c)) for n, c in self._chunks(text)])
                    db.execute("INSERT OR REPLACE INTO files(path, mtime, size) VALUES (?, ?, ?)",
                               (name, st.st_mtime, st.st_size))
                    count += 1
                for gone in set(known) - present:
                    db.execute("DELETE FROM chunks WHERE path = ?", (gone,))
                    db.execute("DELETE FROM files WHERE path = ?", (gone,))
                db.commit()
                return count
            finally:
                db.close()

    def search(self, query: str, limit: int = 5) -> list[Snippet]:
        q = fts_query(query)
        if not q or not self.dir.is_dir():
            return []
        self.reindex()
        db = self._db()
        try:
            rows = db.execute("SELECT path, line, text, bm25(chunks) AS score FROM chunks WHERE chunks MATCH ? "
                              "ORDER BY score LIMIT ?", (q, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            db.close()
        # Return the original (non-normalized) line text.
        out = []
        for path, line, text, score in rows:
            original = self._line_text(path, int(line)) or text
            out.append(Snippet(path, int(line), original, float(score)))
        return out

    def _line_text(self, name: str, line: int) -> str | None:
        try:
            lines = self.read(name).splitlines()
            return lines[line - 1].strip() if 0 < line <= len(lines) else None
        except MemoryFileError:
            return None

    def relevant(self, query: str, limit: int | None = None, max_chars: int | None = None) -> str:
        """Prompt block: USER.md (always, capped) + the most relevant snippets."""
        if not self.config.enabled or not self.dir.is_dir():
            return ""
        limit = self.config.snippets if limit is None else limit
        max_chars = self.config.max_chars if max_chars is None else max_chars
        parts = []
        user = "\n".join(line for line in self.read("USER.md").splitlines()
                         if line.strip() and not line.startswith(("#", "<!--"))).strip()
        if user:
            parts.append("USER.md:\n" + user[: max_chars // 2])
        used = sum(len(p) for p in parts)
        snippets = [s for s in self.search(query, limit) if s.file != "USER.md"] if limit else []
        lines = []
        for s in snippets:
            item = f"- {s.file}:{s.line} {s.text}"
            if used + len(item) > max_chars:
                break
            lines.append(item)
            used += len(item)
        if lines:
            parts.append("\n".join(lines))
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # git (optional, best effort, never touches a repository other than memory/.git)

    def _git_env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL")}
        env.update({"GIT_DIR": str(self.dir / ".git"), "GIT_WORK_TREE": str(self.dir),
                    "GIT_AUTHOR_NAME": "Jackson", "GIT_AUTHOR_EMAIL": "jackson@localhost",
                    "GIT_COMMITTER_NAME": "Jackson", "GIT_COMMITTER_EMAIL": "jackson@localhost",
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
        return env

    def _git_init(self) -> None:
        if (self.dir / ".git").is_dir() or not self.runner.which("git"):
            return
        self.runner.run(["git", "init", "-q", str(self.dir)], timeout=10.0, env=self._git_env())

    def _git_commit(self, message: str) -> None:
        if not self.config.git or not (self.dir / ".git").is_dir() or not self.runner.which("git"):
            return
        env = self._git_env()
        self.runner.run(["git", "add", "-A"], timeout=10.0, env=env, cwd=str(self.dir))
        self.runner.run(["git", "commit", "-q", "--no-verify", "--no-gpg-sign", "-m", message],
                        timeout=10.0, env=env, cwd=str(self.dir))
