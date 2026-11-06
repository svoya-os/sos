# SPDX-License-Identifier: Apache-2.0
"""«Кто сделал, тот не проверяет»: a second look at a turn that changed things (jackson/check.py)."""

import asyncio
import unittest

from jackson import check
from jackson.engine import Session
from tests.fakes import FakeOpenAI, make_app, rmtree, short_tmpdir
from tests.test_engine import run_turn

TWO_WRITES = {"tool_calls": [{"name": "fs__write", "args": {"path": "~/a.txt", "content": "a\n"}},
                             {"name": "fs__write", "args": {"path": "~/b.txt", "content": "b\n"}}]}
ANSWER = {"text": "Записал оба файла."}


def step(name="fs.write", tier=1, ok=True, verified=True, changed=True):
    return check.Step(name, tier, {"path": "~/a.txt"}, ok, verified, "записан", changed)


class RulesTest(unittest.TestCase):
    def test_when_to_check(self):
        self.assertFalse(check.needed([], "auto"))
        self.assertFalse(check.needed([step(changed=False), step(changed=False)], "auto"))   # only looked
        self.assertFalse(check.needed([step()], "auto"))                  # one verified change in your files
        self.assertTrue(check.needed([step(), step()], "auto"))           # two changes
        self.assertTrue(check.needed([step(tier=2)], "auto"))             # the system, or outside the machine
        self.assertTrue(check.needed([step(verified=False)], "auto"))     # a change the tool could not verify
        self.assertTrue(check.needed([step()], "always"))
        self.assertFalse(check.needed([step(), step(), step(tier=3)], "off"))
        self.assertFalse(check.needed([step(ok=False), step(ok=False)], "auto"))   # nothing changed

    def test_reading_the_checker(self):
        self.assertEqual(check.parse('{"ok": true}').ok, True)
        v = check.parse('Вот:\n```json\n{"ok": false, "problems": ["b.txt пустой"]}\n```')
        self.assertEqual((v.ok, v.problems), (False, ["b.txt пустой"]))
        self.assertIsNone(check.parse("всё хорошо"))
        self.assertIsNone(check.parse('{"ok": "yes"}'))
        self.assertIsNone(check.parse('{"ok": false}'))                    # «not ok» with nothing to say
        self.assertEqual(check.parse('{"ok": true, "problems": ["x"]}').ok, False)   # a problem is a problem

    def test_what_the_checker_reads(self):
        text = check.message("запиши a и b", [step(), step(verified=False)], "Записал.", "ru")
        self.assertIn("## Просьба\nзапиши a и b", text)
        self.assertIn('1. fs.write {"path": "~/a.txt"} → ok, проверено: записан', text)
        self.assertIn("НЕ проверено", text)
        self.assertTrue(text.endswith("## Ответ пользователю\nЗаписал."))
        self.assertIn("Эту работу делал не ты", check.system("ru"))
        self.assertIn("You did not do this work", check.system("en"))


class CheckTurnTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            s.close()
        rmtree(self.root)

    def app(self, script, extra=None):
        srv = FakeOpenAI(script).start()
        self.servers.append(srv)
        return make_app(self.root, f"http://127.0.0.1:{srv.port}/v1", extra), srv

    def test_a_problem_is_said_after_the_answer(self):
        app, srv = self.app([TWO_WRITES, ANSWER, {"text": '{"ok": false, "problems": ["b.txt не тот"]}'}])
        session = Session("test", "ru")
        events = asyncio.run(run_turn(app, "запиши a в a.txt и b в b.txt", session=session))
        said = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertEqual(said, "Записал оба файла.\n\n**Проверка:** b.txt не тот")
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(done["check"], {"ok": False, "problems": ["b.txt не тот"]})
        self.assertEqual(len(srv.requests), 3)
        checker = srv.requests[2]
        self.assertFalse(checker.get("tools"))
        system = next(m["content"] for m in checker["messages"] if m["role"] == "system")
        self.assertIn("Эту работу делал не ты", system)
        asked = [m for m in checker["messages"] if m["role"] == "user"]
        self.assertEqual(len(asked), 1)                           # the request, the steps, the answer; no chat
        self.assertIn("fs.write", asked[0]["content"])
        self.assertIn("Записал оба файла.", asked[0]["content"])
        self.assertIn("**Проверка:**", session.history[-1][-1]["content"])   # the next question can refer to it
        self.assertEqual(done["usage"]["inTokens"], 300)          # the check is counted like any request

    def test_a_good_turn_says_nothing_more(self):
        app, srv = self.app([TWO_WRITES, ANSWER, {"text": '{"ok": true}'}])
        events = asyncio.run(run_turn(app, "запиши a и b"))
        said = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertEqual(said, "Записал оба файла.")
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(done["check"], {"ok": True, "problems": []})

    def test_off_and_reading_turns_are_not_checked(self):
        app, srv = self.app([TWO_WRITES, ANSWER], extra={"checks": {"after_actions": "off"}})
        events = asyncio.run(run_turn(app, "запиши a и b"))
        self.assertEqual(len(srv.requests), 2)
        self.assertNotIn("check", next(e for e in events if e["type"] == "done"))
        app2, srv2 = self.app([{"tool_calls": [{"name": "fs__list", "args": {"path": "~"}},
                                               {"name": "fs__list", "args": {"path": "~"}}]}, ANSWER])
        asyncio.run(run_turn(app2, "что у меня в папке?"))
        self.assertEqual(len(srv2.requests), 2)

    def test_a_checker_that_does_not_answer_changes_nothing(self):
        app, srv = self.app([TWO_WRITES, ANSWER, {"text": "не понял задачу"}])
        events = asyncio.run(run_turn(app, "запиши a и b"))
        said = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertEqual(said, "Записал оба файла.")
        self.assertNotIn("check", next(e for e in events if e["type"] == "done"))


if __name__ == "__main__":
    unittest.main()
