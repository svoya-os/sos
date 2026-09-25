#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Map the QML imports used by shell/ to Ubuntu 26.04 package names (qml6-module-*).

Usage: qml_deps.py SHELL_DIR  -> prints a comma-separated dependency list (may be empty).

Quickshell's own modules (Quickshell, Quickshell.*) are statically linked into the quickshell
package; local/relative imports ("./x", "qs.y", quoted paths) need nothing.
"""
from __future__ import annotations

import pathlib
import re
import sys

IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][\w.]*)", re.MULTILINE)

# Explicit table for modules whose Debian package name does not follow the generic rule
# or that are shipped inside another package.
TABLE: dict[str, str | None] = {
    "QtQml": None,                      # part of libqt6qml6 (pulled in by quickshell)
    "QtQml.Models": "qml6-module-qtqml-models",
    "QtQml.WorkerScript": "qml6-module-qtqml-workerscript",
    "QtQuick": "qml6-module-qtquick",
    "QtQuick.Controls": "qml6-module-qtquick-controls",
    "QtQuick.Controls.Basic": "qml6-module-qtquick-controls",
    "QtQuick.Controls.Fusion": "qml6-module-qtquick-controls",
    "QtQuick.Controls.Material": "qml6-module-qtquick-controls",
    "QtQuick.Layouts": "qml6-module-qtquick-layouts",
    "QtQuick.Window": "qml6-module-qtquick-window",
    "QtQuick.Shapes": "qml6-module-qtquick-shapes",
    "QtQuick.Effects": "qml6-module-qtquick-effects",
    "QtQuick.Templates": "qml6-module-qtquick-templates",
    "QtQuick.Dialogs": "qml6-module-qtquick-dialogs",
    "QtQuick.Particles": "qml6-module-qtquick-particles",
    "QtQuick.VectorImage": "qml6-module-qtquick-vectorimage",
    "Qt5Compat.GraphicalEffects": "qml6-module-qt5compat-graphicaleffects",
    "QtMultimedia": "qml6-module-qtmultimedia",
    "QtCore": "qml6-module-qtcore",
    "Qt.labs.platform": "qml6-module-qt-labs-platform",
    "Qt.labs.folderlistmodel": "qml6-module-qt-labs-folderlistmodel",
    "Qt.labs.settings": "qml6-module-qt-labs-settings",
    "Qt.labs.qmlmodels": "qml6-module-qt-labs-qmlmodels",
    "QtWayland.Compositor": "qml6-module-qtwayland-compositor",
}


def package_for(module: str) -> str | None:
    if module == "Quickshell" or module.startswith("Quickshell.") or module.startswith("qs."):
        return None
    if module in TABLE:
        return TABLE[module]
    # QtQuick.Controls.Foo.Bar -> nearest known parent
    parts = module.split(".")
    while len(parts) > 1:
        parts.pop()
        parent = ".".join(parts)
        if parent in TABLE and parent != "QtQuick":
            return TABLE[parent]
    if module.startswith(("Qt", "Qt5Compat")):
        return "qml6-module-" + module.lower().replace(".", "-")
    return None  # third-party or local module: not our business


def scan(root: pathlib.Path) -> list[str]:
    deps: set[str] = set()
    for qml in sorted(root.rglob("*.qml")):
        text = qml.read_text(encoding="utf-8", errors="replace")
        for mod in IMPORT_RE.findall(text):
            pkg = package_for(mod)
            if pkg:
                deps.add(pkg)
    return sorted(deps)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = pathlib.Path(argv[1])
    print(", ".join(scan(root)) if root.is_dir() else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
