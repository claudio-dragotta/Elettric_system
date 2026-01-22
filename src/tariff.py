"""Build hourly tariff series (F1/F2/F3) with Italian holidays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd


@dataclass
class TariffSeries:
    timestamps: pd.DatetimeIndex
    prices_eur_per_mwh: np.ndarray


def build_hourly_index(year: int, hours: np.ndarray) -> pd.DatetimeIndex:
    start = datetime(year, 1, 1)
    return pd.DatetimeIndex([start + timedelta(hours=int(h)) for h in hours])


def _easter_date(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def italian_holidays(year: int) -> set[date]:
    easter = _easter_date(year)
    easter_monday = easter + timedelta(days=1)
    return {
        date(year, 1, 1),   # Capodanno
        date(year, 1, 6),   # Epifania
        easter_monday,
        date(year, 4, 25),  # Liberazione
        date(year, 5, 1),   # Lavoro
        date(year, 6, 2),   # Repubblica
        date(year, 8, 15),  # Ferragosto
        date(year, 11, 1),  # Ognissanti
        date(year, 12, 8),  # Immacolata
        date(year, 12, 25), # Natale
        date(year, 12, 26), # Santo Stefano
    }


def tariff_f1_f2_f3(
    timestamps: pd.DatetimeIndex,
    f1: float,
    f2: float,
    f3: float,
) -> np.ndarray:
    # Italian time-of-use schedule (ARERA, typical):
    # F1: Mon-Fri 08-19
    # F2: Mon-Fri 07-08,19-23 and Sat 07-23
    # F3: nights + Sundays + holidays
    prices = np.full(len(timestamps), f3, dtype=float)
    holidays = italian_holidays(timestamps[0].year)

    for i, ts in enumerate(timestamps):
        dow = ts.weekday()  # 0=Mon ... 6=Sun
        hour = ts.hour
        if ts.date() in holidays or dow == 6:
            prices[i] = f3
            continue
        if dow <= 4:  # Mon-Fri
            if 8 <= hour < 19:
                prices[i] = f1
            elif (7 <= hour < 8) or (19 <= hour < 23):
                prices[i] = f2
            else:
                prices[i] = f3
        elif dow == 5:  # Sat
            if 7 <= hour < 23:
                prices[i] = f2
            else:
                prices[i] = f3

    return prices
