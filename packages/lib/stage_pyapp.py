#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage a private Python package of SOS (jackson, svoya_cli) into a Debian build tree.

    stage_pyapp.py --src jackson --package jackson --dest DEST_ROOT

Finds the importable package inside SRC (SRC/<pkg>/__init__.py, SRC/src/<pkg>/__init__.py or
SRC/__init__.py) and copies it to DEST_ROOT/usr/lib/svoya/<pkg>, leaving out tests, caches and
build junk. Prints the staged path.

Test and build directories are skipped only at the top level of the package: deeper down they are
package data (e.g. svoya_cli/data/new/common/tests/, the project template of `sos new`).
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

SKIP_ANYWHERE = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git"}
SKIP_TOP_LEVEL = {"tests", "test", "build", "dist"}
SKIP_DIRS = SKIP_ANYWHERE | SKIP_TOP_LEVEL  # kept for callers that import it
SKIP_SUFFIXES = {".pyc", ".pyo", ".orig", ".rej", ".swp"}


def find_package(src: pathlib.Path, name: str) -> pathlib.Path:
    for cand in (src / name, src / "src" / name, src):
        if (cand / "__init__.py").is_file() and (cand.name == name or cand == src / name):
            return cand
    if (src / "__init__.py").is_file():
        return src
    raise SystemExit(f"stage_pyapp: no importable package '{name}' under {src}")


def _ignorer(top: pathlib.Path):
    top = top.resolve()

    def _ignore(directory: str, names: list[str]) -> set[str]:
        at_top = pathlib.Path(directory).resolve() == top
        out = set()
        for n in names:
            p = pathlib.Path(directory, n)
            if p.is_dir() and (n in SKIP_ANYWHERE or (at_top and n in SKIP_TOP_LEVEL)):
                out.add(n)
            elif p.suffix in SKIP_SUFFIXES:
                out.add(n)
        return out

    return _ignore


def stage(src: pathlib.Path, name: str, dest_root: pathlib.Path) -> pathlib.Path:
    pkg = find_package(src, name)
    dest = dest_root / "usr" / "lib" / "svoya" / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(pkg, dest, ignore=_ignorer(pkg))
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=pathlib.Path)
    ap.add_argument("--package", required=True)
    ap.add_argument("--dest", required=True, type=pathlib.Path)
    ns = ap.parse_args(argv)
    print(stage(ns.src, ns.package, ns.dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
