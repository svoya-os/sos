"""Snapper wrapper: pre/post pairs with descriptions, cleanup algorithm ``number``.

``sos snapshot create|list`` and the building block for modules, update, doctor --fix and undo.
Every snapshot svoya takes carries ``--userdata svoya=1`` and is also recorded in
``/var/lib/svoya/history.json`` (read instantly by ``sos status``).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from . import ui
from .context import Ctx
from .i18n import tr
from .util import iso, read_json, write_json

CLEANUP = "number"
HISTORY_KEEP = 200


@dataclass
class Snapshot:
    number: int
    type: str = "single"             # single | pre | post
    pre_number: int | None = None
    date: dt.datetime | None = None  # UTC
    description: str = ""
    userdata: dict = field(default_factory=dict)
    cleanup: str = ""

    @property
    def is_svoya(self) -> bool:
        return self.userdata.get("svoya") == "1" or self.description.startswith(("sos:", "svoya"))

    def as_json(self) -> dict:
        return {"number": self.number, "type": self.type, "preNumber": self.pre_number,
                "date": iso(self.date), "description": self.description, "userdata": self.userdata,
                "cleanup": self.cleanup}


def _parse_date(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def parse_snapper_json(text: str, config: str = "root") -> list[Snapshot]:
    """Parse ``snapper --utc --jsonout list`` (dates are UTC because of ``--utc``)."""
    data = json.loads(text)
    rows = data.get(config)
    if rows is None and data:
        rows = next(iter(data.values()))
    out: list[Snapshot] = []
    for r in rows or []:
        num = r.get("number")
        if not isinstance(num, int) or num == 0:      # 0 = "current", not a snapshot
            continue
        out.append(Snapshot(number=num, type=r.get("type") or "single", pre_number=r.get("pre-number"),
                            date=_parse_date(r.get("date")), description=r.get("description") or "",
                            userdata=r.get("userdata") or {}, cleanup=r.get("cleanup") or ""))
    return out


def parse_info_xml(text: str) -> Snapshot | None:
    """``/.snapshots/<n>/info.xml`` (snapper stores UTC dates there)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    def g(tag: str) -> str | None:
        el = root.find(tag)
        return el.text if el is not None else None
    try:
        num = int(g("num") or "")
    except ValueError:
        return None
    ud = {}
    for u in root.findall("userdata"):
        k, v = u.find("key"), u.find("value")
        if k is not None and k.text:
            ud[k.text] = v.text if v is not None and v.text else ""
    pre = g("pre_num")
    return Snapshot(number=num, type=g("type") or "single", pre_number=int(pre) if pre and pre.isdigit() else None,
                    date=_parse_date(g("date")), description=g("description") or "", userdata=ud,
                    cleanup=g("cleanup") or "")


class Snapper:
    def __init__(self, ctx: Ctx, config: str = "root"):
        self.ctx = ctx
        self.config = config

    def available(self) -> bool:
        return bool(self.ctx.runner.which("snapper")) and \
            self.ctx.exists(f"/etc/snapper/configs/{self.config}")

    def why_unavailable(self) -> str:
        if not self.ctx.runner.which("snapper"):
            return tr("snapper is not installed", "snapper не установлен")
        return tr(f"snapper has no '{self.config}' config (is / on btrfs?)",
                  f"у snapper нет конфигурации «{self.config}» (корень не на btrfs?)")

    # ---- read ----
    def list(self) -> list[Snapshot]:
        if self.ctx.runner.which("snapper"):
            r = self.ctx.runner.run(["snapper", "--utc", "--jsonout", "-c", self.config, "list",
                                     "--disable-used-space"], timeout=20)
            if r.ok:
                try:
                    return parse_snapper_json(r.out, self.config)
                except (ValueError, AttributeError):
                    pass
        # Fallback: read snapper's metadata directly (works without DBus permissions if readable)
        out: list[Snapshot] = []
        base = self.ctx.sys("/.snapshots")
        try:
            dirs = [d for d in base.iterdir() if d.name.isdigit()]
        except OSError:
            dirs = []
        for d in dirs:
            try:
                s = parse_info_xml((d / "info.xml").read_text())
            except OSError:
                continue
            if s:
                out.append(s)
        return sorted(out, key=lambda s: s.number)

    def last_date(self) -> dt.datetime | None:
        dates = [s.date for s in self.list() if s.date]
        return max(dates) if dates else None

    def pairs(self, svoya_only: bool = True) -> list[tuple[Snapshot, Snapshot | None]]:
        snaps = self.list()
        posts = {s.pre_number: s for s in snaps if s.type == "post" and s.pre_number}
        out = []
        for s in snaps:
            if s.type == "pre" and (s.is_svoya or not svoya_only):
                out.append((s, posts.get(s.number)))
        return out

    # ---- write ----
    def create(self, description: str, *, kind: str = "single", pre: int | None = None,
               cleanup: str = CLEANUP, userdata: dict | None = None) -> int | None:
        ud = {"svoya": "1", **(userdata or {})}
        argv = ["snapper", "-c", self.config, "create", "--type", kind, "--print-number",
                "--cleanup-algorithm", cleanup, "--description", description,
                "--userdata", ",".join(f"{k}={v}" for k, v in ud.items())]
        if kind == "post":
            if pre is None:
                raise ValueError("post snapshot needs a pre number")
            argv += ["--pre-number", str(pre)]
        r = self.ctx.runner.run(argv, timeout=300, mutating=True)
        if self.ctx.runner.dry_run:
            return None
        if not r.ok:
            raise RuntimeError(r.err.strip() or f"snapper exited with {r.rc}")
        m = re.search(r"(\d+)", r.out)
        num = int(m.group(1)) if m else None
        if num is not None:
            record_history(self.ctx, {"number": num, "type": kind, "pre": pre,
                                      "description": description, "at": iso(self.ctx.now())})
        return num

    def status(self, pre: int, post: int) -> list[str]:
        r = self.ctx.runner.run(["snapper", "-c", self.config, "status", f"{pre}..{post}"], timeout=120)
        return [ln for ln in r.out.splitlines() if ln.strip()] if r.ok else []

    def undochange(self, pre: int, post: int) -> bool:
        r = self.ctx.runner.run(["snapper", "-c", self.config, "undochange", f"{pre}..{post}"],
                                timeout=1800, mutating=True)
        return r.ok


def record_history(ctx: Ctx, entry: dict) -> None:
    path = ctx.paths.history_file
    data = read_json(path, {}) or {}
    snaps = data.setdefault("snapshots", [])
    snaps.append(entry)
    data["snapshots"] = snaps[-HISTORY_KEEP:]
    try:
        write_json(path, data)
    except OSError:
        pass  # not root: snapper itself still has the record


class Guard:
    """``with Guard(ctx, "sos: modules add llm-local") as g:`` → pre snapshot, post on exit.

    If snapshots are unavailable the guard records why (``g.reason``) and the caller decides
    whether to continue; nothing is silently skipped.
    """

    def __init__(self, ctx: Ctx, description: str, userdata: dict | None = None):
        self.ctx = ctx
        self.description = description
        self.userdata = userdata or {}
        self.snapper = Snapper(ctx)
        self.pre: int | None = None
        self.post: int | None = None
        self.reason: str | None = None

    def __enter__(self) -> "Guard":
        if not self.snapper.available():
            self.reason = self.snapper.why_unavailable()
            return self
        try:
            self.pre = self.snapper.create(self.description, kind="pre", userdata=self.userdata)
        except RuntimeError as e:          # e.g. snapperd refuses a user outside ALLOW_USERS/GROUPS
            self.reason = str(e) or "snapper failed"
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.pre is not None:
            try:
                self.post = self.snapper.create(self.description, kind="post", pre=self.pre,
                                                userdata=self.userdata)
            except RuntimeError:
                pass


# ---------------------------------------------------------------- CLI

def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    sn = Snapper(ctx, getattr(args, "config", None) or "root")
    if args.snapshot_cmd == "list":
        snaps = sn.list()
        if not args.all:
            snaps = [s for s in snaps if s.is_svoya] or snaps
        if args.json:
            ui.print_json([s.as_json() for s in snaps])
            return 0
        if not snaps:
            ui.head(tr("no snapshots", "снимков нет") + ("" if sn.available() else f" — {sn.why_unavailable()}"))
            return 0
        ui.head(tr("snapshots", "снимки"))
        st = ui.style()
        for s in snaps[-30:]:
            when = s.date.astimezone().strftime("%Y-%m-%d %H:%M") if s.date else "—"
            kind = {"pre": "▸", "post": "◂"}.get(s.type, "·")
            ui.out(f"  {st.accent(str(s.number).rjust(4))} {st.faint(kind)} {st.dim(when)}  {s.description}")
        return 0
    if args.snapshot_cmd == "create":
        if not sn.available():
            if args.json:
                ui.print_json({"id": None, "error": sn.why_unavailable()})
            else:
                ui.err(f"sos: {sn.why_unavailable()}")
            return 2
        desc = args.description or "sos: manual snapshot"
        if not desc.startswith(("sos", "svoya")):
            desc = f"sos: {desc}"
        try:
            # snapperd lets members of ALLOW_USERS/ALLOW_GROUPS snapshot without root (Jackson's T1 path)
            num = sn.create(desc, kind="single")
        except RuntimeError as e:
            import os
            import sys
            if ctx.is_root or ctx.dry_run or not sys.stdin.isatty():
                if args.json:
                    ui.print_json({"id": None, "error": str(e)})
                else:
                    ui.err(f"sos: {e}")
                return 1
            from .runner import svoya_argv
            os.execvp("pkexec", ["pkexec", *svoya_argv(), "snapshot", "create", "--config", sn.config,
                                 "--description", desc] + (["--json"] if args.json else []))
        if args.json:
            ui.print_json({"id": str(num) if num is not None else None, "number": num, "config": sn.config,
                           "description": desc, "dryRun": ctx.dry_run})
        else:
            ui.head(tr(f"snapshot {num if num is not None else '(dry run)'} created",
                       f"снимок {num if num is not None else '(пробный запуск)'} создан") + f" · {desc}")
        return 0
    return 2

