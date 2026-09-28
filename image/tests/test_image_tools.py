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

    def test_diverted_identity_files_are_not_conffiles(self):
        # dpkg keeps a diverted conffile "deleted" (ISO #8: no /etc/lsb-release, «Welcome to  (GNU/Linux…)»)
        pre = (ROOT / "packages/svoya-base/debian/svoya-base.preinst").read_text()
        diverted = re.search(r'DIVERTED="([^"]+)"', pre).group(1).split()
        rules = (ROOT / "packages/svoya-base/debian/rules").read_text()
        for path in diverted:
            if path.startswith("/etc/"):
                self.assertIn("\\|^" + path.replace(".", "\\.") + "$$|d", rules, path)
        debrand = (ROOT / "image/hooks/70-debrand.sh").read_text()
        for path in diverted:
            self.assertIn(path, debrand)                 # the build fails when one is missing

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

    def test_jackson_ships_the_system_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = self.prepare("svoya-jackson", tmp)
            for name in ("sos", "games"):
                skill = files / f"usr/share/svoya/jackson/skills/{name}/SKILL.md"
                self.assertTrue(skill.is_file(), name)
                self.assertLessEqual(len(skill.read_text(encoding="utf-8")), 4000 + 400)   # body cap + front matter

    def test_grub_font_ranges_are_pairs(self):
        # grub-mkfont reads --range as FROM-TO[,FROM-TO…]; a bare code point is "invalid font range"
        # and the theme ships without fonts (theme-fonts=0 in the VM test).
        text = (ROOT / "branding/grub/make-fonts.sh").read_text()
        ranges = re.search(r'^ranges="([^"]+)"', text, re.M).group(1).split(",")
        for part in ranges:
            a, sep, b = part.partition("-")
            self.assertEqual(sep, "-", part)
            self.assertLessEqual(int(a, 0), int(b, 0), part)

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

    def gpu_env(self, driver: str | None, render: bool, **env) -> dict:
        """Source packages/svoya-session/.../gpu-env against a fake /sys and /dev."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            if driver:
                (root / "sys/bus/pci/drivers" / driver).mkdir(parents=True)
                dev = root / "sys/class/drm/card0/device"
                dev.mkdir(parents=True)
                (dev / "driver").symlink_to(root / "sys/bus/pci/drivers" / driver)
                (root / "sys/class/drm/card0-Virtual-1").mkdir()          # a connector: no driver
            if render:
                (root / "dev/dri").mkdir(parents=True)
                (root / "dev/dri/renderD128").touch()
            script = (f'set -euo pipefail; . "{ROOT}/packages/svoya-session/files/usr/lib/svoya/gpu-env"; '
                      'printf "%s|%s|%s|%s" "${MESA_LOADER_DRIVER_OVERRIDE:-}" "${LIBGL_ALWAYS_SOFTWARE:-}" '
                      '"${GBM_ALWAYS_SOFTWARE:-}" "$(type svoya_gpu_software >/dev/null 2>&1 && echo leaked)"')
            clean = {"PATH": "/usr/bin:/bin", "SVOYA_GPU_ROOT": str(root), **env}
            out = subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True, env=clean).stdout
        override, soft, gbm, leaked = out.split("|")
        self.assertEqual(leaked, "")                 # the helper function does not stay in the session
        return {"override": override, "software": soft, "gbm": gbm}

    def test_gpu_env_software_where_hyprland_cannot_start(self):
        vmw = {"override": "kms_swrast", "software": "1", "gbm": ""}
        # no render node: EGL on GBM asks for a render device unless GBM is in software mode
        # (ISO #9: "DRI2: failed to get compatible render device" on simpledrm)
        display_only = {"override": "", "software": "1", "gbm": "1"}
        hw = {"override": "", "software": "", "gbm": ""}
        self.assertEqual(self.gpu_env("vmwgfx", True), vmw)                          # VirtualBox VMSVGA, VMware
        self.assertEqual(self.gpu_env("simple-framebuffer", False), display_only)    # nomodeset («safe graphics»)
        self.assertEqual(self.gpu_env("bochs-drm", False), display_only)             # QEMU standard VGA
        self.assertEqual(self.gpu_env("virtio_gpu", True), hw)                       # Mesa falls back by itself
        self.assertEqual(self.gpu_env("i915", True), hw)
        self.assertEqual(self.gpu_env(None, False), hw)                              # no display at all
        self.assertEqual(self.gpu_env("vmwgfx", True, SVOYA_GPU="hardware"), hw)
        self.assertEqual(self.gpu_env("simple-framebuffer", False, SVOYA_GPU="hardware"), hw)

    def snap(self, where: str, window: dict | None, monitors: list | None = None) -> list[str]:
        """Run packages/svoya-session/.../snap-window with a fake hyprctl; the hyprctl calls it made."""
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = pathlib.Path(tmp)
            (bin_dir / "window.json").write_text(json.dumps(window or {}))
            (bin_dir / "monitors.json").write_text(json.dumps(monitors or []))
            fake = bin_dir / "hyprctl"
            fake.write_text(f"""#!/bin/sh
printf '%s\\n' "$*" >> {tmp}/calls
case "$*" in
    "-j activewindow") cat {tmp}/window.json ;;
    "-j monitors") cat {tmp}/monitors.json ;;
esac
""")
            fake.chmod(0o755)
            env = {"PATH": f"{tmp}:/usr/bin:/bin", "SVOYA_HYPR_DIR": str(ROOT / "shell/hypr")}
            subprocess.run([sys.executable, str(ROOT / "packages/svoya-session/files/usr/lib/svoya/snap-window"), where],
                           check=True, env=env, capture_output=True, text=True)
            calls = (bin_dir / "calls").read_text().splitlines()
        return [c for c in calls if not c.startswith("-j ")]

    def test_snap_window_like_windows(self):
        mon = [{"id": 0, "x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1.0, "focused": True,
                "reserved": [0, 36, 0, 0]}]
        floating = {"address": "0xabc", "floating": True, "monitor": 0, "fullscreen": 0}
        # tiled (or nothing focused): the arrows move the focus, as before
        self.assertEqual(self.snap("left", {"address": "0x1", "floating": False}), ["dispatch movefocus l"])
        self.assertEqual(self.snap("up", None), ["dispatch movefocus u"])
        # up: maximize (fullscreen 1 keeps the bar); left/right: a half under the bar, gaps kept
        self.assertEqual(self.snap("up", floating, mon), ["dispatch fullscreen 1"])
        left, = self.snap("left", floating, mon)
        self.assertEqual(left, "--batch dispatch resizewindowpixel exact 942 984,address:0xabc ; "
                               "dispatch movewindowpixel exact 12 84,address:0xabc")
        right, = self.snap("right", floating, mon)
        self.assertIn("movewindowpixel exact 966 84,address:0xabc", right)
        # the browser draws its own title bar (no hyprbars bar): it starts right under the gap
        browser, = self.snap("left", dict(floating, **{"class": "firefox"}), mon)
        self.assertEqual(browser, "--batch dispatch resizewindowpixel exact 942 1020,address:0xabc ; "
                                  "dispatch movewindowpixel exact 12 48,address:0xabc")
        # a maximized window leaves that state first; down puts it back in the middle
        calls = self.snap("down", dict(floating, fullscreen=1), mon)
        self.assertEqual(calls[0], "dispatch fullscreenstate 0 0")
        self.assertEqual(calls[1], "--batch dispatch resizewindowpixel exact 1176 678,address:0xabc ; "
                                   "dispatch movewindowpixel exact 372 237,address:0xabc")

    def test_live_only_files_stay_off_the_installed_system(self):
        hook = (ROOT / "image/hooks/50-live.sh").read_text()
        excluded = set(hook.split("live-exclude.rsync\" 0644 <<'EOF'\n", 1)[1].split("\nEOF", 1)[0].splitlines())
        overlay = ROOT / "image/overlay-live"
        for path in overlay.rglob("*"):
            if path.is_file():
                with self.subTest(path=path):
                    self.assertIn("/" + str(path.relative_to(overlay)), excluded)
        for target in re.findall(r'write_file "\$root(/etc/[^"]+)"', hook):
            if target != "/etc/casper.conf":                     # casper is a live-only package
                with self.subTest(target=target):
                    self.assertIn(target, excluded)
        # ISO #13: no AppArmor profile is loaded in the live session (Ubuntu's apparmor.service skips a
        # live system) while the user-namespace restriction stayed on — Steam, Flatpak, bwrap failed
        self.assertRegex(hook, r"(?m)^kernel\.apparmor_restrict_unprivileged_userns = 0$")
        self.assertIn("/etc/sysctl.d/99-sos-live-userns.conf", excluded)

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


class TwoImagesTests(unittest.TestCase):
    """build-iso.sh writes the NVIDIA image and, from the same tree, the standard one: the pool
    without the NVIDIA drivers, the full tree left untouched (the standard one is hard links)."""

    STUBS = {
        # the index the installer reads (target-prepare.sh: Components)
        "apt-ftparchive": 'for a; do case $a in *Components=*) c=${a#*Components=} ;; esac; done\n'
                          'printf "Origin: SOS\\nComponents: %s\\n" "$c"\n',
        "xorriso": 'o=""; p=""; for a; do [ "$p" = -o ] && o=$a; p=$a; done\n'
                   '[ -n "$o" ] && find "${@: -1}" -type f | sort >"$o"; exit 0\n',
    }

    def test_standard_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            iso = tmp / "work" / "iso"
            files = {
                "casper/filesystem.squashfs": "squashfs",
                "casper/filesystem.manifest": "pkg\t1\n",
                "pool/main/g/grub.deb": "grub",
                "pool/nvidia-595-open/n/nvidia.deb": "nvidia",
                "pool/svoya-gpu.json": '{"branches": [{"id": "595-open"}]}',
                "dists/resolute/main/binary-amd64/Packages": "Package: grub\n",
                "dists/resolute/nvidia-595-open/binary-amd64/Packages": "Package: nvidia\n",
                "dists/resolute/Release": "Components: main nvidia-595-open\n",
            }
            for rel, text in files.items():
                (iso / rel).parent.mkdir(parents=True, exist_ok=True)
                (iso / rel).write_text(text)
            stubs = tmp / "bin"
            stubs.mkdir()
            for name, body in self.STUBS.items():
                (stubs / name).write_text("#!/bin/bash\n" + body)
                (stubs / name).chmod(0o755)
            script = f"""
                set -euo pipefail
                source {ROOT}/image/build-iso.sh
                WORK={tmp}/work ISO={iso} ISO_STD={tmp}/work/iso-standard OUT={tmp}/out
                SUITE=resolute ARCH=amd64 SOURCE_DATE_EPOCH=0
                export SOURCE_DATE_EPOCH
                has_nvidia_pool
                make_iso "$ISO" full.iso
                standard_tree
                make_iso "$ISO_STD" standard.iso
            """
            env = {"PATH": f"{stubs}:/usr/bin:/bin", "HOME": str(tmp)}
            res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            std = tmp / "work" / "iso-standard"
            # the full tree keeps everything
            self.assertTrue((iso / "pool/nvidia-595-open/n/nvidia.deb").exists())
            self.assertIn("595-open", (iso / "pool/svoya-gpu.json").read_text())
            self.assertIn("nvidia-595-open", (iso / "dists/resolute/Release").read_text())
            self.assertIn("nvidia.deb", (iso / "md5sum.txt").read_text())
            # the standard tree: main only, an empty driver list, its own checksums
            self.assertFalse((std / "pool/nvidia-595-open").exists())
            self.assertFalse((std / "dists/resolute/nvidia-595-open").exists())
            self.assertEqual(json.loads((std / "pool/svoya-gpu.json").read_text()), {"branches": []})
            self.assertIn("Components: main\n", (std / "dists/resolute/Release").read_text())
            self.assertTrue((std / "dists/resolute/main/binary-amd64/Packages").exists())
            self.assertNotIn("nvidia", (std / "md5sum.txt").read_text())
            self.assertIn("grub.deb", (std / "md5sum.txt").read_text())
            # the squashfs is shared, not copied
            self.assertEqual((std / "casper/filesystem.squashfs").stat().st_ino,
                             (iso / "casper/filesystem.squashfs").stat().st_ino)
            info = {n: json.loads((tmp / "out" / f"{n}.json").read_text()) for n in ("full.iso", "standard.iso")}
            self.assertEqual((info["full.iso"]["variant"], info["full.iso"]["nvidiaBranches"]), ("nvidia", ["595-open"]))
            self.assertEqual((info["standard.iso"]["variant"], info["standard.iso"]["nvidiaBranches"]), ("standard", []))
            self.assertLess(info["standard.iso"]["poolBytes"], info["full.iso"]["poolBytes"])


class ReleaseNotesTests(unittest.TestCase):
    """The download page: the standard image first, the NVIDIA one with how to join its parts."""

    def test_notes_and_join(self):
        sys.path.insert(0, str(ROOT / "scripts" / "release"))
        import notes
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            for name, variant, size in (("sos-26.10-amd64.iso", "standard", 1_800_000_000),
                                        ("sos-26.10-amd64-nvidia.iso", "nvidia", 2_600_000_000)):
                (d / f"{name}.json").write_text(json.dumps({"iso": name, "variant": variant, "isoBytes": size}))
            (d / "sos-26.10-amd64.iso").write_bytes(b"x")
            for n in ("00", "01"):
                (d / f"sos-26.10-amd64-nvidia.iso.part{n}").write_bytes(b"y")
            text = notes.notes(d, "784544be5f10", "test")
        self.assertIn("коммит `784544b`", text)
        self.assertLess(text.index("`sos-26.10-amd64.iso`** (1,7 ГБ, один файл)"),
                        text.index("`sos-26.10-amd64-nvidia.iso`** (2,4 ГБ, частями)"))
        self.assertIn("`sos-26.10-amd64-nvidia.iso.part00`, `sos-26.10-amd64-nvidia.iso.part01`", text)
        self.assertIn("`sos-join.bat` с `sos-join.ps1` (Windows)", text)
        self.assertIn("(1.7 GB, one file)", text)
        self.assertEqual(text.count("sos-join.sh"), 2)              # the NVIDIA image only, RU and EN
        self.assertLess(text.index("Тестовая сборка"), text.index("SOS test build"))

    def test_windows_helpers(self):
        bat = (ROOT / "scripts/release/sos-join.bat").read_bytes()
        self.assertIn(b"\r\n", bat)                                  # cmd.exe wants CRLF
        self.assertTrue(bat.isascii())
        ps1 = (ROOT / "scripts/release/sos-join.ps1").read_bytes()
        self.assertTrue(ps1.startswith(b"\xef\xbb\xbf"))            # UTF-8 with BOM for Windows PowerShell
        self.assertIn("sos-join.ps1", bat.decode())
        attrs = (ROOT / ".gitattributes").read_text()
        self.assertIn("*.bat   text eol=crlf", attrs)

