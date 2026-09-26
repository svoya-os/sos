"""``sos models list | pull | fit | rm | dedup | views``."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

from .. import config as config_mod
from .. import i18n, live, ui
from ..context import Ctx
from ..hw import gpu as gpu_mod
from ..i18n import tr
from ..util import iso
from . import dedup as dedup_mod
from . import estimate as est_mod
from . import gguf, hfcache, licenses, remote, views
from .registry import Registry

GiB = 2**30
SHARD = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$", re.I)


# ---------------------------------------------------------------- GPU / RAM budget

def gpu_budget(ctx: Ctx, spec: str = "auto") -> dict:
    """→ {name, total, used, backend, hypothetical}. ``spec``: auto | <index> | <GiB, e.g. 24 or 24gb>."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:g|gb|gib)", spec.strip().lower()) if spec else None
    if m or (spec and re.fullmatch(r"\d+\.\d+", spec)) or (spec and spec.isdigit() and int(spec) >= 4):
        gbs = float(m.group(1) if m else spec)
        return {"name": f"{i18n.smart(gbs)} {tr('GB', 'ГБ')}", "total": int(gbs * GiB), "used": 0,
                "backend": "cuda", "hypothetical": True}
    gpus = gpu_mod.live_stats(ctx)
    if not gpus:
        return {"name": None, "total": None, "used": None, "backend": "cpu", "hypothetical": False}

    def total_of(g: dict) -> int:
        t = (g.get("vramTotalMiB") or 0) + (g.get("gttTotalMiB") or 0 if g.get("integrated") else 0)
        return t * 2**20

    if spec and spec.isdigit():
        chosen = next((g for g in gpus if g.get("index") == int(spec)), gpus[0])
    else:
        chosen = max(gpus, key=total_of)
    used = ((chosen.get("vramUsedMiB") or 0) + (chosen.get("gttUsedMiB") or 0 if chosen.get("integrated") else 0)) * 2**20
    backend = {"nvidia": "cuda", "amd": "rocm"}.get(chosen.get("vendor", ""), "vulkan")
    return {"name": chosen.get("name"), "total": total_of(chosen) or None, "used": used, "backend": backend,
            "hypothetical": False, "integrated": bool(chosen.get("integrated"))}


def ram_available(ctx: Ctx) -> int | None:
    text = ctx.read("/proc/meminfo") or ""
    m = re.search(r"^MemAvailable:\s+(\d+)\s+kB", text, re.M)
    return int(m.group(1)) * 1024 if m else None


# ---------------------------------------------------------------- headers

def _shard_paths(path: Path, hdr: gguf.GGUFHeader) -> list[Path]:
    n = hdr.get("split.count")
    m = SHARD.search(path.name)
    if not isinstance(n, int) or n <= 1 or not m:
        return [path]
    return [path.with_name(SHARD.sub(f"-{i:05d}-of-{n:05d}.gguf", path.name)) for i in range(1, n + 1)]


def load_local(path: Path) -> tuple[est_mod.ModelShape, gguf.GGUFHeader]:
    hdr = gguf.read_file(path)
    shards = _shard_paths(path, hdr)
    headers, sizes = [], []
    for p in shards:
        h = hdr if p == path else gguf.read_file(p)
        headers.append(h)
        sizes.append(p.stat().st_size)
    if shards[0] != path:   # user pointed at a later shard: metadata lives in the first
        headers.insert(0, headers.pop(shards.index(path)))
    return est_mod.shape_from_headers(headers, sizes), headers[0]


def load_remote(ref: remote.HFRef, token: str | None, op=None) -> tuple[est_mod.ModelShape, gguf.GGUFHeader, int]:
    rd = remote.HttpRangeReader(ref.url(), token, op=op)
    hdr = gguf.read_header(rd)
    headers, sizes, fetched = [hdr], [rd.size or 0], rd.fetched
    n = hdr.get("split.count")
    m = SHARD.search(ref.filename or "")
    if isinstance(n, int) and n > 1 and m:
        for i in range(2, n + 1):
            sref = remote.HFRef(ref.repo, SHARD.sub(f"-{i:05d}-of-{n:05d}.gguf", ref.filename), ref.revision)
            r2 = remote.HttpRangeReader(sref.url(), token, op=op)
            headers.append(gguf.read_header(r2))
            sizes.append(r2.size or 0)
            fetched += r2.fetched
    return est_mod.shape_from_headers(headers, sizes), hdr, fetched


def _params_label(s: est_mod.ModelShape) -> str | None:
    if s.size_label:
        return str(s.size_label)
    if s.params:
        b = s.params / 1e9
        return f"{i18n.smart(b)}B" if b >= 1 else f"{round(s.params / 1e6)}M"
    return None


# ---------------------------------------------------------------- fit

VERDICT = {
    "fits": ("✓ fits", "✓ влезет"),
    "offload": ("≈ fits with offload to RAM", "≈ с выгрузкой в ОЗУ"),
    "no": ("× doesn't fit", "× не влезет"),
}


def cmd_fit(args, ctx: Ctx) -> int:
    cfg = config_mod.load(ctx.paths)
    target = args.model
    local = Path(os.path.expanduser(target))
    fetched = 0
    try:
        if local.exists():
            shape, hdr = load_local(local)
            label, repo, fname = local.name, None, local.name
        else:
            ref = remote.parse_ref(target, args.revision)
            if ref is None or not ref.filename:
                ui.err(tr("sos: give a .gguf path or org/repo/file.gguf", "sos: укажите путь .gguf или org/repo/file.gguf"))
                return 2
            if not ref.filename.lower().endswith(".gguf"):
                ui.err(tr("sos: fit reads GGUF headers; for other formats see `sos models list --catalog`",
                          "sos: fit читает заголовки GGUF; для других форматов — `sos models list --catalog`"))
                return 2
            token = remote.hf_token(ctx.env, ctx.paths.ai_root, ctx.paths.home)
            shape, hdr, fetched = load_remote(ref, token)
            label, repo, fname = f"{ref.repo}/{ref.filename}", ref.repo, ref.filename
    except (gguf.GGUFError, remote.RemoteError, OSError) as e:
        ui.err(f"sos: {e}")
        return 1
    g = gpu_budget(ctx, args.gpu)
    try:
        est = est_mod.estimate(shape, args.ctx, args.kv, flash_attn=not args.no_flash_attn,
                               backend=g["backend"] if g["backend"] != "cpu" else "cuda")
    except ValueError as e:
        ui.err(f"sos: {e}")
        return 2
    ram = ram_available(ctx)
    f = est_mod.fit(shape, est, g["total"], g["used"], ram)
    verdict = licenses.classify(repo=repo, filename=fname, license_id=shape.license)
    region = str(cfg["models"].get("region", "EU"))
    lic_status, lic_reason = verdict.allows(region, bool(cfg["models"].get("commercial", True)))
    sugg = est_mod.suggest_ctx(shape, f.budget, args.kv) if g["total"] and f.verdict != "fits" else None

    if args.json:
        ui.print_json({
            "model": label, "arch": shape.arch, "name": shape.name, "quant": shape.quant,
            "params": shape.params, "sizeLabel": _params_label(shape), "nLayers": shape.n_layers,
            "nCtxTrain": shape.n_ctx_train, "ctx": args.ctx, "kvType": args.kv,
            "estimate": {"weightsBytes": est.weights, "kvBytes": est.kv, "computeBytes": est.compute,
                         "runtimeBytes": est.runtime, "totalBytes": est.total, "exactWeights": shape.exact_weights},
            "gpu": {"name": g["name"], "totalBytes": g["total"], "usedBytes": g["used"],
                    "backend": g["backend"], "hypothetical": g["hypothetical"]},
            "fit": f.as_json(), "suggestedCtx": sugg,
            "license": verdict.as_json(), "usable": {"status": lic_status, "reason": lic_reason, "region": region},
            "bytesFetched": fetched})
        return 0 if f.verdict != "no" else 1

    st = ui.style()
    meta = [x for x in (shape.arch, _params_label(shape), shape.quant) if x]
    ui.head(f"{label} {st.faint('· ' + ' · '.join(meta))}")
    ui.kv(tr("weights", "веса"), i18n.gib(est.weights) + ("" if shape.exact_weights else st.faint(" ≈")), width=11)
    if shape.is_llm:
        ui.kv(tr("kv cache", "kv-кэш"), f"{i18n.gib(est.kv)}  {st.faint(i18n.num(est.n_ctx) + tr(' tok · ', ' ток. · ') + est.kv_type)}", width=11)
        ui.kv(tr("buffers", "буферы"), f"{i18n.gib(est.compute + est.runtime)}  {st.faint(tr('compute + runtime', 'вычисления + среда'))}", width=11)
    tail = ""
    if g["total"]:
        free = max(0, g["total"] - (g["used"] or 0))
        tail = st.faint(tr(f"  of {i18n.gib(g['total'])} · free {i18n.gib(free)}",
                           f"  из {i18n.gib(g['total'])} · свободно {i18n.gib(free)}"))
        if g.get("name"):
            tail += st.faint(f" · {g['name']}")
    ui.kv(tr("total", "итого"), i18n.gib(est.total) + tail, width=11)
    en, ru = VERDICT[f.verdict]
    mark = {"fits": st.ok, "offload": st.warn, "no": st.bad}[f.verdict]
    if not g["total"]:
        ui.out("  " + st.warn(tr("no GPU detected — CPU only", "ГП не найден — только процессор")))
    else:
        ui.out("  " + mark(tr(en, ru)))
    for n_en, n_ru in f.notes:
        ui.note(tr(n_en, n_ru), indent=4)
    if sugg and f.verdict != "fits":
        ui.note(tr(f"fits fully at --ctx {sugg}", f"полностью влезет при --ctx {sugg}"), indent=4)
    lic = verdict.license or tr("unknown", "неизвестна")
    lmark = {"ok": st.ok("✓"), "warn": st.warn("!"), "no": st.bad("×")}[lic_status]
    ui.kv(tr("license", "лицензия"), f"{lic}  {lmark} {lic_reason or tr('commercial use OK in the ' + region, 'можно коммерчески в ' + ('ЕС' if region == 'EU' else region))}", width=11)
    if fetched:
        ui.note(tr(f"read {i18n.size(fetched)} of header over the network", f"прочитано {i18n.size(fetched)} заголовка по сети"))
    return 0 if f.verdict != "no" else 1


# ---------------------------------------------------------------- list

def _open_registry(ctx: Ctx) -> Registry | None:
    return Registry.open(ctx.paths.registry_db)


def sync_registry(reg: Registry | None, files: list[hfcache.CachedFile], now: str) -> None:
    if reg is None or reg.readonly:
        return
    known = {r["path"] for r in reg.all()}
    for f in files:
        p = str(f.blob_path)
        if p in known:
            continue
        rec = {"path": p, "sha256": f.sha256, "size": f.size, "source": "hf", "repo": f.repo,
               "revision": f.commit, "filename": f.filename, "added_at": now,
               "format": "gguf" if f.filename.lower().endswith(".gguf") else Path(f.filename).suffix.lstrip(".") or None}
        license_id = None
        if rec["format"] == "gguf" and not SHARD.search(f.filename) or (rec["format"] == "gguf" and "00001-of" in f.filename):
            try:
                h = gguf.read_file(f.blob_path, read_tensors=False)
                rec.update(arch=h.arch, quant=h.file_type, n_ctx_train=h.arch_get("context_length"))
                license_id = h.get("general.license")
            except (gguf.GGUFError, OSError):
                pass
        v = licenses.classify(repo=f.repo, filename=f.filename, license_id=license_id)
        rec.update(license=v.license, commercial=v.commercial, eu_ok="EU" not in v.excluded,
                   regions_excluded=list(v.excluded))
        reg.upsert(rec)


def cmd_list(args, ctx: Ctx) -> int:
    cfg = config_mod.load(ctx.paths)
    region = str(cfg["models"].get("region", "EU"))
    commercial = bool(cfg["models"].get("commercial", True))
    st = ui.style()
    if args.catalog:
        g = gpu_budget(ctx, "auto")
        budget = max(0, (g["total"] or 0) - est_mod.margin(g["total"] or 0)) if g["total"] else 0
        rows = []
        for e in licenses.catalog():
            if args.kind and e.get("kind") != args.kind:
                continue
            v = licenses.from_catalog(e)
            status, reason = v.allows(region, commercial)
            if status == "no" and not args.all:
                continue
            need = e.get("vram_gb")
            fit = None
            if need and g["total"]:
                fit = "fits" if need * GiB <= budget else ("offload" if need * GiB <= budget + (ram_available(ctx) or 0) / 2 else "no")
            rows.append({"id": e["id"], "name": e["name"], "kind": e.get("kind"), "license": e.get("license"),
                         "vramGb": need, "fit": fit, "usable": status, "reason": reason, "repo": e.get("repo"),
                         "note": i18n.pick(e.get("note")) if e.get("note") else None})
        if args.json:
            ui.print_json({"region": region, "commercial": commercial, "gpu": g["name"], "models": rows})
            return 0
        ui.head(tr(f"catalog · usable {'commercially ' if commercial else ''}in the {region}",
                   f"каталог · можно использовать {'коммерчески ' if commercial else ''}в {'ЕС' if region == 'EU' else region}")
                + (st.faint(tr(" · all", " · все")) if args.all else ""))
        for r in rows:
            vr = f"{i18n.smart(r['vramGb'])} {tr('GB', 'ГБ')}" if r["vramGb"] else "—"
            fit = {"fits": st.ok(tr("✓ fits", "✓ влезет")), "offload": st.warn(tr("≈ offload", "≈ с выгрузкой")),
                   "no": st.bad(tr("× too big", "× не влезет")), None: ""}[r["fit"]]
            lic = {"ok": st.faint(r["license"] or ""), "warn": st.warn(r["reason"]), "no": st.bad("× " + r["reason"])}[r["usable"]]
            ui.out(f"  {r['name'][:24].ljust(24)} {st.faint((r['kind'] or '').ljust(6))} {vr.rjust(8)}  {fit}  {lic}")
        if not args.all:
            ui.note(tr("--all also shows models your region or use is not licensed for",
                       "--all покажет и модели, лицензия которых не подходит вашему региону или использованию"))
        return 0

    hub = ctx.paths.ai_root / "hub"
    files = hfcache.scan(hub)
    reg = _open_registry(ctx)
    sync_registry(reg, files, iso(ctx.now()))
    rows = reg.all() if reg else [{"path": str(f.blob_path), "repo": f.repo, "filename": f.filename,
                                    "size": f.size, "sha256": f.sha256} for f in files]
    if reg:
        reg.close()
    out = []
    for r in rows:
        v = licenses.classify(repo=r.get("repo"), filename=r.get("filename"), license_id=None)
        if v.license is None and r.get("license"):
            v = licenses.classify(license_id=r.get("license"))
        status, reason = v.allows(region, commercial)
        out.append({**r, "usable": status, "reason": reason})
    if args.json:
        ui.print_json({"root": str(ctx.paths.ai_root), "models": out})
        return 0
    total = sum(r.get("size") or 0 for r in out)
    ui.head(tr(f"models in {ctx.paths.ai_root}", f"модели в {ctx.paths.ai_root}") +
            st.faint(f" · {len(out)} · {i18n.gib(total)}"))
    if not out:
        ui.note(tr("empty — `sos models pull org/repo/file.gguf`", "пусто — `sos models pull org/repo/file.gguf`"))
    for r in out:
        mark = {"ok": st.ok("✓"), "warn": st.warn("!"), "no": st.bad("×")}[r["usable"]]
        name = f"{r.get('repo') or ''}/{r.get('filename') or Path(r['path']).name}"
        extra = " ".join(x for x in (r.get("quant"), r.get("license")) if x)
        ui.out(f"  {mark} {name}  {st.faint(i18n.gib(r.get('size')) + '  ' + extra)}"
               + (st.warn(f"  {r['reason']}") if r["usable"] != "ok" and r["reason"] else ""))
    return 0


# ---------------------------------------------------------------- pull

class _Events:
    """``--json``: one JSON object per line (plan · progress · file-done · done · error) for the
    first-run wizard; otherwise calm human output."""

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._last = 0.0

    def __call__(self, event: str, **kw) -> None:
        if self.enabled:
            import json
            import sys
            sys.stdout.write(json.dumps({"event": event, **kw}, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    def progress(self, file: str, done: int, total: int | None) -> None:
        import time
        now = time.monotonic()
        if self.enabled and (now - self._last >= 0.5 or (total and done >= total)):
            self._last = now
            self("progress", file=file, bytes=done, totalBytes=total,
                 fraction=round(done / total, 4) if total else None)


def _plan_from_alias(alias: "suggest_mod.Choice") -> tuple[str, list[str], dict[str, int]]:
    files = [f["file"] for f in alias.files]
    sizes = {f["file"]: f["size"] for f in alias.files}
    if alias.mmproj:
        files.append(alias.mmproj["file"])
        sizes[alias.mmproj["file"]] = alias.mmproj["size"]
    return alias.model["repo"], files, sizes


def cmd_pull(args, ctx: Ctx) -> int:
    from . import suggest as suggest_mod
    cfg = config_mod.load(ctx.paths)
    st = ui.style()
    ev = _Events(bool(getattr(args, "json", False)))
    say = (lambda *a, **k: None) if ev.enabled else ui.kv
    head = (lambda *a, **k: None) if ev.enabled else ui.head
    token = remote.hf_token(ctx.env, ctx.paths.ai_root, ctx.paths.home)
    region = str(cfg["models"].get("region", "EU"))
    commercial = bool(cfg["models"].get("commercial", True))

    def fail(msg: str, rc: int = 1) -> int:
        ev("error", message=msg)
        if not ev.enabled:
            ui.err(f"sos: {msg}")
        return rc

    alias = suggest_mod.resolve(args.repo)
    siblings: dict = {}
    info: dict = {}
    if alias is not None:                        # curated ladder id, e.g. qwen3.5-9b:Q4_K_M
        repo, files, sizes = _plan_from_alias(alias)
        revision = args.revision
        verdict = licenses.classify(license_id=str(alias.model.get("license", "")).lower())
    else:
        ref = remote.parse_ref(args.repo, args.revision)
        if ref is None:
            return fail(tr("expected org/repo[/file] or a model id from `sos models suggest`",
                           "ожидается org/repo[/file] или id модели из `sos models suggest`"), 2)
        repo, revision = ref.repo, ref.revision
        files = list(args.files)
        if ref.filename:
            files.insert(0, ref.filename)
        try:
            info = remote.api_model(repo, revision, token)
        except remote.RemoteError as e:
            return fail(str(e))
        siblings = {s["rfilename"]: s for s in info.get("siblings", [])}
        if not files:
            ggufs = [n for n in siblings if n.lower().endswith(".gguf")]
            if ggufs and not args.include:
                ev("choose", repo=repo, files=sorted(ggufs))
                head(tr(f"{repo} has {len(ggufs)} GGUF files — pick one:", f"в {repo} {len(ggufs)} файлов GGUF — выберите один:"))
                for n in sorted(ggufs):
                    sz = (siblings[n].get("lfs") or {}).get("size") or siblings[n].get("size")
                    if not ev.enabled:
                        ui.out(f"  sos models pull {repo}/{n}  {st.faint(i18n.gib(sz) if sz else '')}")
                return 2
            import fnmatch
            files = [n for n in siblings if not args.include or any(fnmatch.fnmatch(n, p) for p in args.include)]
        missing = [f for f in files if f not in siblings]
        if missing:
            return fail(tr(f"not in {repo}: {', '.join(missing)}", f"нет в {repo}: {', '.join(missing)}"), 2)
        for f in list(files):          # all shards of a split GGUF
            m = SHARD.search(f)
            if m:
                n = int(m.group(2))
                for i in range(1, n + 1):
                    sf = SHARD.sub(f"-{i:05d}-of-{n:05d}.gguf", f)
                    if sf in siblings and sf not in files:
                        files.append(sf)
        sizes = {f: (siblings[f].get("lfs") or {}).get("size") or siblings[f].get("size") or 0 for f in files}
        card = info.get("cardData") or {}
        lic_id = card.get("license") if isinstance(card.get("license"), str) else None
        verdict = licenses.classify(repo=repo, filename=files[0] if files else None, license_id=lic_id)
    total = sum(sizes.values())
    status, reason = verdict.allows(region, commercial)

    # fit: curated entries are estimated offline; other GGUFs from the remote header
    fit_verdict = None
    if alias is not None:
        e = suggest_mod.evaluate(alias, suggest_mod.hardware(ctx))
        fit_verdict, need = e["verdict"], e["memoryBytes8k"]
    else:
        first = next((f for f in files if f.lower().endswith(".gguf") and "mmproj" not in f.lower()
                      and (not SHARD.search(f) or "-00001-of-" in f)), None)
        need = None
        if first:
            try:
                shape, _hdr, _ = load_remote(remote.HFRef(repo, first, revision), token)
                g = gpu_budget(ctx, "auto")
                est = est_mod.estimate(shape, args.ctx, backend=g["backend"] if g["backend"] != "cpu" else "cuda")
                fit_verdict = est_mod.fit(shape, est, g["total"], g["used"], ram_available(ctx)).verdict
                need = est.total
            except (gguf.GGUFError, remote.RemoteError) as e:
                if not ev.enabled:
                    ui.note(tr(f"fit check skipped: {e}", f"проверка пропущена: {e}"))
    root = ctx.paths.ai_root
    probe = root if root.exists() else root.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        free = None
    in_ram = live.is_live(ctx)
    ev("plan", repo=repo, revision=revision, files=files, totalBytes=total, license=verdict.as_json(),
       usable={"status": status, "reason": reason, "region": region}, fit=fit_verdict, memoryBytes8k=need,
       diskFreeBytes=free, live=in_ram)
    head(f"{repo} {st.faint('· ' + i18n.count(len(files), 'file', 'files', 'файл', 'файла', 'файлов') + ' · ' + i18n.gib(total))}")
    say(tr("license", "лицензия"), f"{verdict.license or tr('unknown', 'неизвестна')}  "
        + {"ok": st.ok("✓ " + (reason or tr('OK for you', 'подходит'))), "warn": st.warn("! " + reason),
           "no": st.bad("× " + reason)}[status], width=11)
    if fit_verdict:
        en, ru = VERDICT[fit_verdict]
        say(tr("fit", "влезет?"), tr(en, ru) + (st.faint(f"  {i18n.gib(need)} @ 8k") if need else ""), width=11)
    if free is not None:
        say(tr("disk", "диск"), tr(f"{i18n.gib(total)} of {i18n.gib(free)} free", f"{i18n.gib(total)} из {i18n.gib(free)} свободных"), width=11)
    if in_ram:
        say(tr("live", "живая"), st.warn(tr("! live session: the files go to RAM and are gone after a reboot — install SOS first",
                                          "! живая сессия: файлы лягут в оперативную память и пропадут после перезагрузки — сначала установи СОС")), width=11)

    if args.dry_run:
        ev("done", ok=True, dryRun=True)
        if not ev.enabled:
            ui.note(tr("dry run: nothing downloaded", "пробный запуск: ничего не скачано"))
        return 0
    if status == "no" and not args.accept_license:
        if not ev.enabled:
            ui.note(tr("not downloading. If your use is covered (e.g. personal, outside the region), add --accept-license",
                       "не скачиваю. Если ваше использование разрешено (например, личное или вне региона) — добавьте --accept-license"))
        return fail(reason, 3) if ev.enabled else 3
    if free is not None and total > free:
        return fail(tr("not enough disk space in the store", "не хватает места в хранилище"))
    if fit_verdict == "no" and not args.yes:
        if ev.enabled or not ui.confirm(tr("It will not fit your GPU. Download anyway?", "В видеокарту не влезет. Всё равно скачать?")):
            return fail(tr("does not fit; add --yes to download anyway", "не влезет; добавьте --yes, чтобы скачать всё равно"), 3)
    if not args.yes:
        if ev.enabled:
            return fail(tr("add --yes to download", "добавьте --yes, чтобы скачать"), 3)
        if not ui.confirm(tr("Download?", "Скачать?"), default=True):
            return 1

    hub = root / "hub"
    if ctx.runner.which("hf") and not ev.enabled:
        env = {**ctx.env, "HF_HOME": str(root)}
        rc = ctx.runner.stream(["hf", "download", repo, *files, "--revision", revision], env=env)
        if rc != 0:
            return fail(tr("hf download failed", "hf download завершился с ошибкой"), rc)
    else:
        for f in files:
            url = remote.HFRef(repo, f, revision).url()
            try:
                meta = remote.head(url, token)
                etag = meta.etag or (siblings.get(f, {}).get("lfs") or {}).get("sha256") or siblings.get(f, {}).get("blobId")
                if not etag:
                    return fail(f"{f}: no etag from the Hub")
                commit = meta.commit or info.get("sha") or revision
                dest = hfcache.blob_dest(hub, repo, etag)
                if not ev.enabled:
                    ui.note(f"↓ {f}")
                ev("file", file=f, totalBytes=meta.size or sizes.get(f))
                done = dest if dest.exists() else remote.download(
                    url, dest, token=token, expected_size=meta.size or sizes.get(f) or None,
                    expected_sha256=etag if len(etag) == 64 else None,
                    progress=lambda d, t, _f=f: ev.progress(_f, d, t))
                hfcache.add_file(hub, repo, commit, f, done, etag, revision)
                ev("file-done", file=f)
            except remote.RemoteError as e:
                return fail(f"{f}: {e}")
    reg = _open_registry(ctx)
    sync_registry(reg, [c for c in hfcache.scan(hub) if c.repo == repo and c.filename in files], iso(ctx.now()))
    if reg:
        reg.close()
    ev("done", ok=True, repo=repo, files=files)
    head(tr("done · `sos models views` updates the llama.cpp/ComfyUI/Ollama views",
            "готово · `sos models views` обновит представления llama.cpp/ComfyUI/Ollama"))
    return 0


# ---------------------------------------------------------------- serve

SERVE_UNIT = "svoya-llm.service"


def _healthy(url: str) -> bool:
    import urllib.request
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f"{url}/health", timeout=1) as r:
            return r.status == 200
    except OSError:
        return False


SERVE_CTX = "16384"                    # tokens; as Environment= in modules/llm-local/files/svoya-llm.service


def cmd_serve(args, ctx: Ctx) -> int:
    """Start/stop the local OpenAI-compatible server Jackson uses (llama.cpp router, localhost only)."""
    url = f"http://127.0.0.1:{args.port}"
    r = ctx.runner
    has_unit = bool(r.which("systemctl")) and r.run(["systemctl", "--user", "cat", SERVE_UNIT], timeout=5).ok
    running = _healthy(url)
    if args.status or args.json and not args.stop:
        info = {"running": running, "url": f"{url}/v1", "unit": SERVE_UNIT if has_unit else None}
        if args.json:
            ui.print_json(info)
        else:
            ui.head((tr("running", "работает") if running else tr("stopped", "остановлен")) + ui.style().faint(f" · {url}/v1"))
        if args.status:
            return 0 if running else 1
    if args.stop:
        if has_unit:
            r.run(["systemctl", "--user", "stop", SERVE_UNIT], timeout=30, mutating=True)
        else:
            r.run(["pkill", "-f", f"llama-server .*--port {args.port}"], timeout=5, mutating=True)
        ui.head(tr("local model server stopped", "локальный сервер моделей остановлен"))
        return 0
    if running:
        ui.head(tr(f"already running · {url}/v1", f"уже работает · {url}/v1"))
        return 0
    from .. import ai
    if not ai.enabled(ctx):
        ui.err(tr("sos: AI is switched off — sos ai on", "sos: ИИ выключен — sos ai on"))
        return 3
    views_dir = ctx.paths.ai_root / "views" / "llama.cpp"
    if has_unit and not args.foreground:
        res = r.run(["systemctl", "--user", "start", SERVE_UNIT], timeout=60, mutating=True)
        if not res.ok:
            ui.err(f"sos: {res.err.strip()[:300]}")
            return 1
    elif r.which("llama-server"):
        from types import SimpleNamespace
        cmd_views(SimpleNamespace(out=None, json=False, quiet=True), ctx)
        argv = ["llama-server", "--host", "127.0.0.1", "--port", str(args.port), "--models-dir", str(views_dir),
                "--models-max", "2", "--jinja"]
        # the context window of svoya-llm.service: llama.cpp's default (the model's training context)
        # does not fit in memory
        env = {**os.environ, "LLAMA_ARG_CTX_SIZE": os.environ.get("LLAMA_ARG_CTX_SIZE") or SERVE_CTX}
        if args.foreground and not ctx.dry_run:
            os.execvpe(argv[0], argv, env)
        r.spawn(argv, env=env)
    else:
        ui.err(tr("sos: no local model server yet — sos install llm-local", "sos: локального сервера моделей ещё нет — sos install llm-local"))
        return 2
    ui.head(tr(f"local models at {url}/v1", f"локальные модели на {url}/v1") + ui.style().faint(" · OpenAI/Anthropic API, localhost"))
    if not any(views_dir.glob("*")) if views_dir.is_dir() else True:
        ui.note(tr("no models yet — sos models suggest", "моделей пока нет — sos models suggest"))
    return 0


# ---------------------------------------------------------------- suggest

def cmd_suggest(args, ctx: Ctx) -> int:
    from . import suggest as suggest_mod
    res = suggest_mod.suggest(ctx)
    if args.json:
        # "live": a download would land in RAM (Jackson says to install SOS first)
        ui.print_json({**res, "live": live.is_live(ctx)})
        return 0
    st = ui.style()
    hw = res["hardware"]
    if hw["backend"] == "cpu":
        where = tr(f"CPU only · {i18n.gib(hw['ramTotalBytes'])} RAM", f"только процессор · ОЗУ {i18n.gib(hw['ramTotalBytes'])}")
    else:
        where = f"{hw['gpu']} · {i18n.gib(hw['memoryBytes'])}" + (tr(" unified", " общей памяти") if hw["unified"] else "")
    ui.head(tr("local model · ", "локальная модель · ") + where
            + (st.faint(f"  · {res['tierName']}") if hw["backend"] != "cpu" else ""))
    d = res["default"]
    ui.out(f"  {st.accent('●')} {d['name']} {st.faint(d['quant'])}  {i18n.gib(d['sizeBytes'])}  "
           f"{st.faint(suggest_mod.describe(d))}")
    ui.note(f"{d['note']} · {d['license']}" + (tr(" · sees images", " · понимает картинки") if d["vision"] else ""), indent=4)
    ui.note(d["pull"], indent=4)
    for a in res["alternatives"]:
        ui.out(f"  {st.faint('○')} {a['name']} {st.faint(a['quant'])}  {i18n.gib(a['sizeBytes'])}  "
               f"{st.faint(suggest_mod.describe(a))}")
        if a["verdict"] != "no":              # no ready-made command for a download that cannot run here
            ui.note(a["pull"], indent=4)
    # one step from «which model?» to having it: --yes, or a question in a terminal
    if d["verdict"] == "no" or not d.get("diskOk", True):
        return 0
    if live.is_live(ctx):                     # the files would go to RAM (see pull); install SOS first
        if getattr(args, "yes", False) or sys.stdin.isatty():
            ui.note(tr("live session: install SOS first, then download the model",
                       "живая сессия: сначала установи СОС, потом скачивай модель"))
        return 0
    size = i18n.gib(d["sizeBytes"])
    if getattr(args, "yes", False) or (sys.stdin.isatty() and ui.confirm(
            tr(f"Download {d['name']} ({size})?", f"Скачать {d['name']} ({size})?"), default=True)):
        ns = argparse.Namespace(models_cmd="pull", repo=d["id"], files=[], revision="main", include=[],
                                ctx=res.get("ctx") or 8192, yes=True, accept_license=False,
                                dry_run=ctx.dry_run, json=False)
        return main(ns, ctx)
    return 0


# ---------------------------------------------------------------- rm

def cmd_rm(args, ctx: Ctx) -> int:
    hub = ctx.paths.ai_root / "hub"
    files = hfcache.scan(hub)
    t = args.target
    if re.fullmatch(r"[A-Za-z0-9][\w.-]*/[\w.-]+", t) and not Path(t).exists():
        victims = [f for f in files if f.repo == t]
        whole_repo = True
    else:
        p = Path(os.path.expanduser(t))
        victims = [f for f in files if str(f.blob_path) == str(p.resolve()) if p.exists()] + \
                  [f for f in files if f.sha256 == t or str(f.snapshot_path) == str(p)]
        whole_repo = False
    if not victims:
        ui.err(tr(f"sos: nothing matches {t}", f"sos: ничего не найдено по {t}"))
        return 1
    size = sum(f.size for f in {f.blob_path: f for f in victims}.values())
    ui.head(tr(f"remove {len(victims)} file(s), {i18n.gib(size)}", f"удалить {len(victims)} файл(ов), {i18n.gib(size)}"))
    for f in victims[:20]:
        ui.note(f"{f.repo}/{f.filename}")
    if args.dry_run:
        return 0
    if not ui.confirm(tr("Delete?", "Удалить?"), assume=True if args.yes else None):
        return 1
    removed: list[Path] = []
    if whole_repo:
        removed = hfcache.remove_repo(hub, t)
        paths = [str(f.blob_path) for f in victims]
    else:
        paths = []
        for f in victims:
            removed += hfcache.remove_file(hub, f, files)
            paths.append(str(f.blob_path))
    reg = _open_registry(ctx)
    if reg and not reg.readonly:
        reg.delete_paths(paths)
        reg.close()
    ui.head(tr("removed", "удалено") + f" · {i18n.gib(size)}")
    return 0


# ---------------------------------------------------------------- dedup

def default_roots(ctx: Ctx) -> list[Path]:
    h = ctx.paths.home
    return [ctx.paths.ai_root, h / ".ollama" / "models" / "blobs", ctx.sys("/usr/share/ollama/.ollama/models/blobs"),
            h / ".cache" / "huggingface" / "hub", h / ".cache" / "lm-studio" / "models", h / "ComfyUI" / "models"]


def cmd_dedup(args, ctx: Ctx) -> int:
    roots = [Path(os.path.expanduser(r)) for r in args.roots] or [r for r in default_roots(ctx) if r.exists()]
    reg = _open_registry(ctx)
    groups = dedup_mod.find(roots, cached=reg.cached_hash if reg else None, store=reg.put_hash if reg else None)
    if reg:
        reg.close()
    wasted = sum(g.wasted for g in groups)
    results = []
    if args.apply:
        for g in groups:
            for p, ok, msg in dedup_mod.reflink_group(g, ctx.runner, dry_run=ctx.dry_run):
                results.append({"path": str(p), "ok": ok, "message": msg})
    if args.json:
        ui.print_json({"roots": [str(r) for r in roots], "wastedBytes": wasted,
                       "groups": [{"sha256": g.sha256, "size": g.size, "files": [str(p) for p in g.files]} for g in groups],
                       "reflinks": results})
        return 0
    st = ui.style()
    ui.head(tr(f"duplicates: {len(groups)} groups · {i18n.gib(wasted)} wasted",
               f"дубликаты: {len(groups)} групп · {i18n.gib(wasted)} впустую"))
    for g in groups[:50]:
        ui.out(f"  {st.accent(g.sha256[:12])} {st.faint(i18n.gib(g.size) + ' × ' + str(len(g.files)))}")
        for p in g.files:
            ui.note(str(p), indent=4)
    for r in results:
        ui.note(("✓ " if r["ok"] else "× ") + r["path"] + (f" — {r['message']}" if r["message"] else ""))
    if groups and not args.apply:
        ui.note(tr("`sos models dedup --apply` shares the blocks on btrfs (reflink); files stay independent",
                   "`sos models dedup --apply` разделит блоки на btrfs (reflink); файлы остаются независимыми"))
    return 0


# ---------------------------------------------------------------- views

def cmd_views(args, ctx: Ctx) -> int:
    root = ctx.paths.ai_root
    out = Path(args.out) if args.out else root / "views"
    files = hfcache.scan(root / "hub")
    reports = {}
    for name, planner in (("llama.cpp", views.llama_plan), ("comfyui", views.comfy_plan), ("ollama", views.ollama_plan)):
        d = out / name
        plan = planner(files, d)
        reports[name] = views.apply(plan, d, dry_run=ctx.dry_run)
    if args.json:
        ui.print_json({"out": str(out), "views": reports, "dryRun": ctx.dry_run})
        return 0
    if getattr(args, "quiet", False):
        return 0
    st = ui.style()
    ui.head(tr(f"views in {out}", f"представления в {out}") + (st.faint(tr(" · dry run", " · пробный запуск")) if ctx.dry_run else ""))
    ui.kv("llama.cpp", f"{reports['llama.cpp']['links']} {tr('links', 'ссылок')}  "
          + st.faint(f"llama-server --models-dir {out / 'llama.cpp'}"), width=11)
    ui.kv("comfyui", f"{reports['comfyui']['links']} {tr('links', 'ссылок')}  "
          + st.faint(f"--extra-model-paths-config {out / 'comfyui' / 'extra_model_paths.yaml'}"), width=11)
    ui.kv("ollama", f"{len(reports['ollama']['commands'])} {tr('imports', 'импортов')}  "
          + st.faint(f"bash {out / 'ollama' / 'import.sh'}"), width=11)
    for c in reports["ollama"]["commands"][:10]:
        ui.note(c, indent=4)
    for n in reports["ollama"]["notes"]:
        ui.note(n, indent=4)
    return 0


def main(args, ctx: Ctx | None = None) -> int:
    ctx = ctx or Ctx()
    cmd = args.models_cmd or "list"
    if cmd == "list" and not hasattr(args, "catalog"):
        args.catalog, args.all, args.kind, args.json = False, False, None, False
    return {"list": cmd_list, "fit": cmd_fit, "pull": cmd_pull, "rm": cmd_rm, "dedup": cmd_dedup,
            "views": cmd_views, "suggest": cmd_suggest, "serve": cmd_serve}[cmd](args, ctx)

