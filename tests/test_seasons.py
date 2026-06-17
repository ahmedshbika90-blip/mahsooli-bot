"""Unit tests for ndvi/seasons.py (pure date math, no Earth Engine, no network).

Run:  python -m unittest discover tests
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ndvi"))
import seasons  # noqa: E402


class SeasonWindowTests(unittest.TestCase):
    def test_season_bounds(self):
        self.assertEqual(seasons.season_start(2023), date(2023, 6, 1))
        self.assertEqual(seasons.season_end(2023), date(2024, 3, 31))

    def test_first_and_last_week(self):
        self.assertEqual(seasons.season_week(date(2023, 6, 1), 2023), 1)
        self.assertEqual(seasons.season_week(date(2023, 6, 7), 2023), 1)
        self.assertEqual(seasons.season_week(date(2023, 6, 8), 2023), 2)
        self.assertEqual(seasons.season_week(date(2024, 3, 31), 2023), 44)

    def test_outside_window_is_none(self):
        self.assertIsNone(seasons.season_week(date(2023, 5, 31), 2023))
        self.assertIsNone(seasons.season_week(date(2024, 4, 1), 2023))

    def test_leap_february_inside_season(self):
        # Season 2023 spans Feb 2024, a leap year.
        self.assertEqual(seasons.season_week(date(2024, 2, 29), 2023), 40)

    def test_week44_is_clipped_stub_leap(self):
        start, end_exclusive = seasons.week_date_range(2023, 44)
        self.assertEqual(start, date(2024, 3, 28))
        self.assertEqual(end_exclusive, date(2024, 4, 1))  # 4 days (leap Feb shifts)

    def test_week44_is_clipped_stub_non_leap(self):
        start, end_exclusive = seasons.week_date_range(2024, 44)
        self.assertEqual(start, date(2025, 3, 29))
        self.assertEqual(end_exclusive, date(2025, 4, 1))  # 3 days

    def test_week_range_rejects_bad_week(self):
        with self.assertRaises(ValueError):
            seasons.week_date_range(2023, 0)
        with self.assertRaises(ValueError):
            seasons.week_date_range(2023, seasons.n_weeks() + 1)

    def test_weeks_partition_the_whole_season(self):
        # Every day of the season maps to exactly the week whose range holds it.
        for season_year in (2023, 2024):  # leap and non-leap Feb
            day = seasons.season_start(season_year)
            while day <= seasons.season_end(season_year):
                week = seasons.season_week(day, season_year)
                start, end_exclusive = seasons.week_date_range(season_year, week)
                self.assertTrue(start <= day < end_exclusive,
                                f"{day} not inside week {week} of {season_year}")
                day = date.fromordinal(day.toordinal() + 1)


class CurrentSeasonTests(unittest.TestCase):
    def test_in_season_months(self):
        self.assertEqual(seasons.current_season_year(date(2025, 6, 1)), 2025)
        self.assertEqual(seasons.current_season_year(date(2025, 12, 31)), 2025)
        self.assertEqual(seasons.current_season_year(date(2026, 2, 10)), 2025)
        self.assertEqual(seasons.current_season_year(date(2026, 3, 31)), 2025)

    def test_off_season_months(self):
        self.assertIsNone(seasons.current_season_year(date(2026, 4, 1)))
        self.assertIsNone(seasons.current_season_year(date(2026, 5, 31)))


class SeasonListTests(unittest.TestCase):
    def test_parse_semicolons_and_commas(self):
        self.assertEqual(seasons.parse_seasons("2013;2015;2017"), [2013, 2015, 2017])
        self.assertEqual(seasons.parse_seasons("2023, 2025"), [2023, 2025])
        self.assertEqual(seasons.parse_seasons(" 2024 "), [2024])
        self.assertEqual(seasons.parse_seasons("2023;2023"), [2023])  # deduped

    def test_parse_rejects_garbage(self):
        with self.assertRaises(ValueError):
            seasons.parse_seasons("2019;cotton")
        with self.assertRaises(ValueError):
            seasons.parse_seasons("1999")

    def test_usable_seasons_drops_pre_s2_years(self):
        # Bahaa Eldeen Daood's listed seasons: only 2019+ have Sentinel-2 SR data.
        kept, skipped = seasons.usable_seasons(
            [2013, 2015, 2017, 2019, 2021, 2023, 2025], today=date(2026, 6, 11)
        )
        self.assertEqual(kept, [2019, 2021, 2023, 2025])
        self.assertEqual([y for y, _ in skipped], [2013, 2015, 2017])

    def test_usable_seasons_drops_unfinished_season(self):
        kept, skipped = seasons.usable_seasons([2025, 2026], today=date(2026, 6, 11))
        self.assertEqual(kept, [2025])
        self.assertEqual([y for y, _ in skipped], [2026])
