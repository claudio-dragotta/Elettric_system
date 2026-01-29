"""
Caricamento e preparazione dei dati di input per l'ottimizzazione MPC.

Questo modulo si occupa di:
1. Caricare i file .mat contenenti le serie temporali (PV, eolico, carico, prezzi)
2. Applicare le conversioni di unita' (p.u. -> MW, kW -> MW, EUR/kWh -> EUR/MWh)
3. Allineare le serie temporali su un indice orario comune
4. Costruire la serie dei prezzi di import secondo le fasce orarie ARERA

I dati di input provengono da:
- res_1_year_pu.mat: produzione PV e eolica in per-unit (forecast e actual)
- buildings_load.mat: profilo di carico degli edifici [kW]
- PUN_2022.mat: Prezzo Unico Nazionale orario [EUR/MWh]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from scipy.io import loadmat  # Per caricare file MATLAB .mat

from tariff import build_hourly_index, tariff_f1_f2_f3


@dataclass
class SeriesBundle:
    """
    Contenitore per le serie temporali caricate e i metadati associati.

    Attributi:
        data: DataFrame con tutte le serie temporali (indice = ora)
              Colonne: pv_forecast_mw, pv_actual_mw, wind_forecast_mw, wind_actual_mw,
                       load_forecast_mw, load_actual_mw, pun_eur_per_mwh, import_price_eur_per_mwh
        meta: Dizionario con metadati (potenze nominali, fattori di scala)
    """
    data: pd.DataFrame
    meta: Dict[str, float]


def _load_mat(path: Path) -> Dict[str, np.ndarray]:
    """
    Carica un file MATLAB .mat e restituisce le variabili come dizionario.

    Args:
        path: Percorso del file .mat

    Returns:
        Dizionario {nome_variabile: array} escludendo le variabili di sistema (__*)
    """
    data = loadmat(path, squeeze_me=True, struct_as_record=False)
    # Filtra le variabili di sistema MATLAB (iniziano con '__')
    return {k: v for k, v in data.items() if not k.startswith('__')}


def _normalize_hours(hours: np.ndarray) -> np.ndarray:
    """
    Normalizza l'array delle ore per garantire un indice 0-based sequenziale.

    Gestisce due casi comuni nei dati:
    1. Ore 1-based (1,2,3...): converte a 0-based (0,1,2...)
    2. Solo ora del giorno (0-23): ricostruisce indice sequenziale

    Args:
        hours: Array degli indici orari grezzi

    Returns:
        Array normalizzato con indici orari sequenziali 0-based
    """
    hours = np.asarray(hours).astype(int)

    # Caso 1: indici 1-based -> converte a 0-based
    if hours.min() == 1:
        hours = hours - 1

    # Caso 2: solo ora del giorno (0-23) ripetuta -> ricostruisce sequenza
    if hours.max() <= 23 and len(hours) > 24:
        hours = np.arange(len(hours), dtype=int)

    return hours


def _build_import_price_series(cfg: dict, hours: np.ndarray) -> np.ndarray:
    """
    Costruisce la serie dei prezzi di acquisto dalla rete.

    Due modalita':
    1. use_import_tariff_schedule=True: usa le fasce orarie ARERA (F1/F2/F3)
    2. use_import_tariff_schedule=False: usa la media delle tre fasce

    Args:
        cfg: Configurazione con i prezzi per fascia [EUR/kWh]
        hours: Array degli indici orari

    Returns:
        Array dei prezzi di import [EUR/MWh]
    """
    # Prezzi delle tre fasce orarie [EUR/kWh]
    f1 = cfg['prices']['import_f1_eur_per_kwh']  # Fascia F1 (punta)
    f2 = cfg['prices']['import_f2_eur_per_kwh']  # Fascia F2 (intermedia)
    f3 = cfg['prices']['import_f3_eur_per_kwh']  # Fascia F3 (fuori punta)

    use_schedule = cfg['prices'].get('use_import_tariff_schedule', False)

    if use_schedule:
        # Usa il calendario ARERA con festivita' italiane
        year = int(cfg['project'].get('year', 2022))
        timestamps = build_hourly_index(year, hours)  # Converte ore in datetime
        prices = tariff_f1_f2_f3(timestamps, f1, f2, f3)  # Assegna fascia a ogni ora
    else:
        # Usa semplicemente la media delle tre fasce
        avg = (f1 + f2 + f3) / 3.0
        prices = np.full(len(hours), avg, dtype=float)

    # Conversione EUR/kWh -> EUR/MWh (moltiplica per 1000)
    return prices * 1000.0


def load_timeseries(data_dir: Path, cfg: dict) -> SeriesBundle:
    """
    Carica e prepara tutte le serie temporali necessarie per l'ottimizzazione.

    Passi:
    1. Carica i file .mat (PV, eolico, carico, PUN)
    2. Scala le produzioni RES con le potenze nominali [MW]
    3. Scala il carico secondo la modalita' configurata
    4. Allinea tutte le serie su un indice orario comune
    5. Costruisce la serie dei prezzi di import

    Args:
        data_dir: Cartella contenente i file .mat
        cfg: Dizionario di configurazione

    Returns:
        SeriesBundle con DataFrame delle serie e metadati
    """
    # ==================== CARICAMENTO FILE .MAT ====================

    res = _load_mat(data_dir / 'res_1_year_pu.mat')   # RES (PV + eolico) in per-unit
    load = _load_mat(data_dir / 'buildings_load.mat')  # Carico edifici [kW]
    pun = _load_mat(data_dir / 'PUN_2022.mat')         # Prezzo Unico Nazionale [EUR/MWh]

    # Estrazione arrays dai file caricati
    p_pv = np.asarray(res['P_pv'], dtype=float)    # [n_ore, 2] = [forecast, actual] in p.u.
    p_w = np.asarray(res['P_w'], dtype=float)      # [n_ore, 2] = [forecast, actual] in p.u.
    pul = np.asarray(load['Pul'], dtype=float)     # [n_ore, 3] = [ora, forecast, actual] in kW
    price = np.asarray(pun['pun'], dtype=float).reshape(-1)  # [n_ore] in EUR/MWh

    # ==================== PARAMETRI DI SCALA ====================

    # Potenze nominali degli impianti [MW]
    pv_nom = float(cfg['system']['pv_nom_mw'])      # Potenza nominale PV
    wind_nom = float(cfg['system']['wind_nom_mw'])  # Potenza nominale eolico

    # Parametri di scalatura del carico
    load_scale = float(cfg['system']['load_scale'])           # Fattore di scala fisso
    load_scale_mode = cfg['system'].get('load_scale_mode', 'fixed')  # Modalita' scalatura
    load_nom_mw = float(cfg['system']['load_nom_mw'])         # Potenza nominale carico [MW]

    # ==================== COSTRUZIONE INDICI TEMPORALI ====================

    hours_all = np.arange(p_pv.shape[0], dtype=int)  # Indice orario per RES/PUN
    load_hours = _normalize_hours(pul[:, 0])          # Indice orario per carico (normalizzato)

    # ==================== DATAFRAME ANNUALE (RES + PUN) ====================

    df_year = pd.DataFrame(
        {
            'hour': hours_all,
            'pv_forecast_mw': p_pv[:, 0] * pv_nom,    # PV forecast [MW] = p.u. * nominale
            'pv_actual_mw': p_pv[:, 1] * pv_nom,      # PV actual [MW]
            'wind_forecast_mw': p_w[:, 0] * wind_nom, # Wind forecast [MW]
            'wind_actual_mw': p_w[:, 1] * wind_nom,   # Wind actual [MW]
            'pun_eur_per_mwh': price,                 # PUN [EUR/MWh]
        }
    ).set_index('hour')

    # ==================== SCALATURA CARICO ====================

    # Conversione da kW a MW
    load_forecast_mw = pul[:, 1] / 1000.0  # Carico previsto [MW]
    load_actual_mw = pul[:, 2] / 1000.0    # Carico effettivo [MW]

    # Modalita' di scalatura del carico
    if load_scale_mode == 'max_to_nominal':
        # Scala il carico in modo che il picco sia uguale a load_nom_mw
        peak = float(np.max(load_actual_mw))
        load_scale = load_nom_mw / peak if peak > 0 else 1.0

    # Applica il fattore di scala
    df_load = pd.DataFrame(
        {
            'hour': load_hours,
            'load_forecast_mw': load_forecast_mw * load_scale,  # Carico forecast scalato [MW]
            'load_actual_mw': load_actual_mw * load_scale,      # Carico actual scalato [MW]
        }
    ).set_index('hour')

    # ==================== UNIONE DATAFRAME ====================

    use_full_year = bool(cfg['project'].get('use_full_year', False))
    if use_full_year:
        # Left join: mantiene tutte le ore del RES (anno intero)
        df = df_year.join(df_load, how='left')
    else:
        # Inner join: mantiene solo le ore con dati di carico
        df = df_year.join(df_load, how='inner')

    # ==================== PREZZI DI IMPORT ====================

    # Aggiunge la serie dei prezzi di acquisto dalla rete
    df['import_price_eur_per_mwh'] = _build_import_price_series(cfg, df.index.values)

    # ==================== RESTITUZIONE RISULTATO ====================

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
    """
    Aggiunge le colonne del carico netto al DataFrame.

    Il carico netto e' definito come:
        net_load = load - (pv + wind)

    Rappresenta il carico residuo da soddisfare dopo aver utilizzato le RES.
    - Positivo: il carico supera la produzione RES (serve import/DG/FC)
    - Negativo: surplus di produzione RES (possibile export/curtailment/ELY)

    Args:
        df: DataFrame con le colonne di carico e RES

    Returns:
        DataFrame con le nuove colonne net_load_forecast_mw e net_load_actual_mw
    """
    df = df.copy()

    # Carico netto previsto
    df['net_load_forecast_mw'] = df['load_forecast_mw'] - (
        df['pv_forecast_mw'] + df['wind_forecast_mw']
    )

    # Carico netto effettivo
    df['net_load_actual_mw'] = df['load_actual_mw'] - (
        df['pv_actual_mw'] + df['wind_actual_mw']
    )

    return df
