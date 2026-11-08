"""German public holidays (the 9 that apply in every state).

On a holiday, electricity demand drops like on a Sunday, so prices drop too.
"""
from datetime import date, timedelta
from functools import lru_cache


def easter(year):
    # Gauss/Meeus algorithm for Easter Sunday
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    x = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * x) // 451
    month = (h + x - 7 * m + 114) // 31
    day = (h + x - 7 * m + 114) % 31 + 1
    return date(year, month, day)


@lru_cache
def holidays(year):
    e = easter(year)
    return {
        date(year, 1, 1),            # New Year
        e - timedelta(days=2),       # Good Friday
        e + timedelta(days=1),       # Easter Monday
        date(year, 5, 1),            # Labour Day
        e + timedelta(days=39),      # Ascension Day
        e + timedelta(days=50),      # Whit Monday
        date(year, 10, 3),           # German Unity Day
        date(year, 12, 25),          # Christmas
        date(year, 12, 26),          # Boxing Day
    }


def is_holiday(d):
    return d in holidays(d.year)