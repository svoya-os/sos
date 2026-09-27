# SPDX-License-Identifier: Apache-2.0
"""In the evening Jackson speaks calmer: which voice and how fast, by the clock and the settings."""

import datetime as dt
import unittest

from jackson.voice.client import evening_hours, for_engine, is_evening, voice_now, voice_settings

DAY = dt.datetime(2026, 9, 27, 14, 0)
NIGHT = dt.datetime(2026, 9, 27, 23, 30)
EARLY = dt.datetime(2026, 9, 28, 6, 15)


class EveningTest(unittest.TestCase):
    def test_by_day_the_characters_voice_in_the_evening_a_calmer_one_a_little_slower(self):
        self.assertEqual(voice_now({}, "kent", "supertonic-3", DAY), ("kent", 1.0))
        self.assertEqual(voice_now({}, "kent", "supertonic-3", NIGHT), ("M5", 0.94))
        self.assertEqual(voice_now({}, "kent", "supertonic-3", EARLY), ("M5", 0.94))     # till 07:00
        self.assertEqual(voice_now({}, "kent", "qwen3-tts", NIGHT), ("sysop", 0.94))
        self.assertEqual(voice_now({}, "kent", "", NIGHT), ("kent", 0.94))              # unknown engine: slower only

    def test_everything_can_be_set(self):
        cfg = {"voice": "M1", "evening": "21:30-06:00", "evening_voice": "M2", "evening_speed": 0.9}
        self.assertEqual(voice_now(cfg, "kent", "supertonic-3", DAY), ("M1", 1.0))
        self.assertEqual(voice_now(cfg, "kent", "supertonic-3", NIGHT), ("M2", 0.9))
        self.assertEqual(voice_now(cfg, "kent", "supertonic-3", dt.datetime(2026, 9, 27, 21, 0)), ("M1", 1.0))
        self.assertEqual(voice_now({"evening": "off"}, "kent", "supertonic-3", NIGHT), ("kent", 1.0))
        self.assertEqual(voice_now({"evening": "выкл"}, "kent", "supertonic-3", NIGHT), ("kent", 1.0))
        self.assertEqual(voice_now({"evening_speed": "fast"}, "kent", "supertonic-3", NIGHT), ("M5", 0.94))
        self.assertEqual(voice_now({"evening_speed": 0.2}, "kent", "supertonic-3", NIGHT), ("M5", 0.7))

    def test_what_the_shell_shows(self):
        self.assertEqual(voice_settings({}, "kent", "supertonic-3"),
                         {"voice": "M1", "evening": "20:00-07:00", "eveningVoice": "M5", "eveningSpeed": 0.94,
                          "engine": "supertonic-3"})
        self.assertEqual(voice_settings({"voice": "F2", "evening": "off"}, "kent", "supertonic-3")["evening"], "off")
        self.assertEqual(voice_settings({}, "pirate", "qwen3-tts")["voice"], "pirate")

    def test_with_his_own_voice_the_characters_speak(self):
        # a graphics card (voice-gpu): Кентафурик by day, the calm one (sysop) in the evening; a
        # Supertonic voice kept in the settings stands for its character
        self.assertEqual(voice_now({}, "kent", "qwen3-tts", DAY), ("kent", 1.0))
        self.assertEqual(voice_now({}, "kent", "qwen3-tts", NIGHT), ("sysop", 0.94))
        self.assertEqual(voice_now({"voice": "M1"}, "kent", "qwen3-tts", DAY), ("kent", 1.0))
        self.assertEqual(voice_now({"voice": "M3"}, "kent", "qwen3-tts", DAY), ("dispatcher", 1.0))
        self.assertEqual(voice_now({"voice": "F2"}, "kent", "qwen3-tts", DAY), ("kent", 1.0))
        shown = voice_settings({"voice": "M1", "evening_voice": "M2"}, "kent", "qwen3-tts")
        self.assertEqual((shown["voice"], shown["eveningVoice"]), ("kent", "sysop"))
        self.assertEqual(for_engine("M1", "supertonic-3"), "M1")

    def test_hours(self):
        self.assertEqual(evening_hours("20:00-07:00"), (dt.time(20), dt.time(7)))
        self.assertEqual(evening_hours("20 - 7"), (dt.time(20), dt.time(7)))
        self.assertEqual(evening_hours("18:30–23:00"), (dt.time(18, 30), dt.time(23)))
        self.assertIsNone(evening_hours("вечером"))
        self.assertIsNone(evening_hours("25:00-07:00"))
        self.assertTrue(is_evening(dt.datetime(2026, 1, 1, 22, 0), "18:30-23:00"))
        self.assertFalse(is_evening(dt.datetime(2026, 1, 1, 23, 0), "18:30-23:00"))


if __name__ == "__main__":
    unittest.main()
