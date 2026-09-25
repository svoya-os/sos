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

    def test_cli_replaces_sos(self):
        # resolute: /usr/bin/sos belongs to package "sos"; "sosreport" is its transitional package.
        paras = check_control.parse_paragraphs((ROOT / "packages/svoya-cli/debian/control").read_text())
        cli = next(p for p in paras if p.get("Package") == "svoya-cli")
        for field in ("Conflicts", "Replaces"):
            names = {x.strip().split()[0] for x in cli[field].split(",")}
            self.assertLessEqual({"sos", "sosreport"}, names, field)

    def test_cli_templates_are_not_byte_compiled(self):
        # py3compile (postinst of dh_python3 packages) exits 1 on the first SyntaxError; the `sos new`
        # templates contain {{ placeholders }}, so debian/rules must exclude them ...
        rules = (ROOT / "packages/svoya-cli/debian/rules").read_text()
        self.assertIn("-X '.*/svoya_cli/data/'", rules)
        # ... and every other .py file shipped in /usr/lib/svoya must compile.
        import py_compile
        for pkg in (ROOT / "cli/svoya_cli", ROOT / "jackson/jackson"):
            for py in sorted(pkg.rglob("*.py")):
                if "__pycache__" in py.parts or re.search(r"/svoya_cli/data/", py.as_posix()):
                    continue
                with self.subTest(file=str(py.relative_to(ROOT))), tempfile.TemporaryDirectory() as tmp:
                    py_compile.compile(str(py), cfile=str(pathlib.Path(tmp, "x.pyc")), doraise=True)


class StagePyappTests(unittest.TestCase):
    def test_nested_tests_dirs_are_package_data(self):
        import stage_pyapp
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp, "src")
            for rel in ("pkg/__init__.py", "pkg/tests/test_x.py", "pkg/__pycache__/x.pyc",
                        "pkg/data/new/common/tests/test_smoke.py", "pkg/data/build/keep.txt"):
                p = src / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("")
            dest = stage_pyapp.stage(src, "pkg", pathlib.Path(tmp, "dest"))
            self.assertTrue((dest / "data/new/common/tests/test_smoke.py").is_file())
            self.assertTrue((dest / "data/build/keep.txt").is_file())
            self.assertFalse((dest / "tests").exists())
            self.assertFalse((dest / "__pycache__").exists())


class PrepareScriptTests(unittest.TestCase):
    """The prepare.sh steps that need no network, run against the real component trees."""

    def prepare(self, pkg: str, tmp: str) -> pathlib.Path:
        pkg_dir = pathlib.Path(tmp, pkg)
        (pkg_dir / "debian").mkdir(parents=True)
        subprocess.run(["bash", str(ROOT / "packages" / pkg / "prepare.sh")], check=True, capture_output=True,
                       env={"PATH": "/usr/bin:/bin", "SVOYA_SRC": str(ROOT), "PKG_DIR": str(pkg_dir)})
        return pkg_dir / "files"

    def test_base_identity_comes_from_branding(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = self.prepare("svoya-base", tmp)
            staged = (files / "usr/lib/os-release").read_text()
            self.assertEqual(staged, (ROOT / "branding/os/root/usr/lib/os-release").read_text())
            self.assertIn("UBUNTU_CODENAME=resolute", staged)
            for rel in ("etc/lsb-release", "etc/issue", "etc/issue.net", "etc/upstream-release/lsb-release"):
                self.assertTrue((files / rel).is_file(), rel)
            self.assertTrue((files / "usr/share/svoya/motd").is_file())
        preinst = (ROOT / "packages/svoya-base/debian/svoya-base.preinst").read_text()
        for path in ("/usr/lib/os-release", "/etc/lsb-release", "/etc/issue", "/etc/issue.net"):
            self.assertIn(path, preinst)

    def test_branding_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = self.prepare("svoya-branding", tmp)
            themes = sorted(p.name for p in (files / "usr/share/plymouth/themes").iterdir())
            self.assertEqual(themes, ["svoya-signal"])  # not the preview frames or the test harness
            for rel in ("usr/share/icons/hicolor/scalable/apps/sos.svg",
                        "usr/share/icons/hicolor/symbolic/apps/sos-symbolic.svg",
                        "usr/share/icons/hicolor/256x256/apps/sos.png",
                        "usr/share/grub/themes/svoya/theme.txt",
                        "etc/default/grub.d/90-sos-theme.cfg",
                        "usr/share/sounds/svoya/index.theme",
                        "usr/share/svoya/sounds/index.theme",          # ARCHITECTURE §3 path (link)
                        "usr/share/svoya/wallpapers/wallpapers.json",
                        "usr/share/svoya/fastfetch/logo.txt"):
                self.assertTrue((files / rel).exists(), rel)
            self.assertTrue((files / "usr/share/svoya/sounds").is_symlink())

    def test_installer_branding_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = self.prepare("svoya-installer", tmp)
            welcome = files / "etc/calamares/branding/svoya/welcome.png"
            lockup = ROOT / "branding/out/logo/sos-lockup-stacked-en-on-dark.png"
            self.assertEqual(welcome.read_bytes(), lockup.read_bytes())

    def test_cli_ships_the_complete_project_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = self.prepare("svoya-cli", tmp)
            self.assertTrue((files / "usr/lib/svoya/svoya_cli/data/new/common/tests/test_smoke.py").is_file())
            self.assertTrue((files / "usr/bin/svoya").is_symlink())


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
        self.assertFalse({"snapd", "sos", "sosreport"} & everything)
        self.assertIn("sosreport", remove)
        self.assertIn("sos", remove)
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
