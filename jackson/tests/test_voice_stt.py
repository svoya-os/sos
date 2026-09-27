# SPDX-License-Identifier: Apache-2.0
"""Which recognizer's text Jackson takes: Parakeet for English it is sure of, GigaAM for Russian."""

import unittest

from jackson.voice.stt import BilingualSTT, Heard, is_english, sureness


class Model:
    def __init__(self, name, text, sure=None):
        self.name, self.text, self.sure = name, text, sure
        self.calls = 0

    def hear(self, samples):
        self.calls += 1
        return Heard(self.text, self.sure, self.name)


class Plain:
    """A recognizer that only gives text (the fakes of the service tests, older models)."""

    def __init__(self, name, text):
        self.name, self.text = name, text

    def recognize(self, samples):
        return self.text


class BilingualTest(unittest.TestCase):
    def test_english_it_is_sure_of_is_taken_without_asking_gigaam(self):
        parakeet, gigaam = Model("parakeet", "What time is it now?", 0.97), Model("gigaam", "вот тайм", 0.9)
        stt = BilingualSTT(parakeet, gigaam)
        self.assertEqual(stt.recognize([]), "What time is it now?")
        self.assertEqual((stt.last, gigaam.calls), ("parakeet", 0))
        self.assertEqual(stt.sureness(), 0.97)

    def test_russian_goes_to_gigaam(self):
        stt = BilingualSTT(Model("parakeet", "Какая сегодня погода", 0.95), Model("gigaam", "Какая сегодня погода?", 0.9))
        self.assertEqual(stt.recognize([]), "Какая сегодня погода?")
        self.assertEqual(stt.last, "gigaam")

    def test_unsure_english_loses_to_surer_russian(self):
        # robotic «открой браузер»: Parakeet heard English words that were never said
        stt = BilingualSTT(Model("parakeet", "But Carolina.", 0.55), Model("gigaam", "Открой браузер.", 0.88))
        self.assertEqual(stt.recognize([]), "Открой браузер.")
        self.assertEqual(stt.last, "gigaam")
        self.assertIn("parakeet 0.55", stt.describe())
        self.assertNotIn("браузер", stt.describe())     # the system log never gets the words

    def test_unsure_english_stays_when_gigaam_is_even_less_sure(self):
        # accented English: GigaAM spells it in Cyrillic and is not sure of that either
        stt = BilingualSTT(Model("parakeet", "Open Firefox.", 0.7), Model("gigaam", "Опен файрфокс.", 0.5))
        self.assertEqual(stt.recognize([]), "Open Firefox.")
        self.assertEqual(stt.last, "parakeet")

    def test_nothing_from_gigaam_keeps_parakeet(self):
        stt = BilingualSTT(Model("parakeet", "Привет", 0.8), Model("gigaam", "", None))
        self.assertEqual(stt.recognize([]), "Привет")
        self.assertEqual(stt.last, "parakeet")

    def test_models_that_do_not_say_how_sure_they_are(self):
        stt = BilingualSTT(Plain("parakeet", "Hello there"), Plain("gigaam", "Хэллоу зэа"))
        self.assertEqual(stt.recognize([]), "Hello there")
        stt = BilingualSTT(Plain("parakeet", "привет"), Plain("gigaam", "Привет."))
        self.assertEqual((stt.recognize([]), stt.last), ("Привет.", "gigaam"))
        self.assertIsNone(stt.sureness())

    def test_one_model(self):
        stt = BilingualSTT(Model("parakeet", "Guten Tag", 0.4))
        self.assertEqual((stt.recognize([]), stt.last), ("Guten Tag", "parakeet"))


class HelpersTest(unittest.TestCase):
    def test_is_english(self):
        self.assertTrue(is_english("Open the browser"))
        self.assertTrue(is_english("Open Firefox, пожалуйста"[:14]))
        self.assertFalse(is_english("Открой Firefox"))
        self.assertFalse(is_english(""))

    def test_sureness_is_the_geometric_mean_of_token_probabilities(self):
        import math
        self.assertAlmostEqual(sureness([math.log(0.9), math.log(0.4)]), 0.6)
        self.assertIsNone(sureness([]))
        self.assertIsNone(sureness(None))


if __name__ == "__main__":
    unittest.main()
