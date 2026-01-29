"""
Modello di ottimizzazione MPC (Model Predictive Control) per la gestione energetica.

Questo modulo definisce e risolve il problema di ottimizzazione per un sistema energetico
ibrido composto da:
- Pannelli fotovoltaici (PV)
- Turbine eoliche (Wind)
- Elettrolizzatore per produzione idrogeno (Electrolyzer)
- Celle a combustibile (Fuel Cell)
- Generatore diesel (Diesel Generator)
- Sistema di stoccaggio idrogeno (H2 Storage)
- Connessione alla rete elettrica (Import/Export)

L'obiettivo e' minimizzare i costi operativi soddisfacendo il carico richiesto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import shutil

import cvxpy as cp
import numpy as np
import pandas as pd

# Importazione opzionale di PuLP (solver alternativo)
try:
    import pulp
except Exception:  # pragma: no cover - optional dependency
    pulp = None


@dataclass
class MPCResult:
    """
    Classe che contiene i risultati dell'ottimizzazione MPC.

    Attributi:
        schedule: DataFrame con lo scheduling orario delle potenze [MW] e stato di carica [MWh]
                  Colonne: p_import_mw, p_export_mw, p_ely_mw, p_fc_mw, p_dg_mw, p_curt_mw, soc_mwh
        objective_value: Valore della funzione obiettivo (costo totale in EUR)
    """
    schedule: pd.DataFrame
    objective_value: float


def _solve_with_pulp(
    load: np.ndarray,           # Carico elettrico richiesto [MW] per ogni ora
    pv: np.ndarray,             # Produzione fotovoltaica prevista [MW]
    wind: np.ndarray,           # Produzione eolica prevista [MW]
    import_price: np.ndarray,   # Prezzo di acquisto dalla rete [EUR/MWh]
    export_price: np.ndarray,   # Prezzo di vendita alla rete (PUN) [EUR/MWh]
    cfg: dict,                  # Configurazione del sistema
    soc_init_mwh: float,        # Stato di carica iniziale dello storage [MWh]
    fuel_price: float,          # Prezzo del combustibile diesel [EUR/MWh]
    dt: float,                  # Passo temporale [ore]
) -> MPCResult | None:
    """
    Risolve il problema di ottimizzazione usando PuLP come solver.

    Questa funzione e' un'alternativa al solver CVXPY e viene usata se disponibile
    il solver CBC (o Gurobi/HiGHS).

    Ritorna None se PuLP o CBC non sono disponibili.
    """
    # Verifica disponibilita' di PuLP e del solver CBC
    if pulp is None or shutil.which('cbc') is None:
        return None

    # Estrazione parametri di sistema dalla configurazione
    sys = cfg['system']
    horizon_h = len(load)  # Lunghezza dell'orizzonte di ottimizzazione [ore]
    eta_dg = float(sys.get('eta_dg', 0.6))  # Efficienza del generatore diesel [0-1]

    # Creazione del problema di ottimizzazione (minimizzazione)
    prob = pulp.LpProblem('mpc', pulp.LpMinimize)

    # ==================== VARIABILI DI DECISIONE ====================

    # Potenze continue [MW] - una variabile per ogni ora dell'orizzonte
    p_import = [pulp.LpVariable(f'p_import_{t}', lowBound=0) for t in range(horizon_h)]  # Potenza importata dalla rete
    p_export = [pulp.LpVariable(f'p_export_{t}', lowBound=0) for t in range(horizon_h)]  # Potenza esportata alla rete
    p_ely = [pulp.LpVariable(f'p_ely_{t}', lowBound=0) for t in range(horizon_h)]        # Potenza assorbita dall'elettrolizzatore
    p_fc = [pulp.LpVariable(f'p_fc_{t}', lowBound=0) for t in range(horizon_h)]          # Potenza prodotta dalla cella a combustibile
    p_dg = [pulp.LpVariable(f'p_dg_{t}', lowBound=0) for t in range(horizon_h)]          # Potenza prodotta dal generatore diesel
    p_curt = [pulp.LpVariable(f'p_curt_{t}', lowBound=0) for t in range(horizon_h)]      # Potenza curtailed (tagliata/sprecata)

    # Variabili binarie di accensione/spegnimento (1=acceso, 0=spento)
    u_dg = [pulp.LpVariable(f'u_dg_{t}', cat='Binary') for t in range(horizon_h)]    # Stato on/off generatore diesel
    u_ely = [pulp.LpVariable(f'u_ely_{t}', cat='Binary') for t in range(horizon_h)]  # Stato on/off elettrolizzatore
    u_fc = [pulp.LpVariable(f'u_fc_{t}', cat='Binary') for t in range(horizon_h)]    # Stato on/off cella a combustibile

    # Variabili binarie per mutua esclusione import/export
    u_import = [pulp.LpVariable(f'u_import_{t}', cat='Binary') for t in range(horizon_h)]  # 1 se si importa
    u_export = [pulp.LpVariable(f'u_export_{t}', cat='Binary') for t in range(horizon_h)]  # 1 se si esporta

    # Stato di carica dello storage idrogeno [MWh] (horizon_h + 1 perche' include stato iniziale)
    soc = [pulp.LpVariable(f'soc_{t}', lowBound=0, upBound=float(sys['h2_storage_mwh']))
           for t in range(horizon_h + 1)]

    # ==================== VINCOLI ====================

    # Vincolo: stato di carica iniziale
    prob += soc[0] == soc_init_mwh

    for t in range(horizon_h):
        # Vincolo di mutua esclusione: non si puo' importare ed esportare contemporaneamente
        prob += u_import[t] + u_export[t] <= 1

        # Vincoli di potenza massima (legati allo stato on/off)
        prob += p_import[t] <= float(sys['import_max_mw']) * u_import[t]  # Max potenza importabile
        prob += p_export[t] <= float(sys['export_max_mw']) * u_export[t]  # Max potenza esportabile

        # Vincoli min/max elettrolizzatore (se acceso deve operare tra min e nominale)
        prob += p_ely[t] <= float(sys['ely_nom_mw']) * u_ely[t]   # Potenza nominale elettrolizzatore
        prob += p_ely[t] >= float(sys['ely_min_mw']) * u_ely[t]   # Potenza minima tecnica elettrolizzatore

        # Vincoli min/max cella a combustibile
        prob += p_fc[t] <= float(sys['fc_nom_mw']) * u_fc[t]      # Potenza nominale fuel cell
        prob += p_fc[t] >= float(sys['fc_min_mw']) * u_fc[t]      # Potenza minima tecnica fuel cell

        # Vincoli min/max generatore diesel
        prob += p_dg[t] <= float(sys['dg_nom_mw']) * u_dg[t]      # Potenza nominale diesel
        prob += p_dg[t] >= float(sys['dg_min_mw']) * u_dg[t]      # Potenza minima tecnica diesel

        # Vincolo di bilancio energetico: generazione = consumo
        # Lato generazione: PV + Eolico + Import + Diesel + Fuel Cell
        # Lato consumo: Carico + Elettrolizzatore + Export + Curtailment
        prob += (
            pv[t] + wind[t] + p_import[t] + p_dg[t] + p_fc[t]
            == load[t] + p_ely[t] + p_export[t] + p_curt[t]
        )

        # Dinamica dello storage idrogeno:
        # SOC(t+1) = SOC(t) + dt * (energia_in - energia_out)
        # energia_in = eta_ely * p_ely (idrogeno prodotto dall'elettrolizzatore)
        # energia_out = p_fc / eta_fc (idrogeno consumato dalla fuel cell)
        prob += soc[t + 1] == soc[t] + dt * (
            float(sys['eta_ely']) * p_ely[t] - (1.0 / float(sys['eta_fc'])) * p_fc[t]
        )

    # ==================== FUNZIONE OBIETTIVO ====================

    curtail_penalty = 1.0  # Penalita' per energia curtailed [EUR/MWh]

    # Costo totale = Costo import - Ricavo export + Costo diesel + Penalita' curtailment
    objective = (
        # Costo dell'energia importata dalla rete
        pulp.lpSum(import_price[t] * p_import[t] * dt for t in range(horizon_h))
        # Ricavo dalla vendita di energia alla rete (sottratto perche' e' un guadagno)
        - pulp.lpSum(export_price[t] * p_export[t] * dt for t in range(horizon_h))
        # Costo del combustibile diesel (diviso per efficienza per ottenere energia primaria)
        + pulp.lpSum((fuel_price / eta_dg) * p_dg[t] * dt for t in range(horizon_h))
        # Penalita' per energia curtailed (incentiva a non sprecare energia)
        + pulp.lpSum(curtail_penalty * p_curt[t] * dt for t in range(horizon_h))
    )
    prob += objective

    # ==================== RISOLUZIONE ====================

    # Prova i solver in ordine di preferenza: Gurobi (piu' veloce) -> HiGHS -> CBC (fallback)
    try:
        solver = pulp.GUROBI(msg=False)
    except:
        try:
            solver = pulp.HiGHS(msg=False)
        except:
            solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)

    # ==================== COSTRUZIONE RISULTATI ====================

    # Crea DataFrame con lo scheduling ottimale
    schedule = pd.DataFrame(
        {
            'hour': np.arange(horizon_h),
            'p_import_mw': [pulp.value(v) for v in p_import],   # Potenza importata [MW]
            'p_export_mw': [pulp.value(v) for v in p_export],   # Potenza esportata [MW]
            'p_ely_mw': [pulp.value(v) for v in p_ely],         # Potenza elettrolizzatore [MW]
            'p_fc_mw': [pulp.value(v) for v in p_fc],           # Potenza fuel cell [MW]
            'p_dg_mw': [pulp.value(v) for v in p_dg],           # Potenza diesel [MW]
            'p_curt_mw': [pulp.value(v) for v in p_curt],       # Potenza curtailed [MW]
            'soc_mwh': [pulp.value(v) for v in soc[1:]],        # Stato di carica [MWh]
        }
    ).set_index('hour')

    return MPCResult(schedule=schedule, objective_value=float(pulp.value(prob.objective)))


def solve_horizon(
    df: pd.DataFrame,                       # DataFrame con i dati di input (previsioni, prezzi)
    cfg: dict,                              # Dizionario di configurazione del sistema
    start_hour: int,                        # Ora di inizio dell'orizzonte
    horizon_h: int,                         # Lunghezza dell'orizzonte [ore]
    soc_init_mwh: float = 0.0,              # Stato di carica iniziale [MWh]
    fuel_eur_per_kwh: float | None = None,  # Prezzo combustibile [EUR/kWh], se None usa config
) -> MPCResult:
    """
    Risolve il problema MPC per una singola finestra temporale (orizzonte).

    Questa e' la funzione principale da chiamare per ottenere lo scheduling ottimale.
    Prova prima il solver PuLP, se non disponibile usa CVXPY.

    Args:
        df: DataFrame contenente le colonne:
            - load_forecast_mw: previsione del carico [MW]
            - pv_forecast_mw: previsione produzione PV [MW]
            - wind_forecast_mw: previsione produzione eolica [MW]
            - import_price_eur_per_mwh: prezzo di acquisto [EUR/MWh]
            - pun_eur_per_mwh: prezzo di vendita (PUN) [EUR/MWh]
        cfg: Configurazione con parametri di sistema e prezzi
        start_hour: Indice dell'ora di inizio nel DataFrame
        horizon_h: Numero di ore da ottimizzare
        soc_init_mwh: Stato di carica iniziale dello storage idrogeno
        fuel_eur_per_kwh: Costo del combustibile diesel. Se None usa valore da config.

    Returns:
        MPCResult con schedule ottimale e valore della funzione obiettivo
    """
    # Estrazione parametri dalla configurazione
    dt = float(cfg['project']['timestep_h'])  # Passo temporale [ore]

    sys = cfg['system']
    h2_cap = float(sys['h2_storage_mwh'])  # Capacita' storage idrogeno [MWh]
    eta_ely = float(sys['eta_ely'])        # Efficienza elettrolizzatore [0-1]
    eta_fc = float(sys['eta_fc'])          # Efficienza fuel cell [0-1]

    # Estrazione della finestra temporale dal DataFrame
    idx = np.arange(start_hour, start_hour + horizon_h)
    block = df.loc[idx].copy()

    # Estrazione dei vettori di input per l'ottimizzazione
    load = block['load_forecast_mw'].to_numpy()   # Carico previsto [MW]
    pv = block['pv_forecast_mw'].to_numpy()       # Produzione PV prevista [MW]
    wind = block['wind_forecast_mw'].to_numpy()   # Produzione eolica prevista [MW]

    import_price = block['import_price_eur_per_mwh'].to_numpy()  # Prezzo acquisto [EUR/MWh]
    export_price = block['pun_eur_per_mwh'].to_numpy()           # Prezzo vendita PUN [EUR/MWh]

    # Conversione prezzo combustibile da EUR/kWh a EUR/MWh
    if fuel_eur_per_kwh is None:
        fuel_eur_per_kwh = float(cfg['prices']['fuel_eur_per_kwh'])
    fuel_price = fuel_eur_per_kwh * 1000.0  # [EUR/MWh]

    # ==================== TENTATIVO CON PULP ====================

    pulp_result = _solve_with_pulp(
        load=load,
        pv=pv,
        wind=wind,
        import_price=import_price,
        export_price=export_price,
        cfg=cfg,
        soc_init_mwh=soc_init_mwh,
        fuel_price=fuel_price,
        dt=dt,
    )
    if pulp_result is not None:
        pulp_result.schedule.index = idx  # Aggiorna indice con ore reali
        return pulp_result

    # ==================== FALLBACK A CVXPY ====================

    # Se PuLP non e' disponibile, usa CVXPY come solver alternativo

    # Variabili di decisione continue [MW]
    p_import = cp.Variable(horizon_h, nonneg=True)  # Potenza importata dalla rete
    p_export = cp.Variable(horizon_h, nonneg=True)  # Potenza esportata alla rete
    p_ely = cp.Variable(horizon_h, nonneg=True)     # Potenza elettrolizzatore
    p_fc = cp.Variable(horizon_h, nonneg=True)      # Potenza fuel cell
    p_dg = cp.Variable(horizon_h, nonneg=True)      # Potenza generatore diesel
    p_curt = cp.Variable(horizon_h, nonneg=True)    # Potenza curtailed

    # Variabili binarie on/off per unita' con potenza minima tecnica
    u_dg = cp.Variable(horizon_h, boolean=True)     # Stato on/off diesel
    u_ely = cp.Variable(horizon_h, boolean=True)    # Stato on/off elettrolizzatore
    u_fc = cp.Variable(horizon_h, boolean=True)     # Stato on/off fuel cell

    # Variabili binarie per mutua esclusione import/export
    u_import = cp.Variable(horizon_h, boolean=True)
    u_export = cp.Variable(horizon_h, boolean=True)

    # Stato di carica storage [MWh]
    soc = cp.Variable(horizon_h + 1)

    # ==================== VINCOLI CVXPY ====================

    constraints = [soc[0] == soc_init_mwh]  # Condizione iniziale

    # Mutua esclusione: non si puo' importare ed esportare contemporaneamente
    constraints += [u_import + u_export <= 1]

    # Vincoli di potenza massima (big-M constraints)
    constraints += [p_import <= float(sys['import_max_mw']) * u_import]
    constraints += [p_export <= float(sys['export_max_mw']) * u_export]

    # Vincoli min/max per elettrolizzatore
    constraints += [p_ely <= float(sys['ely_nom_mw']) * u_ely]
    constraints += [p_ely >= float(sys['ely_min_mw']) * u_ely]

    # Vincoli min/max per fuel cell
    constraints += [p_fc <= float(sys['fc_nom_mw']) * u_fc]
    constraints += [p_fc >= float(sys['fc_min_mw']) * u_fc]

    # Vincoli min/max per generatore diesel
    constraints += [p_dg <= float(sys['dg_nom_mw']) * u_dg]
    constraints += [p_dg >= float(sys['dg_min_mw']) * u_dg]

    # Vincoli sullo stato di carica dello storage
    constraints += [soc >= 0.0, soc <= h2_cap]

    # Bilancio energetico: generazione = consumo
    constraints += [
        pv + wind + p_import + p_dg + p_fc
        == load + p_ely + p_export + p_curt
    ]

    # Dinamica dello storage idrogeno (equazione di stato)
    constraints += [
        soc[1:] == soc[:-1] + dt * (eta_ely * p_ely - (1.0 / eta_fc) * p_fc)
    ]

    # ==================== FUNZIONE OBIETTIVO CVXPY ====================

    curtail_penalty = 1.0  # Penalita' per curtailment [EUR/MWh]
    eta_dg = float(sys.get('eta_dg', 0.6))  # Efficienza diesel

    # Costruzione del costo totale
    cost = cp.sum(cp.multiply(import_price, p_import) * dt)        # Costo import
    cost -= cp.sum(cp.multiply(export_price, p_export) * dt)       # Ricavo export (negativo)
    cost += cp.sum(cp.multiply(fuel_price / eta_dg, p_dg) * dt)    # Costo diesel
    cost += curtail_penalty * cp.sum(p_curt * dt)                  # Penalita' curtailment

    # ==================== RISOLUZIONE CVXPY ====================

    problem = cp.Problem(cp.Minimize(cost), constraints)

    # Prova i solver in ordine di preferenza: Gurobi -> CBC -> ECOS_BB (fallback)
    try:
        problem.solve(solver=cp.GUROBI, verbose=False)
    except Exception:
        try:
            problem.solve(solver=cp.CBC, verbose=False)
        except Exception:
            problem.solve(solver=cp.ECOS_BB, verbose=False)

    # ==================== COSTRUZIONE RISULTATI ====================

    schedule = pd.DataFrame(
        {
            'hour': idx,
            'p_import_mw': p_import.value,   # Potenza importata ottimale [MW]
            'p_export_mw': p_export.value,   # Potenza esportata ottimale [MW]
            'p_ely_mw': p_ely.value,         # Potenza elettrolizzatore ottimale [MW]
            'p_fc_mw': p_fc.value,           # Potenza fuel cell ottimale [MW]
            'p_dg_mw': p_dg.value,           # Potenza diesel ottimale [MW]
            'p_curt_mw': p_curt.value,       # Potenza curtailed ottimale [MW]
            'soc_mwh': soc.value[1:],        # Stato di carica ottimale [MWh]
        }
    ).set_index('hour')

    return MPCResult(schedule=schedule, objective_value=float(problem.value))
