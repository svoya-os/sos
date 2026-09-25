import argparse
import contextlib
import io
import json
import unittest

from svoya_cli import commands, i18n, install, menu, session, ui
from svoya_cli.main import main as sos_main
from svoya_cli.util import toml_dumps

from .helpers import FakeRunner, SandboxTest, capture


class NormalizeTest(unittest.TestCase):
    def test_short_verbs_and_russian(self):
        n = commands.normalize
        self.assertEqual(n([]), ["menu"])
        self.assertEqual(n(["fix"]), ["doctor", "--fix"])
        self.assertEqual(n(["починить", "--dry-run"]), ["doctor", "--fix", "--dry-run"])
        self.assertEqual(n(["gpu"]), ["doctor", "--gpu"])
        self.assertEqual(n(["видеокарта", "--json"]), ["doctor", "--gpu", "--json"])
        self.assertEqual(n(["установить", "obsidian"]), ["install", "obsidian"])
        self.assertEqual(n(["поставить", "llm-local"]), ["install", "llm-local"])
        self.assertEqual(n(["удалить", "notes"]), ["remove", "notes"])
        self.assertEqual(n(["обновить"]), ["update"])
        self.assertEqual(n(["откатить"]), ["undo"])
        self.assertEqual(n(["отменить", "список"]), ["undo", "--list"])
        self.assertEqual(n(["модели"]), ["models", "list"])
        self.assertEqual(n(["модели", "подобрать"]), ["models", "suggest"])
        self.assertEqual(n(["модули", "профили"]), ["modules", "profiles"])
        self.assertEqual(n(["help"]), ["--help"])

    def test_theme_words(self):
        n = commands.normalize
        self.assertEqual(n(["theme", "night"]), ["theme", "apply", "graphite"])
        self.assertEqual(n(["тема", "день"]), ["theme", "apply", "paper"])
        self.assertEqual(n(["тема", "авто"]), ["theme", "apply", "auto"])
        self.assertEqual(n(["theme", "phosphor"]), ["theme", "apply", "phosphor"])
        self.assertEqual(n(["theme"]), ["theme", "current"])
        self.assertEqual(n(["theme", "list", "--json"]), ["theme", "list", "--json"])
        self.assertEqual(n(["theme", "apply", "ночь"]), ["theme", "apply", "graphite"])

    def test_did_you_mean(self):
        self.assertIn("models", commands.suggest("modles"))
        self.assertTrue(any(s.startswith("тема") for s in commands.suggest("темаа")))
        self.assertTrue(any("update" in s for s in commands.suggest("updaet")))

    def test_unknown_command_exit_code(self):
        from unittest import mock
        err = io.StringIO()
        with contextlib.redirect_stderr(err), mock.patch.dict("os.environ", {"SVOYA_LANG": "en"}):
            self.assertEqual(sos_main(["modles"]), 2)       # main() picks the language from the environment
        self.assertIn("Did you mean", err.getvalue())

    def test_completion(self):
        self.assertIn("theme", commands.complete(["the"]))
        self.assertEqual(commands.complete(["theme", "ni"]), ["night"])
        self.assertIn("obsidian", commands.complete(["install", "obs"]))
        self.assertIn("qwen3.5-9b:Q4_K_M", commands.complete(["models", "pull", "qwen3.5-9b:"]))
        _, out = capture(sos_main, ["__complete", "modules", "add", "llm"])
        self.assertIn("llm-local", out.split())


class InstallResolveTest(SandboxTest):
    def test_resolution_order(self):
        ctx = self.sb.ctx(FakeRunner())
        kind, obj = install.resolve(ctx, "obsidian")
        self.assertEqual((kind, obj["id"]), ("module", "notes"))
        kind, obj = install.resolve(ctx, "телеграм")
        self.assertEqual((kind, obj["id"]), ("app", "org.telegram.desktop"))
        self.assertEqual(install.resolve(ctx, "qwen3.5-9b"), ("model", "qwen3.5-9b"))
        self.assertEqual(install.resolve(ctx, "unsloth/Qwen3.5-4B-GGUF")[0], "model")
        self.assertIsNone(install.resolve(ctx, "definitely-not-a-thing"))

    def test_app_install_dry_run(self):
        r = FakeRunner(dry_run=True)
        ctx = self.sb.ctx(r, dry_run=True)
        args = argparse.Namespace(cmd="install", things=["gimp"], yes=True, json=False)
        self.assertEqual(install.main(args, ctx), 0)
        self.assertIn("flatpak install --user -y --noninteractive flathub org.gimp.GIMP", self.output())

    def test_unknown_suggests(self):
        ctx = self.sb.ctx(FakeRunner())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = install.main(argparse.Namespace(cmd="install", things=["obsidain"], yes=False, json=False), ctx)
        self.assertEqual(rc, 2)
        self.assertIn("obsidian", err.getvalue())

    def test_apps_table(self):
        apps = install.load_apps()
        self.assertEqual(apps["libreoffice"]["id"], "org.libreoffice.LibreOffice")
        self.assertTrue(apps["discord"]["proprietary"])
        for a in apps.values():
            self.assertRegex(a["id"], r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$")


class MenuTest(SandboxTest):
    def test_prompt_fallback(self):
        lines = []
        choice = menu.prompt_select("t", menu.MAIN, read=lambda _p: "3", write=lines.append)
        self.assertEqual(choice, "fix")
        self.assertEqual(len(lines), 1 + len(menu.MAIN))
        self.assertEqual(menu.prompt_select("t", menu.MAIN, read=lambda _p: "Тема", write=lines.append), "theme")
        self.assertIsNone(menu.prompt_select("t", menu.MAIN, read=lambda _p: "", write=lines.append))

    def test_actions_map_to_commands(self):
        ran = []
        fake_run = lambda argv: ran.append(argv) or 0  # noqa: E731
        self.assertEqual(menu.action("fix", fake_run), 0)
        self.assertEqual(menu.action("gpu", fake_run), 0)
        self.assertEqual(menu.action("update", fake_run), 0)
        menu.action("undo", fake_run, ask=lambda _p: "41")
        self.assertIsNone(menu.action("exit", fake_run))
        self.assertEqual(ran, [["doctor", "--fix"], ["doctor", "--gpu"], ["update"], ["undo", "--list"], ["undo", "41"]])

    def test_theme_menu_offers_accents(self):
        from unittest import mock
        ran = []
        fake_run = lambda argv: ran.append(argv) or 0  # noqa: E731
        with mock.patch.object(menu, "select", side_effect=["__accent", "lilac", "__accent", "__custom", "paper"]):
            menu.action("theme", fake_run)
            menu.action("theme", fake_run, ask=lambda _p: "#7f5af0")
            menu.action("theme", fake_run)
        self.assertEqual(ran, [["theme", "accent", "lilac"], ["theme", "accent", "#7f5af0"], ["theme", "apply", "paper"]])
        ids = [i[0] for i in menu._accent_items()]
        self.assertEqual(ids[0], "signal")
        self.assertEqual(ids[-1], "__custom")

    def test_menu_entries_bilingual(self):
        keys = [m[0] for m in menu.MAIN]
        self.assertEqual(keys, ["install", "models", "fix", "gpu", "update", "undo", "theme", "jackson", "exit"])
        self.assertEqual([m[2] for m in menu.MAIN][:3], ["Установить…", "Модели", "Починить"])


class SessionTest(SandboxTest):
    def test_start_is_idempotent(self):
        shell = self.sb.dir / "shell"
        r = FakeRunner(available={"systemctl", "quickshell", "dbus-update-activation-environment"})
        ctx = self.sb.ctx(r, SVOYA_SHELL_DIR=str(shell), WAYLAND_DISPLAY="wayland-1", HYPRLAND_INSTANCE_SIGNATURE="abc")
        steps = {s["step"]: s for s in session.start(ctx)}
        self.assertTrue(r.called("dbus-update-activation-environment", "--systemd", "WAYLAND_DISPLAY",
                                 "HYPRLAND_INSTANCE_SIGNATURE"))
        self.assertTrue(steps["theme"]["ok"])
        self.assertTrue(r.called("systemctl", "--user", "start", "--no-block", "jacksond.service"))
        self.assertIn(["quickshell", "-p", str(shell)], r.spawned)
        self.assertIn(["quickshell", "-p", f"{shell}/setup"], r.spawned)       # first login
        self.assertTrue(ctx.paths.theme_json.exists())
        # the shell is now "running" and first-run is done → nothing new is spawned
        self.sb.write("/proc/4242/cmdline", b"/usr/bin/quickshell\0-p\0" + str(shell).encode() + b"\0")
        ctx.paths.first_run_marker.parent.mkdir(parents=True, exist_ok=True)
        ctx.paths.first_run_marker.write_text("")
        r2 = FakeRunner(available={"systemctl", "quickshell"})
        steps2 = {s["step"]: s for s in session.start(self.sb.ctx(r2, SVOYA_SHELL_DIR=str(shell)))}
        self.assertEqual(steps2["shell"]["detail"], "already running")
        self.assertFalse(any(c[0] == "quickshell" for c in r2.spawned))
        self.assertNotIn("first-run", steps2)

    def test_shell_runs_supervised_when_shell_run_is_installed(self):
        shell = self.sb.dir / "shell"
        self.sb.write("/usr/lib/svoya/shell-run", "#!/bin/sh\n")
        r = FakeRunner(available={"systemctl", "quickshell"})
        ctx = self.sb.ctx(r, SVOYA_SHELL_DIR=str(shell), WAYLAND_DISPLAY="wayland-1", LANG="ru_RU.UTF-8")
        session.start(ctx)
        self.assertIn(["/usr/lib/svoya/shell-run", str(shell)], r.spawned)                 # logs + restarts
        self.assertIn(["/usr/lib/svoya/shell-run", "--once", f"{shell}/setup"], r.spawned)  # wizard: logs only
        self.assertFalse(any(c[:1] == ["quickshell"] for c in r.spawned))
        # the language reaches services started later (Jackson answers in the user's language)
        imported = [c for c in r.calls if c[:3] == ["systemctl", "--user", "import-environment"]]
        self.assertTrue(imported and "LANG" in imported[0])

    def test_ai_switched_off_skips_jackson(self):
        (self.sb.home / ".config/svoya").mkdir(parents=True)
        (self.sb.home / ".config/svoya/svoya.toml").write_text("[ai]\nenabled = false\n")
        r = FakeRunner(available={"systemctl"})
        steps = {s["step"]: s for s in session.start(self.sb.ctx(r, SVOYA_SHELL_DIR=str(self.sb.dir / "sh")))}
        self.assertIn("AI off", steps["jacksond"]["detail"])
        self.assertFalse(r.called("systemctl", "--user", "start"))


class I18nUtilTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("en")

    def test_numbers(self):
        i18n.set_lang("ru")
        self.assertEqual(i18n.num(48213), f"48{i18n.NNBSP}213")
        self.assertEqual(i18n.num(11.24, 1), "11,2")
        self.assertEqual(i18n.gib(11.2 * 2**30), "11,2 ГБ")
        self.assertEqual(i18n.count(3, "package", "packages", "пакет", "пакета", "пакетов"), "3 пакета")
        self.assertEqual(i18n.count(11, "package", "packages", "пакет", "пакета", "пакетов"), "11 пакетов")
        self.assertEqual(i18n.duration(1080), "18 мин")
        i18n.set_lang("en")
        self.assertEqual(i18n.num(48213), "48,213")
        self.assertEqual(i18n.count(1, "file", "files", "файл", "файла", "файлов"), "1 file")

    def test_lang_detection(self):
        self.assertEqual(i18n.detect_lang({"LANG": "ru_RU.UTF-8"}), "ru")
        self.assertEqual(i18n.detect_lang({"LC_ALL": "en_US.UTF-8", "LANG": "ru_RU.UTF-8"}), "en")
        self.assertEqual(i18n.detect_lang({"SVOYA_LANG": "ru", "LANG": "C"}), "ru")
        self.assertEqual(i18n.detect_lang({}), "en")

    def test_no_color_and_truecolor(self):
        s = ui.Style(stream=io.StringIO(), env={"NO_COLOR": "1", "FORCE_COLOR": "1"})
        self.assertFalse(s.enabled)
        s = ui.Style(stream=io.StringIO(), env={"FORCE_COLOR": "1", "COLORTERM": "truecolor"})
        self.assertEqual(s.accent("x"), "\x1b[38;2;255;181;71mx\x1b[0m")
        s = ui.Style(stream=io.StringIO(), env={"FORCE_COLOR": "1", "TERM": "xterm-256color"})
        self.assertIn("38;5;", s.accent("x"))

    def test_toml_dumps_roundtrip(self):
        import tomllib
        data = {"a": 1, "b": "x\"y", "t": {"k": [1, 2], "f": 1.5, "on": True}, "arr": [{"n": "1"}, {"n": "2"}]}
        self.assertEqual(tomllib.loads(toml_dumps(data)), data)

    def test_json_outputs_are_parseable(self):
        _, out = capture(sos_main, ["theme", "list", "--json"])
        ids = [t["id"] for t in json.loads(out)]
        self.assertEqual(ids[:3], ["graphite", "paper", "phosphor"])


if __name__ == "__main__":
    unittest.main()
