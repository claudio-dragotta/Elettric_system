# Sistema Energetico Integrato con Idrogeno (MPC)

Sistema di ottimizzazione energetica basato su **Model Predictive Control (MPC)** per un distretto industriale con fonti rinnovabili, storage a idrogeno e scambio bidirezionale con la rete.

---

## Panoramica

- Ottimizzazione oraria con strategia **receding horizon** (passo 1h, orizzonte 24h).
- Modello **MILP** con vincoli minimi tecnici e mutua esclusione import/export.
- Dati 2022 (PUN 2022) + scenario test 2025 (PUN 2025 e tariffe ARERA aggiornate).
- Report e grafici basati sulle **serie forecast** (coerenti con l'MPC).
- Output pronti per analisi comparativa 2022 vs 2025.

---

## Schema del sistema

```
                    +------------------+
                    |      RETE        |
                    | Import (max 20MW)|
                    | Export (max 16MW)|
                    +--------+---------+
                             |
    +------------+           |           +------------+
    |   PV 4MW   |----+      |      +----|  DG 5MW    |
    +------------+    |      |      |    +------------+
                      v      v      v
    +------------+  +-----------------+  +------------+
    | Wind 11MW  |->|   NODO ENERGIA  |<-| Fuel Cell  |
    +------------+  |   (bilancio)    |  |   7MW      |
                    +-----------------+  +------------+
                      |      |      |           ^
                      v      |      v           |
               +------+      |    +-------------+
               | LOAD |      |    | Elettroliz. |
               | 20MW |      |    |    7MW      |
               +------+      |    +------^------+
                             |           |
                             |    +------v------+
                             |    | Storage H2  |
                             |    |   12 MWh    |
                             |    +-------------+
```

---

## Dati e scenari

**Scenario 2022 (baseline)**
- RES e load da `data/res_1_year_pu.mat` e `data/buildings_load.mat`.
- PUN 2022 da `data/PUN_2022.mat`.
- Config: `configs/system.yaml`.

**Scenario 2025 (test)**
- Stessi profili RES/load del 2022.
- PUN 2025 da `test_2025/PUN_2025.mat`.
- Tariffe ARERA e costi combustibile 2025 in `test_2025/system_2025.yaml`.

**Periodo simulato:** 6,528 ore (~272 giorni), coerente con l'intersezione dei dati di carico.

---

## Risultati principali (forecast, output presenti nel repo)

| Metrica | 2022 cf=0.45 | 2025 cf=0.14 |
|---------|------------:|------------:|
| Ore simulate | 6,528 | 6,528 |
| Costo netto | 18,361,900 EUR | 5,400,369 EUR |
| Costo medio | 385.34 EUR/MWh | 113.33 EUR/MWh |
| Energia import | 36,568.61 MWh | 36,587.74 MWh |
| Energia export | 518.76 MWh | 547.89 MWh |
| Energia DG | 0.00 MWh | 0.00 MWh |

Dettagli completi: `outputs/tabella_comparativa_2022_2025.txt`.

---

## Quick Start

### 1) Installazione

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2) MPC 2022 (scenari cf=0.45 e cf=0.60)

```bash
python src/run_mpc_full.py --horizon 24 --fuel-values 0.45,0.60 --out outputs/mpc_2022.csv
```

Output:
- `outputs/mpc_2022_cf045.csv`
- `outputs/mpc_2022_cf060.csv`

### 3) Report + grafici base

```bash
python src/report.py --schedule outputs/mpc_2022_cf045.csv --out outputs/report_2022_cf045.csv --fuel-cost 0.45 --plots
python src/report.py --schedule outputs/mpc_2022_cf060.csv --out outputs/report_2022_cf060.csv --fuel-cost 0.60 --plots
```

Grafici in `outputs/plots/`:
`load_renewables.png`, `grid_dg.png`, `hydrogen.png`, `prices.png`.

### 4) Grafici avanzati (presentazioni)

```bash
python src/plot_results.py --schedule-45 outputs/mpc_2022_cf045.csv --schedule-60 outputs/mpc_2022_cf060.csv --hours 168 --start 0 --scenario both
```

### 5) Scenario 2025

```bash
# Se serve rigenerare il MAT dal file Excel
python test_2025/convert_pun.py

# Esegue gli scenari 2025 (24h + full) -> genera file *_24h e *_full
python test_2025/run_test_2025.py
```

Output consolidati per confronto (presenti nel repo):
- `test_2025/outputs_2025/mpc_2025_cf014.csv`
- `test_2025/outputs_2025/mpc_2025_cf020.csv`

### 6) Confronto 2022 vs 2025 (tabella + plot)

```bash
python generate_comparison_table.py > outputs/tabella_comparativa_2022_2025.txt
python create_all_plots.py
```

---

## Output principali

- Scheduling MPC 2022: `outputs/mpc_2022_cf045.csv`, `outputs/mpc_2022_cf060.csv`
- Scheduling MPC 2025: `test_2025/outputs_2025/mpc_2025_cf014.csv`, `test_2025/outputs_2025/mpc_2025_cf020.csv`
- Tabella comparativa: `outputs/tabella_comparativa_2022_2025.txt`
- Grafici comparativi e di sistema: `outputs/plots/*.png`
- Output storici: `outputs/vecchi/` e `test_2025/outputs_2025/vecchi/`

---

## Struttura del progetto

```
Elettric_system/
|-- configs/
|   |-- system.yaml               # Parametri sistema 2022 (potenze, efficienze, prezzi)
|-- data/
|   |-- buildings_load.mat        # Profilo di carico
|   |-- PUN_2022.mat               # Prezzi PUN 2022
|   |-- res_1_year_pu.mat          # Profili PV/Wind (forecast + actual)
|-- src/
|   |-- model.py                   # Modello MPC/MILP
|   |-- run_mpc_full.py            # MPC receding horizon
|   |-- loader.py                  # Caricamento dati + tariffe
|   |-- tariff.py                  # Fasce ARERA
|   |-- report.py                  # KPI + grafici base
|   |-- plot_results.py            # Grafici avanzati
|-- test_2025/
|   |-- system_2025.yaml           # Config 2025 (tariffe e fuel aggiornati)
|   |-- PUN_2025.mat               # Prezzi PUN 2025
|   |-- run_test_2025.py           # MPC 2025
|   |-- outputs_2025/              # Output scenario 2025
|-- outputs/
|   |-- mpc_2022_cf045.csv
|   |-- mpc_2022_cf060.csv
|   |-- tabella_comparativa_2022_2025.txt
|   |-- plots/
|   |-- vecchi/                    # Output legacy
|-- create_all_plots.py            # Plot comparativi 2022 vs 2025
|-- generate_comparison_table.py   # Tabella comparativa completa
|-- REPORT_FINALE.md               # Report completo
|-- GUIDA_PROGETTO.md              # Guida sintetica del progetto
|-- requirements.txt
```

---

## Parametri di sistema (fisici)

| Componente | Parametro | Valore |
|------------|-----------|--------|
| PV | Potenza nominale | 4.0 MW |
| Wind | Potenza nominale | 11.34 MW |
| Load | Potenza nominale | 20.0 MW |
| Grid Import | Potenza massima | 20.0 MW |
| Grid Export | Potenza massima | 16.0 MW |
| Elettrolizzatore | Nominale / Minimo | 7.0 / 0.7 MW |
| Elettrolizzatore | Efficienza | 70% |
| Fuel Cell | Nominale / Minimo | 7.0 / 0.7 MW |
| Fuel Cell | Efficienza | 60% |
| Storage H2 | Capacita | 12.0 MWh |
| Diesel Generator | Nominale / Minimo | 5.0 / 1.0 MW |
| Diesel Generator | Efficienza | 60% |

---

## Note di modello

- Bilancio energetico: `PV + Wind + Import + DG + FC = Load + ELY + Export + Curtailment`.
- SOC H2: `soc(t+1)=soc(t)+dt*(eta_ely*p_ely - p_fc/eta_fc)`.
- Import ed export sono mutuamente esclusivi (vincolo binario).
- Report e grafici usano **serie forecast** per coerenza con l'ottimizzazione MPC.

---

## Documentazione

- `REPORT_FINALE.md` (analisi completa)
- `GUIDA_PROGETTO.md` (guida sintetica)
- `Sistema-Energetico-Integrato-con-Idrogeno.pdf` (relazione estesa)

---

## Licenza

Progetto accademico - Tutti i diritti riservati
