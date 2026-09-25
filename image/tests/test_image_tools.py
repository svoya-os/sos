# SPDX-License-Identifier: Apache-2.0
"""image/ and packages/ helpers: pool metadata, QML dependency mapping, control file checks,
package lists and the boot menu template."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "image" / "lib"))
sys.path.insert(0, str(ROOT / "packages" / "lib"))

import check_control  # noqa: E402
import pool_meta  # noqa: E402
import qml_deps  # noqa: E402

SHOW = """Package: nvidia-driver-595-open
Version: 595.91.07-0ubuntu0.26.04.1
Modaliases: nvidia(pci:v000010DEd00002684sv*sd*bc03sc*i*, pci:v000010DEd00002B85sv*sd*bc03sc*i*,
 pci:v000010DEd00002C02sv*sd*bc03sc*i*)
Description: NVIDIA driver (open kernel) metapackage

"""


class PoolMetaTests(unittest.TestCase):
    def test_modaliases_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            show = pathlib.Path(tmp, "show")
            show.write_text(SHOW)
            data = pool_meta.build([f"595-open:nvidia-595-open:nvidia-driver-595-open:{show}:a,b"])
        b = data["branches"][0]
        self.assertEqual(b["driver"], "595.91.07")
        self.assertEqual(b["packages"], ["a", "b"])
        self.assertEqual(len(b["modaliases"]), 3)
        self.assertTrue(all(p.startswith("pci:v000010DE") for p in b["modaliases"]))

    def test_missing_modaliases_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            show = pathlib.Path(tmp, "show")
            show.write_text("Package: x\nVersion: 1\n")
            with self.assertRaises(SystemExit):
                pool_meta.build([f"b:c:x:{show}:p"])


class QmlDepsTests(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(qml_deps.package_for("QtQuick"), "qml6-module-qtquick")
        self.assertEqual(qml_deps.package_for("QtQuick.Controls.Basic"), "qml6-module-qtquick-controls")
        self.assertEqual(qml_deps.package_for("Qt5Compat.GraphicalEffects"), "qml6-module-qt5compat-graphicaleffects")
        self.assertIsNone(qml_deps.package_for("Quickshell.Services.Pipewire"))
        self.assertIsNone(qml_deps.package_for("QtQml"))
        self.assertEqual(qml_deps.package_for("QtPositioning"), "qml6-module-qtpositioning")

    def test_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            pathlib.Path(tmp, "a.qml").write_text("import QtQuick\nimport QtQuick.Layouts\nimport Quickshell\n")
            pathlib.Path(tmp, "b.qml").write_text('import "./components"\nimport qs.core\n')
            self.assertEqual(qml_deps.scan(pathlib.Path(tmp)), ["qml6-module-qtquick", "qml6-module-qtquick-layouts"])


class ControlTests(unittest.TestCase):
    def test_all_package_control_files(self):
        controls = sorted(ROOT.glob("packages/*/debian/control")) + sorted(ROOT.glob("packages/external/*/debian/control"))
        self.assertGreaterEqual(len(controls), 11)
        for c in controls:
            with self.subTest(control=str(c.relative_to(ROOT))):
                self.assertEqual(check_control.check(c.read_text()), [])

    def test_detects_errors(self):
        self.assertTrue(check_control.check("Source: x\n\nPackage: y\n"))
        self.assertTrue(check_control.check("Source: x\nMaintainer: a <b@c>\nBuild-Depends: debhelper-compat (= 13)\n"
                                            "Standards-Version: 4.7.0\n\nPackage: y\nArchitecture: all\n"
                                            "Depends: foo (>> )\nDescription: s\n long\n"))

    def test_cli_replaces_sosreport(self):
        text = (ROOT / "packages/svoya-cli/debian/control").read_text()
        self.assertIn("Conflicts: sosreport", text)


class ListsAndBootTests(unittest.TestCase):
    def read_list(self, name: str) -> list[str]:
        out = subprocess.run(["bash", "-c", f'. "{ROOT}/image/lib/common.sh"; read_list "{ROOT}/image/packages/{name}"'],
                             check=True, capture_output=True, text=True).stdout
        return out.split()

    def test_lists(self):
        base, desktop, live, remove = (self.read_list(n) for n in ("base.list", "desktop.list", "live.list", "remove.list"))
        everything = set(base) | set(desktop) | set(live)
        self.assertIn("svoya-base", base)
        self.assertIn("initramfs-tools", base)
        self.assertIn("casper", live)
        self.assertIn("flatpak", desktop)
        self.assertFalse({"snapd", "sosreport"} & everything)
        self.assertIn("sosreport", remove)
        for name in everything:
            self.assertRegex(name, r"^\??[a-z0-9][a-z0-9.+-]+$")

    def test_grub_menu_entries(self):
        cfg = (ROOT / "image/boot/grub.cfg").read_text()
        self.assertIn('menuentry "SOS @VERSION@"', cfg)
        self.assertIn("(safe graphics", cfg)
        self.assertIn("test in RAM", cfg)
        self.assertIn("проверка в памяти", cfg)
        self.assertEqual(cfg.count("{"), cfg.count("}"))
        for placeholder in set(re.findall(r"@[A-Z_]+@", cfg)):
            self.assertIn(placeholder, ("@DISK_ID@", "@LIVE_USER@", "@LIVE_HOSTNAME@", "@VERSION@"))


if __name__ == "__main__":
    unittest.main()
