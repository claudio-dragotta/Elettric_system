# Elettric_system

Project overview
- This repository contains data and a working pipeline for an energy system study with PV, wind, load, and price signals.
- The pipeline is described in `PIPELINE.md`.

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
