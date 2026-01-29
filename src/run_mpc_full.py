"""
Esecuzione dell'MPC a orizzonte mobile (receding horizon) sull'intero dataset.

Questo script e' il punto di ingresso principale per eseguire l'ottimizzazione MPC
su tutto il periodo disponibile nei dati. Implementa la strategia "receding horizon":
- Ad ogni ora, risolve un problema di ottimizzazione per le prossime N ore (orizzonte)
- Applica solo la prima decisione ottimale
- Avanza di un'ora e ripete

Output: file CSV con lo scheduling ottimale ora per ora.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm  # Barra di avanzamento per cicli lunghi
import yaml

# Aggiunge la cartella corrente al path per gli import locali
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loader import load_timeseries, add_net_load
from model import solve_horizon


def run_receding(
    df: pd.DataFrame,                       # DataFrame con dati di input (previsioni, prezzi)
    cfg: dict,                              # Configurazione del sistema
    start: int,                             # Ora di inizio della simulazione
    horizon: int,                           # Lunghezza dell'orizzonte di ottimizzazione [ore]
    fuel_eur_per_kwh: float | None = None,  # Costo del combustibile [EUR/kWh]
) -> pd.DataFrame:
    """
    Esegue l'MPC a orizzonte mobile su tutto il dataset.

    Strategia receding horizon:
    1. Per ogni ora t, risolve l'ottimizzazione per [t, t+horizon]
    2. Estrae solo la decisione per l'ora t (prima ora dell'orizzonte)
    3. Aggiorna lo stato di carica (SOC) per l'ora successiva
    4. Avanza a t+1 e ripete

    Args:
        df: DataFrame con le colonne di input necessarie per l'ottimizzazione
        cfg: Dizionario di configurazione del sistema
        start: Indice dell'ora da cui iniziare la simulazione
        horizon: Numero di ore dell'orizzonte di ottimizzazione
        fuel_eur_per_kwh: Costo del combustibile diesel (opzionale)

    Returns:
        DataFrame con lo scheduling ottimale per ogni ora, contenente:
        - p_import_mw: potenza importata dalla rete [MW]
        - p_export_mw: potenza esportata alla rete [MW]
        - p_ely_mw: potenza assorbita dall'elettrolizzatore [MW]
        - p_fc_mw: potenza prodotta dalla fuel cell [MW]
        - p_dg_mw: potenza prodotta dal generatore diesel [MW]
        - p_curt_mw: potenza curtailed [MW]
        - soc_mwh: stato di carica dello storage idrogeno [MWh]
        - objective_eur: valore della funzione obiettivo [EUR]
    """
    results = []  # Lista per accumulare i risultati di ogni ora
    soc = 0.0  # Stato di carica iniziale dello storage [MWh]
    last_hour = df.index.max()  # Ultima ora disponibile nei dati

    # Ciclo principale: itera su tutte le ore valide
    # Si ferma quando l'orizzonte non puo' piu' essere completato
    for hour in tqdm(range(start, int(last_hour) - horizon + 1), desc='MPC'):
        # Risolve l'ottimizzazione per l'orizzonte [hour, hour+horizon]
        res = solve_horizon(df, cfg, hour, horizon, soc, fuel_eur_per_kwh=fuel_eur_per_kwh)

        # Estrae la prima riga dello schedule (decisione per l'ora corrente)
        first = res.schedule.iloc[0]

        # Aggiorna lo stato di carica per l'iterazione successiva
        soc = float(first['soc_mwh'])

        # Salva i risultati per questa ora
        results.append(
            {
                'hour': hour,                                    # Indice orario
                'p_import_mw': float(first['p_import_mw']),      # Potenza importata [MW]
                'p_export_mw': float(first['p_export_mw']),      # Potenza esportata [MW]
                'p_ely_mw': float(first['p_ely_mw']),            # Potenza elettrolizzatore [MW]
                'p_fc_mw': float(first['p_fc_mw']),              # Potenza fuel cell [MW]
                'p_dg_mw': float(first['p_dg_mw']),              # Potenza diesel [MW]
                'p_curt_mw': float(first['p_curt_mw']),          # Potenza curtailed [MW]
                'soc_mwh': soc,                                  # Stato di carica [MWh]
                'objective_eur': float(res.objective_value),    # Costo totale orizzonte [EUR]
            }
        )

    # Costruisce il DataFrame finale con indice = ora
    return pd.DataFrame(results).set_index('hour')


def main() -> None:
    """
    Funzione principale: parsing argomenti e esecuzione MPC.

    Argomenti da linea di comando:
    --config: percorso file di configurazione YAML (default: configs/system.yaml)
    --start: ora di inizio simulazione (default: 0)
    --horizon: lunghezza orizzonte [ore] (default: da config)
    --fuel-values: lista di costi combustibile da testare, separati da virgola
    --out: percorso file di output CSV (default: outputs/mpc_2022.csv)
    """
    # Definizione degli argomenti da linea di comando
    parser = argparse.ArgumentParser(description='Run receding-horizon MPC over dataset.')
    parser.add_argument('--config', default='configs/system.yaml')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--horizon', type=int, default=None)
    parser.add_argument(
        '--fuel-values',
        default='',
        help='Comma-separated fuel cost values in EUR/kWh (e.g., 0.45,0.60)',
    )
    parser.add_argument('--out', default='outputs/mpc_2022.csv')
    args = parser.parse_args()

    # Caricamento configurazione da file YAML
    cfg = yaml.safe_load(Path(args.config).read_text(encoding='ascii'))

    # Estrazione parametri dalla configurazione
    horizon = args.horizon or int(cfg['project']['horizon_h'])  # Orizzonte di ottimizzazione
    load_nom = float(cfg['system']['load_nom_mw'])  # Carico nominale per stampa info

    # Preparazione lista dei costi combustibile da testare
    fuel_values = []
    if args.fuel_values.strip():
        # Se specificati da linea di comando, usa quelli
        fuel_values = [float(v) for v in args.fuel_values.split(',') if v.strip()]
    else:
        # Altrimenti usa i valori dal file di configurazione
        fuel_values = [float(cfg['prices']['fuel_eur_per_kwh'])]  # Valore principale
        alt_fuel = cfg['prices'].get('fuel_alt_eur_per_kwh')      # Valore alternativo (opzionale)
        if alt_fuel is not None:
            fuel_values.append(float(alt_fuel))

    # Caricamento delle serie temporali dai file .mat
    bundle = load_timeseries(Path('data'), cfg)
    df = add_net_load(bundle.data)  # Aggiunge colonna net_load (carico - RES)

    # Esegue MPC per ogni valore di costo combustibile
    for fuel_cost in fuel_values:
        # Esecuzione dell'MPC receding horizon
        schedule = run_receding(df, cfg, args.start, horizon, fuel_eur_per_kwh=fuel_cost)

        # Costruzione del percorso di output
        out_path = Path(args.out)
        if len(fuel_values) > 1:
            # Se ci sono piu' scenari, aggiunge il costo al nome file
            # Es: mpc_2022_cf045.csv, mpc_2022_cf060.csv
            fuel_str = f'{fuel_cost:.2f}'.replace('.', '')  # 0.45 -> "045"
            out_path = out_path.with_name(f'{out_path.stem}_cf{fuel_str}{out_path.suffix}')

        # Salvataggio risultati su CSV
        out_path.parent.mkdir(parents=True, exist_ok=True)
        schedule.to_csv(out_path)

        print(f'wrote {out_path} rows={len(schedule)} (load={load_nom}MW, cf={fuel_cost})')


if __name__ == '__main__':
    main()
