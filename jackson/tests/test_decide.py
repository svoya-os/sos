# SPDX-License-Identifier: Apache-2.0
"""Local decisions (jackson/decide.py) and the fast path's use of them."""

import asyncio
import unittest

from jackson import decide, fastpath
from tests.fakes import FakeOpenAI, make_app, rmtree, short_tmpdir
from tests.test_engine import kinds, run_turn


def reply(**probs):
    return {"choices": [{"logprobs": {"content": [{"token": "x", "logprob": 0.0, "top_logprobs": [
        {"token": t, "logprob": __import__("math").log(p)} for t, p in probs.items()]}]}}]}


class LetterProbabilitiesTest(unittest.TestCase):
    def test_letters_spaces_and_dots_add_up(self):
        probs = decide.letter_probabilities(reply(**{"B": 0.5, " b": 0.2, "B.": 0.1, "A": 0.2}), 3)
        self.assertEqual([round(p, 3) for p in probs], [0.2, 0.8, 0.0])

    def test_unusable_replies_are_none(self):
        self.assertIsNone(decide.letter_probabilities({"choices": [{"message": {"content": "A"}}]}, 2))
        self.assertIsNone(decide.letter_probabilities(reply(**{"<think>": 0.95, "A": 0.05}), 2))
        self.assertIsNone(decide.letter_probabilities(reply(**{"D": 0.9, "A": 0.1}), 2))   # D is not an option

    def test_messages(self):
        msgs = decide.build_messages("потише бы", ["громче", "тише"])
        self.assertTrue(msgs[1]["content"].startswith("Options:\nA. громче\nB. тише\n"))   # cached prefix
        self.assertIn("Request: потише бы", msgs[1]["content"])


class FastDecisionTest(unittest.TestCase):
    def test_candidates(self):
        self.assertEqual(fastpath.decision_candidate("Слушай, сделай-ка потише, соседи жалуются"),
                         "слушай сделай-ка потише соседи жалуются")
        self.assertIsNone(fastpath.decision_candidate("напиши письмо начальнику про отпуск"))   # no hint
        self.assertIsNone(fastpath.decision_candidate("звук " * 13))                            # too long
        self.assertIsNone(fastpath.decision_candidate("почему не работает вай-фай?"))           # a question…
        self.assertIsNotNone(fastpath.decision_candidate("сколько там заряда?"))               # …unless read-only
        # «погромче» and «посветлее» said in passing (tests/decide-eval found them missing)
        self.assertIsNotNone(fastpath.decision_candidate("слушай, сделай-ка погромче, ничего не слышно"))
        self.assertIsNotNone(fastpath.decision_candidate("можно экран посветлее"))
        self.assertIsNotNone(fastpath.decision_candidate("звук тихий, прибавь"))
        self.assertEqual(len(fastpath.decision_options("ru")), len(fastpath.DECIDABLE) + 1)

    def test_thresholds_and_questions(self):
        idx = {name: i for i, (name, _, _) in enumerate(fastpath.DECIDABLE)}
        m = fastpath.decided_match(idx["volume_down"], 0.95, "сделай-ка потише")
        self.assertEqual((m.name, m.args), ("volume_down", {}))
        self.assertIsNone(fastpath.decided_match(idx["volume_down"], 0.85, "сделай-ка потише"))  # changes: 0.9
        self.assertEqual(fastpath.decided_match(idx["battery"], 0.85, "сколько там заряда").name, "battery")
        # a question never switches anything off
        self.assertIsNone(fastpath.decided_match(idx["wifi_off"], 0.99, "почему не работает вай фай"))
        self.assertIsNone(fastpath.decided_match(len(fastpath.DECIDABLE), 0.99, "как дела"))     # «none»

    def test_a_request_that_wants_more_than_the_intent_goes_to_the_model(self):
        idx = {name: i for i, (name, _, _) in enumerate(fastpath.DECIDABLE)}

        def picked(name, text):
            m = fastpath.decided_match(idx[name], 0.99, fastpath.normalize(text))
            return m.name if m else None
        for name, text in [("screenshot", "сделай скрин и отправь Маше"), ("screenshot", "сними экран на видео"),
                           ("screenshot", "screenshot this and send it to Bob"),
                           ("battery", "где купить батарею подешевле"), ("battery", "how much does a new battery cost"),
                           ("time", "сколько времени уйдёт на обновление"), ("time", "how long does the update take"),
                           ("lock", "заблокируй этот сайт"), ("lock", "lock the app"),
                           ("wifi_on", "раздай вайфай на телефон"), ("wifi_on", "share my wifi password")]:
            with self.subTest(text=text):
                self.assertIsNone(picked(name, text))
        # the plain commands still run
        for name, text in [("screenshot", "сделай скрин"), ("screenshot", "take a screenshot"),
                           ("battery", "проверь заряд батареи"), ("battery", "оцени заряд"), ("time", "который час"),
                           ("time", "what time is it"), ("lock", "заблокируй экран"), ("wifi_on", "включи вайфай")]:
            with self.subTest(text=text):
                self.assertEqual(picked(name, text), name)


class EngineDecisionTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            s.close()
        rmtree(self.root)

    def app(self, decide_fn, extra=None, script=None):
        srv = FakeOpenAI(script or [{"text": "Обычный ответ модели."}], decide=decide_fn).start()
        self.servers.append(srv)
        return make_app(self.root, f"http://127.0.0.1:{srv.port}/v1", extra), srv

    def letter_of(self, name):
        return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[[n for n, _, _ in fastpath.DECIDABLE].index(name)]

    def test_a_command_the_patterns_missed(self):
        app, srv = self.app(lambda body: {self.letter_of("volume_down"): 0.96, "A": 0.04})
        events = asyncio.run(run_turn(app, "слушай, сделай-ка потише, соседи жалуются"))
        self.assertEqual(kinds(events), ["route", "tool", "tool", "token", "done"])
        route = events[0] if events[0]["type"] == "route" else next(e for e in events if e["type"] == "route")
        self.assertIn("96%", route["reason"])
        tool = [e for e in events if e["type"] == "tool"][0]
        self.assertEqual(tool["name"], "fast.volume_down")
        decision_req = srv.requests[0]
        self.assertEqual((decision_req["max_tokens"], decision_req["logprobs"]), (1, True))
        self.assertEqual(decision_req["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(len(srv.requests), 1)                           # no model turn after it
        audit = (app.paths.data_dir / "audit.jsonl").read_text(encoding="utf-8")
        self.assertIn('"fastpath.decide"', audit)

    def test_unsure_goes_to_the_model(self):
        app, srv = self.app(lambda body: {self.letter_of("volume_down"): 0.6, "A": 0.4})
        events = asyncio.run(run_turn(app, "слушай, сделай-ка потише, соседи жалуются"))
        self.assertIn("Обычный ответ модели.", "".join(e.get("text", "") for e in events if e["type"] == "token"))
        self.assertEqual(len(srv.requests), 2)                           # the decision, then the model turn

    def test_switched_off(self):
        app, srv = self.app(lambda body: {"A": 1.0}, extra={"fastpath": {"decide": False}})
        asyncio.run(run_turn(app, "слушай, сделай-ка потише, соседи жалуются"))
        self.assertFalse(any(r.get("logprobs") for r in srv.requests))


if __name__ == "__main__":
    unittest.main()
