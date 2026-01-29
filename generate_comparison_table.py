"""
Genera tabella comparativa completa 2022 vs 2025 con tutti gli scenari cf
"""
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'test_2025')
import pandas as pd
import numpy as np
import yaml
from pathlib import Path

# Carica dati 2022
cfg_2022 = yaml.safe_load(Path('configs/system.yaml').read_text(encoding='utf-8'))
from loader import load_timeseries, add_net_load
bundle_2022 = load_timeseries(Path('data'), cfg_2022)
df_2022 = add_net_load(bundle_2022.data)

# Carica dati 2025
cfg_2025 = yaml.safe_load(Path('test_2025/system_2025.yaml').read_text(encoding='utf-8'))
from run_test_2025 import load_timeseries_2025
bundle_2025 = load_timeseries_2025(Path('data'), Path('test_2025'), cfg_2025)
df_2025 = add_net_load(bundle_2025.data)

# Carica tutti gli schedule
sched_2022_cf045 = pd.read_csv('outputs/mpc_2022_cf045.csv').set_index('hour')
sched_2022_cf060 = pd.read_csv('outputs/mpc_2022_cf060.csv').set_index('hour')
sched_2025_cf014 = pd.read_csv('test_2025/outputs_2025/mpc_2025_cf014.csv').set_index('hour')
sched_2025_cf020 = pd.read_csv('test_2025/outputs_2025/mpc_2025_cf020.csv').set_index('hour')

eta_dg = cfg_2022['system']['eta_dg']
dt = 1.0

print('=' * 100)
print('TABELLA COMPARATIVA COMPLETA 2022 vs 2025 - TUTTI GLI SCENARI')
print('=' * 100)

# ============================================================================
# 1. PREZZI DI MERCATO (PUN)
# ============================================================================
print('\n' + '=' * 100)
print('1. PREZZI DI MERCATO (PUN - Prezzo Export)')
print('=' * 100)
fmt = '{:<25} {:>20} {:>20} {:>15}'
print(fmt.format('Statistica', '2022', '2025', 'Variazione'))
print('-' * 80)

pun_2022 = df_2022['pun_eur_per_mwh']
pun_2025 = df_2025['pun_eur_per_mwh']

stats = [
    ('Minimo', pun_2022.min(), pun_2025.min()),
    ('Massimo', pun_2022.max(), pun_2025.max()),
    ('Media', pun_2022.mean(), pun_2025.mean()),
    ('Mediana', pun_2022.median(), pun_2025.median()),
    ('Deviazione Std', pun_2022.std(), pun_2025.std()),
    ('Percentile 10', pun_2022.quantile(0.10), pun_2025.quantile(0.10)),
    ('Percentile 25', pun_2022.quantile(0.25), pun_2025.quantile(0.25)),
    ('Percentile 75', pun_2022.quantile(0.75), pun_2025.quantile(0.75)),
    ('Percentile 90', pun_2022.quantile(0.90), pun_2025.quantile(0.90)),
    ('Percentile 95', pun_2022.quantile(0.95), pun_2025.quantile(0.95)),
]

for name, v22, v25 in stats:
    var = ((v25 - v22) / v22 * 100) if v22 != 0 else 0
    print(fmt.format(name, f'{v22:.2f} EUR/MWh', f'{v25:.2f} EUR/MWh', f'{var:+.1f}%'))

# ============================================================================
# 2. PREZZI IMPORT (Tariffe ARERA)
# ============================================================================
print('\n' + '=' * 100)
print('2. PREZZI IMPORT (Tariffe ARERA)')
print('=' * 100)
print(fmt.format('Fascia', '2022', '2025', 'Variazione'))
print('-' * 80)

tariffe = [
    ('F1 (ore punta)', cfg_2022['prices']['import_f1_eur_per_kwh'] * 1000, cfg_2025['prices']['import_f1_eur_per_kwh'] * 1000),
    ('F2 (ore intermedie)', cfg_2022['prices']['import_f2_eur_per_kwh'] * 1000, cfg_2025['prices']['import_f2_eur_per_kwh'] * 1000),
    ('F3 (fuori punta)', cfg_2022['prices']['import_f3_eur_per_kwh'] * 1000, cfg_2025['prices']['import_f3_eur_per_kwh'] * 1000),
]

for name, v22, v25 in tariffe:
    var = ((v25 - v22) / v22 * 100)
    print(fmt.format(name, f'{v22:.2f} EUR/MWh', f'{v25:.2f} EUR/MWh', f'{var:+.1f}%'))

# ============================================================================
# 3. COSTI OPERATIVI - TUTTI GLI SCENARI
# ============================================================================
print('\n' + '=' * 100)
print('3. COSTI COMBUSTIBILE E DG - TUTTI GLI SCENARI')
print('=' * 100)
fmt3 = '{:<20} {:>20} {:>20} {:>20} {:>20}'
print(fmt3.format('Parametro', '2022 cf=0.45', '2022 cf=0.60', '2025 cf=0.14', '2025 cf=0.20'))
print('-' * 100)

cf_values = [0.45, 0.60, 0.14, 0.20]
dg_costs = [cf / eta_dg * 1000 for cf in cf_values]

print(fmt3.format('cf (EUR/kWh)', '0.45', '0.60', '0.14', '0.20'))
print(fmt3.format('Costo DG (EUR/MWh)', f'{dg_costs[0]:.0f}', f'{dg_costs[1]:.0f}', f'{dg_costs[2]:.0f}', f'{dg_costs[3]:.0f}'))

# ============================================================================
# 4. FLUSSI ENERGETICI - TUTTI GLI SCENARI
# ============================================================================
print('\n' + '=' * 100)
print('4. FLUSSI ENERGETICI (MWh) - TUTTI GLI SCENARI')
print('=' * 100)
print(fmt3.format('Flusso', '2022 cf=0.45', '2022 cf=0.60', '2025 cf=0.14', '2025 cf=0.20'))
print('-' * 100)

schedules = [sched_2022_cf045, sched_2022_cf060, sched_2025_cf014, sched_2025_cf020]
labels = ['2022 cf=0.45', '2022 cf=0.60', '2025 cf=0.14', '2025 cf=0.20']

flussi_names = [
    ('Import dalla rete', 'p_import_mw'),
    ('Export alla rete', 'p_export_mw'),
    ('Diesel Generator (DG)', 'p_dg_mw'),
    ('Elettrolizzatore (ELY)', 'p_ely_mw'),
    ('Fuel Cell (FC)', 'p_fc_mw'),
    ('Curtailment', 'p_curt_mw'),
]

for name, col in flussi_names:
    values = [f'{s[col].sum() * dt:.2f}' for s in schedules]
    print(fmt3.format(name, *values))

# ============================================================================
# 5. UTILIZZO DG - DETTAGLIO
# ============================================================================
print('\n' + '=' * 100)
print('5. UTILIZZO DIESEL GENERATOR (DG) - DETTAGLIO')
print('=' * 100)
print(fmt3.format('Parametro', '2022 cf=0.45', '2022 cf=0.60', '2025 cf=0.14', '2025 cf=0.20'))
print('-' * 100)

dg_energy = [s['p_dg_mw'].sum() * dt for s in schedules]
dg_hours = [(s['p_dg_mw'] > 0.001).sum() for s in schedules]
dg_max = [s['p_dg_mw'].max() for s in schedules]
dg_mean_when_on = []
for s in schedules:
    dg_on = s[s['p_dg_mw'] > 0.001]['p_dg_mw']
    dg_mean_when_on.append(dg_on.mean() if len(dg_on) > 0 else 0)

print(fmt3.format('Energia DG (MWh)', *[f'{v:.2f}' for v in dg_energy]))
print(fmt3.format('Ore DG attivo', *[str(v) for v in dg_hours]))
print(fmt3.format('% tempo DG attivo', *[f'{v/6528*100:.2f}%' for v in dg_hours]))
print(fmt3.format('Potenza max DG (MW)', *[f'{v:.2f}' for v in dg_max]))
print(fmt3.format('Potenza media DG (MW)', *[f'{v:.2f}' for v in dg_mean_when_on]))

# Costo DG
dg_costs_eur = [dg_energy[i] * (cf_values[i] / eta_dg * 1000) for i in range(4)]
print(fmt3.format('Costo DG (EUR)', *[f'{v:,.0f}' for v in dg_costs_eur]))

# ============================================================================
# 6. STATISTICHE OPERATIVE
# ============================================================================
print('\n' + '=' * 100)
print('6. STATISTICHE OPERATIVE')
print('=' * 100)
print(fmt3.format('Statistica', '2022 cf=0.45', '2022 cf=0.60', '2025 cf=0.14', '2025 cf=0.20'))
print('-' * 100)

stats_data = []
for s in schedules:
    stats_data.append({
        'ore': len(s),
        'export': (s['p_export_mw'] > 0.001).sum(),
        'dg': (s['p_dg_mw'] > 0.001).sum(),
        'ely': (s['p_ely_mw'] > 0.001).sum(),
        'fc': (s['p_fc_mw'] > 0.001).sum(),
        'simult': ((s['p_import_mw'] > 0.001) & (s['p_export_mw'] > 0.001)).sum(),
    })

print(fmt3.format('Ore totali', *[str(d['ore']) for d in stats_data]))
print(fmt3.format('Ore con Export', *[str(d['export']) for d in stats_data]))
print(fmt3.format('Ore con DG', *[str(d['dg']) for d in stats_data]))
print(fmt3.format('Ore con ELY', *[str(d['ely']) for d in stats_data]))
print(fmt3.format('Ore con FC', *[str(d['fc']) for d in stats_data]))
print(fmt3.format('Ore Import+Export', *[str(d['simult']) for d in stats_data]))

# ============================================================================
# 7. SISTEMA IDROGENO
# ============================================================================
print('\n' + '=' * 100)
print('7. SISTEMA IDROGENO (H2)')
print('=' * 100)
print(fmt3.format('Parametro', '2022 cf=0.45', '2022 cf=0.60', '2025 cf=0.14', '2025 cf=0.20'))
print('-' * 100)

h2_cap = cfg_2022['system']['h2_storage_mwh']
eta_ely = cfg_2022['system']['eta_ely']
eta_fc = cfg_2022['system']['eta_fc']

ely_vals = [s['p_ely_mw'].sum() * dt for s in schedules]
fc_vals = [s['p_fc_mw'].sum() * dt for s in schedules]
cycles = [(ely_vals[i] + fc_vals[i]) / (2 * h2_cap) for i in range(4)]
eff = [fc_vals[i] / ely_vals[i] * 100 if ely_vals[i] > 0 else 0 for i in range(4)]

print(fmt3.format('Capacita H2 (MWh)', *[f'{h2_cap}' for _ in range(4)]))
print(fmt3.format('Energia ELY (MWh)', *[f'{v:.2f}' for v in ely_vals]))
print(fmt3.format('Energia FC (MWh)', *[f'{v:.2f}' for v in fc_vals]))
print(fmt3.format('Cicli equivalenti', *[f'{v:.1f}' for v in cycles]))
print(fmt3.format('Efficienza reale (%)', *[f'{v:.1f}%' for v in eff]))

# ============================================================================
# 8. ANALISI ECONOMICA
# ============================================================================
print('\n' + '=' * 100)
print('8. ANALISI ECONOMICA (EUR)')
print('=' * 100)
print(fmt3.format('Voce', '2022 cf=0.45', '2022 cf=0.60', '2025 cf=0.14', '2025 cf=0.20'))
print('-' * 100)

# Merge con dati prezzi
merged_2022 = df_2022.copy()
merged_2025 = df_2025.copy()

dfs = [df_2022, df_2022, df_2025, df_2025]
cfs = [0.45, 0.60, 0.14, 0.20]

cost_import = []
income_export = []
cost_dg = []
net_cost = []

for i, (df, s, cf) in enumerate(zip(dfs, schedules, cfs)):
    merged = df.join(s, how='inner')
    ci = (merged['p_import_mw'] * merged['import_price_eur_per_mwh'] * dt).sum()
    ie = (merged['p_export_mw'] * merged['pun_eur_per_mwh'] * dt).sum()
    cd = (merged['p_dg_mw'] * (cf * 1000 / eta_dg) * dt).sum()
    cost_import.append(ci)
    income_export.append(ie)
    cost_dg.append(cd)
    net_cost.append(ci - ie + cd)

print(fmt3.format('Costo Import', *[f'{v:,.0f}' for v in cost_import]))
print(fmt3.format('Ricavo Export', *[f'{v:,.0f}' for v in income_export]))
print(fmt3.format('Costo DG', *[f'{v:,.0f}' for v in cost_dg]))
print(fmt3.format('COSTO NETTO', *[f'{v:,.0f}' for v in net_cost]))

# Carico totale
load_2022 = (df_2022.loc[sched_2022_cf045.index, 'load_actual_mw'] * dt).sum()
load_2025 = (df_2025.loc[sched_2025_cf014.index, 'load_actual_mw'] * dt).sum()
loads = [load_2022, load_2022, load_2025, load_2025]

print()
print(fmt3.format('Carico totale (MWh)', *[f'{v:,.0f}' for v in loads]))

cpm = [net_cost[i] / loads[i] for i in range(4)]
print(fmt3.format('Costo medio (EUR/MWh)', *[f'{v:.2f}' for v in cpm]))

# ============================================================================
# 9. CONFRONTO SINTETICO
# ============================================================================
print('\n' + '=' * 100)
print('9. CONFRONTO SINTETICO 2022 vs 2025')
print('=' * 100)
fmt2 = '{:<40} {:>25} {:>25}'
print(fmt2.format('Parametro', '2022 (media scenari)', '2025 (media scenari)'))
print('-' * 90)

# Medie
avg_import_22 = (schedules[0]['p_import_mw'].sum() + schedules[1]['p_import_mw'].sum()) / 2 * dt
avg_import_25 = (schedules[2]['p_import_mw'].sum() + schedules[3]['p_import_mw'].sum()) / 2 * dt
avg_export_22 = (schedules[0]['p_export_mw'].sum() + schedules[1]['p_export_mw'].sum()) / 2 * dt
avg_export_25 = (schedules[2]['p_export_mw'].sum() + schedules[3]['p_export_mw'].sum()) / 2 * dt
avg_dg_22 = (schedules[0]['p_dg_mw'].sum() + schedules[1]['p_dg_mw'].sum()) / 2 * dt
avg_dg_25 = (schedules[2]['p_dg_mw'].sum() + schedules[3]['p_dg_mw'].sum()) / 2 * dt
avg_cost_22 = (net_cost[0] + net_cost[1]) / 2
avg_cost_25 = (net_cost[2] + net_cost[3]) / 2
avg_cpm_22 = (cpm[0] + cpm[1]) / 2
avg_cpm_25 = (cpm[2] + cpm[3]) / 2

print(fmt2.format('PUN medio (EUR/MWh)', f'{pun_2022.mean():.2f}', f'{pun_2025.mean():.2f}'))
print(fmt2.format('Import medio F1 (EUR/MWh)', f'{cfg_2022["prices"]["import_f1_eur_per_kwh"]*1000:.2f}', f'{cfg_2025["prices"]["import_f1_eur_per_kwh"]*1000:.2f}'))
print(fmt2.format('Import (MWh)', f'{avg_import_22:,.0f}', f'{avg_import_25:,.0f}'))
print(fmt2.format('Export (MWh)', f'{avg_export_22:,.0f}', f'{avg_export_25:,.0f}'))
print(fmt2.format('DG (MWh)', f'{avg_dg_22:,.0f}', f'{avg_dg_25:,.0f}'))
print(fmt2.format('Costo netto medio (EUR)', f'{avg_cost_22:,.0f}', f'{avg_cost_25:,.0f}'))
print(fmt2.format('Costo medio per MWh (EUR/MWh)', f'{avg_cpm_22:.2f}', f'{avg_cpm_25:.2f}'))

var_cost = (avg_cost_25 - avg_cost_22) / avg_cost_22 * 100
print()
print(f'RISPARMIO 2025 vs 2022: {-var_cost:.1f}%')

# ============================================================================
# 10. CONFIGURAZIONE SISTEMA
# ============================================================================
print('\n' + '=' * 100)
print('10. CONFIGURAZIONE SISTEMA (invariata)')
print('=' * 100)
fmt_sys = '{:<35} {:>15}'
print(fmt_sys.format('Parametro', 'Valore'))
print('-' * 55)

sys_params = [
    ('PV nominale', f"{cfg_2022['system']['pv_nom_mw']} MW"),
    ('Wind nominale', f"{cfg_2022['system']['wind_nom_mw']} MW"),
    ('Carico nominale', f"{cfg_2022['system']['load_nom_mw']} MW"),
    ('Import max', f"{cfg_2022['system']['import_max_mw']} MW"),
    ('Export max', f"{cfg_2022['system']['export_max_mw']} MW"),
    ('ELY nominale', f"{cfg_2022['system']['ely_nom_mw']} MW"),
    ('FC nominale', f"{cfg_2022['system']['fc_nom_mw']} MW"),
    ('DG nominale', f"{cfg_2022['system']['dg_nom_mw']} MW"),
    ('Storage H2', f"{cfg_2022['system']['h2_storage_mwh']} MWh"),
    ('Efficienza ELY', f"{cfg_2022['system']['eta_ely']*100:.0f}%"),
    ('Efficienza FC', f"{cfg_2022['system']['eta_fc']*100:.0f}%"),
    ('Efficienza DG', f"{cfg_2022['system']['eta_dg']*100:.0f}%"),
    ('Horizon MPC', f"{cfg_2022['project']['horizon_h']} h"),
]

for name, val in sys_params:
    print(fmt_sys.format(name, val))

print('\n' + '=' * 100)
print('NOTE:')
print('=' * 100)
print('- Il modello include vincolo di MUTUA ESCLUSIONE import/export (non simultanei)')
print('- Export avviene SOLO da surplus rinnovabili, NON da arbitraggio')
print('- DG MAI usato in nessuno scenario perche:')
print('    2022: Costo DG (750-1000 EUR/MWh) > Import F3 (469 EUR/MWh)')
print('    2025: Costo DG (233-333 EUR/MWh) > Import F3 (136 EUR/MWh)')
print('- Sistema H2 usato per gestire picchi di surplus RES (pochi cicli/anno)')
print('- Periodo simulato: ~272 giorni (6528 ore)')
print('=' * 100)
