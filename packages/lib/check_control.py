#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Minimal static checks for a debian/control file (no python3-debian needed).

Checks: deb822 syntax, a source paragraph with Source/Maintainer/Build-Depends/Standards-Version,
every binary paragraph has Package/Architecture/Description, Architecture values are sane and
relationship fields parse as comma-separated "name (op version) [arch]" items.
"""
from __future__ import annotations

import re
import sys

REL_FIELDS = ("Depends", "Pre-Depends", "Recommends", "Suggests", "Conflicts", "Breaks",
              "Replaces", "Provides", "Enhances", "Build-Depends", "Build-Depends-Indep",
              "Build-Depends-Arch")
ITEM_RE = re.compile(
    r"^(?P<name>[a-z0-9${}:.+-]+(?::any)?)"            # package name or ${substvar}
    r"(?:\s*\((?P<op><<|<=|=|>=|>>)\s*(?P<ver>[^)\s]+)\))?"
    r"(?:\s*\[(?P<arch>[^\]]+)\])?"
    r"(?:\s*<(?P<prof>[^>]+)>)?$"
)
VALID_ARCH = {"all", "any", "amd64", "arm64", "linux-any"}


def parse_paragraphs(text: str) -> list[dict[str, str]]:
    paras: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    last = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("#"):
            continue
        if not raw.strip():
            if cur:
                paras.append(cur)
                cur, last = {}, None
            continue
        if raw[0] in " \t":
            if last is None:
                raise ValueError(f"line {lineno}: continuation line without a field")
            cur[last] += "\n" + raw.strip()
            continue
        if ":" not in raw:
            raise ValueError(f"line {lineno}: expected 'Field: value'")
        key, value = raw.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", key):
            raise ValueError(f"line {lineno}: bad field name {key!r}")
        if key in cur:
            raise ValueError(f"line {lineno}: duplicate field {key}")
        cur[key] = value.strip()
        last = key
    if cur:
        paras.append(cur)
    return paras


def check_relations(field: str, value: str) -> list[str]:
    errors = []
    flat = " ".join(value.split())
    for group in filter(None, (g.strip() for g in flat.split(","))):
        for alt in (a.strip() for a in group.split("|")):
            if alt.startswith("${") and alt.endswith("}"):
                continue
            if not ITEM_RE.match(alt):
                errors.append(f"{field}: cannot parse {alt!r}")
    return errors


def check(text: str) -> list[str]:
    try:
        paras = parse_paragraphs(text)
    except ValueError as exc:
        return [str(exc)]
    if not paras:
        return ["empty control file"]
    errors: list[str] = []
    src, bins = paras[0], paras[1:]
    for f in ("Source", "Maintainer", "Build-Depends", "Standards-Version"):
        if f not in src:
            errors.append(f"source paragraph lacks {f}")
    if not bins:
        errors.append("no binary package paragraphs")
    for p in bins:
        name = p.get("Package", "?")
        for f in ("Package", "Architecture", "Description"):
            if f not in p:
                errors.append(f"{name}: lacks {f}")
        for arch in p.get("Architecture", "").split():
            if arch not in VALID_ARCH:
                errors.append(f"{name}: unusual Architecture {arch}")
        desc = p.get("Description", "")
        if desc and "\n" not in desc:
            errors.append(f"{name}: Description needs a long description")
    for p in paras:
        for f in REL_FIELDS:
            if f in p:
                errors.extend(check_relations(f, p[f]))
    return errors


def main(argv: list[str]) -> int:
    rc = 0
    for path in argv[1:]:
        with open(path, encoding="utf-8") as fh:
            errs = check(fh.read())
        for e in errs:
            print(f"{path}: {e}", file=sys.stderr)
        rc |= bool(errs)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
