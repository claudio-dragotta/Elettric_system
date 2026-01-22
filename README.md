# Elettric_system

Project overview

- This repository contains data and a working pipeline for an energy system study with PV, wind, load, and price signals.
- The pipeline is described in `PIPELINE.md`.
- The final write-up is in [REPORT_FINALE.md](REPORT_FINALE.md).
- Configuration lives in `configs/system.yaml` (all model parameters and scenarios).

Data files

- `data/res_1_year_pu.mat`: PV and wind profiles in p.u. (forecast and actual).
- `data/buildings_load.mat`: building load (hour, forecast kWh, actual kWh).
- `data/PUN_2022.mat`: price series (EUR/MWh).
- `data/Projects.pdf`: project assumptions and system data.

Key assumptions

- PV nominal: 4 MW.
- Wind nominal: 11.34 MW.
- Load nominal: 20 MW (to be confirmed).
- Import/export price assumptions are in `data/Projects.pdf`.

Next steps

- Confirm load nominal and scaling for `Pul`.
- Decide how to build the hourly import price series (F1/F2/F3).
- Run the pipeline and produce metrics and plots.

Quick start (Python)

- `pip install -r requirements.txt`
- `python src/run_mpc.py --horizon 24 --start 0 --out outputs/mpc_schedule.csv`
- `python src/run_mpc_full.py --horizon 24 --start 0 --out outputs/mpc_receding.csv`

Scenarios

- `configs/system.yaml` supports `load_nom_mw_values` (default: 16 and 20 MW).
- Default load nominal is 20 MW.
- To use 16 MW, run: `python src/run_mpc.py --load-nom 16`
- For both scenarios: `python src/run_mpc_full.py --load-nom-values 16,20`

Reports

- Build summary metrics: `python src/report.py --schedule outputs/mpc_receding.csv --out outputs/report.csv`
- Build metrics + plots: `python src/report.py --schedule outputs/mpc_receding.csv --out outputs/report.csv --plots`

Solver note (MIP)

The model uses CBC via PuLP if available, otherwise falls back to ECOS_BB.

CBC setup (Windows, recommended)

1) Install Anaconda or Miniconda.
2) Open PowerShell and initialize conda:
   - `conda init powershell`
   - close and reopen the terminal
3) Create and activate a dedicated environment:
   - `conda create -n elettric python=3.12 -y`
   - `conda activate elettric`
4) Install dependencies with CBC and PuLP:
   - `conda install -n elettric -c conda-forge cvxpy coincbc coin-or-cbc numpy pandas scipy pyyaml matplotlib pulp tqdm -y`
5) Verify CBC:
   - `where.exe cbc`
   - `python -c "import shutil; print(shutil.which('cbc'))"`
6) Run:
   - `python src/run_mpc_full.py --horizon 24 --start 0 --out outputs/mpc_receding.csv`
