"""Define and solve the MPC optimization model for one horizon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import shutil

import cvxpy as cp
import numpy as np
import pandas as pd

try:
    import pulp
except Exception:  # pragma: no cover - optional dependency
    pulp = None


@dataclass
class MPCResult:
    schedule: pd.DataFrame
    objective_value: float


def _solve_with_pulp(
    load: np.ndarray,
    pv: np.ndarray,
    wind: np.ndarray,
    import_price: np.ndarray,
    export_price: np.ndarray,
    cfg: dict,
    soc_init_mwh: float,
    fuel_price: float,
    dt: float,
) -> MPCResult | None:
    if pulp is None or shutil.which('cbc') is None:
        return None

    sys = cfg['system']
    horizon_h = len(load)
    eta_dg = float(sys.get('eta_dg', 0.6))

    prob = pulp.LpProblem('mpc', pulp.LpMinimize)

    p_import = [pulp.LpVariable(f'p_import_{t}', lowBound=0) for t in range(horizon_h)]
    p_export = [pulp.LpVariable(f'p_export_{t}', lowBound=0) for t in range(horizon_h)]
    p_ely = [pulp.LpVariable(f'p_ely_{t}', lowBound=0) for t in range(horizon_h)]
    p_fc = [pulp.LpVariable(f'p_fc_{t}', lowBound=0) for t in range(horizon_h)]
    p_dg = [pulp.LpVariable(f'p_dg_{t}', lowBound=0) for t in range(horizon_h)]
    p_curt = [pulp.LpVariable(f'p_curt_{t}', lowBound=0) for t in range(horizon_h)]

    u_dg = [pulp.LpVariable(f'u_dg_{t}', cat='Binary') for t in range(horizon_h)]
    u_ely = [pulp.LpVariable(f'u_ely_{t}', cat='Binary') for t in range(horizon_h)]
    u_fc = [pulp.LpVariable(f'u_fc_{t}', cat='Binary') for t in range(horizon_h)]

    soc = [pulp.LpVariable(f'soc_{t}', lowBound=0, upBound=float(sys['h2_storage_mwh']))
           for t in range(horizon_h + 1)]

    prob += soc[0] == soc_init_mwh

    for t in range(horizon_h):
        prob += p_import[t] <= float(sys['import_max_mw'])
        prob += p_export[t] <= float(sys['export_max_mw'])
        prob += p_ely[t] <= float(sys['ely_nom_mw']) * u_ely[t]
        prob += p_ely[t] >= float(sys['ely_min_mw']) * u_ely[t]
        prob += p_fc[t] <= float(sys['fc_nom_mw']) * u_fc[t]
        prob += p_fc[t] >= float(sys['fc_min_mw']) * u_fc[t]
        prob += p_dg[t] <= float(sys['dg_nom_mw']) * u_dg[t]
        prob += p_dg[t] >= float(sys['dg_min_mw']) * u_dg[t]

        prob += (
            pv[t] + wind[t] + p_import[t] + p_dg[t] + p_fc[t]
            == load[t] + p_ely[t] + p_export[t] + p_curt[t]
        )

        prob += soc[t + 1] == soc[t] + dt * (
            float(sys['eta_ely']) * p_ely[t] - (1.0 / float(sys['eta_fc'])) * p_fc[t]
        )

    curtail_penalty = 1.0
    objective = (
        pulp.lpSum(import_price[t] * p_import[t] * dt for t in range(horizon_h))
        - pulp.lpSum(export_price[t] * p_export[t] * dt for t in range(horizon_h))
        + pulp.lpSum((fuel_price / eta_dg) * p_dg[t] * dt for t in range(horizon_h))
        + pulp.lpSum(curtail_penalty * p_curt[t] * dt for t in range(horizon_h))
    )
    prob += objective

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)

    schedule = pd.DataFrame(
        {
            'hour': np.arange(horizon_h),
            'p_import_mw': [pulp.value(v) for v in p_import],
            'p_export_mw': [pulp.value(v) for v in p_export],
            'p_ely_mw': [pulp.value(v) for v in p_ely],
            'p_fc_mw': [pulp.value(v) for v in p_fc],
            'p_dg_mw': [pulp.value(v) for v in p_dg],
            'p_curt_mw': [pulp.value(v) for v in p_curt],
            'soc_mwh': [pulp.value(v) for v in soc[1:]],
        }
    ).set_index('hour')

    return MPCResult(schedule=schedule, objective_value=float(pulp.value(prob.objective)))


def solve_horizon(
    df: pd.DataFrame,
    cfg: dict,
    start_hour: int,
    horizon_h: int,
    soc_init_mwh: float = 0.0,
    fuel_eur_per_kwh: float | None = None,
) -> MPCResult:
    """Solve MPC for a single horizon window.

    Args:
        fuel_eur_per_kwh: Fuel cost in EUR/kWh. If None, uses config value.
    """
    dt = float(cfg['project']['timestep_h'])

    sys = cfg['system']
    h2_cap = float(sys['h2_storage_mwh'])
    eta_ely = float(sys['eta_ely'])
    eta_fc = float(sys['eta_fc'])

    idx = np.arange(start_hour, start_hour + horizon_h)
    block = df.loc[idx].copy()

    load = block['load_forecast_mw'].to_numpy()
    pv = block['pv_forecast_mw'].to_numpy()
    wind = block['wind_forecast_mw'].to_numpy()

    import_price = block['import_price_eur_per_mwh'].to_numpy()
    export_price = block['pun_eur_per_mwh'].to_numpy()

    if fuel_eur_per_kwh is None:
        fuel_eur_per_kwh = float(cfg['prices']['fuel_eur_per_kwh'])
    fuel_price = fuel_eur_per_kwh * 1000.0

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
        pulp_result.schedule.index = idx
        return pulp_result

    # Decision variables (MW)
    p_import = cp.Variable(horizon_h, nonneg=True)
    p_export = cp.Variable(horizon_h, nonneg=True)
    p_ely = cp.Variable(horizon_h, nonneg=True)
    p_fc = cp.Variable(horizon_h, nonneg=True)
    p_dg = cp.Variable(horizon_h, nonneg=True)
    p_curt = cp.Variable(horizon_h, nonneg=True)

    # Binary on/off for units with minimum technical power.
    u_dg = cp.Variable(horizon_h, boolean=True)
    u_ely = cp.Variable(horizon_h, boolean=True)
    u_fc = cp.Variable(horizon_h, boolean=True)

    soc = cp.Variable(horizon_h + 1)

    constraints = [soc[0] == soc_init_mwh]

    constraints += [p_import <= float(sys['import_max_mw'])]
    constraints += [p_export <= float(sys['export_max_mw'])]
    constraints += [p_ely <= float(sys['ely_nom_mw']) * u_ely]
    constraints += [p_ely >= float(sys['ely_min_mw']) * u_ely]
    constraints += [p_fc <= float(sys['fc_nom_mw']) * u_fc]
    constraints += [p_fc >= float(sys['fc_min_mw']) * u_fc]
    constraints += [p_dg <= float(sys['dg_nom_mw']) * u_dg]
    constraints += [p_dg >= float(sys['dg_min_mw']) * u_dg]

    constraints += [soc >= 0.0, soc <= h2_cap]

    # Energy balance
    constraints += [
        pv + wind + p_import + p_dg + p_fc
        == load + p_ely + p_export + p_curt
    ]

    # Storage dynamics (MWh)
    constraints += [
        soc[1:] == soc[:-1] + dt * (eta_ely * p_ely - (1.0 / eta_fc) * p_fc)
    ]

    curtail_penalty = 1.0
    eta_dg = float(sys.get('eta_dg', 0.6))

    cost = cp.sum(cp.multiply(import_price, p_import) * dt)
    cost -= cp.sum(cp.multiply(export_price, p_export) * dt)
    cost += cp.sum(cp.multiply(fuel_price / eta_dg, p_dg) * dt)
    cost += curtail_penalty * cp.sum(p_curt * dt)

    problem = cp.Problem(cp.Minimize(cost), constraints)
    try:
        problem.solve(solver=cp.CBC, verbose=False)
    except Exception:
        # Fallback if CBC is not available in the environment.
        problem.solve(solver=cp.ECOS_BB, verbose=False)

    schedule = pd.DataFrame(
        {
            'hour': idx,
            'p_import_mw': p_import.value,
            'p_export_mw': p_export.value,
            'p_ely_mw': p_ely.value,
            'p_fc_mw': p_fc.value,
            'p_dg_mw': p_dg.value,
            'p_curt_mw': p_curt.value,
            'soc_mwh': soc.value[1:],
        }
    ).set_index('hour')

    return MPCResult(schedule=schedule, objective_value=float(problem.value))
