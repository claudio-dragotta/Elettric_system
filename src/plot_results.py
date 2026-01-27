"""Generate detailed plots for MPC results - similar to reference project."""

from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yaml

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loader import load_timeseries, add_net_load


def plot_mpc_results(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    title: str = "",
    save_path: str | None = None,
    hours: int | None = None,
    start_hour: int = 0,
):
    """
    Plot MPC results with 4 subplots:
    1. Load and Renewables (PV, Wind, Total RES)
    2. Power flows (Import, Export, DG)
    3. Hydrogen system (Electrolyzer, Fuel Cell, charge/discharge style)
    4. H2 Storage State of Charge
    """
    # Merge data
    merged = df.join(schedule, how='inner')

    # Slice if hours specified
    if hours is not None:
        end_hour = min(start_hour + hours, len(merged))
        merged = merged.iloc[start_hour:end_hour]

    # Create timestamp for x-axis
    start_date = datetime(2022, 1, 1)
    timesteps = merged.index.values
    timestamps = [start_date + timedelta(hours=int(h)) for h in timesteps]

    fig, axes = plt.subplots(4, 1, figsize=(15, 14), sharex=True)

    # === SUBPLOT 1: Load and Renewables ===
    ax1 = axes[0]
    ax1.plot(timesteps, merged['load_forecast_mw'], label='Load', color='red', linewidth=1.5)
    ax1.plot(timesteps, merged['pv_forecast_mw'], label='PV', color='orange', linewidth=1)
    ax1.plot(timesteps, merged['wind_forecast_mw'], label='Wind', color='green', linewidth=1)
    ax1.fill_between(timesteps, 0, merged['pv_forecast_mw'] + merged['wind_forecast_mw'],
                     alpha=0.3, color='green', label='Total RES')
    ax1.set_ylabel('Power [MW]')
    ax1.set_title(title if title else 'MPC Results')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(bottom=0)

    # === SUBPLOT 2: Grid and DG Power Flows ===
    ax2 = axes[1]
    ax2.plot(timesteps, merged['p_import_mw'], label='Import (+)', color='blue', linewidth=1.5)
    ax2.plot(timesteps, -merged['p_export_mw'], label='Export (-)', color='cyan', linewidth=1.5)
    ax2.plot(timesteps, merged['p_dg_mw'], label='Diesel Gen', color='brown', linewidth=1.5)
    ax2.axhline(y=0, color='black', linewidth=0.5)
    ax2.fill_between(timesteps, 0, merged['p_import_mw'], alpha=0.3, color='blue')
    ax2.fill_between(timesteps, 0, -merged['p_export_mw'], alpha=0.3, color='cyan')
    ax2.set_ylabel('Power [MW]')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    # === SUBPLOT 3: Hydrogen System (like battery charge/discharge) ===
    ax3 = axes[2]
    # ELY consumes power (like charging) -> show as negative
    # FC produces power (like discharging) -> show as positive
    ax3.plot(timesteps, merged['p_fc_mw'], label='Fuel Cell (+) [produces]', color='purple', linewidth=1.5)
    ax3.plot(timesteps, -merged['p_ely_mw'], label='Electrolyzer (-) [consumes]', color='magenta', linewidth=1.5)
    ax3.axhline(y=0, color='black', linewidth=0.5)
    ax3.fill_between(timesteps, 0, merged['p_fc_mw'], alpha=0.3, color='purple')
    ax3.fill_between(timesteps, 0, -merged['p_ely_mw'], alpha=0.3, color='magenta')
    ax3.set_ylabel('Power [MW]')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    # === SUBPLOT 4: H2 Storage State of Charge ===
    ax4 = axes[3]
    h2_capacity = 12.0  # MWh from config
    soc_percent = (merged['soc_mwh'] / h2_capacity) * 100
    ax4.plot(timesteps, soc_percent, label='H2 SoC', color='teal', linewidth=1.5)
    ax4.fill_between(timesteps, 0, soc_percent, alpha=0.3, color='teal')
    ax4.axhline(y=0, color='gray', linestyle='--', linewidth=0.5, label='Min (0%)')
    ax4.axhline(y=100, color='gray', linestyle='--', linewidth=0.5, label='Max (100%)')
    ax4.set_ylabel('H2 SoC [%]')
    ax4.set_xlabel('Hour')
    ax4.set_ylim(-5, 105)
    ax4.legend(loc='upper right')
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Saved: {save_path}')

    plt.show()
    return fig


def plot_energy_balance(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    title: str = "",
    save_path: str | None = None,
    hours: int | None = None,
    start_hour: int = 0,
):
    """
    Plot energy balance: Total IN vs Total OUT
    """
    merged = df.join(schedule, how='inner')

    if hours is not None:
        end_hour = min(start_hour + hours, len(merged))
        merged = merged.iloc[start_hour:end_hour]

    timesteps = merged.index.values

    # Calculate totals
    total_in = (merged['pv_forecast_mw'] + merged['wind_forecast_mw'] +
                merged['p_import_mw'] + merged['p_dg_mw'] + merged['p_fc_mw'])
    total_out = (merged['load_forecast_mw'] + merged['p_export_mw'] +
                 merged['p_ely_mw'] + merged['p_curt_mw'])

    fig, ax = plt.subplots(figsize=(15, 6))

    ax.plot(timesteps, total_in, label='Total IN (PV+Wind+Import+DG+FC)', color='green', linewidth=1.5)
    ax.plot(timesteps, total_out, label='Total OUT (Load+Export+ELY+Curt)', color='red', linewidth=1.5, linestyle='--')
    ax.fill_between(timesteps, total_in, total_out, alpha=0.3, color='yellow')

    ax.set_ylabel('Power [MW]')
    ax.set_xlabel('Hour')
    ax.set_title(title if title else 'Energy Balance: IN = OUT')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Saved: {save_path}')

    plt.show()
    return fig


def plot_prices(
    df: pd.DataFrame,
    title: str = "",
    save_path: str | None = None,
    hours: int | None = None,
    start_hour: int = 0,
):
    """
    Plot import and export prices
    """
    if hours is not None:
        end_hour = min(start_hour + hours, len(df))
        df = df.iloc[start_hour:end_hour]

    timesteps = df.index.values

    fig, ax = plt.subplots(figsize=(15, 5))

    ax.plot(timesteps, df['import_price_eur_per_mwh'], label='Import Price (ARERA)', color='red', linewidth=1)
    ax.plot(timesteps, df['pun_eur_per_mwh'], label='Export Price (PUN)', color='blue', linewidth=1)
    ax.axhline(y=750, color='brown', linestyle='--', linewidth=1, label='DG Cost (cf=0.45)')
    ax.axhline(y=1000, color='orange', linestyle='--', linewidth=1, label='DG Cost (cf=0.60)')

    ax.set_ylabel('Price [EUR/MWh]')
    ax.set_xlabel('Hour')
    ax.set_title(title if title else 'Energy Prices')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Saved: {save_path}')

    plt.show()
    return fig


def plot_comparison(
    df: pd.DataFrame,
    schedule_45: pd.DataFrame,
    schedule_60: pd.DataFrame,
    title: str = "",
    save_path: str | None = None,
    hours: int | None = None,
    start_hour: int = 0,
):
    """
    Compare cf=0.45 vs cf=0.60 scenarios
    """
    merged_45 = df.join(schedule_45, how='inner', rsuffix='_45')
    merged_60 = df.join(schedule_60, how='inner', rsuffix='_60')

    if hours is not None:
        end_hour = min(start_hour + hours, len(merged_45))
        merged_45 = merged_45.iloc[start_hour:end_hour]
        merged_60 = merged_60.iloc[start_hour:end_hour]

    timesteps = merged_45.index.values

    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True)

    # DG comparison
    ax1 = axes[0]
    ax1.plot(timesteps, merged_45['p_dg_mw'], label='DG (cf=0.45)', color='brown', linewidth=1.5)
    ax1.plot(timesteps, merged_60['p_dg_mw'], label='DG (cf=0.60)', color='orange', linewidth=1.5, linestyle='--')
    ax1.set_ylabel('DG Power [MW]')
    ax1.set_title(title if title else 'Comparison: cf=0.45 vs cf=0.60')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Import/Export comparison
    ax2 = axes[1]
    ax2.plot(timesteps, merged_45['p_import_mw'], label='Import (cf=0.45)', color='blue', linewidth=1)
    ax2.plot(timesteps, merged_60['p_import_mw'], label='Import (cf=0.60)', color='lightblue', linewidth=1, linestyle='--')
    ax2.plot(timesteps, -merged_45['p_export_mw'], label='Export (cf=0.45)', color='green', linewidth=1)
    ax2.plot(timesteps, -merged_60['p_export_mw'], label='Export (cf=0.60)', color='lightgreen', linewidth=1, linestyle='--')
    ax2.axhline(y=0, color='black', linewidth=0.5)
    ax2.set_ylabel('Power [MW]')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    # H2 SoC comparison
    ax3 = axes[2]
    h2_cap = 12.0
    ax3.plot(timesteps, (merged_45['soc_mwh'] / h2_cap) * 100, label='H2 SoC (cf=0.45)', color='teal', linewidth=1.5)
    ax3.plot(timesteps, (merged_60['soc_mwh'] / h2_cap) * 100, label='H2 SoC (cf=0.60)', color='cyan', linewidth=1.5, linestyle='--')
    ax3.set_ylabel('H2 SoC [%]')
    ax3.set_xlabel('Hour')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Saved: {save_path}')

    plt.show()
    return fig


def plot_weekly_window(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    week_start_hour: int,
    fuel_cost: float,
    save_dir: Path,
):
    """
    Plot a specific week (168 hours) like the reference project does for 72h windows.
    """
    hours = 168  # 1 week

    # Determine period name
    start_date = datetime(2022, 1, 1) + timedelta(hours=week_start_hour)
    period_name = start_date.strftime('%B_%d')

    title = f'MPC Results - Week starting {start_date.strftime("%B %d, %Y")} (cf={fuel_cost})'
    save_path = save_dir / f'plot_{period_name}_cf{str(fuel_cost).replace(".", "")}.png'

    plot_mpc_results(df, schedule, title=title, save_path=str(save_path),
                     hours=hours, start_hour=week_start_hour)


def main():
    parser = argparse.ArgumentParser(description='Plot MPC results.')
    parser.add_argument('--config', default='configs/system.yaml')
    parser.add_argument('--schedule-45', default='outputs/mpc_receding_cf045.csv')
    parser.add_argument('--schedule-60', default='outputs/mpc_receding_cf060.csv')
    parser.add_argument('--hours', type=int, default=168, help='Hours to plot (default: 168 = 1 week)')
    parser.add_argument('--start', type=int, default=0, help='Start hour')
    parser.add_argument('--out-dir', default='outputs/plots')
    parser.add_argument('--all-periods', action='store_true', help='Generate plots for Jan, Jul, Oct')
    args = parser.parse_args()

    # Load data
    cfg = yaml.safe_load(Path(args.config).read_text())
    bundle = load_timeseries(Path('data'), cfg)
    df = add_net_load(bundle.data)

    # Load schedules
    s45 = pd.read_csv(args.schedule_45).set_index('hour')
    s60 = pd.read_csv(args.schedule_60).set_index('hour')

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all_periods:
        # Generate plots for January, July, October (like reference project)
        # January: hour 0
        # July: hour 4344 (after Jan-Jun)
        # October: hour 6552 (but we only have 6528 hours, so use hour 5500)

        periods = [
            (0, 'January'),
            (4344, 'July'),
            (5500, 'October'),
        ]

        for start_h, period_name in periods:
            if start_h + args.hours <= len(df):
                print(f'\n=== Plotting {period_name} (cf=0.45) ===')
                plot_mpc_results(
                    df, s45,
                    title=f'MPC - {period_name} ({args.hours}h) - cf=0.45',
                    save_path=str(out_dir / f'plot_{period_name.lower()}_cf045.png'),
                    hours=args.hours,
                    start_hour=start_h
                )

                print(f'\n=== Plotting {period_name} (cf=0.60) ===')
                plot_mpc_results(
                    df, s60,
                    title=f'MPC - {period_name} ({args.hours}h) - cf=0.60',
                    save_path=str(out_dir / f'plot_{period_name.lower()}_cf060.png'),
                    hours=args.hours,
                    start_hour=start_h
                )
    else:
        # Single plot
        print('\n=== MPC Results (cf=0.45) ===')
        plot_mpc_results(
            df, s45,
            title=f'MPC Results ({args.hours}h) - cf=0.45',
            save_path=str(out_dir / 'mpc_results_cf045.png'),
            hours=args.hours,
            start_hour=args.start
        )

        print('\n=== MPC Results (cf=0.60) ===')
        plot_mpc_results(
            df, s60,
            title=f'MPC Results ({args.hours}h) - cf=0.60',
            save_path=str(out_dir / 'mpc_results_cf060.png'),
            hours=args.hours,
            start_hour=args.start
        )

        print('\n=== Comparison cf=0.45 vs cf=0.60 ===')
        plot_comparison(
            df, s45, s60,
            title=f'Comparison cf=0.45 vs cf=0.60 ({args.hours}h)',
            save_path=str(out_dir / 'comparison_cf045_vs_cf060.png'),
            hours=args.hours,
            start_hour=args.start
        )

        print('\n=== Energy Prices ===')
        plot_prices(
            df,
            title=f'Energy Prices ({args.hours}h)',
            save_path=str(out_dir / 'prices.png'),
            hours=args.hours,
            start_hour=args.start
        )


if __name__ == '__main__':
    main()
