"""Run a single-horizon MPC optimization and save the schedule."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loader import load_timeseries, add_net_load
from model import solve_horizon


def main() -> None:
    parser = argparse.ArgumentParser(description='Run MPC optimization for a horizon.')
    parser.add_argument('--config', default='configs/system.yaml')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--horizon', type=int, default=None)
    parser.add_argument('--soc-init', type=float, default=0.0)
    parser.add_argument('--fuel', type=float, default=None, help='Fuel price in EUR/kWh')
    parser.add_argument('--load-nom', type=float, default=None, help='Load nominal in MW')
    parser.add_argument('--out', default='outputs/mpc_schedule.csv')
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding='ascii'))
    if args.load_nom is not None:
        cfg['system']['load_nom_mw'] = float(args.load_nom)
    horizon = args.horizon or int(cfg['project']['horizon_h'])

    bundle = load_timeseries(Path('data'), cfg)
    df = add_net_load(bundle.data)

    result = solve_horizon(df, cfg, args.start, horizon, args.soc_init, args.fuel)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.schedule.to_csv(out_path)

    print(f'objective={result.objective_value:.2f} EUR')
    print(f'wrote {out_path}')


if __name__ == '__main__':
    main()
