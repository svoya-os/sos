# SPDX-License-Identifier: Apache-2.0
import time
import unittest

from jackson import fastpath
from jackson.fastpath import FastCtx, match, normalize, parse_duration, parse_number
from jackson.osctl import OsControl
from jackson.paths import Paths
from jackson.svoya import SvoyaCli
from tests.fakes import FakeRunner, install_desktop_entry, rmtree, short_tmpdir

POSITIVE = {
    "громче": "volume_up", "Джексон, сделай погромче, пожалуйста": "volume_up", "прибавь звук на 20%": "volume_up",
    "louder": "volume_up", "turn the volume up by 5": "volume_up",
    "тише": "volume_down", "убавь громкость": "volume_down", "volume down": "volume_down",
    "громкость 30": "volume_set", "поставь громкость на тридцать процентов": "volume_set",
    "set volume to 70%": "volume_set", "какая громкость?": "volume_get", "what's the volume": "volume_get",
    "выключи звук": "mute", "mute": "mute", "включи звук": "unmute", "unmute": "unmute",
    "ярче": "brightness_up", "сделай экран потемнее": "brightness_down", "яркость 60%": "brightness_set",
    "brightness up": "brightness_up", "dim the screen": "brightness_down",
    "открой загрузки": "open_folder", "open downloads": "open_folder",
    "заблокируй экран": "lock", "lock the screen": "lock", "сделай скриншот": "screenshot", "screenshot": "screenshot",
    "тёмная тема": "theme", "включи светлую тему": "theme", "тема авто": "theme", "dark mode": "theme",
    "switch to light theme": "theme",
    "таймер на 5 минут": "timer", "поставь таймер на полчаса": "timer", "напомни через 10 минут выключить чайник": "timer",
    "set a timer for 30 seconds": "timer", "remind me in 2 hours to stretch": "timer",
    "какая у меня видеокарта?": "gpu", "сколько видеопамяти": "gpu", "what's my gpu": "gpu", "vram": "gpu",
    "сколько места на диске": "disk", "disk space": "disk", "заряд батареи": "battery", "battery": "battery",
    "включи вайфай": "wifi_on", "выключи wi-fi": "wifi_off", "turn off wifi": "wifi_off",
    "включи блютуз": "bluetooth_on", "bluetooth off": "bluetooth_off",
    "сколько оперативной памяти": "ram", "memory usage": "ram", "какой процессор": "cpu",
    "сколько работает компьютер": "uptime", "uptime": "uptime", "который час": "time", "what time is it": "time",
    "какое сегодня число": "date", "мой ip": "ip", "what's my ip address": "ip",
    "что ты умеешь?": "help", "what can you do": "help", "отмени": "undo", "верни как было": "undo", "undo": "undo",
    "какие модели доступны": "models", "только локально": "route_local", "можно облако": "route_any",
    "новый разговор": "new_chat", "start over": "new_chat",
}

NEGATIVE = [
    "как сделать тёмную тему в VS Code?",
    "почему у меня тише звук в наушниках после обновления",
    "открой файл отчёт.pdf и перескажи",
    "напиши скрипт, который делает скриншот каждые 5 минут",
    "what is the best GPU for training llama models",
    "сколько места займёт модель на 14b",
    "открой несуществующее приложение",
    "расскажи анекдот",
]


class ParsingTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        self.runner = FakeRunner(self.paths)
        self.osc = OsControl(self.runner, self.paths, SvoyaCli(self.runner, self.paths), sleep=lambda s: None)
        install_desktop_entry(self.paths, "org.mozilla.firefox", "Firefox", "firefox %u",
                              "Name[ru]=Firefox\nGenericName[ru]=Веб-браузер\nKeywords=web;browser;")

    def tearDown(self):
        rmtree(self.root)

    def test_positive(self):
        failures = []
        for text, intent in POSITIVE.items():
            m = match(text, self.osc)
            if m is None or m.name != intent:
                failures.append((text, intent, m.name if m else None))
        self.assertEqual(failures, [])
        self.assertGreaterEqual(len({i for i in POSITIVE.values()}), 30)

    def test_open_app_needs_an_installed_app(self):
        self.assertEqual(match("открой firefox", self.osc).name, "open_app")
        self.assertEqual(match("запусти браузер", self.osc).name, "open_app")
        self.assertEqual(match("open Firefox", self.osc).args["_entry"].id, "org.mozilla.firefox")
        self.assertIsNone(match("открой blender", self.osc))

    def test_negative(self):
        for text in NEGATIVE:
            self.assertIsNone(match(text, self.osc), text)

    def test_normalize_and_numbers(self):
        self.assertEqual(normalize("Эй, Джексон!  Сделай ГРОМЧЕ, пожалуйста."), "сделай громче")
        self.assertEqual(normalize("Hey Jackson, can you mute?"), "mute")
        self.assertEqual(parse_number("двадцать пять"), 25)
        self.assertEqual(parse_number("thirty"), 30)
        self.assertEqual(parse_duration("полчаса", None), 1800)
        self.assertEqual(parse_duration("2", "часа"), 7200)
        self.assertEqual(parse_duration("30", "seconds"), 30)
        self.assertEqual(parse_duration("5", None), 300)

    def test_matching_is_fast(self):
        t0 = time.monotonic()
        for _ in range(20):
            for text in list(POSITIVE) + NEGATIVE:
                match(text, self.osc)
        per = (time.monotonic() - t0) / (20 * (len(POSITIVE) + len(NEGATIVE)))
        self.assertLess(per, 0.05)


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        self.runner = FakeRunner(self.paths)
        self.osc = OsControl(self.runner, self.paths, SvoyaCli(self.runner, self.paths), sleep=lambda s: None)
        install_desktop_entry(self.paths, "firefox", "Firefox", "firefox %u")

    def tearDown(self):
        rmtree(self.root)

    def run_text(self, text, lang="ru", persona="sysop"):
        m = match(text, self.osc)
        self.assertIsNotNone(m, text)
        return fastpath.run(m, FastCtx(self.osc, lang, persona))

    def test_volume_verified_and_undoable(self):
        res = self.run_text("громче")
        self.assertTrue(res.ok and res.verified)
        self.assertEqual(res.text, "Громкость 50%.")
        self.assertAlmostEqual(self.runner.volume, 0.50)
        self.assertEqual(res.undo[0].data["prev"], 0.40)
        self.assertEqual(self.run_text("volume 25", "en").text, "Volume 25%.")

    def test_no_false_done_when_nothing_changed(self):
        self.runner.broken.add("wpctl")
        res = self.run_text("громче")
        self.assertFalse(res.ok)
        self.assertIn("осталась 40%", res.text)

    def test_missing_backend_is_honest(self):
        self.runner.available.discard("wpctl")
        res = self.run_text("тише")
        self.assertFalse(res.ok)
        self.assertIn("wpctl", res.text)

    def test_mute_brightness_radios(self):
        self.assertTrue(self.run_text("выключи звук").ok and self.runner.muted)
        res = self.run_text("яркость 75")
        self.assertTrue(res.ok)
        self.assertEqual(self.runner.brightness, 18000)
        off = self.run_text("выключи wi-fi")
        self.assertTrue(off.ok and not self.runner.wifi)
        self.assertEqual(off.undo[0].kind, "wifi")
        self.assertTrue(self.run_text("выключи вайфай").ok)  # already off: still honest
        self.assertIn("уже", self.run_text("выключи вайфай").text)
        self.assertTrue(self.run_text("bluetooth on", "en").ok and self.runner.bt)

    def test_theme_via_sos(self):
        res = self.run_text("светлая тема")
        self.assertTrue(res.ok and res.verified)
        self.assertEqual(self.runner.theme, "paper")
        self.assertIn(["sos", "theme", "apply", "paper"], self.runner.calls)

    def test_timer_lock_screenshot(self):
        res = self.run_text("напомни через 10 минут выключить чайник")
        self.assertTrue(res.ok and res.verified)
        self.assertTrue(self.runner.timers)
        self.assertIn("10 минут", res.text)
        systemd_run = next(c for c in self.runner.calls if c[0] == "systemd-run")
        self.assertIn("--on-active=600s", systemd_run)
        self.assertIn("выключить чайник", systemd_run)
        self.assertTrue(self.run_text("заблокируй экран").verified)
        shot = self.run_text("скриншот")
        self.assertTrue(shot.ok)
        self.assertTrue(shot.data["path"].endswith(".png"))

    def test_gpu_from_sos_status(self):
        res = self.run_text("какая у меня видеокарта")
        self.assertIn("RTX 4090", res.text)
        self.assertIn("11,2 из 24 ГБ", res.text)

    def test_open_app_verifies_process(self):
        res = self.run_text("открой firefox")
        self.assertTrue(res.ok)
        self.assertTrue(res.verified)
        self.assertIn("Запустил Firefox", res.text)

    def test_info_intents(self):
        self.assertIn("свободно", self.run_text("сколько места на диске").text)
        self.assertIn("192.168.1.23", self.run_text("мой ip").text)
        self.assertIn("Без модели", self.run_text("что ты умеешь").text)

    def test_persona_styling_never_touches_errors(self):
        self.runner.available.discard("wpctl")
        self.runner.available.discard("pactl")
        res = self.run_text("громче", persona="dispatcher")
        self.assertFalse(res.text.startswith("✓"))
        self.runner.available.add("wpctl")
        self.assertTrue(self.run_text("громче", persona="dispatcher").text.startswith("✓"))


if __name__ == "__main__":
    unittest.main()
