"""
Generazione di grafici avanzati per l'analisi dei risultati MPC.

Questo modulo fornisce visualizzazioni dettagliate per comprendere:
1. Il bilancio energetico del sistema (fonti vs consumi)
2. Le opportunita' di arbitraggio sui prezzi
3. Il comportamento del sistema di stoccaggio idrogeno
4. I riassunti giornalieri delle energie
5. Il dettaglio di singole ore per analisi puntuale

I grafici sono progettati per presentazioni e report tecnici.
"""

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


def plot_energy_balance_stacked(
    df: pd.DataFrame,           # DataFrame con dati di input
    schedule: pd.DataFrame,     # DataFrame con scheduling ottimale
    title: str = "",            # Titolo del grafico
    save_path: str | None = None,  # Percorso per salvare l'immagine
    hours: int | None = None,   # Numero di ore da visualizzare
    start_hour: int = 0,        # Ora di inizio della finestra
):
    """
    GRAFICO PRINCIPALE: Bilancio energetico con aree impilate (stacked).

    Visualizzazione:
    - SOPRA (positivo): fonti di energia (RES, Import, DG, FC)
    - SOTTO (negativo): usi di energia (Export, ELY)
    - LINEA ROSSA: carico da soddisfare (domanda)

    Il grafico permette di verificare visivamente il bilancio energetico:
    la somma delle fonti deve eguagliare carico + usi.

    Pannelli:
    1. Bilancio energetico stacked
    2. Prezzi e margine di arbitraggio
    3. Flussi di rete e componenti

    Args:
        df: DataFrame con le serie temporali
        schedule: DataFrame con le decisioni dell'ottimizzatore
        title: Titolo principale del grafico
        save_path: Se specificato, salva il grafico su file
        hours: Numero di ore da mostrare (default: tutte)
        start_hour: Ora iniziale della finestra da visualizzare

    Returns:
        Oggetto Figure di matplotlib
    """
    merged = df.join(schedule, how='inner')

    # Selezione della finestra temporale
    if hours is not None:
        end_hour = min(start_hour + hours, len(merged))
        merged = merged.iloc[start_hour:end_hour]

    timesteps = merged.index.values

    # ==================== PREPARAZIONE DATI ====================

    # Produzione rinnovabile totale
    res_total = merged['pv_forecast_mw'] + merged['wind_forecast_mw']

    # FONTI (positive) - energia che entra nel sistema
    y_res = res_total.values           # Rinnovabili (PV + eolico)
    y_import = merged['p_import_mw'].values  # Import dalla rete
    y_dg = merged['p_dg_mw'].values    # Generatore diesel
    y_fc = merged['p_fc_mw'].values    # Fuel cell (scarica H2)

    # USI (negative) - energia che esce dal sistema (oltre al carico)
    y_export = -merged['p_export_mw'].values  # Export alla rete (negativo)
    y_ely = -merged['p_ely_mw'].values        # Elettrolizzatore (carica H2, negativo)

    # Carico (linea di riferimento)
    y_load = merged['load_forecast_mw'].values

    # ==================== CREAZIONE FIGURA ====================

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)

    # ==========================================================
    # PANNELLO 1: BILANCIO ENERGETICO STACKED
    # ==========================================================
    ax1 = axes[0]

    # Stack positivo (fonti di energia) - dal basso verso l'alto
    ax1.fill_between(timesteps, 0, y_res,
                     label='RES (PV+Wind)', color='green', alpha=0.7)
    ax1.fill_between(timesteps, y_res, y_res + y_import,
                     label='Import', color='blue', alpha=0.7)
    ax1.fill_between(timesteps, y_res + y_import, y_res + y_import + y_dg,
                     label='Diesel Gen', color='brown', alpha=0.7)
    ax1.fill_between(timesteps, y_res + y_import + y_dg, y_res + y_import + y_dg + y_fc,
                     label='Fuel Cell', color='purple', alpha=0.7)

    # Stack negativo (usi di energia oltre il carico)
    ax1.fill_between(timesteps, 0, y_export,
                     label='Export', color='cyan', alpha=0.7)
    ax1.fill_between(timesteps, y_export, y_export + y_ely,
                     label='Electrolyzer', color='magenta', alpha=0.7)

    # Linea del carico (domanda da soddisfare)
    ax1.plot(timesteps, y_load, 'r-', linewidth=2, label='Load (domanda)')

    # Calcolo bilancio per verifica
    total_in = y_res + y_import + y_dg + y_fc   # Totale fonti
    total_out = y_load - y_export - y_ely       # Totale usi (export e ely sono gia' negativi)

    ax1.axhline(y=0, color='black', linewidth=1)
    ax1.set_ylabel('Potenza [MW]')
    ax1.set_title(title if title else 'Bilancio Energetico')
    ax1.legend(loc='upper right', ncol=4)
    ax1.grid(True, alpha=0.3)

    # ==========================================================
    # PANNELLO 2: PREZZI E CONVENIENZA ARBITRAGGIO
    # ==========================================================
    ax2 = axes[1]

    # Serie dei prezzi
    ax2.plot(timesteps, merged['import_price_eur_per_mwh'],
             'r-', linewidth=1.5, label='Prezzo Import (ARERA)')
    ax2.plot(timesteps, merged['pun_eur_per_mwh'],
             'b-', linewidth=1.5, label='Prezzo Export (PUN)')

    # Linea orizzontale del costo marginale diesel (750 EUR/MWh per cf=0.45)
    ax2.axhline(y=750, color='brown', linestyle='--', linewidth=1, label='Costo DG')

    # Evidenzia zone di arbitraggio (quando conviene comprare e rivendere)
    pun = merged['pun_eur_per_mwh'].values
    imp_price = merged['import_price_eur_per_mwh'].values
    arbitrage_mask = pun > imp_price  # Arbitraggio se PUN > prezzo import

    ax2.fill_between(timesteps, imp_price, pun,
                     where=arbitrage_mask,
                     alpha=0.3, color='gold', label='Margine arbitraggio')

    ax2.set_ylabel('Prezzo [EUR/MWh]')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(bottom=0)

    # ==========================================================
    # PANNELLO 3: FLUSSI RETE E STORAGE
    # ==========================================================
    ax3 = axes[2]

    # Flussi con la rete elettrica
    ax3.plot(timesteps, merged['p_import_mw'],
             'b-', linewidth=1.5, label='Import')
    ax3.plot(timesteps, merged['p_export_mw'],
             'c-', linewidth=1.5, label='Export')
    ax3.plot(timesteps, merged['p_dg_mw'],
             color='brown', linewidth=1.5, label='Diesel Gen')

    # Sistema idrogeno
    ax3.plot(timesteps, merged['p_ely_mw'],
             'm--', linewidth=1, label='Electrolyzer')
    ax3.plot(timesteps, merged['p_fc_mw'],
             color='purple', linestyle='--', linewidth=1, label='Fuel Cell')

    ax3.axhline(y=0, color='black', linewidth=0.5)
    ax3.set_ylabel('Potenza [MW]')
    ax3.set_xlabel('Ora')
    ax3.legend(loc='upper right', ncol=3)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Salvato: {save_path}')

    plt.show()
    return fig


def plot_arbitrage_analysis(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    title: str = "",
    save_path: str | None = None,
    hours: int | None = None,
    start_hour: int = 0,
):
    """
    Grafico specifico per l'analisi delle opportunita' di arbitraggio.

    L'arbitraggio consiste nel comprare energia quando il prezzo e' basso
    e rivenderla quando il prezzo e' alto. Questo grafico mostra:
    - Quando conviene comprare dalla rete e rivendere
    - Quando conviene anche usare il diesel per vendere

    Pannelli:
    1. Prezzi e zone di arbitraggio colorate
    2. Decisioni del modello (import/export/diesel)

    Args:
        df: DataFrame con le serie temporali
        schedule: DataFrame con le decisioni dell'ottimizzatore
        title: Titolo del grafico
        save_path: Percorso per salvare l'immagine
        hours: Numero di ore da visualizzare
        start_hour: Ora iniziale

    Returns:
        Oggetto Figure di matplotlib
    """
    merged = df.join(schedule, how='inner')

    if hours is not None:
        end_hour = min(start_hour + hours, len(merged))
        merged = merged.iloc[start_hour:end_hour]

    timesteps = merged.index.values

    fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True)

    # ==========================================================
    # PANNELLO 1: PREZZI E ZONE ARBITRAGGIO
    # ==========================================================
    ax1 = axes[0]

    pun = merged['pun_eur_per_mwh'].values      # Prezzo di vendita (PUN)
    imp_price = merged['import_price_eur_per_mwh'].values  # Prezzo di acquisto

    ax1.plot(timesteps, imp_price, 'r-', linewidth=2, label='Prezzo Import')
    ax1.plot(timesteps, pun, 'b-', linewidth=2, label='Prezzo Export (PUN)')
    ax1.axhline(y=750, color='brown', linestyle='--', linewidth=1.5, label='Costo DG (750 EUR/MWh)')

    # Zona arbitraggio Tipo 1: PUN > Import (conviene comprare e vendere)
    ax1.fill_between(timesteps, imp_price, pun,
                     where=(pun > imp_price),
                     alpha=0.4, color='green', label='Arbitraggio: compra+vendi')

    # Zona arbitraggio Tipo 2: PUN > DG cost (conviene anche accendere il diesel)
    ax1.fill_between(timesteps, 750, pun,
                     where=(pun > 750),
                     alpha=0.3, color='orange', label='Arbitraggio: anche DG conviene')

    ax1.set_ylabel('Prezzo [EUR/MWh]')
    ax1.set_title(title if title else 'Analisi Arbitraggio')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(bottom=0)

    # ==========================================================
    # PANNELLO 2: DECISIONI DEL MODELLO
    # ==========================================================
    ax2 = axes[1]

    # Barre per import (positive) e export (negative)
    ax2.bar(timesteps, merged['p_import_mw'],
            width=0.8, label='Import', color='blue', alpha=0.7)
    ax2.bar(timesteps, -merged['p_export_mw'],
            width=0.8, label='Export', color='cyan', alpha=0.7)
    ax2.bar(timesteps, merged['p_dg_mw'],
            width=0.4, label='Diesel Gen', color='brown', alpha=0.9)

    # Linee di riferimento per i limiti
    ax2.axhline(y=0, color='black', linewidth=1)
    ax2.axhline(y=20, color='blue', linestyle=':', linewidth=1, alpha=0.5)
    ax2.axhline(y=-16, color='cyan', linestyle=':', linewidth=1, alpha=0.5)
    ax2.text(timesteps[0], 20.5, 'Max Import (20 MW)', fontsize=8, color='blue')
    ax2.text(timesteps[0], -17, 'Max Export (16 MW)', fontsize=8, color='cyan')

    ax2.set_ylabel('Potenza [MW]')
    ax2.set_xlabel('Ora')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Salvato: {save_path}')

    plt.show()
    return fig


def plot_h2_system(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    title: str = "",
    save_path: str | None = None,
    hours: int | None = None,
    start_hour: int = 0,
):
    """
    Grafico dedicato al sistema di stoccaggio idrogeno.

    Mostra il comportamento dell'elettrolizzatore, della fuel cell
    e l'evoluzione dello stato di carica del serbatoio H2.

    Pannelli:
    1. Potenze ELY (consumo, negativo) e FC (produzione, positivo)
    2. Stato di carica dello storage in percentuale

    Args:
        df: DataFrame con le serie temporali
        schedule: DataFrame con le decisioni dell'ottimizzatore
        title: Titolo del grafico
        save_path: Percorso per salvare l'immagine
        hours: Numero di ore da visualizzare
        start_hour: Ora iniziale

    Returns:
        Oggetto Figure di matplotlib
    """
    merged = df.join(schedule, how='inner')

    if hours is not None:
        end_hour = min(start_hour + hours, len(merged))
        merged = merged.iloc[start_hour:end_hour]

    timesteps = merged.index.values
    h2_capacity = 12.0  # Capacita' storage idrogeno [MWh]

    fig, axes = plt.subplots(2, 1, figsize=(16, 8), sharex=True)

    # ==========================================================
    # PANNELLO 1: POTENZE ELY e FC
    # ==========================================================
    ax1 = axes[0]

    # Elettrolizzatore (consuma energia elettrica per produrre H2) - mostrato negativo
    ax1.fill_between(timesteps, 0, -merged['p_ely_mw'],
                     label='Electrolyzer (consuma)', color='magenta', alpha=0.7)

    # Fuel Cell (consuma H2 per produrre energia elettrica) - mostrato positivo
    ax1.fill_between(timesteps, 0, merged['p_fc_mw'],
                     label='Fuel Cell (produce)', color='purple', alpha=0.7)

    ax1.axhline(y=0, color='black', linewidth=1)
    ax1.set_ylabel('Potenza [MW]')
    ax1.set_title(title if title else 'Sistema Idrogeno')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # ==========================================================
    # PANNELLO 2: SOC H2 STORAGE
    # ==========================================================
    ax2 = axes[1]

    # Converte SOC da MWh a percentuale della capacita'
    soc_percent = (merged['soc_mwh'] / h2_capacity) * 100

    ax2.fill_between(timesteps, 0, soc_percent,
                     color='teal', alpha=0.5)
    ax2.plot(timesteps, soc_percent, 'teal', linewidth=2, label='H2 SoC')

    # Linee di riferimento per 0% e 100%
    ax2.axhline(y=0, color='gray', linestyle='--', linewidth=1)
    ax2.axhline(y=100, color='gray', linestyle='--', linewidth=1)

    ax2.set_ylabel('H2 SoC [%]')
    ax2.set_xlabel('Ora')
    ax2.set_ylim(-5, 105)
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Salvato: {save_path}')

    plt.show()
    return fig


def plot_daily_summary(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    title: str = "",
    save_path: str | None = None,
):
    """
    Grafico riassuntivo giornaliero: energie totali per ogni giorno.

    Aggrega i dati orari in totali giornalieri per una visione d'insieme
    su periodi lunghi.

    Pannelli:
    1. Fonti giornaliere (stacked bar) + linea del carico
    2. Export e consumo elettrolizzatore giornalieri

    Args:
        df: DataFrame con le serie temporali
        schedule: DataFrame con le decisioni dell'ottimizzatore
        title: Titolo del grafico
        save_path: Percorso per salvare l'immagine

    Returns:
        Oggetto Figure di matplotlib
    """
    merged = df.join(schedule, how='inner')

    # Raggruppa per giorno (ogni 24 ore)
    merged['day'] = merged.index // 24

    # Aggregazione giornaliera (somma delle potenze = energia in MWh con dt=1h)
    daily = merged.groupby('day').agg({
        'load_forecast_mw': 'sum',
        'pv_forecast_mw': 'sum',
        'wind_forecast_mw': 'sum',
        'p_import_mw': 'sum',
        'p_export_mw': 'sum',
        'p_dg_mw': 'sum',
        'p_ely_mw': 'sum',
        'p_fc_mw': 'sum',
    }).rename(columns={
        'load_forecast_mw': 'Load',
        'pv_forecast_mw': 'PV',
        'wind_forecast_mw': 'Wind',
        'p_import_mw': 'Import',
        'p_export_mw': 'Export',
        'p_dg_mw': 'DG',
        'p_ely_mw': 'ELY',
        'p_fc_mw': 'FC',
    })

    # Calcola RES totale
    daily['RES'] = daily['PV'] + daily['Wind']

    fig, axes = plt.subplots(2, 1, figsize=(16, 10))

    # ==========================================================
    # PANNELLO 1: FONTI GIORNALIERE (stacked bar)
    # ==========================================================
    ax1 = axes[0]

    days = daily.index.values
    width = 0.8

    # Barre impilate: RES + Import + DG + FC
    ax1.bar(days, daily['RES'], width, label='RES', color='green', alpha=0.7)
    ax1.bar(days, daily['Import'], width, bottom=daily['RES'],
            label='Import', color='blue', alpha=0.7)
    ax1.bar(days, daily['DG'], width, bottom=daily['RES'] + daily['Import'],
            label='DG', color='brown', alpha=0.7)
    ax1.bar(days, daily['FC'], width, bottom=daily['RES'] + daily['Import'] + daily['DG'],
            label='FC', color='purple', alpha=0.7)

    # Linea del carico giornaliero
    ax1.plot(days, daily['Load'], 'r-o', linewidth=2, markersize=3, label='Load')

    ax1.set_ylabel('Energia [MWh/giorno]')
    ax1.set_title(title if title else 'Energie Giornaliere')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3, axis='y')

    # ==========================================================
    # PANNELLO 2: EXPORT E ELY GIORNALIERI
    # ==========================================================
    ax2 = axes[1]

    # Export (positivo) e ELY (negativo per simmetria)
    ax2.bar(days, daily['Export'], width, label='Export', color='cyan', alpha=0.7)
    ax2.bar(days, -daily['ELY'], width, label='ELY', color='magenta', alpha=0.7)

    ax2.axhline(y=0, color='black', linewidth=1)
    ax2.set_ylabel('Energia [MWh/giorno]')
    ax2.set_xlabel('Giorno')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Salvato: {save_path}')

    plt.show()
    return fig


def plot_single_hour_breakdown(
    df: pd.DataFrame,
    schedule: pd.DataFrame,
    hour: int,              # Ora specifica da analizzare
    save_path: str | None = None,
):
    """
    Grafico dettagliato per una singola ora.

    Utile per analizzare nel dettaglio le decisioni del modello
    in un istante specifico, mostrando il bilancio energetico
    e il calcolo economico.

    Pannelli:
    1. Bilancio: barre IN (fonti) vs OUT (usi)
    2. Riepilogo testuale con calcolo economico

    Args:
        df: DataFrame con le serie temporali
        schedule: DataFrame con le decisioni dell'ottimizzatore
        hour: Indice dell'ora da analizzare
        save_path: Percorso per salvare l'immagine

    Returns:
        Oggetto Figure di matplotlib (o None se ora non trovata)
    """
    merged = df.join(schedule, how='inner')

    if hour not in merged.index:
        print(f"Ora {hour} non trovata nei dati")
        return None

    row = merged.loc[hour]

    # ==================== ESTRAZIONE DATI ====================

    # Produzioni
    pv = row['pv_forecast_mw']
    wind = row['wind_forecast_mw']
    res = pv + wind  # RES totale

    # Carico
    load = row['load_forecast_mw']

    # Decisioni ottimizzatore
    imp = row['p_import_mw']    # Import dalla rete
    exp = row['p_export_mw']    # Export alla rete
    dg = row['p_dg_mw']         # Diesel
    ely = row['p_ely_mw']       # Elettrolizzatore
    fc = row['p_fc_mw']         # Fuel cell

    # Prezzi
    imp_price = row['import_price_eur_per_mwh']
    pun = row['pun_eur_per_mwh']

    # ==================== CREAZIONE FIGURA ====================

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # ==========================================================
    # PANNELLO 1: BILANCIO IN vs OUT
    # ==========================================================
    ax1 = axes[0]

    # Valori e colori per le barre IN
    in_values = [res, imp, dg, fc]
    in_labels = ['RES', 'Import', 'DG', 'FC']
    in_colors = ['green', 'blue', 'brown', 'purple']

    # Valori e colori per le barre OUT
    out_values = [load, exp, ely]
    out_labels = ['Load', 'Export', 'ELY']
    out_colors = ['red', 'cyan', 'magenta']

    # Barra IN (impilata)
    bottom_in = 0
    for val, label, color in zip(in_values, in_labels, in_colors):
        if val > 0.01:  # Mostra solo se > 0
            ax1.bar(0, val, bottom=bottom_in, color=color, label=f'{label}: {val:.2f} MW')
            bottom_in += val

    # Barra OUT (impilata)
    bottom_out = 0
    for val, label, color in zip(out_values, out_labels, out_colors):
        if val > 0.01:
            ax1.bar(1, val, bottom=bottom_out, color=color, label=f'{label}: {val:.2f} MW')
            bottom_out += val

    ax1.set_xticks([0, 1])
    ax1.set_xticklabels(['ENTRATE\n(IN)', 'USCITE\n(OUT)'])
    ax1.set_ylabel('Potenza [MW]')
    ax1.set_title(f'Ora {hour}: Bilancio Energetico')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3, axis='y')

    # Totali sopra le barre
    total_in = sum(in_values)
    total_out = sum(out_values)
    ax1.text(0, total_in + 0.5, f'Tot: {total_in:.2f} MW', ha='center', fontsize=10, fontweight='bold')
    ax1.text(1, total_out + 0.5, f'Tot: {total_out:.2f} MW', ha='center', fontsize=10, fontweight='bold')

    # ==========================================================
    # PANNELLO 2: CALCOLO ECONOMICO
    # ==========================================================
    ax2 = axes[1]
    ax2.axis('off')  # Nessun asse, solo testo

    # Calcoli economici per questa ora
    cost_import = imp * imp_price              # Costo import [EUR]
    cost_dg = dg * 750                         # Costo diesel (assumendo cf=0.45)
    revenue_export = exp * pun                 # Ricavo export [EUR]
    net = revenue_export - cost_import - cost_dg  # Netto [EUR]

    # Testo formattato con il riepilogo
    text = f"""
    ORA {hour}
    {'='*40}

    PREZZI:
      Import (ARERA):  {imp_price:.2f} EUR/MWh
      Export (PUN):    {pun:.2f} EUR/MWh
      Costo DG:        750.00 EUR/MWh

    FLUSSI:
      Import:  {imp:.2f} MW
      Export:  {exp:.2f} MW
      DG:      {dg:.2f} MW
      Load:    {load:.2f} MW
      RES:     {res:.2f} MW (PV:{pv:.2f} + Wind:{wind:.2f})

    CALCOLO ECONOMICO:
      Costo Import:  {imp:.2f} x {imp_price:.2f} = {cost_import:.2f} EUR
      Costo DG:      {dg:.2f} x 750.00 = {cost_dg:.2f} EUR
      Ricavo Export: {exp:.2f} x {pun:.2f} = {revenue_export:.2f} EUR
      {'─'*40}
      NETTO: {revenue_export:.2f} - {cost_import:.2f} - {cost_dg:.2f} = {net:.2f} EUR

    {'ARBITRAGGIO ATTIVO!' if (imp > 0 and exp > 0) else ''}
    """

    ax2.text(0.1, 0.9, text, transform=ax2.transAxes, fontsize=11,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f'Salvato: {save_path}')

    plt.show()
    return fig


def main():
    """
    Funzione principale: genera tutti i grafici dai risultati MPC.

    Argomenti da linea di comando:
    --config: percorso file di configurazione YAML
    --schedule-45: percorso CSV scheduling con cf=0.45 EUR/kWh
    --schedule-60: percorso CSV scheduling con cf=0.60 EUR/kWh
    --hours: numero di ore da plottare (default: 168 = 1 settimana)
    --start: ora di inizio
    --out-dir: cartella di output per i grafici
    --scenario: quale scenario plottare (cf045, cf060, both)
    --hour-detail: se specificato, mostra solo il dettaglio di quell'ora
    """
    parser = argparse.ArgumentParser(description='Plot MPC results (improved version).')
    parser.add_argument('--config', default='configs/system.yaml')
    parser.add_argument('--schedule-45', default='outputs/mpc_2022_cf045.csv')
    parser.add_argument('--schedule-60', default='outputs/mpc_2022_cf060.csv')
    parser.add_argument('--hours', type=int, default=168, help='Ore da plottare (default: 168 = 1 settimana)')
    parser.add_argument('--start', type=int, default=0, help='Ora di inizio')
    parser.add_argument('--out-dir', default='outputs/plots')
    parser.add_argument('--scenario', choices=['cf045', 'cf060', 'both'], default='cf045')
    parser.add_argument('--hour-detail', type=int, default=None, help='Mostra dettaglio per ora specifica')
    args = parser.parse_args()

    # Caricamento configurazione e dati
    cfg = yaml.safe_load(Path(args.config).read_text())
    bundle = load_timeseries(Path('data'), cfg)
    df = add_net_load(bundle.data)

    # Caricamento degli scheduling per i due scenari di costo combustibile
    s45 = pd.read_csv(args.schedule_45).set_index('hour')  # Scenario cf=0.45
    s60 = pd.read_csv(args.schedule_60).set_index('hour')  # Scenario cf=0.60

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Selezione degli scenari da plottare
    if args.scenario == 'cf045':
        schedules = [('cf045', s45)]
    elif args.scenario == 'cf060':
        schedules = [('cf060', s60)]
    else:
        schedules = [('cf045', s45), ('cf060', s60)]

    # Se richiesto dettaglio di un'ora specifica
    if args.hour_detail is not None:
        for name, sched in schedules:
            print(f'\n=== Dettaglio Ora {args.hour_detail} ({name}) ===')
            plot_single_hour_breakdown(
                df, sched, args.hour_detail,
                save_path=str(out_dir / f'hour_{args.hour_detail}_{name}.png')
            )
        return

    # Generazione di tutti i grafici per ogni scenario
    for name, sched in schedules:
        print(f'\n=== Bilancio Energetico ({name}) ===')
        plot_energy_balance_stacked(
            df, sched,
            title=f'Bilancio Energetico - {name} ({args.hours}h)',
            save_path=str(out_dir / f'balance_{name}.png'),
            hours=args.hours,
            start_hour=args.start
        )

        print(f'\n=== Analisi Arbitraggio ({name}) ===')
        plot_arbitrage_analysis(
            df, sched,
            title=f'Analisi Arbitraggio - {name} ({args.hours}h)',
            save_path=str(out_dir / f'arbitrage_{name}.png'),
            hours=args.hours,
            start_hour=args.start
        )

        print(f'\n=== Sistema H2 ({name}) ===')
        plot_h2_system(
            df, sched,
            title=f'Sistema Idrogeno - {name} ({args.hours}h)',
            save_path=str(out_dir / f'h2_system_{name}.png'),
            hours=args.hours,
            start_hour=args.start
        )

        print(f'\n=== Riepilogo Giornaliero ({name}) ===')
        plot_daily_summary(
            df, sched,
            title=f'Energie Giornaliere - {name}',
            save_path=str(out_dir / f'daily_summary_{name}.png'),
        )


if __name__ == '__main__':
    main()
