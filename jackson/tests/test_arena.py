# SPDX-License-Identifier: Apache-2.0
"""«Арена»: three roles answer on their own, then the host sums up (jackson/arena.py)."""

import asyncio
import json
import unittest

from jackson import arena
from jackson.engine import Session
from tests.fakes import FakeOpenAI, asked, make_app, rmtree, short_tmpdir
from tests.test_engine import kinds, run_turn

ROLE_REPLIES = [{"text": "Да, переходить стоит: всё нужное есть."},
                {"text": "Это неверно для игр с античитом: часть не запустится."},
                {"text": "Не знаю, какие у тебя игры; проверь их на protondb."}]
VERDICT = {"text": "**Итог**: переходи, но сначала проверь свои игры."}


def system_of(body):
    for m in body.get("messages") or []:
        if m.get("role") == "system":
            return m.get("content") or ""
    return body.get("system") or ""


def user_of(body):
    return [m for m in body.get("messages") or [] if m.get("role") == "user"]


class ParseTest(unittest.TestCase):
    def test_triggers(self):
        self.assertEqual(arena.parse("арена: стоит ли переходить с Windows?"), "стоит ли переходить с Windows?")
        self.assertEqual(arena.parse("Арена, стоит ли?"), "стоит ли?")
        self.assertEqual(arena.parse("консилиум — купить RTX 5070 или подождать?"),
                         "купить RTX 5070 или подождать?")
        self.assertEqual(arena.parse("council: is Rust worth it for me?"), "is Rust worth it for me?")
        self.assertEqual(arena.parse("  ARENA - multi\nline"), "multi\nline")

    def test_ordinary_questions_stay_ordinary(self):
        for text in ("Арена в Таллине на сколько мест?", "аренда: сколько стоит квартира?", "арена:", "арена: ок",
                     "консилиумы врачей полезны?", "что такое арена"):
            with self.subTest(text=text):
                self.assertIsNone(arena.parse(text))


class ArenaTurnTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.srv = FakeOpenAI(ROLE_REPLIES + [VERDICT]).start()
        self.app = make_app(self.root, f"http://127.0.0.1:{self.srv.port}/v1")

    def tearDown(self):
        self.srv.close()
        rmtree(self.root)

    def test_three_roles_then_the_verdict(self):
        session = Session("test", "ru")
        events = asyncio.run(run_turn(self.app, "арена: стоит ли мне перейти с Windows на СОС?", session=session))
        self.assertEqual(kinds(events)[0], "route")
        self.assertEqual(kinds(events)[-1], "done")
        said = "".join(e["text"] for e in events if e["type"] == "token")
        # the debate, in order, then the host's verdict
        order = [said.index(x) for x in ("**Сторонник**", "переходить стоит", "**Критик**", "Это неверно",
                                         "**Проверяющий**", "protondb", "---", "**Итог**")]
        self.assertEqual(order, sorted(order))
        reqs = self.srv.requests
        self.assertEqual(len(reqs), 4)
        for i, role in enumerate(arena.ROLES):
            body = reqs[i]
            self.assertIn(role.prompt["ru"], system_of(body))
            self.assertIn("Инструментов у тебя нет", system_of(body))
            self.assertFalse(body.get("tools"))                         # a council thinks, it does not act
            users = user_of(body)
            self.assertEqual(len(users), 1)                             # no history, no other answers
            self.assertEqual(asked(users[0]["content"]), "стоит ли мне перейти с Windows на СОС?")
            self.assertEqual(body.get("max_tokens"), arena.ROLE_TOKENS)
        chair = reqs[3]
        self.assertIn("ведущий «Арены»", system_of(chair))
        self.assertIn("кентафурик", system_of(chair))                   # Jackson's own manner
        text = user_of(chair)[0]["content"]
        for reply in ROLE_REPLIES:
            self.assertIn(reply["text"], text)
        self.assertNotIn("Ответ прозвучит вслух", system_of(chair))
        done = next(e for e in events if e["type"] == "done")
        self.assertFalse(done["leftMachine"])
        self.assertEqual(done["usage"]["inTokens"], 400)                # four requests, 100 each
        # one turn in the history: the question and everything that was said
        self.assertEqual(len(session.history), 1)
        user, answer = session.history[0]
        self.assertTrue(asked(user["content"]).startswith("арена:"))
        self.assertIn("**Критик**", answer["content"])
        self.assertIn("**Итог**", answer["content"])
        # and a line in the hash-chained audit log (which model, local or not, how many roles)
        lines = [json.loads(x) for x in self.app.paths.audit_file.read_text(encoding="utf-8").splitlines()]
        entry = next(x for x in lines if x.get("kind") == "arena" or x.get("type") == "arena" or "arena" in x.values())
        self.assertTrue(entry.get("local"))
        self.assertEqual(entry.get("roles"), 3)

    def test_spoken_question_hears_only_the_verdict(self):
        events = asyncio.run(run_turn(self.app, "Арена, стоит ли мне перейти?", context={"voice": True}))
        said = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertEqual(said, VERDICT["text"])
        self.assertIn("Ответ прозвучит вслух", system_of(self.srv.requests[3]))
        self.assertEqual(len(self.srv.requests), 4)

    def test_english(self):
        events = asyncio.run(run_turn(self.app, "council: should I switch to SOS?", session=Session("test", "en")))
        said = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertIn("**Advocate**", said)
        self.assertIn("**Checker**", said)
        self.assertIn("host of the SOS \"Arena\"", system_of(self.srv.requests[3]))

    def test_ordinary_question_is_one_request(self):
        asyncio.run(run_turn(self.app, "Арена в Таллине на сколько мест?"))
        self.assertEqual(len(self.srv.requests), 1)
        self.assertNotIn("Арены", system_of(self.srv.requests[0]))


if __name__ == "__main__":
    unittest.main()
