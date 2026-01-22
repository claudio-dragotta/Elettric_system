Pipeline for Elettric_system data

Goal
- Build a clean, aligned time-series dataset for renewables (PV, wind), building load, and prices.
- Produce forecast vs actual comparisons and cost/energy metrics.

Inputs (from data/)
- res_1_year_pu.mat: P_pv, P_w [8760 x 2], columns = [forecast, actual], p.u.
- buildings_load.mat: Pul [6552 x 3], columns = [hour, forecast_kWh, actual_kWh]
- PUN_2022.mat: pun [8760], price in EUR/MWh
- Projects.pdf: system data and price assumptions (see below)

System data (from Projects.pdf)
- PV nominal: 4 MW
- Wind nominal: 11.34 MW
- Load nominal: 20 MW (note: info.md says 16 MW, confirm)
- Import limit: P_i_max = 20 MW
- Export limit: P_e_max = 16 MW
- Electrolyzer: P_ely_nom = 7 MW, P_ely_min = 0.7 MW, eta_ely = 0.7
- Fuel cell: P_fc_nom = 7 MW, P_fc_min = 0.7 MW, eta_fc = 0.6
- H2 storage: E_h = 12 MWh
- Non-renewable DG: P_g_nom = 5 MW, P_g_min = 1 MW, eta_g = 0.6

Price assumptions (from Projects.pdf)
- Import energy price c_l: F1=0.53276, F2=0.54858, F3=0.46868 EUR/kWh
- Export energy price p_e: PUN (pun) EUR/MWh
- Fuel price for DG c_f: test with 0.45 and 0.60 EUR/kWh

Step 1 - Load and inspect
- Load MAT files and confirm shapes and ranges.
- Verify no unexpected NaN or negative values.
- Ensure arrays are float and in expected units.

Step 2 - Build time index
- Use hourly index for the price and renewables (8760 hours).
- For buildings load, use the first column as hour index (0-based or 1-based).
- Decide alignment rule:
  - Option A (intersect): keep only hours present in Pul.
  - Option B (full-year): create 8760 rows and place Pul values, leaving missing hours as NaN.

Step 3 - Unit normalization
- Buildings load is in kWh per hour. Convert to MW:
  - load_MW = load_kWh / 1000.0
- PV/Wind are in p.u. Convert to MW using installed capacities:
  - pv_MW = P_pv_pu * 4.0
  - wind_MW = P_w_pu * 11.34
- If load scaling is required (Pul "to be scaled"), apply factor here:
  - load_MW = load_MW * LOAD_SCALE

Step 4 - Create forecast/actual series
- Split all series into forecast and actual columns:
  - pv_forecast, pv_actual
  - wind_forecast, wind_actual
  - load_forecast, load_actual
- Build net load:
  - net_load_actual = load_actual - (pv_actual + wind_actual)
  - net_load_forecast = load_forecast - (pv_forecast + wind_forecast)

Step 5 - Price alignment and cost
- Align `pun` to the same hour index as the other series.
- Decide import price series c_l:
  - Option A: build hourly c_l from F1/F2/F3 schedule.
  - Option B: use a weighted or simple average.
- Compute hourly energy cost (EUR):
  - import_cost = max(net_load_MW, 0) * c_l_EUR_per_MWh
  - export_income = max(-net_load_MW, 0) * pun_EUR_per_MWh
  - net_cost = import_cost - export_income
- Produce forecast vs actual cost trajectories.

Step 6 - Metrics and validation
- Forecast accuracy:
  - MAE/RMSE for PV, wind, load, net load.
- Energy and cost summaries:
  - Total energy (MWh) and total cost (EUR) for actual vs forecast.
- Sanity checks:
  - Net load should not be negative if renewables are smaller than load.
  - Check peak and minimum values.

Step 7 - Visualizations (deliverables)
- Time series plots: forecast vs actual for PV, wind, load, net load, price.
- Monthly or weekly aggregates.
- Error distributions (histogram of forecast error).

Outputs
- Cleaned aligned dataset (CSV or MAT) with columns:
  - hour, price, pv_forecast, pv_actual, wind_forecast, wind_actual, load_forecast, load_actual, net_load_forecast, net_load_actual, cost_forecast, cost_actual
- Plots and metric report.

Open questions to finalize
- Confirm load nominal: 16 MW or 20 MW?
- Confirm Pul scaling factor (if any).
- Confirm whether to build hourly c_l (F1/F2/F3) or use an average.
- Should the analysis focus on the 6552 hours available for Pul or the full year with gaps?
