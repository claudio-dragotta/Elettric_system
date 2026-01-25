"""Run receding-horizon MPC over the dataset and save schedules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loader import load_timeseries, add_net_load
from model import solve_horizon


def run_receding(
    df: pd.DataFrame,
    cfg: dict,
    start: int,
    horizon: int,
    fuel_eur_per_kwh: float | None = None,
) -> pd.DataFrame:
    results = []
    soc = 0.0
    last_hour = df.index.max()

    for hour in tqdm(range(start, int(last_hour) - horizon + 1), desc='MPC'):
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


def main() -> None:
    parser = argparse.ArgumentParser(description='Run receding-horizon MPC over dataset.')
    parser.add_argument('--config', default='configs/system.yaml')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--horizon', type=int, default=None)
    parser.add_argument(
        '--load-nom-values',
        default='',
        help='Comma-separated load nominal values in MW (e.g., 16,20)',
    )
    parser.add_argument(
        '--fuel-values',
        default='',
        help='Comma-separated fuel cost values in EUR/kWh (e.g., 0.45,0.60)',
    )
    parser.add_argument('--out', default='outputs/mpc_receding.csv')
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding='ascii'))
    horizon = args.horizon or int(cfg['project']['horizon_h'])

    load_values = []
    if args.load_nom_values.strip():
        load_values = [float(v) for v in args.load_nom_values.split(',') if v.strip()]
    else:
        cfg_values = cfg['system'].get('load_nom_mw_values', [])
        if cfg_values:
            load_values = [float(v) for v in cfg_values]
        else:
            load_values = [float(cfg['system']['load_nom_mw'])]

    fuel_values = []
    if args.fuel_values.strip():
        fuel_values = [float(v) for v in args.fuel_values.split(',') if v.strip()]
    else:
        fuel_values = [float(cfg['prices']['fuel_eur_per_kwh'])]
        alt_fuel = cfg['prices'].get('fuel_alt_eur_per_kwh')
        if alt_fuel is not None:
            fuel_values.append(float(alt_fuel))

    for load_nom in load_values:
        cfg['system']['load_nom_mw'] = load_nom
        bundle = load_timeseries(Path('data'), cfg)
        df = add_net_load(bundle.data)

        for fuel_cost in fuel_values:
            schedule = run_receding(df, cfg, args.start, horizon, fuel_eur_per_kwh=fuel_cost)

            out_path = Path(args.out)
            suffix_parts = []
            if len(load_values) > 1:
                suffix_parts.append(f'load{int(load_nom)}')
            if len(fuel_values) > 1:
                fuel_str = f'{fuel_cost:.2f}'.replace('.', '')
                suffix_parts.append(f'cf{fuel_str}')
            if suffix_parts:
                suffix = '_' + '_'.join(suffix_parts)
                out_path = out_path.with_name(out_path.stem + suffix + out_path.suffix)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            schedule.to_csv(out_path)

            print(f'wrote {out_path} rows={len(schedule)} (load={load_nom}MW, cf={fuel_cost})')


if __name__ == '__main__':
    main()
