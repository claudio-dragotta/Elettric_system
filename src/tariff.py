"""
Gestione delle tariffe elettriche italiane a fasce orarie (F1/F2/F3).

Questo modulo implementa la logica delle fasce orarie ARERA per il mercato
elettrico italiano, incluso il calendario delle festivita' nazionali.

Fasce orarie ARERA:
- F1 (punta): Lun-Ven 08:00-19:00 (esclusi festivi)
- F2 (intermedia): Lun-Ven 07:00-08:00 e 19:00-23:00, Sab 07:00-23:00
- F3 (fuori punta): notti (23:00-07:00), domeniche, festivi

Riferimento: Delibera ARERA per le tariffe di fornitura elettrica.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd


@dataclass
class TariffSeries:
    """
    Contenitore per una serie di tariffe orarie.

    Attributi:
        timestamps: Indice temporale delle ore
        prices_eur_per_mwh: Array dei prezzi corrispondenti [EUR/MWh]
    """
    timestamps: pd.DatetimeIndex
    prices_eur_per_mwh: np.ndarray


def build_hourly_index(year: int, hours: np.ndarray) -> pd.DatetimeIndex:
    """
    Costruisce un indice temporale DatetimeIndex a partire da indici orari.

    Converte gli indici orari (0, 1, 2, ..., N) in timestamp datetime
    a partire dal 1 gennaio dell'anno specificato.

    Args:
        year: Anno di riferimento
        hours: Array di indici orari (0 = prima ora dell'anno)

    Returns:
        DatetimeIndex con i timestamp corrispondenti

    Esempio:
        hours = [0, 1, 2] -> [2022-01-01 00:00, 2022-01-01 01:00, 2022-01-01 02:00]
    """
    start = datetime(year, 1, 1)  # Primo istante dell'anno
    return pd.DatetimeIndex([start + timedelta(hours=int(h)) for h in hours])


def _easter_date(year: int) -> date:
    """
    Calcola la data della Pasqua per un dato anno.

    Implementa l'algoritmo anonimo gregoriano per il calcolo della Pasqua.
    Riferimento: https://en.wikipedia.org/wiki/Date_of_Easter

    Args:
        year: Anno per cui calcolare la Pasqua

    Returns:
        Data della domenica di Pasqua
    """
    # Algoritmo anonimo gregoriano
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
    """
    Restituisce l'insieme delle festivita' nazionali italiane per un dato anno.

    Le festivita' sono trattate come domeniche ai fini delle fasce orarie
    (applicazione della tariffa F3 per tutto il giorno).

    Args:
        year: Anno di riferimento

    Returns:
        Set di date delle festivita' nazionali

    Festivita' incluse:
    - 1 gennaio: Capodanno
    - 6 gennaio: Epifania
    - Lunedi' dell'Angelo (Pasquetta)
    - 25 aprile: Festa della Liberazione
    - 1 maggio: Festa dei Lavoratori
    - 2 giugno: Festa della Repubblica
    - 15 agosto: Ferragosto (Assunzione)
    - 1 novembre: Ognissanti
    - 8 dicembre: Immacolata Concezione
    - 25 dicembre: Natale
    - 26 dicembre: Santo Stefano
    """
    # Calcola la Pasqua per determinare il Lunedi' dell'Angelo
    easter = _easter_date(year)
    easter_monday = easter + timedelta(days=1)  # Pasquetta

    return {
        date(year, 1, 1),    # Capodanno
        date(year, 1, 6),    # Epifania
        easter_monday,       # Lunedi' dell'Angelo
        date(year, 4, 25),   # Festa della Liberazione
        date(year, 5, 1),    # Festa dei Lavoratori
        date(year, 6, 2),    # Festa della Repubblica
        date(year, 8, 15),   # Ferragosto
        date(year, 11, 1),   # Ognissanti
        date(year, 12, 8),   # Immacolata Concezione
        date(year, 12, 25),  # Natale
        date(year, 12, 26),  # Santo Stefano
    }


def tariff_f1_f2_f3(
    timestamps: pd.DatetimeIndex,
    f1: float,  # Prezzo fascia F1 (punta) [EUR/kWh]
    f2: float,  # Prezzo fascia F2 (intermedia) [EUR/kWh]
    f3: float,  # Prezzo fascia F3 (fuori punta) [EUR/kWh]
) -> np.ndarray:
    """
    Assegna il prezzo corretto ad ogni ora secondo le fasce ARERA.

    Schema fasce orarie ARERA (tipico):
    - F1: Lun-Ven 08:00-19:00 (ore di punta, massima domanda)
    - F2: Lun-Ven 07:00-08:00 e 19:00-23:00, Sab 07:00-23:00 (intermedia)
    - F3: Lun-Sab 23:00-07:00, Dom tutto il giorno, festivi (fuori punta)

    Args:
        timestamps: Indice temporale delle ore da classificare
        f1: Prezzo per la fascia F1 [EUR/kWh]
        f2: Prezzo per la fascia F2 [EUR/kWh]
        f3: Prezzo per la fascia F3 [EUR/kWh]

    Returns:
        Array dei prezzi assegnati ad ogni ora [EUR/kWh]
    """
    # Inizializza tutti i prezzi a F3 (default per notti/domeniche/festivi)
    prices = np.full(len(timestamps), f3, dtype=float)

    # Carica le festivita' dell'anno
    holidays = italian_holidays(timestamps[0].year)

    # Ciclo su ogni timestamp per assegnare la fascia corretta
    for i, ts in enumerate(timestamps):
        dow = ts.weekday()  # Giorno della settimana: 0=Lun, 1=Mar, ..., 6=Dom
        hour = ts.hour      # Ora del giorno (0-23)

        # Festivi e domeniche -> sempre F3
        if ts.date() in holidays or dow == 6:
            prices[i] = f3
            continue

        # Lunedi' - Venerdi' (dow = 0-4)
        if dow <= 4:
            if 8 <= hour < 19:
                # Ore 08:00-18:59 -> F1 (punta)
                prices[i] = f1
            elif (7 <= hour < 8) or (19 <= hour < 23):
                # Ore 07:00-07:59 e 19:00-22:59 -> F2 (intermedia)
                prices[i] = f2
            else:
                # Ore 00:00-06:59 e 23:00-23:59 -> F3 (fuori punta)
                prices[i] = f3

        # Sabato (dow = 5)
        elif dow == 5:
            if 7 <= hour < 23:
                # Ore 07:00-22:59 -> F2 (intermedia)
                prices[i] = f2
            else:
                # Ore 00:00-06:59 e 23:00-23:59 -> F3 (fuori punta)
                prices[i] = f3

    return prices
