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


def run_receding(df: pd.DataFrame, cfg: dict, start: int, horizon: int) -> pd.DataFrame:
    results = []
    soc = 0.0
    last_hour = df.index.max()

    for hour in tqdm(range(start, int(last_hour) - horizon + 1), desc='MPC'):
        res = solve_horizon(df, cfg, hour, horizon, soc)
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
    parser.add_argument('--out', default='outputs/mpc_receding.csv')
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding='ascii'))
    horizon = args.horizon or int(cfg['project']['horizon_h'])

    values = []
    if args.load_nom_values.strip():
        values = [float(v) for v in args.load_nom_values.split(',') if v.strip()]
    else:
        cfg_values = cfg['system'].get('load_nom_mw_values', [])
        if cfg_values:
            values = [float(v) for v in cfg_values]
        else:
            values = [float(cfg['system']['load_nom_mw'])]

    for load_nom in values:
        cfg['system']['load_nom_mw'] = load_nom
        bundle = load_timeseries(Path('data'), cfg)
        df = add_net_load(bundle.data)

        schedule = run_receding(df, cfg, args.start, horizon)

        out_path = Path(args.out)
        if len(values) > 1:
            suffix = f'_load{int(load_nom)}'
            out_path = out_path.with_name(out_path.stem + suffix + out_path.suffix)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        schedule.to_csv(out_path)

        print(f'wrote {out_path} rows={len(schedule)}')


if __name__ == '__main__':
    main()
