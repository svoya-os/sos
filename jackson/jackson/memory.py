# SPDX-License-Identifier: Apache-2.0
"""Memory as plain Markdown, indexed with SQLite FTS5.

Files (inside Jackson's memory folder): ``USER.md``, ``MEMORY.md``, ``journal/YYYY-MM-DD.md``.
The folder defaults to ~/.local/share/svoya/jackson/memory/ and is configurable (``memory.dir``).

Obsidian: when the folder is inside an Obsidian vault (an ancestor has ``.obsidian/``) or
``memory.obsidian = "on"``, Jackson writes Obsidian-friendly Markdown (YAML front matter with
created/updated/tags, [[wikilinks]], no HTML), indexes the whole vault for ``notes.search`` and
never writes outside its own subfolder unless the user allows it (see tools/notes.py). If the
folder *is* the vault root, Jackson uses ``<vault>/Jackson`` as its subfolder.

Every write is reversible (the previous content is kept in a content-addressed store) and is
announced to the client by the caller. Outside Obsidian, when `git` is available the folder is
also a git repository with one commit per change.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import MemoryConfig
from .paths import Paths
from .runner import Runner

JOURNAL_RE = re.compile(r"^journal/\d{4}-\d{2}-\d{2}\.md$")
FILES = ("USER.md", "MEMORY.md")
MAX_NOTE_BYTES = 1024 * 1024
MAX_VAULT_FILES = 20_000

HEADERS = {
    "USER.md": {"ru": ("Обо мне", "Что Джексон знает о тебе. Файл можно править руками.", "user"),
                "en": ("About me", "What Jackson knows about you. Edit freely.", "user")},
    "MEMORY.md": {"ru": ("Память", "Долгосрочные заметки Джексона. Файл можно править руками.", "memory"),
                  "en": ("Memory", "Jackson's long-term notes. Edit freely.", "memory")},
}

STOPWORDS = set("""
что как это мне меня мой моя мое моё мои для про или где когда какой какая какое какие есть был была были
ты вы я он она оно они мы и в во на с со у о об по за из от до не ни ли же бы то а но да нет пожалуйста
джексон скажи расскажи покажи можешь надо нужно очень тебя тебе твой твоя свой
the a an is are was were what how my me you your for and or of to in on with it this that please jackson
do does did can could would should tell show about from have has had be been
""".split())

FM_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*\n?", re.DOTALL)


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


# ---------------------------------------------------------------------------
# YAML front matter (a tiny, lossless subset: we only touch created/updated/tags)

def split_frontmatter(text: str) -> tuple[list[tuple[str, str]], str]:
    m = FM_RE.match(text)
    if not m:
        return [], text
    items: list[tuple[str, str]] = []
    for line in m.group(1).splitlines():
        if items and (line.startswith((" ", "\t", "- ")) or not line.strip()):
            key, raw = items[-1]
            items[-1] = (key, raw + "\n" + line)
            continue
        key, sep, value = line.partition(":")
        items.append((key.strip() if sep else line, value.strip() if sep else ""))
    return items, text[m.end():]


def join_frontmatter(items: list[tuple[str, str]], body: str) -> str:
    lines = []
    for key, value in items:
        lines.append(f"{key}: {value}" if value and not value.startswith("\n") else f"{key}:{value}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body.lstrip("\n")


def touch_frontmatter(text: str, tags: list[str], now: dt.datetime | None = None) -> str:
    """Ensure created/updated/tags; keep every other key exactly as it was."""
    stamp = (now or dt.datetime.now()).strftime("%Y-%m-%dT%H:%M")
    items, body = split_frontmatter(text)
    keys = [k for k, _ in items]
    if "created" not in keys:
        items.insert(0, ("created", stamp))
    if "updated" in keys:
        items = [(k, stamp if k == "updated" else v) for k, v in items]
    else:
        items.insert(1, ("updated", stamp))
    if "tags" not in keys and tags:
        items.append(("tags", "[" + ", ".join(dict.fromkeys(tags)) + "]"))
    return join_frontmatter(items, body)


def find_vault(start: Path, home: Path) -> Path | None:
    try:
        start = start.resolve()
    except OSError:
        return None
    for candidate in (start, *start.parents):
        if (candidate / ".obsidian").is_dir():
            return candidate
        if candidate == home or candidate == Path(candidate.anchor):
            break
    return None


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
        self.lang = lang if lang in ("ru", "en") else "en"
        base = self._expand(self.config.dir) if self.config.dir else paths.memory_dir
        vault = find_vault(base, paths.home) if self.config.obsidian != "off" else None
        if vault is None and self.config.obsidian == "on":
            vault = base
        self.vault: Path | None = vault
        self.obsidian = vault is not None
        if self.obsidian and vault is not None and _same(base, vault):
            base = vault / "Jackson"
        self.dir = base
        self.root = vault if vault is not None else base     # everything below is indexed
        self.blobs = paths.undo_store / "memory"
        self._lock = threading.RLock()
        self._last_scan = 0.0

    def _expand(self, raw: str) -> Path:
        if raw == "~" or raw.startswith("~/"):
            return self.paths.home / raw[2:] if raw != "~" else self.paths.home
        return Path(raw)

    # ------------------------------------------------------------------
    def _header(self, name: str) -> str:
        title, note, tag = HEADERS[name][self.lang]
        if self.obsidian:
            return touch_frontmatter(f"# {title}\n\n_{note}_\n", ["jackson", tag])
        return f"# {title}\n\n<!-- {note} -->\n"

    def ensure(self) -> None:
        with self._lock:
            self.paths.ensure_data_dir()
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / "journal").mkdir(exist_ok=True)
            for name in FILES:
                p = self.dir / name
                if not p.exists():
                    p.write_text(self._header(name), encoding="utf-8")
            if self.config.git and not self.obsidian:
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

    def inside(self, path: Path) -> bool:
        """Is *path* inside Jackson's own memory folder?"""
        return _within(path, self.dir)

    def in_vault(self, path: Path) -> bool:
        return self.vault is not None and _within(path, self.vault)

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except (OSError, ValueError):
            return str(path)

    # ------------------------------------------------------------------
    def _store_blob(self, text: str) -> str:
        digest = sha256_text(text)
        self.blobs.mkdir(parents=True, exist_ok=True)
        blob = self.blobs / f"{digest}.md"
        if not blob.exists():
            blob.write_text(text, encoding="utf-8")
        return digest

    def _write(self, name: str, text: str, message: str, tags: tuple[str, ...] = ("jackson",)) -> MemoryChange:
        path = self.path_of(name)
        prev = self.read(name)
        prev_sha = self._store_blob(prev)
        if self.obsidian:
            text = touch_frontmatter(text, list(tags))
        write_text_atomic(path, text)
        self._git_commit(message)
        self.reindex(throttle=False)
        return MemoryChange(name, prev_sha, sha256_text(text), message)

    def remember(self, text: str, target: str = "memory", today: dt.date | None = None) -> MemoryChange:
        text = " ".join(text.split())
        if not text:
            raise MemoryFileError("empty memory")
        name = "USER.md" if target == "user" else "MEMORY.md"
        with self._lock:
            self.ensure()
            current = self.read(name)
            if f" · {text}" in current:
                return MemoryChange(name, sha256_text(current), sha256_text(current), "already known", [])
            line = f"- {(today or dt.date.today()).isoformat()} · {text}"
            change = self._write(name, current.rstrip("\n") + "\n" + line + "\n", f"remember: {text[:60]}",
                                 ("jackson", "user" if target == "user" else "memory"))
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
        day = when.strftime("%Y-%m-%d")
        name = f"journal/{day}.md"
        entry = " ".join(entry.split())
        with self._lock:
            self.ensure()
            current = self.read(name)
            if not current:
                current = f"# {day}\n\n"
                if self.obsidian:  # link days together the Obsidian way
                    prev_day = (when - dt.timedelta(days=1)).strftime("%Y-%m-%d")
                    current += f"← [[{prev_day}]] · [[USER]] · [[MEMORY]]\n\n"
            line = f"- {when.strftime('%H:%M')} · {entry}"
            change = self._write(name, current.rstrip("\n") + "\n" + line + "\n", f"journal: {entry[:60]}",
                                 ("jackson", "journal"))
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
            path = self.path_of(name)
            if prev:
                write_text_atomic(path, prev)
            elif path.exists():
                from .trash import Trash
                Trash(self.paths.trash_dir).put(path)  # the file did not exist before: never hard-delete
            self._git_commit(f"undo: {name}")
            self.reindex(throttle=False)

    def undo_handler(self, action: Any) -> str:
        self.restore(action.data["file"], action.data["prev"], action.data.get("sha256"))
        return f"{action.data['file']} restored"

    # ------------------------------------------------------------------
    # notes (the vault in Obsidian mode, Jackson's folder otherwise)

    def scan(self) -> list[tuple[str, Path]]:
        if not self.root.is_dir():
            return []
        out: list[tuple[str, Path]] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "node_modules")
            for name in sorted(filenames):
                if name.endswith(".md") and not name.startswith("."):
                    p = Path(dirpath) / name
                    out.append((p.relative_to(self.root).as_posix(), p))
                    if len(out) >= MAX_VAULT_FILES:
                        return out
        return out

    def resolve_note(self, ref: str) -> Path | None:
        """A note by relative path or by [[wikilink]] title (Jackson's folder wins ties)."""
        title = ref.strip().removeprefix("[[").removesuffix("]]").split("|", 1)[0].split("#", 1)[0].strip()
        if not title:
            return None
        if "/" in title or title.endswith(".md"):
            candidate = (self.root / (title if title.endswith(".md") else title + ".md"))
            try:
                resolved = candidate.resolve()
            except OSError:
                return None
            if not _within(resolved, self.root.resolve()):
                return None
            return resolved if resolved.is_file() else None
        want = normalize(title)
        hits = [p for _, p in self.scan() if normalize(p.stem) == want]
        hits.sort(key=lambda p: (not self.inside(p), len(str(p))))
        return hits[0] if hits else None

    def note_target(self, ref: str) -> Path:
        """Where a write of *ref* goes: an existing note, else a new one in Jackson's folder."""
        existing = self.resolve_note(ref)
        if existing is not None:
            return existing
        title = ref.strip().removeprefix("[[").removesuffix("]]").split("|", 1)[0].strip()
        if "/" in title:
            rel = title if title.endswith(".md") else title + ".md"
            return (self.root / rel).resolve()
        safe = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", title.removesuffix(".md")).strip() or "note"
        return self.dir / f"{safe[:120]}.md"

    # ------------------------------------------------------------------
    # FTS5 index

    def _db(self) -> sqlite3.Connection:
        self.paths.ensure_data_dir()
        db = sqlite3.connect(str(self.paths.index_db), timeout=5.0)
        db.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER)")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5("
                   "path UNINDEXED, line UNINDEXED, text, tokenize='unicode61 remove_diacritics 2')")
        row = db.execute("SELECT value FROM meta WHERE key = 'root'").fetchone()
        if row is None or row[0] != str(self.root):
            db.execute("DELETE FROM chunks")
            db.execute("DELETE FROM files")
            db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('root', ?)", (str(self.root),))
            db.commit()
        return db

    @staticmethod
    def _chunks(text: str) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        para: list[str] = []
        start = 0
        m = FM_RE.match(text)
        skip_until = text[: m.end()].count("\n") if m else 0
        for i, line in enumerate(text.splitlines(), start=1):
            if i <= skip_until:
                continue
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

    def reindex(self, full: bool = False, throttle: bool = True) -> int:
        """Re-index changed notes; returns how many files were (re)indexed."""
        if not self.root.is_dir():
            return 0
        now = time.monotonic()
        if throttle and not full and now - self._last_scan < 3.0:
            return 0
        with self._lock:
            self._last_scan = now
            db = self._db()
            try:
                known = {row[0]: (row[1], row[2]) for row in db.execute("SELECT path, mtime, size FROM files")}
                present = set()
                count = 0
                for key, p in self.scan():
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    if st.st_size > MAX_NOTE_BYTES:
                        continue
                    present.add(key)
                    if not full and known.get(key) == (st.st_mtime, st.st_size):
                        continue
                    db.execute("DELETE FROM chunks WHERE path = ?", (key,))
                    text = p.read_text(encoding="utf-8", errors="replace")
                    db.executemany("INSERT INTO chunks(path, line, text) VALUES (?, ?, ?)",
                                   [(key, n, normalize(c)) for n, c in self._chunks(text)])
                    db.execute("INSERT OR REPLACE INTO files(path, mtime, size) VALUES (?, ?, ?)",
                               (key, st.st_mtime, st.st_size))
                    count += 1
                for gone in set(known) - present:
                    db.execute("DELETE FROM chunks WHERE path = ?", (gone,))
                    db.execute("DELETE FROM files WHERE path = ?", (gone,))
                db.commit()
                return count
            finally:
                db.close()

    def search(self, query: str, limit: int = 5, scope: str = "all") -> list[Snippet]:
        """Full-text search. scope: "all" (every indexed note) or "memory" (Jackson's folder only)."""
        q = fts_query(query)
        if not q or not self.root.is_dir():
            return []
        self.reindex()
        prefix = self.rel(self.dir) + "/" if self.obsidian else ""
        db = self._db()
        try:
            rows = db.execute("SELECT path, line, text, bm25(chunks) AS score FROM chunks WHERE chunks MATCH ? "
                              "ORDER BY score LIMIT ?", (q, max(limit * 4, 20))).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            db.close()
        out = []
        for path, line, text, score in rows:
            if scope == "memory" and prefix and not str(path).startswith(prefix):
                continue
            original = self._line_text(str(path), int(line)) or text
            out.append(Snippet(str(path), int(line), original, float(score)))
            if len(out) >= limit:
                break
        return out

    def _line_text(self, key: str, line: int) -> str | None:
        try:
            lines = (self.root / key).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return None
        return lines[line - 1].strip() if 0 < line <= len(lines) else None

    def relevant(self, query: str, limit: int | None = None, max_chars: int | None = None) -> str:
        """Prompt block: USER.md (always, capped) + the most relevant snippets."""
        if not self.config.enabled or not self.dir.is_dir():
            return ""
        limit = self.config.snippets if limit is None else limit
        max_chars = self.config.max_chars if max_chars is None else max_chars
        parts = []
        _, user_body = split_frontmatter(self.read("USER.md"))
        user = "\n".join(line for line in user_body.splitlines()
                         if line.strip() and not line.startswith(("#", "<!--", "_"))).strip()
        if user:
            parts.append("USER.md:\n" + user[: max_chars // 2])
        used = sum(len(p) for p in parts)
        user_key = self.rel(self.dir / "USER.md") if self.obsidian else "USER.md"
        snippets = [s for s in self.search(query, limit) if s.file != user_key] if limit else []
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
        if not self.config.git or self.obsidian or not (self.dir / ".git").is_dir() or not self.runner.which("git"):
            return
        env = self._git_env()
        self.runner.run(["git", "add", "-A"], timeout=10.0, env=env, cwd=str(self.dir))
        self.runner.run(["git", "commit", "-q", "--no-verify", "--no-gpg-sign", "-m", message],
                        timeout=10.0, env=env, cwd=str(self.dir))


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return a == b


def _within(path: Path, root: Path) -> bool:
    try:
        path, root = path.resolve(), root.resolve()
    except OSError:
        pass
    return path == root or root in path.parents


def write_text_atomic(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".jackson-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            mode = os.stat(path).st_mode & 0o777
        except FileNotFoundError:
            pass
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
