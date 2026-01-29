"""
Generazione di report e metriche aggregate dai risultati dell'ottimizzazione MPC.

Questo modulo calcola KPI (Key Performance Indicators) energetici ed economici
a partire dallo scheduling ottimale e dai dati di input, e genera grafici
riassuntivi per l'analisi dei risultati.

Metriche calcolate:
- Energie totali per ogni componente [MWh]
- Costi e ricavi [EUR]
- Indicatori del sistema idrogeno (cicli equivalenti, efficienza)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from loader import load_timeseries, add_net_load


def _safe_sum(series: pd.Series) -> float:
    """
    Calcola la somma di una serie gestendo i valori NaN.

    Sostituisce i NaN con 0 prima di sommare, evitando errori
    quando alcuni dati sono mancanti.

    Args:
        series: Serie pandas da sommare

    Returns:
        Somma dei valori (NaN trattati come 0)
    """
    return float(series.fillna(0.0).sum())


def build_report(
    df: pd.DataFrame,                       # DataFrame con dati di input (prezzi, previsioni)
    schedule: pd.DataFrame,                 # DataFrame con scheduling ottimale
    cfg: dict,                              # Configurazione del sistema
    fuel_eur_per_kwh: float | None = None,  # Costo combustibile [EUR/kWh]
) -> pd.DataFrame:
    """
    Calcola le metriche aggregate dallo scheduling MPC.

    Unisce i dati di input con lo scheduling e calcola:
    1. Energie totali per ogni flusso [MWh]
    2. Costi e ricavi economici [EUR]
    3. Metriche del sistema idrogeno

    Args:
        df: DataFrame con le serie temporali di input
        schedule: DataFrame con le decisioni dell'ottimizzatore
        cfg: Dizionario di configurazione
        fuel_eur_per_kwh: Costo del combustibile (opzionale, default da config)

    Returns:
        DataFrame con una riga contenente tutte le metriche calcolate
    """
    # Estrazione parametri dalla configurazione
    dt = float(cfg['project']['timestep_h'])  # Passo temporale [ore]

    if fuel_eur_per_kwh is None:
        fuel_eur_per_kwh = float(cfg['prices']['fuel_eur_per_kwh'])
    fuel_price = fuel_eur_per_kwh * 1000.0  # Conversione EUR/kWh -> EUR/MWh
    eta_dg = float(cfg['system'].get('eta_dg', 0.6))  # Efficienza diesel

    # Unione dati di input e scheduling (inner join sulle ore comuni)
    merged = df.join(schedule, how='inner')

    # ==================== METRICHE ENERGETICHE [MWh] ====================

    metrics = {
        'hours': len(merged),  # Numero di ore simulate

        # Energie in ingresso
        'energy_load_mwh': _safe_sum(merged['load_forecast_mw'] * dt),   # Energia carico
        'energy_pv_mwh': _safe_sum(merged['pv_forecast_mw'] * dt),       # Energia PV
        'energy_wind_mwh': _safe_sum(merged['wind_forecast_mw'] * dt),   # Energia eolica

        # Energie scambiate con la rete
        'energy_import_mwh': _safe_sum(merged['p_import_mw'] * dt),      # Energia importata
        'energy_export_mwh': _safe_sum(merged['p_export_mw'] * dt),      # Energia esportata

        # Energie diesel e idrogeno
        'energy_dg_mwh': _safe_sum(merged['p_dg_mw'] * dt),              # Energia diesel
        'energy_ely_mwh': _safe_sum(merged['p_ely_mw'] * dt),            # Energia elettrolizzatore
        'energy_fc_mwh': _safe_sum(merged['p_fc_mw'] * dt),              # Energia fuel cell

        # Energia sprecata
        'energy_curt_mwh': _safe_sum(merged['p_curt_mw'] * dt),          # Energia curtailed
    }

    # ==================== METRICHE ECONOMICHE [EUR] ====================

    # Costo dell'energia importata dalla rete
    # cost = sum(p_import * prezzo_import * dt)
    metrics['cost_import_eur'] = _safe_sum(
        merged['p_import_mw'] * merged['import_price_eur_per_mwh'] * dt
    )

    # Ricavo dalla vendita di energia alla rete (al prezzo PUN)
    # income = sum(p_export * PUN * dt)
    metrics['income_export_eur'] = _safe_sum(
        merged['p_export_mw'] * merged['pun_eur_per_mwh'] * dt
    )

    # Costo del combustibile diesel
    # Il costo e' (fuel_price / eta_dg) perche' per produrre 1 MWh elettrico
    # servono (1/eta_dg) MWh di combustibile
    metrics['cost_dg_eur'] = _safe_sum(merged['p_dg_mw'] * (fuel_price / eta_dg) * dt)

    # Costo netto totale = import - export + diesel
    metrics['net_cost_eur'] = (
        metrics['cost_import_eur'] - metrics['income_export_eur'] + metrics['cost_dg_eur']
    )

    # ==================== METRICHE SISTEMA IDROGENO ====================

    h2_capacity = float(cfg['system'].get('h2_storage_mwh', 12.0))  # Capacita' storage [MWh]

    # Throughput totale = energia processata da ELY + FC
    throughput = metrics['energy_ely_mwh'] + metrics['energy_fc_mwh']

    # Cicli equivalenti = throughput / (2 * capacita')
    # Un ciclo completo = carica (ELY) + scarica (FC) = 2 * capacita'
    metrics['h2_equivalent_cycles'] = throughput / (2 * h2_capacity) if h2_capacity > 0 else 0

    # Efficienza roundtrip = energia_out / energia_in * 100
    # Quanto dell'energia in ingresso (ELY) si recupera in uscita (FC)
    metrics['h2_roundtrip_efficiency'] = (
        metrics['energy_fc_mwh'] / metrics['energy_ely_mwh'] * 100
        if metrics['energy_ely_mwh'] > 0 else 0
    )

    return pd.DataFrame(metrics, index=[0])


def save_report(report: pd.DataFrame, out_path: Path) -> None:
    """
    Salva il report delle metriche su file CSV.

    Args:
        report: DataFrame con le metriche calcolate
        out_path: Percorso del file di output
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_path, index=False)


def save_plots(df: pd.DataFrame, schedule: pd.DataFrame, out_dir: Path) -> None:
    """
    Genera e salva grafici riassuntivi dei risultati.

    Grafici generati:
    1. load_renewables.png: Carico e produzione RES nel tempo
    2. grid_dg.png: Flussi con la rete e produzione diesel
    3. hydrogen.png: Sistema idrogeno (ELY, FC, SOC)
    4. prices.png: Prezzi di import e export

    Args:
        df: DataFrame con i dati di input
        schedule: DataFrame con lo scheduling ottimale
        out_dir: Cartella di output per i grafici
    """
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    merged = df.join(schedule, how='inner')

    # ==================== GRAFICO 1: CARICO E RINNOVABILI ====================

    plt.figure(figsize=(12, 6))
    plt.plot(merged.index, merged['load_forecast_mw'], label='load')
    plt.plot(merged.index, merged['pv_forecast_mw'], label='pv')
    plt.plot(merged.index, merged['wind_forecast_mw'], label='wind')
    plt.legend()
    plt.title('Load and renewables')
    plt.xlabel('hour')
    plt.ylabel('MW')
    plt.tight_layout()
    plt.savefig(out_dir / 'load_renewables.png', dpi=150)
    plt.close()

    # ==================== GRAFICO 2: RETE E DIESEL ====================

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

    # ==================== GRAFICO 3: SISTEMA IDROGENO ====================

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

    # ==================== GRAFICO 4: PREZZI ====================

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
    """
    Funzione principale: genera report e grafici dai risultati MPC.

    Argomenti da linea di comando:
    --config: percorso file di configurazione YAML
    --schedule: percorso file CSV con scheduling MPC
    --out: percorso file di output per il report
    --fuel-cost: costo combustibile [EUR/kWh] (opzionale)
    --load-nom: potenza nominale carico [MW] per scalatura (opzionale)
    --plots: flag per generare i grafici
    """
    parser = argparse.ArgumentParser(description='Build report and plots from MPC output.')
    parser.add_argument('--config', default='configs/system.yaml')
    parser.add_argument('--schedule', default='outputs/mpc_2022_cf045.csv')
    parser.add_argument('--out', default='outputs/report_2022_cf045.csv')
    parser.add_argument('--fuel-cost', type=float, default=None, help='Fuel cost EUR/kWh')
    parser.add_argument('--load-nom', type=float, default=None, help='Load nominal MW for scaling')
    parser.add_argument('--plots', action='store_true', help='Generate plots in outputs/plots')
    args = parser.parse_args()

    # Caricamento configurazione
    cfg = yaml.safe_load(Path(args.config).read_text(encoding='ascii'))

    # Override del carico nominale se specificato
    if args.load_nom is not None:
        cfg['system']['load_nom_mw'] = args.load_nom

    # Caricamento dati di input
    bundle = load_timeseries(Path('data'), cfg)
    df = add_net_load(bundle.data)

    # Caricamento scheduling MPC
    schedule = pd.read_csv(args.schedule)
    if 'hour' in schedule.columns:
        schedule = schedule.set_index('hour')

    # Generazione report
    report = build_report(df, schedule, cfg, fuel_eur_per_kwh=args.fuel_cost)
    save_report(report, Path(args.out))
    print(f'wrote {args.out}')

    # Generazione grafici (opzionale)
    if args.plots:
        save_plots(df, schedule, Path('outputs/plots'))
        print('wrote outputs/plots/*.png')


if __name__ == '__main__':
    main()
