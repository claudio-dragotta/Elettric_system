"""Load and align input datasets, apply unit conversions, and build price series."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from scipy.io import loadmat

from tariff import build_hourly_index, tariff_f1_f2_f3


@dataclass
class SeriesBundle:
    data: pd.DataFrame
    meta: Dict[str, float]


def _load_mat(path: Path) -> Dict[str, np.ndarray]:
    data = loadmat(path, squeeze_me=True, struct_as_record=False)
    return {k: v for k, v in data.items() if not k.startswith('__')}


def _normalize_hours(hours: np.ndarray) -> np.ndarray:
    hours = np.asarray(hours).astype(int)
    if hours.min() == 1:
        hours = hours - 1
    if hours.max() <= 23 and len(hours) > 24:
        # Hour-of-day values only; rebuild as sequential hours.
        hours = np.arange(len(hours), dtype=int)
    return hours


def _build_import_price_series(cfg: dict, hours: np.ndarray) -> np.ndarray:
    f1 = cfg['prices']['import_f1_eur_per_kwh']
    f2 = cfg['prices']['import_f2_eur_per_kwh']
    f3 = cfg['prices']['import_f3_eur_per_kwh']
    use_schedule = cfg['prices'].get('use_import_tariff_schedule', False)
    if use_schedule:
        year = int(cfg['project'].get('year', 2022))
        timestamps = build_hourly_index(year, hours)
        prices = tariff_f1_f2_f3(timestamps, f1, f2, f3)
    else:
        avg = (f1 + f2 + f3) / 3.0
        prices = np.full(len(hours), avg, dtype=float)

    # convert EUR/kWh to EUR/MWh
    return prices * 1000.0


def load_timeseries(data_dir: Path, cfg: dict) -> SeriesBundle:
    res = _load_mat(data_dir / 'res_1_year_pu.mat')
    load = _load_mat(data_dir / 'buildings_load.mat')
    pun = _load_mat(data_dir / 'PUN_2022.mat')

    p_pv = np.asarray(res['P_pv'], dtype=float)
    p_w = np.asarray(res['P_w'], dtype=float)
    pul = np.asarray(load['Pul'], dtype=float)
    price = np.asarray(pun['pun'], dtype=float).reshape(-1)

    pv_nom = float(cfg['system']['pv_nom_mw'])
    wind_nom = float(cfg['system']['wind_nom_mw'])
    load_scale = float(cfg['system']['load_scale'])
    load_scale_mode = cfg['system'].get('load_scale_mode', 'fixed')
    load_nom_mw = float(cfg['system']['load_nom_mw'])

    hours_all = np.arange(p_pv.shape[0], dtype=int)
    load_hours = _normalize_hours(pul[:, 0])

    df_year = pd.DataFrame(
        {
            'hour': hours_all,
            'pv_forecast_mw': p_pv[:, 0] * pv_nom,
            'pv_actual_mw': p_pv[:, 1] * pv_nom,
            'wind_forecast_mw': p_w[:, 0] * wind_nom,
            'wind_actual_mw': p_w[:, 1] * wind_nom,
            'pun_eur_per_mwh': price,
        }
    ).set_index('hour')

    load_forecast_mw = pul[:, 1] / 1000.0
    load_actual_mw = pul[:, 2] / 1000.0

    if load_scale_mode == 'max_to_nominal':
        peak = float(np.max(load_actual_mw))
        load_scale = load_nom_mw / peak if peak > 0 else 1.0

    df_load = pd.DataFrame(
        {
            'hour': load_hours,
            'load_forecast_mw': load_forecast_mw * load_scale,
            'load_actual_mw': load_actual_mw * load_scale,
        }
    ).set_index('hour')

    use_full_year = bool(cfg['project'].get('use_full_year', False))
    if use_full_year:
        df = df_year.join(df_load, how='left')
    else:
        df = df_year.join(df_load, how='inner')

    df['import_price_eur_per_mwh'] = _build_import_price_series(cfg, df.index.values)

    return SeriesBundle(
        data=df,
        meta={
            'pv_nom_mw': pv_nom,
            'wind_nom_mw': wind_nom,
            'load_scale': load_scale,
            'load_scale_mode': load_scale_mode,
        },
    )


def add_net_load(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['net_load_forecast_mw'] = df['load_forecast_mw'] - (
        df['pv_forecast_mw'] + df['wind_forecast_mw']
    )
    df['net_load_actual_mw'] = df['load_actual_mw'] - (
        df['pv_actual_mw'] + df['wind_actual_mw']
    )
    return df
