"""
NDVI shared helper - cotton-season window math (pure stdlib, no Earth Engine).

One cotton season Y runs SEASON_START (Jun 1 of year Y) through SEASON_END
(Mar 31 of year Y+1), covering the full Sudan rainfed cotton cycle including
harvest spillover into the next calendar year. Weeks are keyed RELATIVE to the
season start as absolute date offsets:

    week = (date - season_start).days // NDVI_WEEK_DAYS + 1     (1..44)

so curves from different years align week-for-week, leap years need no special
casing, and the old calendar DOY week-53 problem does not exist. Week 44 is a
short 3-4 day stub clipped at the season end.

Both the baseline builder (which filters Earth Engine by week_date_range) and
the current step (which derives the live week from the run date) go through
this module so the two can never drift apart.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config


def season_start(season_year: int) -> date:
    """First day of season `season_year` (default Jun 1 of that year)."""
    return date(season_year, config.SEASON_START_MONTH, config.SEASON_START_DAY)


def season_end(season_year: int) -> date:
    """Last day (inclusive) of season `season_year` (default Mar 31 of Y+1)."""
    end_year = season_year if config.SEASON_END_MONTH >= config.SEASON_START_MONTH \
        else season_year + 1
    return date(end_year, config.SEASON_END_MONTH, config.SEASON_END_DAY)


def n_weeks() -> int:
    """Number of week bins in one season (44 for 7-day bins over Jun-Mar)."""
    return config.NDVI_SEASON_WEEKS


def season_week(d: date, season_year: int):
    """
    1-based season-week index of `d` within season `season_year`, or None when
    `d` falls outside the season window.
    """
    if d < season_start(season_year) or d > season_end(season_year):
        return None
    return (d - season_start(season_year)).days // config.NDVI_WEEK_DAYS + 1


def week_date_range(season_year: int, week: int):
    """
    (start_date, end_date_exclusive) covered by season-week `week`, clipped at
    the season end. These absolute dates are what the Earth Engine filterDate
    calls use, so leap years and the Dec->Jan boundary are handled here once.
    """
    if not 1 <= week <= n_weeks():
        raise ValueError(f"week must be 1..{n_weeks()}, got {week}")
    start = season_start(season_year) + timedelta(days=(week - 1) * config.NDVI_WEEK_DAYS)
    end_exclusive = min(
        start + timedelta(days=config.NDVI_WEEK_DAYS),
        season_end(season_year) + timedelta(days=1),
    )
    return start, end_exclusive


def current_season_year(d: date):
    """
    The season year a run date belongs to, or None when off-season.

    Jun-Dec -> that calendar year; Jan-Mar -> the previous year (harvest tail);
    Apr-May -> None (between seasons; the current step reports "Off-season"
    and spends no Earth Engine quota).
    """
    if d.month >= config.SEASON_START_MONTH:
        return d.year
    if d.month <= config.SEASON_END_MONTH:
        return d.year - 1
    return None


def parse_seasons(raw: str):
    """
    Parse the registry's ';'-separated season years ("2019;2021;2023") into a
    sorted list of ints. Raises ValueError on anything unparseable.
    """
    years = []
    for part in (raw or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        year = int(part)
        if not 2000 <= year <= 2100:
            raise ValueError(f"season year out of range: {year}")
        years.append(year)
    return sorted(set(years))


def usable_seasons(seasons, today: date = None):
    """
    Split season years into (kept, skipped_with_reason).

    Skipped:
      - years before MIN_SEASON_YEAR (no usable Sentinel-2 SR over Sudan), and
      - seasons whose end date is still in the future (a partial year would
        bias the baseline curve).
    """
    today = today or date.today()
    kept, skipped = [], []
    for year in seasons:
        if year < config.MIN_SEASON_YEAR:
            skipped.append((year, f"before MIN_SEASON_YEAR={config.MIN_SEASON_YEAR} "
                                  f"(no Sentinel-2 SR over Sudan)"))
        elif season_end(year) >= today:
            skipped.append((year, "season not finished yet (partial data would "
                                  "bias the baseline)"))
        else:
            kept.append(year)
    return kept, skipped
