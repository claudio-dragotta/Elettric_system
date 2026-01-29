"""
Crea tutti i grafici comparativi 2022 vs 2025
- Profili di potenza
- Sistema ELY/FC
- Bilancio energetico
"""
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'test_2025')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import yaml
from pathlib import Path

from loader import load_timeseries, add_net_load
from run_test_2025 import load_timeseries_2025

# Carica configurazioni
cfg_2022 = yaml.safe_load(Path('configs/system.yaml').read_text(encoding='utf-8'))
cfg_2025 = yaml.safe_load(Path('test_2025/system_2025.yaml').read_text(encoding='utf-8'))

# Carica dati
bundle_2022 = load_timeseries(Path('data'), cfg_2022)
df_2022 = add_net_load(bundle_2022.data)

bundle_2025 = load_timeseries_2025(Path('data'), Path('test_2025'), cfg_2025)
df_2025 = add_net_load(bundle_2025.data)

# Carica schedule
sched_2022 = pd.read_csv('outputs/mpc_2022_cf045.csv').set_index('hour')
sched_2025 = pd.read_csv('test_2025/outputs_2025/mpc_2025_cf014.csv').set_index('hour')

# Merge dati
merged_2022 = df_2022.join(sched_2022, how='inner')
merged_2025 = df_2025.join(sched_2025, how='inner')

# Crea date
start_2022 = datetime(2022, 1, 1)
start_2025 = datetime(2025, 1, 1)
dates_2022 = [start_2022 + timedelta(hours=int(h)) for h in merged_2022.index]
dates_2025 = [start_2025 + timedelta(hours=int(h)) for h in merged_2025.index]

print('Dati caricati. Creazione grafici...')

# ============================================================================
# GRAFICO 1: Profilo di Potenza 2022
# ============================================================================
fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)

ax = axes[0]
ax.fill_between(dates_2022, merged_2022['load_forecast_mw'], alpha=0.7, label='Load', color='gray')
ax.fill_between(dates_2022, merged_2022['pv_forecast_mw'], alpha=0.7, label='PV', color='orange')
ax.fill_between(dates_2022, merged_2022['wind_forecast_mw'], alpha=0.7, label='Wind', color='blue')
ax.set_ylabel('Potenza (MW)')
ax.set_title('Profilo di Potenza 2022 - Load e Rinnovabili', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 25)

ax = axes[1]
ax.fill_between(dates_2022, merged_2022['p_import_mw'], alpha=0.7, label='Import', color='red')
ax.fill_between(dates_2022, -merged_2022['p_export_mw'], alpha=0.7, label='Export', color='green')
ax.axhline(y=0, color='black', linewidth=0.5)
ax.set_ylabel('Potenza (MW)')
ax.set_title('Scambi con la Rete 2022', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

ax = axes[2]
ax.fill_between(dates_2022, merged_2022['p_ely_mw'], alpha=0.7, label='ELY (carica H2)', color='purple')
ax.fill_between(dates_2022, -merged_2022['p_fc_mw'], alpha=0.7, label='FC (scarica H2)', color='cyan')
ax.fill_between(dates_2022, merged_2022['p_dg_mw'], alpha=0.7, label='DG', color='brown')
ax.axhline(y=0, color='black', linewidth=0.5)
ax.set_ylabel('Potenza (MW)')
ax.set_xlabel('Data')
ax.set_title('Sistema H2 e DG 2022', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

for ax in axes:
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))

plt.tight_layout()
plt.savefig('outputs/plots/profilo_potenza_2022.png', dpi=150, bbox_inches='tight')
plt.close()
print('1. Salvato: profilo_potenza_2022.png')

# ============================================================================
# GRAFICO 2: Profilo di Potenza 2025
# ============================================================================
fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)

ax = axes[0]
ax.fill_between(dates_2025, merged_2025['load_forecast_mw'], alpha=0.7, label='Load', color='gray')
ax.fill_between(dates_2025, merged_2025['pv_forecast_mw'], alpha=0.7, label='PV', color='orange')
ax.fill_between(dates_2025, merged_2025['wind_forecast_mw'], alpha=0.7, label='Wind', color='blue')
ax.set_ylabel('Potenza (MW)')
ax.set_title('Profilo di Potenza 2025 - Load e Rinnovabili', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 25)

ax = axes[1]
ax.fill_between(dates_2025, merged_2025['p_import_mw'], alpha=0.7, label='Import', color='red')
ax.fill_between(dates_2025, -merged_2025['p_export_mw'], alpha=0.7, label='Export', color='green')
ax.axhline(y=0, color='black', linewidth=0.5)
ax.set_ylabel('Potenza (MW)')
ax.set_title('Scambi con la Rete 2025', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

ax = axes[2]
ax.fill_between(dates_2025, merged_2025['p_ely_mw'], alpha=0.7, label='ELY (carica H2)', color='purple')
ax.fill_between(dates_2025, -merged_2025['p_fc_mw'], alpha=0.7, label='FC (scarica H2)', color='cyan')
ax.fill_between(dates_2025, merged_2025['p_dg_mw'], alpha=0.7, label='DG', color='brown')
ax.axhline(y=0, color='black', linewidth=0.5)
ax.set_ylabel('Potenza (MW)')
ax.set_xlabel('Data')
ax.set_title('Sistema H2 e DG 2025', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

for ax in axes:
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))

plt.tight_layout()
plt.savefig('outputs/plots/profilo_potenza_2025.png', dpi=150, bbox_inches='tight')
plt.close()
print('2. Salvato: profilo_potenza_2025.png')

# ============================================================================
# GRAFICO 3: Sistema ELY/FC dettaglio - 2022
# ============================================================================
fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)

ax = axes[0]
ax.plot(dates_2022, merged_2022['p_ely_mw'], 'purple', linewidth=0.8, label='ELY (MW)')
ax.plot(dates_2022, merged_2022['p_fc_mw'], 'cyan', linewidth=0.8, label='FC (MW)')
ax.set_ylabel('Potenza (MW)')
ax.set_title('Sistema Idrogeno 2022 - Potenza ELY e FC', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

ax = axes[1]
ax.plot(dates_2022, merged_2022['soc_mwh'], 'green', linewidth=1, label='SOC H2 (MWh)')
ax.axhline(y=12, color='red', linestyle='--', alpha=0.5, label='Capacita max (12 MWh)')
ax.set_ylabel('SOC (MWh)')
ax.set_title('Stato di Carica Storage H2', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 14)

surplus = (merged_2022['pv_forecast_mw'] + merged_2022['wind_forecast_mw'] - merged_2022['load_forecast_mw']).clip(lower=0)
ax = axes[2]
ax.fill_between(dates_2022, surplus, alpha=0.5, label='Surplus RES (PV+Wind-Load)', color='yellow')
ax.plot(dates_2022, merged_2022['p_ely_mw'], 'purple', linewidth=1, label='ELY')
ax.set_ylabel('Potenza (MW)')
ax.set_xlabel('Data')
ax.set_title('Surplus Rinnovabili vs Utilizzo ELY', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

for ax in axes:
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))

plt.tight_layout()
plt.savefig('outputs/plots/sistema_h2_2022.png', dpi=150, bbox_inches='tight')
plt.close()
print('3. Salvato: sistema_h2_2022.png')

# ============================================================================
# GRAFICO 4: Sistema ELY/FC dettaglio - 2025
# ============================================================================
fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)

ax = axes[0]
ax.plot(dates_2025, merged_2025['p_ely_mw'], 'purple', linewidth=0.8, label='ELY (MW)')
ax.plot(dates_2025, merged_2025['p_fc_mw'], 'cyan', linewidth=0.8, label='FC (MW)')
ax.set_ylabel('Potenza (MW)')
ax.set_title('Sistema Idrogeno 2025 - Potenza ELY e FC', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

ax = axes[1]
ax.plot(dates_2025, merged_2025['soc_mwh'], 'green', linewidth=1, label='SOC H2 (MWh)')
ax.axhline(y=12, color='red', linestyle='--', alpha=0.5, label='Capacita max (12 MWh)')
ax.set_ylabel('SOC (MWh)')
ax.set_title('Stato di Carica Storage H2', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 14)

surplus_25 = (merged_2025['pv_forecast_mw'] + merged_2025['wind_forecast_mw'] - merged_2025['load_forecast_mw']).clip(lower=0)
ax = axes[2]
ax.fill_between(dates_2025, surplus_25, alpha=0.5, label='Surplus RES (PV+Wind-Load)', color='yellow')
ax.plot(dates_2025, merged_2025['p_ely_mw'], 'purple', linewidth=1, label='ELY')
ax.set_ylabel('Potenza (MW)')
ax.set_xlabel('Data')
ax.set_title('Surplus Rinnovabili vs Utilizzo ELY', fontweight='bold')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

for ax in axes:
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))

plt.tight_layout()
plt.savefig('outputs/plots/sistema_h2_2025.png', dpi=150, bbox_inches='tight')
plt.close()
print('4. Salvato: sistema_h2_2025.png')

# ============================================================================
# GRAFICO 5: Bilancio Energetico - Confronto 2022 vs 2025
# ============================================================================
dt = 1.0

# Calcola energie per 2022
e_2022 = {
    'PV': (merged_2022['pv_forecast_mw'] * dt).sum(),
    'Wind': (merged_2022['wind_forecast_mw'] * dt).sum(),
    'Import': (merged_2022['p_import_mw'] * dt).sum(),
    'FC': (merged_2022['p_fc_mw'] * dt).sum(),
    'DG': (merged_2022['p_dg_mw'] * dt).sum(),
    'Load': (merged_2022['load_forecast_mw'] * dt).sum(),
    'Export': (merged_2022['p_export_mw'] * dt).sum(),
    'ELY': (merged_2022['p_ely_mw'] * dt).sum(),
    'Curt': (merged_2022['p_curt_mw'] * dt).sum(),
}

# Calcola energie per 2025
e_2025 = {
    'PV': (merged_2025['pv_forecast_mw'] * dt).sum(),
    'Wind': (merged_2025['wind_forecast_mw'] * dt).sum(),
    'Import': (merged_2025['p_import_mw'] * dt).sum(),
    'FC': (merged_2025['p_fc_mw'] * dt).sum(),
    'DG': (merged_2025['p_dg_mw'] * dt).sum(),
    'Load': (merged_2025['load_forecast_mw'] * dt).sum(),
    'Export': (merged_2025['p_export_mw'] * dt).sum(),
    'ELY': (merged_2025['p_ely_mw'] * dt).sum(),
    'Curt': (merged_2025['p_curt_mw'] * dt).sum(),
}

# Bilancio: IN = OUT
# IN: PV + Wind + Import + FC + DG
# OUT: Load + Export + ELY + Curt

in_2022 = e_2022['PV'] + e_2022['Wind'] + e_2022['Import'] + e_2022['FC'] + e_2022['DG']
out_2022 = e_2022['Load'] + e_2022['Export'] + e_2022['ELY'] + e_2022['Curt']

in_2025 = e_2025['PV'] + e_2025['Wind'] + e_2025['Import'] + e_2025['FC'] + e_2025['DG']
out_2025 = e_2025['Load'] + e_2025['Export'] + e_2025['ELY'] + e_2025['Curt']

fig, axes = plt.subplots(1, 2, figsize=(16, 8))

# Grafico a barre - Energia IN
ax = axes[0]
labels_in = ['PV', 'Wind', 'Import', 'FC', 'DG']
values_2022_in = [e_2022[k] for k in labels_in]
values_2025_in = [e_2025[k] for k in labels_in]

x = np.arange(len(labels_in))
width = 0.35

bars1 = ax.bar(x - width/2, values_2022_in, width, label='2022', color='steelblue', alpha=0.8)
bars2 = ax.bar(x + width/2, values_2025_in, width, label='2025', color='coral', alpha=0.8)

ax.set_ylabel('Energia (MWh)')
ax.set_title('Energia IN - Fonti di Generazione', fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(labels_in)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

# Aggiungi valori sopra le barre
for bar in bars1:
    height = bar.get_height()
    if height > 100:
        ax.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

for bar in bars2:
    height = bar.get_height()
    if height > 100:
        ax.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

# Grafico a barre - Energia OUT
ax = axes[1]
labels_out = ['Load', 'Export', 'ELY', 'Curt']
values_2022_out = [e_2022[k] for k in labels_out]
values_2025_out = [e_2025[k] for k in labels_out]

x = np.arange(len(labels_out))

bars1 = ax.bar(x - width/2, values_2022_out, width, label='2022', color='steelblue', alpha=0.8)
bars2 = ax.bar(x + width/2, values_2025_out, width, label='2025', color='coral', alpha=0.8)

ax.set_ylabel('Energia (MWh)')
ax.set_title('Energia OUT - Consumi e Uscite', fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(labels_out)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

for bar in bars1:
    height = bar.get_height()
    if height > 100:
        ax.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

for bar in bars2:
    height = bar.get_height()
    if height > 100:
        ax.annotate(f'{height:,.0f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

plt.suptitle('Bilancio Energetico: Confronto 2022 vs 2025', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('outputs/plots/bilancio_energetico_confronto.png', dpi=150, bbox_inches='tight')
plt.close()
print('5. Salvato: bilancio_energetico_confronto.png')

# ============================================================================
# GRAFICO 6: Sankey-style Bilancio Energetico
# ============================================================================
fig, axes = plt.subplots(1, 2, figsize=(16, 10))

for idx, (year, e, in_tot, out_tot) in enumerate([(2022, e_2022, in_2022, out_2022),
                                                   (2025, e_2025, in_2025, out_2025)]):
    ax = axes[idx]

    # Dati per stacked bar
    in_data = [e['PV'], e['Wind'], e['Import'], e['FC'], e['DG']]
    out_data = [e['Load'], e['Export'], e['ELY'], e['Curt']]

    in_labels = ['PV', 'Wind', 'Import', 'FC', 'DG']
    out_labels = ['Load', 'Export', 'ELY', 'Curt']

    in_colors = ['orange', 'blue', 'red', 'cyan', 'brown']
    out_colors = ['gray', 'green', 'purple', 'yellow']

    # Stacked bar IN
    bottom = 0
    for i, (val, label, color) in enumerate(zip(in_data, in_labels, in_colors)):
        ax.bar(0, val, bottom=bottom, width=0.6, label=f'{label}: {val:,.0f} MWh', color=color, alpha=0.8)
        if val > 500:
            ax.text(0, bottom + val/2, f'{label}\n{val:,.0f}', ha='center', va='center', fontsize=9, fontweight='bold')
        bottom += val

    # Stacked bar OUT
    bottom = 0
    for i, (val, label, color) in enumerate(zip(out_data, out_labels, out_colors)):
        ax.bar(1, val, bottom=bottom, width=0.6, color=color, alpha=0.8)
        if val > 500:
            ax.text(1, bottom + val/2, f'{label}\n{val:,.0f}', ha='center', va='center', fontsize=9, fontweight='bold')
        bottom += val

    ax.set_xticks([0, 1])
    ax.set_xticklabels(['ENERGIA IN', 'ENERGIA OUT'])
    ax.set_ylabel('Energia (MWh)')
    ax.set_title(f'Bilancio Energetico {year}\nIN: {in_tot:,.0f} MWh | OUT: {out_tot:,.0f} MWh', fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    # Verifica bilancio
    diff = abs(in_tot - out_tot)
    ax.text(0.5, -0.1, f'Differenza IN-OUT: {diff:.1f} MWh ({diff/in_tot*100:.3f}%)',
            ha='center', transform=ax.transAxes, fontsize=10)

plt.tight_layout()
plt.savefig('outputs/plots/bilancio_energetico_stacked.png', dpi=150, bbox_inches='tight')
plt.close()
print('6. Salvato: bilancio_energetico_stacked.png')

# ============================================================================
# GRAFICO 7: Confronto Diretto 2022 vs 2025 - Profilo Settimanale Medio
# ============================================================================
# Calcola profilo medio settimanale (168 ore)
merged_2022['hour_of_week'] = merged_2022.index % 168
merged_2025['hour_of_week'] = merged_2025.index % 168

weekly_2022 = merged_2022.groupby('hour_of_week').mean()
weekly_2025 = merged_2025.groupby('hour_of_week').mean()

fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)

# Import
ax = axes[0]
ax.plot(weekly_2022.index, weekly_2022['p_import_mw'], 'b-', linewidth=2, label='2022', alpha=0.8)
ax.plot(weekly_2025.index, weekly_2025['p_import_mw'], 'r-', linewidth=2, label='2025', alpha=0.8)
ax.set_ylabel('Potenza (MW)')
ax.set_title('Profilo Settimanale Medio - Import dalla Rete', fontweight='bold')
ax.legend()
ax.grid(True, alpha=0.3)

# Export
ax = axes[1]
ax.plot(weekly_2022.index, weekly_2022['p_export_mw'], 'b-', linewidth=2, label='2022', alpha=0.8)
ax.plot(weekly_2025.index, weekly_2025['p_export_mw'], 'r-', linewidth=2, label='2025', alpha=0.8)
ax.set_ylabel('Potenza (MW)')
ax.set_title('Profilo Settimanale Medio - Export alla Rete', fontweight='bold')
ax.legend()
ax.grid(True, alpha=0.3)

# ELY + FC
ax = axes[2]
ax.plot(weekly_2022.index, weekly_2022['p_ely_mw'], 'b-', linewidth=2, label='ELY 2022', alpha=0.8)
ax.plot(weekly_2025.index, weekly_2025['p_ely_mw'], 'r-', linewidth=2, label='ELY 2025', alpha=0.8)
ax.plot(weekly_2022.index, weekly_2022['p_fc_mw'], 'b--', linewidth=2, label='FC 2022', alpha=0.8)
ax.plot(weekly_2025.index, weekly_2025['p_fc_mw'], 'r--', linewidth=2, label='FC 2025', alpha=0.8)
ax.set_ylabel('Potenza (MW)')
ax.set_xlabel('Ora della Settimana')
ax.set_title('Profilo Settimanale Medio - Sistema H2 (ELY e FC)', fontweight='bold')
ax.legend()
ax.grid(True, alpha=0.3)

# Aggiungi etichette giorni
for ax in axes:
    for i, day in enumerate(['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']):
        ax.axvline(x=i*24, color='gray', linestyle=':', alpha=0.5)
        if ax == axes[2]:
            ax.text(i*24 + 12, ax.get_ylim()[1]*0.95, day, ha='center', fontsize=10)

plt.tight_layout()
plt.savefig('outputs/plots/profilo_settimanale_confronto.png', dpi=150, bbox_inches='tight')
plt.close()
print('7. Salvato: profilo_settimanale_confronto.png')

# ============================================================================
# GRAFICO 8: Riepilogo Finale - Tabella Visiva
# ============================================================================
fig, ax = plt.subplots(figsize=(14, 10))
ax.axis('off')

# Dati tabella
table_data = [
    ['Parametro', '2022', '2025', 'Variazione'],
    ['', '', '', ''],
    ['PREZZI', '', '', ''],
    ['PUN medio (EUR/MWh)', f'{324.22:.0f}', f'{116.42:.0f}', '-64%'],
    ['Import F1 (EUR/MWh)', '533', '164', '-69%'],
    ['Import F3 (EUR/MWh)', '469', '136', '-71%'],
    ['Costo DG cf=base (EUR/MWh)', '750', '233', '-69%'],
    ['', '', '', ''],
    ['ENERGIA (MWh)', '', '', ''],
    ['Import dalla rete', f'{e_2022["Import"]:,.0f}', f'{e_2025["Import"]:,.0f}', f'{(e_2025["Import"]-e_2022["Import"])/e_2022["Import"]*100:+.1f}%'],
    ['Export alla rete', f'{e_2022["Export"]:,.0f}', f'{e_2025["Export"]:,.0f}', f'{(e_2025["Export"]-e_2022["Export"])/e_2022["Export"]*100:+.1f}%'],
    ['ELY (carica H2)', f'{e_2022["ELY"]:,.0f}', f'{e_2025["ELY"]:,.0f}', f'{(e_2025["ELY"]-e_2022["ELY"])/e_2022["ELY"]*100:+.1f}%'],
    ['FC (scarica H2)', f'{e_2022["FC"]:,.0f}', f'{e_2025["FC"]:,.0f}', f'{(e_2025["FC"]-e_2022["FC"])/e_2022["FC"]*100:+.1f}%'],
    ['DG', f'{e_2022["DG"]:,.0f}', f'{e_2025["DG"]:,.0f}', 'N/A'],
    ['', '', '', ''],
    ['BILANCIO', '', '', ''],
    ['Energia IN totale', f'{in_2022:,.0f}', f'{in_2025:,.0f}', ''],
    ['Energia OUT totale', f'{out_2022:,.0f}', f'{out_2025:,.0f}', ''],
    ['Errore bilancio', f'{abs(in_2022-out_2022):.1f}', f'{abs(in_2025-out_2025):.1f}', ''],
]

# Crea tabella
table = ax.table(cellText=table_data, loc='center', cellLoc='center',
                 colWidths=[0.35, 0.2, 0.2, 0.15])
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.8)

# Formatta header
for j in range(4):
    table[(0, j)].set_facecolor('#4472C4')
    table[(0, j)].set_text_props(color='white', fontweight='bold')

# Formatta sezioni
for i in [2, 8, 15]:
    for j in range(4):
        table[(i, j)].set_facecolor('#D9E2F3')
        table[(i, j)].set_text_props(fontweight='bold')

ax.set_title('Riepilogo Confronto 2022 vs 2025', fontsize=16, fontweight='bold', pad=20)

plt.tight_layout()
plt.savefig('outputs/plots/riepilogo_confronto.png', dpi=150, bbox_inches='tight')
plt.close()
print('8. Salvato: riepilogo_confronto.png')

print('\n' + '='*60)
print('TUTTI I GRAFICI CREATI CON SUCCESSO!')
print('='*60)
print('\nFile salvati in outputs/plots/:')
print('  1. profilo_potenza_2022.png')
print('  2. profilo_potenza_2025.png')
print('  3. sistema_h2_2022.png')
print('  4. sistema_h2_2025.png')
print('  5. bilancio_energetico_confronto.png')
print('  6. bilancio_energetico_stacked.png')
print('  7. profilo_settimanale_confronto.png')
print('  8. riepilogo_confronto.png')

print('\n' + '='*60)
print('VERIFICA BILANCIO ENERGETICO')
print('='*60)
print(f'\n2022:')
print(f'  IN  = PV + Wind + Import + FC + DG = {in_2022:,.2f} MWh')
print(f'  OUT = Load + Export + ELY + Curt   = {out_2022:,.2f} MWh')
print(f'  Differenza: {abs(in_2022-out_2022):.2f} MWh ({abs(in_2022-out_2022)/in_2022*100:.4f}%)')

print(f'\n2025:')
print(f'  IN  = PV + Wind + Import + FC + DG = {in_2025:,.2f} MWh')
print(f'  OUT = Load + Export + ELY + Curt   = {out_2025:,.2f} MWh')
print(f'  Differenza: {abs(in_2025-out_2025):.2f} MWh ({abs(in_2025-out_2025)/in_2025*100:.4f}%)')
