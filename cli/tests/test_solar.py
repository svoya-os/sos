import datetime as dt
import unittest

from svoya_cli.theme import solar

UTC = dt.timezone.utc


def minutes(t: dt.datetime) -> int:
    return t.hour * 60 + t.minute


class SolarTest(unittest.TestCase):
    """Published sunrise/sunset times (timeanddate.com / NOAA), local times converted to UTC; ±3 min."""

    def check(self, date, lat, lon, rise_utc, set_utc):
        st = solar.sun_times(date, lat, lon)
        for got, want in ((st.sunrise, rise_utc), (st.sunset, set_utc)):
            h, m = map(int, want.split(":"))
            diff = abs(minutes(got.astimezone(UTC)) - (h * 60 + m))
            self.assertLessEqual(min(diff, 1440 - diff), 3, f"{date} {lat},{lon}: {got:%H:%M} vs {want}")

    def test_tallinn_midsummer(self):          # 04:02 / 22:43 EEST
        self.check(dt.date(2024, 6, 21), 59.437, 24.745, "01:02", "19:43")

    def test_tallinn_midwinter(self):          # 09:17 / 15:21 EET
        self.check(dt.date(2024, 12, 21), 59.437, 24.745, "07:17", "13:21")

    def test_london(self):                     # 04:43 / 21:21 BST
        self.check(dt.date(2024, 6, 20), 51.5074, -0.1278, "03:43", "20:21")

    def test_new_york(self):                   # 07:20 / 16:39 EST
        self.check(dt.date(2024, 1, 1), 40.7128, -74.006, "12:20", "21:39")

    def test_sydney_southern_summer(self):     # 05:41 / 20:05 AEDT (sunrise is the previous UTC day)
        self.check(dt.date(2024, 12, 21), -33.8688, 151.2093, "18:41", "09:05")

    def test_polar(self):
        self.assertEqual(solar.sun_times(dt.date(2024, 6, 21), 69.6492, 18.9553).polar, "day")
        self.assertEqual(solar.sun_times(dt.date(2024, 12, 21), 69.6492, 18.9553).polar, "night")

    def test_is_daytime_and_fallback(self):
        day, why = solar.is_daytime(dt.datetime(2024, 6, 21, 12, 0, tzinfo=UTC), 59.437, 24.745)
        self.assertEqual((day, why), (True, "sun"))
        night, _ = solar.is_daytime(dt.datetime(2024, 12, 21, 20, 0, tzinfo=UTC), 59.437, 24.745)
        self.assertFalse(night)
        _, why = solar.is_daytime(dt.datetime(2024, 6, 21, 12, 0, tzinfo=UTC), 69.6492, 18.9553)
        self.assertEqual(why, "fallback (polar-day)")
        _, why = solar.is_daytime(dt.datetime(2024, 6, 21, 12, 0, tzinfo=UTC), 123, 0)
        self.assertEqual(why, "fallback (invalid-location)")


if __name__ == "__main__":
    unittest.main()
