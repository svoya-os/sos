# SPDX-License-Identifier: Apache-2.0
"""Jackson's answer as speech: sentences ready while the answer streams, numbers spelled out."""

import unittest

from jackson.voice.speech import (SpeechStream, clean_inline, en_number, numbers_to_words, ru_number,
                                  ru_plural, speakable)


class NumbersTest(unittest.TestCase):
    def test_russian_numbers_and_the_noun_after_them(self):
        self.assertEqual(ru_number(0), "ноль")
        self.assertEqual(ru_number(21), "двадцать один")
        self.assertEqual(ru_number(2, feminine=True), "две")
        self.assertEqual(ru_number(2026), "две тысячи двадцать шесть")
        self.assertEqual(ru_number(1_001_000), "один миллион одна тысяча")
        self.assertEqual([ru_plural(n, "процент", "процента", "процентов") for n in (1, 3, 5, 11, 21, 112)],
                         ["процент", "процента", "процентов", "процентов", "процент", "процентов"])

    def test_english_numbers(self):
        self.assertEqual(en_number(0), "zero")
        self.assertEqual(en_number(115), "one hundred fifteen")
        self.assertEqual(en_number(2026), "two thousand twenty-six")

    def test_what_jackson_says_in_russian(self):
        cases = {
            "громкость 70%": "громкость семьдесят процентов",
            "встреча в 15:30": "встреча в пятнадцать тридцать",
            "в 9:05": "в девять ноль пять",
            "свободно 12 ГБ": "свободно двенадцать гигабайт",
            "осталась 1 минута, потом 2 минуты": "осталась одна минута, потом две минуты",
            "за окном -5 °C": "за окном минус пять градусов",
            "3,5%": "три и пять процента",
            "2 000 ₽": "две тысячи рублей",
            "$5": "пять долларов",
            "21 процент": "двадцать один процент",
        }
        for text, said in cases.items():
            self.assertEqual(numbers_to_words(text, "ru"), said, text)

    def test_what_jackson_says_in_english(self):
        self.assertEqual(numbers_to_words("volume at 70%, meeting at 3:30 PM", "en"),
                         "volume at seventy percent, meeting at three thirty PM")
        self.assertEqual(numbers_to_words("1 minute, 12 GB, 3.5%", "en"),
                         "one minute, twelve gigabytes, three point five percent")

    def test_names_with_digits_are_left_alone(self):
        self.assertEqual(numbers_to_words("Qwen3.5 и v0.2", "ru"), "Qwen3.5 и v0.2")
        self.assertEqual(numbers_to_words("5 с половиной", "ru"), "пять с половиной")


class MarkdownTest(unittest.TestCase):
    def test_markup_links_and_emoji_are_not_read_out(self):
        self.assertEqual(clean_inline("Я **сохранил** [заметку](file:///x) 🎉", "ru"), "Я сохранил заметку")
        self.assertEqual(clean_inline("Подробнее: https://svoya.dev/docs. Дальше?", "ru"), "Подробнее: ссылка. Дальше?")
        self.assertEqual(clean_inline("Сохранил в ~/Документы/план.md.", "ru"), "Сохранил в план.md.")
        self.assertEqual(clean_inline("run `sos doctor` now", "en"), "run sos doctor now")

    def test_code_and_tables_are_mentioned_once(self):
        md = "Вот так:\n\n```bash\nsos install steam\n```\n\nи так:\n\n```\nls\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nВсё."
        self.assertEqual(speakable(md, "ru"), ["Вот так: Код — на экране.", "и так: Таблица — на экране.", "Всё."])

    def test_headers_and_list_items_are_sentences(self):
        md = "## Итог\n\n- громкость 70%\n- встреча в 15:30\n"
        self.assertEqual(speakable(md, "ru"), ["Итог.", "громкость семьдесят процентов.", "встреча в пятнадцать тридцать."])


class StreamTest(unittest.TestCase):
    def test_the_first_sentence_is_ready_before_the_answer_ends(self):
        s = SpeechStream("ru")
        self.assertEqual(s.feed("Готово! Громкость "), ["Готово!"])
        self.assertEqual(s.feed("теперь 70%, а"), [])
        self.assertEqual(s.flush(), ["Громкость теперь семьдесят процентов, а."])   # the end sounds like one

    def test_a_long_first_sentence_starts_at_a_comma(self):
        s = SpeechStream("en")
        got = s.feed("I checked the disk, the memory and the processor, and everything looks fine")
        self.assertEqual(got, ["I checked the disk, the memory and the processor,"])

    def test_small_pieces_give_the_same_sentences(self):
        md = "Готово: громкость 70%.\n\n```\ncode\n```\n\nДальше — [ссылка](http://x.y). Ещё вопрос?"
        whole = speakable(md, "ru")
        s = SpeechStream("ru")
        pieces = []
        for i in range(0, len(md), 2):
            pieces += s.feed(md[i:i + 2])
        pieces += s.flush()
        self.assertEqual(pieces, whole)

    def test_nothing_to_say(self):
        self.assertEqual(speakable("```\nonly code\n```", "en"), ["The code is on the screen."])
        self.assertEqual(speakable("🎉🎉", "ru"), [])

    def test_numbers_can_stay_digits(self):
        self.assertEqual(speakable("It is 70%.", "en", numbers=False), ["It is 70%."])


if __name__ == "__main__":
    unittest.main()
