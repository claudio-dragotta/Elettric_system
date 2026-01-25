"""Generate summary metrics and optional plots from MPC outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from loader import load_timeseries, add_net_load


def _safe_sum(series: pd.Series) -> float:
    return float(series.fillna(0.0).sum())


def build_report(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    cfg: dict,
    fuel_eur_per_kwh: float | None = None,
) -> pd.DataFrame:
    dt = float(cfg['project']['timestep_h'])
    if fuel_eur_per_kwh is None:
        fuel_eur_per_kwh = float(cfg['prices']['fuel_eur_per_kwh'])
    fuel_price = fuel_eur_per_kwh * 1000.0
    eta_dg = float(cfg['system'].get('eta_dg', 0.6))

    merged = df.join(schedule, how='inner')

    metrics = {
        'hours': len(merged),
        'energy_load_mwh': _safe_sum(merged['load_actual_mw'] * dt),
        'energy_pv_mwh': _safe_sum(merged['pv_actual_mw'] * dt),
        'energy_wind_mwh': _safe_sum(merged['wind_actual_mw'] * dt),
        'energy_import_mwh': _safe_sum(merged['p_import_mw'] * dt),
        'energy_export_mwh': _safe_sum(merged['p_export_mw'] * dt),
        'energy_dg_mwh': _safe_sum(merged['p_dg_mw'] * dt),
        'energy_ely_mwh': _safe_sum(merged['p_ely_mw'] * dt),
        'energy_fc_mwh': _safe_sum(merged['p_fc_mw'] * dt),
        'energy_curt_mwh': _safe_sum(merged['p_curt_mw'] * dt),
    }

    metrics['cost_import_eur'] = _safe_sum(
        merged['p_import_mw'] * merged['import_price_eur_per_mwh'] * dt
    )
    metrics['income_export_eur'] = _safe_sum(
        merged['p_export_mw'] * merged['pun_eur_per_mwh'] * dt
    )
    metrics['cost_dg_eur'] = _safe_sum(merged['p_dg_mw'] * (fuel_price / eta_dg) * dt)
    metrics['net_cost_eur'] = (
        metrics['cost_import_eur'] - metrics['income_export_eur'] + metrics['cost_dg_eur']
    )

    return pd.DataFrame(metrics, index=[0])


def save_report(report: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_path, index=False)


def save_plots(df: pd.DataFrame, schedule: pd.DataFrame, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    merged = df.join(schedule, how='inner')

    plt.figure(figsize=(12, 6))
    plt.plot(merged.index, merged['load_actual_mw'], label='load')
    plt.plot(merged.index, merged['pv_actual_mw'], label='pv')
    plt.plot(merged.index, merged['wind_actual_mw'], label='wind')
    plt.legend()
    plt.title('Load and renewables')
    plt.xlabel('hour')
    plt.ylabel('MW')
    plt.tight_layout()
    plt.savefig(out_dir / 'load_renewables.png', dpi=150)
    plt.close()

    plt.figure(figsize=(12, 6))
    plt.plot(merged.index, merged['p_import_mw'], label='import')
    plt.plot(merged.index, merged['p_export_mw'], label='export')
    plt.plot(merged.index, merged['p_dg_mw'], label='dg')
    plt.legend()
    plt.title('Grid and DG')
    plt.xlabel('hour')
    plt.ylabel('MW')
    plt.tight_layout()
    plt.savefig(out_dir / 'grid_dg.png', dpi=150)
    plt.close()

    plt.figure(figsize=(12, 6))
    plt.plot(merged.index, merged['p_ely_mw'], label='ely')
    plt.plot(merged.index, merged['p_fc_mw'], label='fc')
    plt.plot(merged.index, merged['soc_mwh'], label='soc')
    plt.legend()
    plt.title('Hydrogen system')
    plt.xlabel('hour')
    plt.ylabel('MW / MWh')
    plt.tight_layout()
    plt.savefig(out_dir / 'hydrogen.png', dpi=150)
    plt.close()

    plt.figure(figsize=(12, 6))
    plt.plot(merged.index, merged['import_price_eur_per_mwh'], label='import price')
    plt.plot(merged.index, merged['pun_eur_per_mwh'], label='export price')
    plt.legend()
    plt.title('Prices')
    plt.xlabel('hour')
    plt.ylabel('EUR/MWh')
    plt.tight_layout()
    plt.savefig(out_dir / 'prices.png', dpi=150)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Build report and plots from MPC output.')
    parser.add_argument('--config', default='configs/system.yaml')
    parser.add_argument('--schedule', default='outputs/mpc_receding.csv')
    parser.add_argument('--out', default='outputs/report.csv')
    parser.add_argument('--fuel-cost', type=float, default=None, help='Fuel cost EUR/kWh')
    parser.add_argument('--load-nom', type=float, default=None, help='Load nominal MW for scaling')
    parser.add_argument('--plots', action='store_true', help='Generate plots in outputs/plots')
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding='ascii'))
    if args.load_nom is not None:
        cfg['system']['load_nom_mw'] = args.load_nom
    bundle = load_timeseries(Path('data'), cfg)
    df = add_net_load(bundle.data)

    schedule = pd.read_csv(args.schedule)
    if 'hour' in schedule.columns:
        schedule = schedule.set_index('hour')

    report = build_report(df, schedule, cfg, fuel_eur_per_kwh=args.fuel_cost)
    save_report(report, Path(args.out))
    print(f'wrote {args.out}')

    if args.plots:
        save_plots(df, schedule, Path('outputs/plots'))
        print('wrote outputs/plots/*.png')


if __name__ == '__main__':
    main()
