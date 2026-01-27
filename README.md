# Sistema Energetico Integrato con Idrogeno - MPC

Sistema di ottimizzazione energetica basato su **Model Predictive Control (MPC)** per un distretto industriale con fonti rinnovabili, storage a idrogeno e scambio bidirezionale con la rete.

---

## Descrizione del progetto

Il sistema ottimizza ora per ora le decisioni energetiche per:
- **Minimizzare i costi** di approvvigionamento energetico
- **Massimizzare i ricavi** dalla vendita di energia
- **Soddisfare sempre il carico** elettrico
- **Minimizzare il curtailment** delle rinnovabili

### Schema del sistema

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
               +------+      |    +------+------+
                             |           |
                             |    +------v------+
                             |    | Storage H2  |
                             |    |   12 MWh    |
                             |    +-------------+
```

---

## Risultati principali

| Metrica | cf=0.45 | cf=0.60 |
|---------|--------:|--------:|
| Ore simulate | 6,528 | 6,528 |
| Costo netto | 17,527,353 EUR | 17,533,477 EUR |
| Costo per MWh | 367.83 EUR | 367.96 EUR |
| Energia DG | 128.76 MWh | **0 MWh** |
| Ore con DG attivo | 39 | **0** |

**Conclusione**: Il DG conviene solo per arbitraggio quando PUN > 750 EUR/MWh. Con cf=0.60 non viene mai usato.

---

## Quick Start

### 1. Installazione

```bash
# Clona il repository
git clone <repo-url>
cd Elettric_system

# Crea ambiente virtuale
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Installa dipendenze
pip install -r requirements.txt
```

### 2. Esegui simulazione MPC

```bash
# Esegue MPC rolling horizon per entrambi gli scenari (cf=0.45 e cf=0.60)
python src/run_mpc_full.py --horizon 24 --fuel-values 0.45,0.60
```

Output:
- `outputs/mpc_receding_cf045.csv` - Schedule orario (cf=0.45)
- `outputs/mpc_receding_cf060.csv` - Schedule orario (cf=0.60)

### 3. Genera report

```bash
# Report con metriche aggregate
python src/report.py --schedule outputs/mpc_receding_cf045.csv --out outputs/report_cf045.csv --fuel-cost 0.45 --plots

python src/report.py --schedule outputs/mpc_receding_cf060.csv --out outputs/report_cf060.csv --fuel-cost 0.60
```

### 4. Genera grafici dettagliati

```bash
# Grafici per la prima settimana
python src/plot_results.py --hours 168 --start 0

# Grafici per periodi specifici (Gennaio, Luglio, Ottobre)
python src/plot_results.py --all-periods
```

---

## Struttura del progetto

```
Elettric_system/
├── configs/
│   └── system.yaml           # Parametri del sistema (potenze, efficienze, prezzi)
│
├── data/
│   ├── buildings_load.mat    # Profilo di carico (6552 ore)
│   ├── PUN_2022.mat          # Prezzi PUN orari
│   ├── res_1_year_pu.mat     # Profili PV e Wind in p.u.
│   └── Projects.pdf          # Traccia del progetto
│
├── src/
│   ├── model.py              # Modello MPC/MILP (variabili, vincoli, obiettivo)
│   ├── run_mpc_full.py       # Loop MPC rolling horizon
│   ├── loader.py             # Caricamento dati da .mat
│   ├── tariff.py             # Tariffe ARERA (F1/F2/F3)
│   ├── report.py             # Generazione report e grafici base
│   └── plot_results.py       # Grafici dettagliati
│
├── outputs/
│   ├── mpc_receding_cf045.csv
│   ├── mpc_receding_cf060.csv
│   ├── DECISIONI_ORA_PER_ORA.csv
│   ├── report_cf045.csv
│   ├── report_cf060.csv
│   └── plots/
│
├── REPORT_FINALE.md          # Report completo con analisi
├── README.md                 # Questo file
└── requirements.txt          # Dipendenze Python
```

---

## Parametri del sistema

| Componente | Parametro | Valore |
|------------|-----------|--------|
| **PV** | Potenza nominale | 4.0 MW |
| **Wind** | Potenza nominale | 11.34 MW |
| **Load** | Potenza nominale | 20.0 MW |
| **Grid Import** | Potenza massima | 20.0 MW |
| **Grid Export** | Potenza massima | 16.0 MW |
| **Elettrolizzatore** | Nominale / Minimo | 7.0 / 0.7 MW |
| **Elettrolizzatore** | Efficienza | 70% |
| **Fuel Cell** | Nominale / Minimo | 7.0 / 0.7 MW |
| **Fuel Cell** | Efficienza | 60% |
| **Storage H2** | Capacita | 12.0 MWh |
| **Diesel Generator** | Nominale / Minimo | 5.0 / 1.0 MW |
| **Diesel Generator** | Efficienza | 60% |

---

## Metodologia MPC

### Rolling Horizon (4 step)

```
Per ogni ora t:
  1. RACCOGLI previsioni (PV, Wind, Load, Prezzi) per t → t+24
  2. RISOLVI ottimizzazione MILP su orizzonte 24h
  3. APPLICA solo la decisione per l'ora t
  4. AVANZA a t+1 e ripeti
```

### Bilancio energetico

```
P_pv + P_wind + P_import + P_dg + P_fc = P_load + P_ely + P_export + P_curt
```

### Funzione obiettivo

```
min: sum( c_import * P_import - PUN * P_export + (c_fuel/eta_dg) * P_dg + lambda * P_curt )
```

---

## File di output

### DECISIONI_ORA_PER_ORA.csv

Contiene per ogni ora le decisioni ottimali:

| Colonna | Descrizione |
|---------|-------------|
| datetime | Data e ora |
| load_MW | Carico da soddisfare |
| pv_MW, wind_MW | Produzione rinnovabili |
| cf045_import_MW | Import dalla rete (cf=0.45) |
| cf045_export_MW | Export alla rete (cf=0.45) |
| cf045_DG_MW | Potenza diesel (cf=0.45) |
| cf045_ELY_MW | Potenza elettrolizzatore |
| cf045_FC_MW | Potenza fuel cell |
| cf045_H2_SOC_MWh | Stato storage H2 |
| cf060_* | Stessi campi per cf=0.60 |

### Come leggere le decisioni

```
SE import_MW > 0    -> Compra dalla rete
SE export_MW > 0    -> Vendi alla rete
SE DG_MW > 0        -> Accendi il diesel
SE ELY_MW > 0       -> Carica storage H2
SE FC_MW > 0        -> Scarica storage H2
```

---

## Tariffe energia

### Import (ARERA)

| Fascia | Orario | Prezzo |
|--------|--------|--------|
| F1 | Lun-Ven 08-19 | 532.76 EUR/MWh |
| F2 | Lun-Ven 07-08, 19-23; Sab 07-23 | 548.58 EUR/MWh |
| F3 | Notti, Dom, Festivi | 468.68 EUR/MWh |

### Export (PUN)

- Prezzo variabile ora per ora (10-870 EUR/MWh)
- Media 2022: ~324 EUR/MWh

### Costo DG

| cf | Costo carburante | Costo elettrico |
|----|------------------|-----------------|
| 0.45 | 0.45 EUR/kWh | 750 EUR/MWh |
| 0.60 | 0.60 EUR/kWh | 1000 EUR/MWh |

---

## Solver

Il modello usa **MILP** (Mixed Integer Linear Programming) per gestire i vincoli di potenza minima.

### Solver supportati

1. **CBC** (consigliato) - via PuLP o CVXPY
2. **ECOS_BB** - fallback se CBC non disponibile

### Installazione CBC (opzionale, migliora performance)

```bash
# Con conda
conda install -c conda-forge coincbc

# Verifica
python -c "import shutil; print(shutil.which('cbc'))"
```

---

## Documentazione

- **[REPORT_FINALE.md](REPORT_FINALE.md)** - Report completo con:
  - Analisi dettagliata dei risultati
  - Spiegazione arbitraggio e strategie
  - Guida per estendere il modello
  - Teoria MPC per l'esame
  - Domande frequenti
  - Glossario dei termini

---

## Autori

Progetto sviluppato per il corso di Innovazione - UCBM

---

## Licenza

Progetto accademico - Tutti i diritti riservati
