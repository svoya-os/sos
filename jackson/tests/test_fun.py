# SPDX-License-Identifier: Apache-2.0
"""Games, jokes, memes, greetings and Morse (jackson/fun.py) and their fast-path intents."""

import datetime as dt
import random
import unittest

from jackson import fastpath, fun, variety
from jackson.osctl import OsControl
from jackson.paths import Paths
from tests.fakes import FakeRunner, rmtree, short_tmpdir


class FunTest(unittest.TestCase):
    def test_coin_and_dice(self):
        seen = {fun.coin(random.Random(i), False)[0] for i in range(40)}
        self.assertEqual(seen, {"Орёл.", "Решка."})
        for i in range(60):
            ru, en = fun.dice(random.Random(i), 6, True)
            n = int(ru.split()[1])
            self.assertTrue(1 <= n <= 6, ru)
        crit = next(fun.dice(random.Random(i), 20, True) for i in range(500)
                    if fun.dice(random.Random(i), 20, True)[0].startswith("Выпало 20 "))
        self.assertIn("Критический успех", crit[0])

    def test_rock_paper_scissors_rules(self):
        class Fixed(random.Random):
            def __init__(self, n):
                super().__init__(0)
                self.n = n

            def randrange(self, *a):
                return self.n
        # mine: 0 rock, 1 scissors, 2 paper
        self.assertIn("Ничья", fun.rps(Fixed(0), "камень", False)[0])
        self.assertIn("Ты выиграл", fun.rps(Fixed(1), "камень", False)[0])      # rock beats scissors
        self.assertIn("Я выиграл", fun.rps(Fixed(2), "камень", False)[0])       # paper beats rock
        self.assertIn("Ты выиграл", fun.rps(Fixed(0), "бумагу", False)[0])     # paper beats rock
        self.assertIn("I win", fun.rps(Fixed(0), "scissors", False)[1])        # rock beats scissors
        self.assertIn("камень, ножницы или бумага", fun.rps(Fixed(0), None, True)[0])

    def test_pick_number_joke_memes(self):
        self.assertIn(fun.pick(random.Random(1), " пицца ", "суши", False)[0], ("Выбираю «пицца».", "Выбираю «суши»."))
        for i in range(30):
            n = int(fun.number(random.Random(i), 10, 1)[0].split()[0])       # swapped bounds are fine
            self.assertTrue(1 <= n <= 10)
        self.assertIn(fun.joke(random.Random(3))[0], fun.JOKES_RU)
        self.assertIn("кросавчег", fun.meme("preved", True)[0])
        self.assertNotIn("кросавчег", fun.meme("preved", False)[0])
        self.assertIn("шнейне", fun.pepe(random.Random(2), True)[0])

    def test_morse(self):
        self.assertEqual(fun.morse("SOS"), "··· ——— ···")
        self.assertEqual(fun.morse("сос"), "··· ——— ···")
        self.assertEqual(fun.morse("привет мир"), "·——· ·—· ·· ·—— · — / —— ·· ·—·")
        self.assertEqual(fun.morse("!!!"), "—·—·—— —·—·—— —·—·——")
        self.assertEqual(fun.morse("😀"), "")

    def test_greetings_know_the_time(self):
        def g(*args, kent=True):
            return fun.greeting(dt.datetime(*args), kent)[0]
        night = g(2026, 9, 23, 2, 30)
        self.assertTrue(any(w in night for w in ("Не спится", "полуночник", "Ночной")), night)
        self.assertTrue(g(2026, 9, 21, 8, 0).startswith("Понедельник"))    # a Monday
        self.assertTrue(g(2026, 9, 25, 19, 0).startswith("Пятница"))       # a Friday evening
        self.assertIn("С наступающим", g(2026, 12, 31, 12, 0))
        self.assertIn("С Новым годом", g(2027, 1, 1, 12, 0))
        self.assertIn("первым апреля", g(2027, 4, 1, 12, 0))
        self.assertIn("Днём программиста", g(2026, 9, 13, 12, 0))    # day 256
        self.assertIn("Днём программиста", g(2028, 9, 12, 12, 0))    # day 256 in a leap year
        self.assertNotIn("программиста", g(2028, 9, 13, 12, 0))
        self.assertEqual(g(2026, 9, 23, 14, 0, kent=False), "Добрый день! Чем помочь?")
        for seed in range(12):                                         # the name instead of «кентафурик»
            named = fun.greeting(dt.datetime(2026, 9, 23, 14, 0), True, name="Макс", rng=random.Random(seed))[0]
            self.assertLessEqual(named.count("Макс"), 1)
            self.assertNotIn("кентафурик", named)

    def test_greetings_are_never_the_same_twice_in_a_row(self):
        # «Йоу», «здарова», «салют», «хэй»… the кентафурик does not repeat himself (jackson/variety.py)
        variety.forget()
        rng = random.Random(7)
        day = [fun.greeting(dt.datetime(2026, 9, 23, 14, 0), True, rng=rng)[0] for _ in range(24)]
        self.assertTrue(all(a != b for a, b in zip(day, day[1:])))
        self.assertGreaterEqual(len(set(day)), 6)
        self.assertTrue(any(t.startswith(("Йоу", "Йо-йо")) for t in day))
        self.assertTrue(any(t.startswith("Здарова") for t in day))
        words = {t.split("!")[0].split(",")[0].split("?")[0] for t in day}
        self.assertGreaterEqual(len(words), 4)                     # different openings, not one phrase
        for slot, lines in fun.HELLO_KENT.items():
            with self.subTest(slot=slot):
                self.assertGreaterEqual(len(lines), 3)
                self.assertTrue(all(ru and en for ru, en in lines))
        thanks = [fun.meme("thanks", True, rng)[0] for _ in range(10)]
        self.assertTrue(all(a != b for a, b in zip(thanks, thanks[1:])))
        self.assertEqual(fun.meme("thanks", False, rng)[0], "Пожалуйста!")
        jokes = [fun.joke(rng)[0] for _ in range(len(fun.JOKES_RU) // 2 + 1)]
        self.assertEqual(len(jokes), len(set(jokes)))              # no joke twice until half of them were told


class FunIntentTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        paths = Paths.for_root(self.root)
        self.osc = OsControl(FakeRunner(paths), paths, None)

    def tearDown(self):
        rmtree(self.root)

    def say(self, text, persona="kent", humor=1, lang="ru"):
        m = fastpath.match(text, self.osc)
        self.assertIsNotNone(m, text)
        return m.name, fastpath.run(m, fastpath.FastCtx(self.osc, lang, persona, humor=humor, seed="t-1"))

    def test_phrases(self):
        expect = {"подбрось монетку": "coin", "Орёл или решка?": "coin", "кинь кубик d20": "dice", "d6": "dice",
                  "шар судьбы, стоит ли мне идти": "ball", "да или нет": "ball", "камень": "rps",
                  "сыграем в камень ножницы бумага": "rps", "выбери за меня пиццу или суши": "pick",
                  "загадай число от 1 до 10": "number", "расскажи анекдот": "joke", "пошути": "joke",
                  "пепе шнейне фа": "pepe", "превед медвед": "preved", "это фиаско, братан": "fiasco",
                  "Хьюстон, у нас проблемы": "houston", "кто молодец?": "good_job", "спасибо!": "thanks",
                  "как дела?": "how_are_you", "в чём смысл жизни": "answer42", "морзянкой привет": "morse",
                  "Привет, Джексон!": "hello", "tell me a joke": "joke", "flip a coin": "coin",
                  "hi, what can you do": "help", "привет, подбрось монетку": "coin",   # a greeting, then a command
                  "which model fits this computer": "model_suggest", "какую модель поставить": "model_suggest"}
        for text, name in expect.items():
            self.assertEqual(self.say(text)[0], name, text)
        for text in ("как сделать тёмную тему в VS Code", "выбери лучший ноутбук", "напиши анекдот про кота в стихах"):
            self.assertIsNone(fastpath.match(text, self.osc), text)

    def test_replies_keep_their_own_voice(self):
        name, r = self.say("пепе шнейне")
        self.assertTrue(r.ok)
        self.assertIn("шнейне", r.text)
        self.assertFalse(r.text.startswith(tuple(f.split()[0] for f in ("Базару", "Лови,", "Чётко."))))
        name, plain = self.say("пепе шнейне", persona="dispatcher")
        self.assertEqual(plain.text, "Мем знаю: «пепе, шнейне, фа». Чем помочь?")
        name, r = self.say("кинь кубик d2000")
        self.assertFalse(r.ok)
        name, r = self.say("морзянкой sos")
        self.assertEqual(r.text, "··· ——— ···")
        r.after()                           # after the answer: the beeps, through `sos morse`
        self.assertIn(["sos", "morse", "--quiet", "sos"], self.osc.runner.calls)
        self.osc.runner.available.discard("sos")
        self.assertIsNone(self.say("морзянкой sos")[1].after)        # no sos: text only


if __name__ == "__main__":
    unittest.main()
