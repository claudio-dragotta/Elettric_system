"""
Test MPC con dati 2025
Esegue il modello MPC usando PUN 2025 e tariffe ARERA aggiornate
"""

from __future__ import annotations

import sys
from pathlib import Path

# Aggiungi src al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / 'src'))

import numpy as np
import pandas as pd
from scipy.io import loadmat, savemat
from tqdm import tqdm
import yaml

from loader import load_timeseries, add_net_load, _load_mat
from model import solve_horizon


def load_timeseries_2025(data_dir: Path, test_dir: Path, cfg: dict):
    """
    Carica i dati per il test 2025:
    - RES e Load dal 2022 (stessi profili)
    - PUN dal 2025
    """
    from loader import (
        _normalize_hours, _build_import_price_series, SeriesBundle
    )

    # Carica RES e Load dal 2022 (profili invariati)
    res = _load_mat(data_dir / 'res_1_year_pu.mat')
    load = _load_mat(data_dir / 'buildings_load.mat')

    # Carica PUN 2025
    pun_2025 = _load_mat(test_dir / 'PUN_2025.mat')

    p_pv = np.asarray(res['P_pv'], dtype=float)
    p_w = np.asarray(res['P_w'], dtype=float)
    pul = np.asarray(load['Pul'], dtype=float)
    price = np.asarray(pun_2025['pun'], dtype=float).reshape(-1)

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
            'pun_eur_per_mwh': price[:len(hours_all)],  # Troncato se necessario
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


def run_receding(
    df: pd.DataFrame,
    cfg: dict,
    start: int,
    horizon: int,
    fuel_eur_per_kwh: float | None = None,
    n_steps: int | None = None,
    desc: str = 'MPC 2025',
) -> pd.DataFrame:
    """Esegue MPC receding horizon"""
    results = []
    soc = 0.0
    last_hour = df.index.max()

    end_hour = int(last_hour) - horizon + 1
    if n_steps is not None:
        end_hour = min(start + n_steps, end_hour)

    for hour in tqdm(range(start, end_hour), desc=desc):
        res = solve_horizon(df, cfg, hour, horizon, soc, fuel_eur_per_kwh=fuel_eur_per_kwh)
        first = res.schedule.iloc[0]
        soc = float(first['soc_mwh'])
        results.append(
            {
                'hour': hour,
                'p_import_mw': float(first['p_import_mw']),
                'p_export_mw': float(first['p_export_mw']),
                'p_ely_mw': float(first['p_ely_mw']),
                'p_fc_mw': float(first['p_fc_mw']),
                'p_dg_mw': float(first['p_dg_mw']),
                'p_curt_mw': float(first['p_curt_mw']),
                'soc_mwh': soc,
                'objective_eur': float(res.objective_value),
            }
        )

    return pd.DataFrame(results).set_index('hour')


def run_scenario(df, cfg, fuel_cost, output_dir, start, horizon, n_steps=None, suffix=''):
    """Esegue un singolo scenario MPC"""
    fuel_str = f'{fuel_cost:.2f}'.replace('.', '')
    filename = f'mpc_2025_{suffix}_cf{fuel_str}.csv' if suffix else f'mpc_2025_cf{fuel_str}.csv'
    out_path = output_dir / filename

    desc = f'MPC {suffix}' if suffix else 'MPC 2025'
    schedule = run_receding(df, cfg, start, horizon, fuel_eur_per_kwh=fuel_cost, n_steps=n_steps, desc=desc)
    schedule.to_csv(out_path)

    print(f"\n  Risultati:")
    print(f"    Ore simulate: {len(schedule)}")
    print(f"    Import totale: {schedule['p_import_mw'].sum():.2f} MWh")
    print(f"    Export totale: {schedule['p_export_mw'].sum():.2f} MWh")
    print(f"    DG totale: {schedule['p_dg_mw'].sum():.2f} MWh")
    print(f"    ELY totale: {schedule['p_ely_mw'].sum():.2f} MWh")
    print(f"    FC totale: {schedule['p_fc_mw'].sum():.2f} MWh")
    print(f"    File: {out_path.name}")

    return schedule


def main():
    print("="*60)
    print("TEST MPC CON DATI 2025")
    print("="*60)

    # Percorsi
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    data_dir = project_root / 'data'
    output_dir = test_dir / 'outputs_2025'

    # Crea cartella output
    output_dir.mkdir(exist_ok=True)

    # Carica config 2025
    config_path = test_dir / 'system_2025.yaml'
    cfg = yaml.safe_load(config_path.read_text(encoding='utf-8'))

    print(f"\nConfig: {config_path}")
    print(f"Output: {output_dir}")

    # Verifica che PUN_2025.mat esista
    pun_file = test_dir / 'PUN_2025.mat'
    if not pun_file.exists():
        print(f"\nERRORE: File {pun_file} non trovato!")
        print("Esegui prima: python convert_pun.py")
        return

    # Carica dati
    print("\nCaricamento dati...")
    bundle = load_timeseries_2025(data_dir, test_dir, cfg)
    df = add_net_load(bundle.data)

    print(f"Ore disponibili: {len(df)}")
    print(f"PUN 2025 - Min: {df['pun_eur_per_mwh'].min():.2f}, Max: {df['pun_eur_per_mwh'].max():.2f}, Media: {df['pun_eur_per_mwh'].mean():.2f} EUR/MWh")

    # Parametri
    horizon = int(cfg['project']['horizon_h'])
    start = int(cfg['project']['start_hour'])

    # Scenari fuel cost
    fuel_values = [
        float(cfg['prices']['fuel_eur_per_kwh']),
        float(cfg['prices']['fuel_alt_eur_per_kwh']),
    ]

    print(f"\nScenari fuel cost:")
    for fc in fuel_values:
        dg_cost = fc / cfg['system']['eta_dg']
        print(f"  cf={fc:.2f} -> Costo DG = {dg_cost*1000:.0f} EUR/MWh")

    # ========================================
    # TEST 1: 24 ore
    # ========================================
    print(f"\n{'='*60}")
    print("TEST 1: 24 ORE")
    print(f"{'='*60}")

    for fuel_cost in fuel_values:
        print(f"\n  cf={fuel_cost:.2f}:")
        run_scenario(df, cfg, fuel_cost, output_dir, start, horizon, n_steps=24, suffix='24h')

    # ========================================
    # TEST 2: Periodo completo (272 giorni)
    # ========================================
    print(f"\n{'='*60}")
    print("TEST 2: PERIODO COMPLETO (~272 giorni)")
    print(f"{'='*60}")

    for fuel_cost in fuel_values:
        print(f"\n  cf={fuel_cost:.2f}:")
        run_scenario(df, cfg, fuel_cost, output_dir, start, horizon, n_steps=None, suffix='full')

    print(f"\n{'='*60}")
    print("TEST COMPLETATO!")
    print(f"Output in: {output_dir}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
