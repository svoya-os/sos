# SPDX-License-Identifier: Apache-2.0
"""«установи телеграм» opens `sos install` in a terminal; «открой навыки» / «создай навык …»."""

import unittest

from jackson import fastpath, skills
from jackson.osctl import OsControl
from jackson.paths import Paths
from tests.fakes import FakeRunner, rmtree, short_tmpdir

BASE = {"sos", "notify-send", "systemd-run", "systemctl", "pgrep", "gtk-launch"}


class Base(unittest.TestCase):
    extra: set[str] = {"kitty", "xdg-open"}

    def setUp(self):
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        self.paths.home.mkdir(parents=True, exist_ok=True)
        self.runner = FakeRunner(self.paths, available=BASE | self.extra)
        self.osc = OsControl(self.runner, self.paths, None)

    def tearDown(self):
        rmtree(self.root)

    def say(self, text, persona="dispatcher"):
        m = fastpath.match(text, self.osc)
        self.assertIsNotNone(m, text)
        return m, fastpath.run(m, fastpath.FastCtx(self.osc, "ru", persona, humor=1, seed="t"))

    def spawned(self):
        return [argv for _, argv in self.runner.spawned]


class InstallTest(Base):
    def test_app_install_opens_a_terminal(self):
        m, r = self.say("Джексон, установи телеграм")
        self.assertEqual(m.intent.name, "install")
        self.assertTrue(r.ok, r.text)
        self.assertIn("Открыл установку Telegram в терминале", r.text)
        (argv,) = self.spawned()
        self.assertEqual(argv[:3], ["kitty", "-e", "sh"])
        self.assertEqual(argv[-3:], ["sos", "install", "telegram"])      # the user confirms there

    def test_module_asks_for_the_password(self):
        m, r = self.say("поставь стим")
        self.assertIn("модуля «Игры»", r.text)
        self.assertIn("пароль", r.text)
        self.assertEqual(self.spawned()[0][-3:], ["sos", "install", "gaming"])

    def test_installed_and_unknown(self):
        m, r = self.say("установи гимп")
        self.assertIn("уже стоит", r.text)
        self.assertEqual(self.spawned(), [])
        self.assertIsNone(fastpath.match("скачай модель квен побольше", self.osc))   # the model decides
        self.assertEqual(fastpath.match("поставь таймер на 5 минут", self.osc).intent.name, "timer")

    def test_opening_a_missing_app_offers_the_install(self):
        m, r = self.say("открой майнкрафт")
        self.assertEqual(m.intent.name, "install")
        self.assertIn("Пока не установлено. Открыл установку Prism Launcher", r.text)


class ModelTest(Base):
    def test_which_model_fits_without_a_model(self):
        m, r = self.say("which model fits this computer")
        self.assertEqual(m.intent.name, "model_suggest")
        self.assertIn("Qwen3.5 4B (Q4_K_M, 3,2 ГБ, около 12 токенов в секунду на процессоре)", r.text)
        self.assertIn("«установи модель»", r.text)
        m, r = self.say("установи модель")
        self.assertEqual(self.spawned()[0][-3:], ["sos", "install", "qwen3.5-4b:Q4_K_M"])
        self.assertIn("Открыл установку Qwen3.5 4B (3,2 ГБ)", r.text)


class NoTerminalTest(Base):
    extra = set()

    def test_says_the_command(self):
        m, r = self.say("установи телеграм")
        self.assertFalse(r.ok)
        self.assertIn("sos install telegram", r.text)


class SkillsTest(Base):
    def test_open_the_folder(self):
        m, r = self.say("открой навыки")
        self.assertEqual(m.intent.name, "skills")
        folder = self.paths.skills_dir
        self.assertTrue((folder / "README.md").exists())
        self.assertIn(folder.as_uri(), (self.paths.config_home / "gtk-3.0" / "bookmarks").read_text())
        self.assertIn(["xdg-open", str(folder)], self.spawned())
        self.assertIn("Открыл папку навыков: ~/.local/share/svoya/jackson/skills", r.text)
        self.assertEqual(fastpath.match("где мои навыки", self.osc).intent.name, "skills")

    def test_new_skill_from_a_template(self):
        m, r = self.say("создай навык Пицца")
        self.assertEqual(m.intent.name, "new_skill")
        path = self.paths.skills_dir / "пицца" / "SKILL.md"
        self.assertTrue(path.exists())
        self.assertEqual(skills.parse_skill(path).name, "Пицца")
        self.assertIn(["xdg-open", str(path)], self.spawned())
        m, r = self.say("создай навык пицца")
        self.assertIn("уже есть", r.text)

    def test_readme_and_bookmark_only_once(self):
        folder, created = skills.init_dir(self.paths.skills_dir, self.paths.config_home, "en")
        self.assertTrue(created)
        (folder / "README.md").unlink()
        bookmarks = self.paths.config_home / "gtk-3.0" / "bookmarks"
        bookmarks.write_text("")
        self.assertFalse(skills.init_dir(self.paths.skills_dir, self.paths.config_home, "en")[1])
        self.assertFalse((folder / "README.md").exists())              # deleting it sticks
        self.assertEqual(bookmarks.read_text(), "")


if __name__ == "__main__":
    unittest.main()
