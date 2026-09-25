# SPDX-License-Identifier: Apache-2.0
"""Avatar & name (avatar.json), accent, look commands, the AI switch (DESIGN §10–§13, WORKFLOWS §2/§3/§8)."""

import asyncio
import json
import os
import stat
import subprocess
import sys
import time
import unittest
from pathlib import Path

from jackson import avatar as av
from jackson import fastpath
from jackson.client import connect
from jackson.daemon import JacksonService
from jackson.engine import Session
from jackson.fastpath import FastCtx, match
from jackson.osctl import OsControl
from jackson.paths import Paths
from jackson.persona import system_prompt
from jackson.svoya import SvoyaCli
from tests.fakes import FakeOpenAI, FakeRunner, env_for, make_app, rmtree, short_tmpdir
from tests.test_daemon import until
from tests.test_engine import run_turn

BIN = Path(__file__).resolve().parents[1] / "bin"


class AvatarModuleTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.path = Paths.for_root(self.root).avatar_file

    def tearDown(self):
        rmtree(self.root)

    def test_defaults_when_missing_and_per_character(self):
        look = av.load(self.path)
        self.assertEqual(look.to_event(), {"character": "imp", "skin": "ember", "outfit": "accent", "style": "hoodie",
                                           "headphones": True, "glasses": "none", "hood": True, "name": "Джексон"})
        self.assertEqual(look.display_name("en"), "Jackson")
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"character": "cat"}')
        cat = av.load(self.path).to_event()
        self.assertEqual((cat["skin"], cat["style"], cat["glasses"]), ("blue", "jacket", "shades"))

    def test_invalid_values_fall_back(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"character": "dragon", "skin": "ginger", "glasses": "vr", "name": "x\\ny", "hood": 1}')
        look = av.load(self.path).to_event()
        self.assertEqual((look["character"], look["skin"], look["glasses"], look["name"], look["hood"]),
                         ("imp", "ember", "none", "Джексон", True))
        self.path.write_text("not json")
        self.assertEqual(av.load(self.path).data["character"], "imp")

    def test_russian_aliases_and_validation(self):
        s = av.apply_change({}, av.parse_key("персонаж"), "Кот")
        s = av.apply_change(s, av.parse_key("окрас"), "рыжий")
        s = av.apply_change(s, av.parse_key("очки"), "круглые")
        s = av.apply_change(s, av.parse_key("наушники"), "нет")
        s = av.apply_change(s, av.parse_key("стиль"), "футболка")
        s = av.apply_change(s, av.parse_key("одежда"), "сирень")
        s = av.apply_change(s, av.parse_key("имя"), "Макс")
        self.assertEqual(s, {"character": "cat", "skin": "ginger", "glasses": "round", "headphones": False,
                             "style": "tee", "outfit": "lilac", "name": "Макс"})
        with self.assertRaises(av.AvatarError) as ctx:
            av.apply_change(s, "hood", "да")
        self.assertIn("капюшона", ctx.exception.text("ru"))
        with self.assertRaises(av.AvatarError):
            av.apply_change(s, "skin", "ember")            # an imp skin on a cat
        with self.assertRaises(av.AvatarError):
            av.apply_change(s, "name", "x" * 40)
        imp = av.apply_change(s, "character", "черт")    # switching drops the cat-only skin
        self.assertNotIn("skin", imp)
        self.assertEqual(av.resolve(imp)["skin"], "ember")

    def test_write_is_atomic_and_keeps_unknown_keys(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"character": "imp", "shellOnly": {"blink": 3}}')
        stored = av.apply_change(av.read_stored(self.path), "glasses", "shades")
        av.write(self.path, stored)
        data = json.loads(self.path.read_text())
        self.assertEqual(data["shellOnly"], {"blink": 3})
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o644)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), ["avatar.json"])


class LookFastPathTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        self.runner = FakeRunner(self.paths)
        self.osc = OsControl(self.runner, self.paths, SvoyaCli(self.runner, self.paths), sleep=lambda s: None)
        self.changes = 0

    def tearDown(self):
        rmtree(self.root)

    def ctx(self, lang="ru"):
        def bump():
            self.changes += 1
        return FastCtx(self.osc, lang, "sysop", avatar_path=self.paths.avatar_file, on_avatar_change=bump,
                       ai_off_reason=lambda: "user" if self.paths.ai_off_markers[1].exists() else None)

    def run_text(self, text, lang="ru", names=()):
        m = match(text, self.osc, names)
        self.assertIsNotNone(m, text)
        return m, fastpath.run(m, self.ctx(lang))

    def test_parsing(self):
        cases = {"сделай акцент фиолетовым": ("accent", "фиолетовым"), "акцент сирень": ("accent", "сирень"),
                 "поменяй акцент на зелёный": ("accent", "зеленый"), "фиолетовый акцент": ("accent", "фиолетовый"),
                 "верни оранжевый": ("accent", "оранжевый"), "make the accent green": ("accent", "green"),
                 "lilac accent": ("accent", "lilac")}
        for text, (intent, color) in cases.items():
            m = match(text, self.osc)
            self.assertEqual((m.name, m.args.get("color")), (intent, color), text)
        for text in ("без цвета", "убери цвет", "no color"):
            self.assertEqual(match(text, self.osc).name, "accent")
            self.assertTrue(match(text, self.osc).args.get("mono"))
        for text, intent in {"включи бумагу": "theme", "включи графит": "theme", "включи фосфор": "theme",
                             "switch to paper": "theme", "стань котом": "character", "стань рыжим котом": "character",
                             "стань чёртом": "character", "become a cat": "character", "надень очки": "glasses",
                             "надень тёмные очки": "glasses", "сними очки": "glasses", "сними наушники": "headphones",
                             "надень наушники": "headphones", "капюшон долой": "hood", "надень капюшон": "hood",
                             "надень худи": "style", "переоденься в куртку": "style",
                             "тебя теперь зовут Макс": "rename", "your name is Max": "rename",
                             "выключи ИИ": "ai_off", "turn AI off": "ai_off", "выключись": "ai_off",
                             "включи ИИ": "ai_on"}.items():
            m = match(text, self.osc)
            self.assertIsNotNone(m, text)
            self.assertEqual(m.name, intent, text)
        for text in ("как поменять акцент в vs code?", "что значит акцент в дизайне и зачем он нужен", "как тебя зовут"):
            m = match(text, self.osc)
            self.assertTrue(m is None or m.name != "accent" and m.name != "rename", text)

    def test_accent_verified_and_undoable(self):
        _, res = self.run_text("сделай акцент фиолетовым")
        self.assertTrue(res.ok and res.verified)
        self.assertEqual(res.text, "Акцент: Сирень.")
        self.assertIn(["sos", "theme", "accent", "фиолетовым", "--json"], self.runner.calls)
        self.assertEqual(res.undo[0].kind, "accent")
        self.assertEqual(res.undo[0].data["prev"], "default")
        _, again = self.run_text("акцент сирень")
        self.assertIn("уже", again.text)
        _, mono = self.run_text("без цвета")
        self.assertEqual(self.runner.accent, "mono")
        self.assertEqual(mono.undo[0].data["prev"], "lilac")
        _, en = self.run_text("make the accent green", "en")
        self.assertEqual(en.text, "Accent: Phosphor.")

    def test_accent_honest_failures(self):
        _, red = self.run_text("сделай акцент красным")
        self.assertFalse(red.ok)
        self.assertIn("Роза", red.text)
        _, unknown = self.run_text("акцент шотландка")
        self.assertFalse(unknown.ok)
        self.runner.broken.add("accent")   # sos says ok, but theme.json does not follow
        _, lie = self.run_text("акцент сирень")
        self.assertFalse(lie.ok)
        self.assertFalse(lie.verified)
        self.runner.available.discard("sos")
        _, missing = self.run_text("акцент сирень")
        self.assertIn("sos", missing.text)

    def test_theme_words(self):
        _, res = self.run_text("включи бумагу")
        self.assertTrue(res.ok)
        self.assertEqual(self.runner.theme, "paper")
        self.run_text("включи фосфор")
        self.assertEqual(self.runner.theme, "phosphor")

    def test_avatar_changes_verified_and_undoable(self):
        _, res = self.run_text("стань рыжим котом")
        self.assertTrue(res.ok and res.verified)
        self.assertEqual(res.text, "Готово — теперь я кот.")
        self.assertEqual(json.loads(self.paths.avatar_file.read_text()), {"character": "cat", "skin": "ginger"})
        self.assertIsNone(res.undo[0].data["prev"])
        self.assertEqual(self.changes, 1)
        _, glasses = self.run_text("надень очки")
        self.assertEqual(av.load(self.paths.avatar_file).data["glasses"], "round")
        self.assertEqual(glasses.undo[0].data["prev"], {"character": "cat", "skin": "ginger"})
        self.run_text("сними наушники")
        self.assertFalse(av.load(self.paths.avatar_file).data["headphones"])
        _, hood = self.run_text("капюшон долой")
        self.assertFalse(hood.ok)                  # a cat has no hood — said honestly
        self.assertIn("капюшона", hood.text)
        self.run_text("стань чёртом")
        _, hood = self.run_text("капюшон долой")
        self.assertTrue(hood.ok)
        self.assertFalse(av.load(self.paths.avatar_file).data["hood"])
        _, same = self.run_text("капюшон долой")
        self.assertIn("и так", same.text)

    def test_rename_confirms_with_the_new_name_and_answers_to_it(self):
        _, res = self.run_text("Джексон, тебя теперь зовут Макс")
        self.assertTrue(res.ok)
        self.assertEqual(res.text, "Окей, теперь я Макс.")
        self.assertEqual(av.load(self.paths.avatar_file).name, "Макс")
        _, en = self.run_text("your name is Alёna", "en")
        self.assertEqual(en.text, "Okay, I'm Alёna now.")
        m = match("Макс, громче", self.osc, ("Макс",))
        self.assertEqual(m.name, "volume_up")
        self.assertIn("Ты — Макс", system_prompt(lang="ru", persona="kent", name="Макс"))
        self.assertIn("You are Max", system_prompt(lang="en", persona="kent", name="Max"))

    def test_ai_off_answers_first_and_is_undoable(self):
        _, res = self.run_text("выключи ИИ")
        self.assertTrue(res.ok)
        self.assertIn("sos ai on", res.text)
        self.assertIsNotNone(res.after)
        self.assertFalse(self.paths.ai_off_markers[1].exists())   # nothing happened yet: answer first
        res.after()
        self.assertTrue(self.paths.ai_off_markers[1].exists())
        self.assertEqual(self.runner.spawned[-1][1], ["sos", "ai", "off"])
        _, again = self.run_text("выключи ИИ")
        self.assertIn("уже выключен", again.text)
        _, on = self.run_text("включи ИИ")
        self.assertTrue(on.ok and on.verified)
        self.assertFalse(self.paths.ai_off_markers[1].exists())


class AiSwitchEngineTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.srv = FakeOpenAI([{"text": "Ответ модели."}]).start()
        self.app = make_app(self.root, f"http://127.0.0.1:{self.srv.port}/v1")

    def tearDown(self):
        self.srv.close()
        rmtree(self.root)

    def test_ai_off_refuses_model_turns_but_keeps_quick_commands(self):
        marker = self.app.paths.ai_off_markers[1]
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("off")
        events = asyncio.run(run_turn(self.app, "расскажи про квантовые компьютеры"))
        err = next(e for e in events if e["type"] == "error")
        self.assertTrue(err["aiOff"])
        self.assertEqual(err["off"], "user")
        self.assertIn("sos ai on", err["message"])
        self.assertEqual(self.srv.requests, [])            # no model was called at all
        quick = asyncio.run(run_turn(self.app, "громче", turn_id="t-2"))
        self.assertEqual(next(e for e in quick if e["type"] == "done")["model"], "fastpath")

    def test_system_wide_switch_and_config_switch(self):
        sysm = self.app.paths.ai_off_markers[0]
        sysm.parent.mkdir(parents=True, exist_ok=True)
        sysm.write_text("off")
        err = next(e for e in asyncio.run(run_turn(self.app, "привет")) if e["type"] == "error")
        self.assertIn("--system", err["message"])
        sysm.unlink()
        self.app.paths.svoya_toml.parent.mkdir(parents=True, exist_ok=True)
        self.app.paths.svoya_toml.write_text("[ai]\nenabled = false\n")
        self.assertEqual(self.app.ai_state(), {"enabled": False, "off": "config"})

    def test_turning_ai_off_happens_after_the_answer(self):
        events = []
        stamps = {}

        async def main():
            async def emit(ev):
                events.append(ev)
                if ev["type"] == "done":
                    stamps["done"] = time.monotonic()
            from jackson.engine import Turn
            turn = Turn(id="t-off", session=Session("c", "ru"), text="выключи ИИ", emit=emit)
            await self.app.engine.run_turn(turn)
            await asyncio.sleep(0.6)
        asyncio.run(main())
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(len(done["actions"]), 1)
        spawned = [(t_, argv) for t_, argv in self.app.runner.spawned if argv[:3] == ["sos", "ai", "off"]]
        self.assertEqual(len(spawned), 1)
        self.assertGreater(spawned[0][0], stamps["done"])
        self.assertTrue(self.app.paths.ai_off_markers[1].exists())
        out = self.app.undo.undo(done["actions"][0], "ru")   # `jackson undo` works while AI is off
        self.assertTrue(out.ok, out.message)
        self.assertFalse(self.app.paths.ai_off_markers[1].exists())

    def test_model_prompt_uses_the_custom_name(self):
        self.app.paths.avatar_file.parent.mkdir(parents=True, exist_ok=True)
        self.app.paths.avatar_file.write_text('{"name": "Макс"}')
        self.app.reload_avatar()
        asyncio.run(run_turn(self.app, "кто ты такой вообще?"))
        self.assertIn("Ты — Макс", self.srv.requests[0]["messages"][0]["content"])


class LookServiceTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.srv = FakeOpenAI([{"text": "ok"}]).start()
        self.app = make_app(self.root, f"http://127.0.0.1:{self.srv.port}/v1")

    def tearDown(self):
        self.srv.close()
        rmtree(self.root)

    def test_welcome_state_and_live_avatar_updates(self):
        async def main():
            svc = JacksonService(self.app, health_interval=60, look_interval=0.05)
            await svc.start()
            task = asyncio.get_running_loop().create_task(svc.serve_forever(handle_signals=False))
            try:
                a = await connect(self.app.paths.socket)
                welcome = await a.hello("shell", "ru")
                self.assertEqual(welcome["avatar"]["character"], "imp")
                self.assertEqual(welcome["name"], "Джексон")
                self.assertEqual(welcome["ai"], {"enabled": True, "off": None})
                await a.send({"type": "ask", "id": "t1", "text": "стань котом"})
                events = await until(a, ("done",), "t1")
                states = [e for e in events if e["type"] == "state"]
                self.assertEqual(states[-1]["avatar"]["character"], "cat")   # the look changed mid-turn
                await until(a, ("state",), "t1")                              # idle
                # the shell's customizer edits the file → every client gets a fresh state
                self.app.paths.avatar_file.write_text('{"character": "cat", "glasses": "round", "name": "Барсик"}')
                ev = (await until(a, ("state",), timeout=5))[-1]
                self.assertEqual(ev["detail"], "avatar")
                self.assertEqual((ev["avatar"]["glasses"], ev["avatar"]["name"]), ("round", "Барсик"))
                await a.send({"type": "status"})
                st = (await until(a, ("status",)))[-1]
                self.assertEqual((st["name"], st["avatar"]["name"]), ("Барсик", "Барсик"))
                await a.close()
            finally:
                svc.request_stop()
                await asyncio.wait_for(task, 10)
        asyncio.run(main())


class LookCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = FakeOpenAI(lambda body: {"text": "ok"}).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def setUp(self):
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        self.paths.config_dir.mkdir(parents=True)
        self.paths.runtime_base.mkdir(parents=True)
        os.chmod(self.paths.runtime_base, 0o700)
        self.paths.config_file.write_text(f'[providers.local]\nbase_url = "http://127.0.0.1:{self.srv.port}/v1"\n'
                                          '[providers.ollama]\nenabled = false\n[memory]\ngit = false\n')
        self.env = env_for(self.paths)
        self.env["NO_COLOR"] = "1"

    def tearDown(self):
        rmtree(self.root)

    def j(self, *args):
        return subprocess.run([sys.executable, str(BIN / "j"), *args], capture_output=True, text=True, env=self.env,
                              timeout=60, stdin=subprocess.DEVNULL)

    def test_avatar_set_show_reset_undo(self):
        self.assertIn("Чёрт", self.j("avatar").stdout)
        res = self.j("avatar", "set", "персонаж", "кот")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(self.paths.avatar_file.read_text()), {"character": "cat"})
        self.assertEqual(self.j("avatar", "set", "очки", "круглые").returncode, 0)
        self.assertEqual(self.j("avatar", "set", "окрас", "рыжий").returncode, 0)
        name = self.j("avatar", "set", "имя", "Макс")
        action = name.stdout.split("jackson undo ")[1].split(")")[0]
        shown = self.j("avatar")
        self.assertIn("Рыжий", shown.stdout)
        self.assertIn("круглые очки", shown.stdout)
        self.assertIn("Макс", shown.stdout)
        bad = self.j("avatar", "set", "капюшон", "да")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("капюшона", bad.stderr)
        self.assertEqual(self.j("avatar", "set", "очки", "vr").returncode, 2)
        undo = subprocess.run([sys.executable, str(BIN / "jackson"), "undo", action], capture_output=True,
                              text=True, env=self.env, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(undo.returncode, 0, undo.stdout + undo.stderr)
        self.assertNotIn("name", json.loads(self.paths.avatar_file.read_text()))
        self.assertEqual(self.j("avatar", "reset").returncode, 0)
        self.assertEqual(json.loads(self.paths.avatar_file.read_text()), {})
        data = json.loads(self.j("avatar", "show", "--json").stdout)
        self.assertEqual(data["character"], "imp")

    def test_status_uses_the_name_and_shows_the_ai_switch(self):
        self.j("avatar", "set", "name", "Max")
        marker = self.paths.ai_off_markers[1]
        marker.write_text("off")
        st = self.j("status")
        self.assertIn("Max", st.stdout)
        self.assertIn("sos ai on", st.stdout)
        res = self.j("что", "такое", "SOS?")
        self.assertEqual(res.returncode, 1)
        self.assertIn("ИИ сейчас выключен", res.stderr)
        self.assertIn("sos ai on", res.stderr)
        self.assertNotIn("✗", res.stderr)             # a calm switch state, not an error
        quick = self.j("который", "час")
        self.assertEqual(quick.returncode, 0)


if __name__ == "__main__":
    unittest.main()
