# Guida Completa al Progetto MPC - Sistema Energetico

---

## 1. Panoramica

Questo progetto implementa un **Model Predictive Control (MPC)** per l'ottimizzazione della gestione energetica di un distretto industriale con:

- Fotovoltaico (PV)
- Eolico (Wind)
- Generatore Diesel (DG)
- Sistema Idrogeno (Elettrolizzatore + Fuel Cell + Storage)
- Connessione alla rete (Import/Export)

---

## 2. Cos'e il MILP e Perche lo Usiamo

### 2.1 Definizione

**MILP (Mixed Integer Linear Programming)** = Programmazione Lineare Mista Intera

E' una tecnica di ottimizzazione matematica dove:

| Componente | Significato |
|------------|-------------|
| **Linear** | Funzione obiettivo e vincoli sono lineari (es. 2x + 3y <= 10) |
| **Integer** | Alcune variabili devono essere numeri interi |
| **Mixed** | Mix di variabili continue (es. potenza MW) e intere/binarie (es. ON/OFF) |

### 2.2 Perche serve il MILP nel nostro progetto?

Il problema di gestione energetica ha **vincoli di minimo tecnico**:

**Esempio: Generatore Diesel**
- Se acceso: deve produrre ALMENO 1 MW (non puo funzionare al 5%)
- Se spento: produce 0 MW
- Questo NON e un vincolo lineare semplice!

**Soluzione MILP**: Introduciamo variabili binarie (0 o 1)

```
u_dg in {0, 1}    (variabile binaria: 0=spento, 1=acceso)

Vincoli:
  P_dg <= 5 * u_dg     (se u_dg=0 -> P_dg<=0, se u_dg=1 -> P_dg<=5)
  P_dg >= 1 * u_dg     (se u_dg=0 -> P_dg>=0, se u_dg=1 -> P_dg>=1)
```

### 2.3 Variabili del nostro modello

| Tipo | Variabili | Descrizione |
|------|-----------|-------------|
| **Continue** | P_import, P_export, P_dg, P_ely, P_fc, P_curt, SOC | Potenze [MW] e stato di carica [MWh] |
| **Binarie** | u_dg, u_ely, u_fc | ON/OFF delle unita con minimo tecnico |

### 2.4 Dove viene implementato

Nel file **`model.py`** (righe 166-181):

```python
# Variabili continue (potenze)
p_import = cp.Variable(horizon_h, nonneg=True)
p_export = cp.Variable(horizon_h, nonneg=True)
p_dg = cp.Variable(horizon_h, nonneg=True)
p_ely = cp.Variable(horizon_h, nonneg=True)
p_fc = cp.Variable(horizon_h, nonneg=True)

# Variabili binarie (ON/OFF)
u_dg = cp.Variable(horizon_h, boolean=True)
u_ely = cp.Variable(horizon_h, boolean=True)
u_fc = cp.Variable(horizon_h, boolean=True)

# Vincoli minimo tecnico (esempio DG)
constraints += [p_dg <= 5.0 * u_dg]   # Max quando acceso
constraints += [p_dg >= 1.0 * u_dg]   # Min quando acceso
```

### 2.5 Solver utilizzati

| Solver | Libreria | Tipo | Note |
|--------|----------|------|------|
| **CBC** | PuLP | Open source | Preferito, piu veloce per MILP |
| **ECOS_BB** | CVXPY | Open source | Fallback se CBC non disponibile |

### 2.6 Confronto: LP vs MILP

| Aspetto | LP (senza binarie) | MILP (con binarie) |
|---------|-------------------|-------------------|
| Minimo tecnico | NO - Non gestibile | SI - Gestito con u*P_min |
| Velocita | Molto veloce | Piu lento |
| Complessita | O(n^3) | NP-hard |
| Soluzione | Sempre ottimo globale | Ottimo globale (ma piu tempo) |

### 2.7 Esempio pratico

**Senza MILP** (solo LP): Il diesel potrebbe produrre 0.1 MW -> irrealistico!

**Con MILP**: Il diesel produce 0 MW (spento) OPPURE almeno 1 MW (acceso) -> realistico!

```
Ora 100: Serve poco      -> DG spento (u_dg=0, P_dg=0)
Ora 200: Serve molto     -> DG acceso (u_dg=1, P_dg=3.5 MW)
Ora 201: Serve pochissimo -> DG spento (u_dg=0, P_dg=0)
         NON puo fare P_dg=0.2 MW!
```

---

## 3. Struttura del Progetto

```
Elettric_system/
|
|-- configs/
|   |-- system.yaml              # Configurazione parametri sistema
|
|-- data/
|   |-- PUN_2022.mat             # Prezzi PUN orari (borsa elettrica)
|   |-- res_1_year_pu.mat        # Profili PV e Wind (per-unit)
|   |-- buildings_load.mat       # Profilo carico edifici
|
|-- src/
|   |-- loader.py                # Caricamento e preprocessing dati
|   |-- tariff.py                # Gestione tariffe ARERA (F1/F2/F3)
|   |-- model.py                 # Modello di ottimizzazione MILP
|   |-- run_mpc_full.py          # Script principale di esecuzione
|   |-- report.py                # Generazione report statistiche
|   |-- plot_results.py          # Generazione grafici
|
|-- test_2025/
|   |-- system_2025.yaml         # Config 2025 (tariffe e fuel aggiornati)
|   |-- PUN_2025.mat             # Prezzi PUN 2025
|   |-- run_test_2025.py         # MPC 2025
|   |-- outputs_2025/            # Output scenario 2025
|
|-- outputs/
|   |-- mpc_2022_cf045.csv       # Risultati scenario cf=0.45
|   |-- mpc_2022_cf060.csv       # Risultati scenario cf=0.60
|   |-- tabella_comparativa_2022_2025.txt
|   |-- plots/                   # Grafici generati
|   |-- vecchi/                  # Output legacy
|
|-- create_all_plots.py          # Plot comparativi 2022 vs 2025
|-- generate_comparison_table.py # Tabella comparativa completa
|
|-- GUIDA_PROGETTO.md            # Questo file
```

---

## 4. Descrizione degli Script

### 4.1 loader.py - Caricamento Dati

**Cosa fa:**
- Carica i file .mat (MATLAB) con i dati di input
- Converte i profili PV e Wind da per-unit a MW
- Scala il carico in modo che il picco = 20 MW (load_nom_mw)
- Costruisce le serie temporali dei prezzi import (tariffe ARERA)

**Funzioni principali:**
```python
load_timeseries(data_dir, cfg)  # Carica tutti i dati
add_net_load(df)                # Calcola carico netto (Load - RES)
```

**Input:**
- data/PUN_2022.mat - Prezzi PUN orari
- data/res_1_year_pu.mat - Profili rinnovabili
- data/buildings_load.mat - Profilo carico

**Output:**
- DataFrame con colonne: load, pv, wind, pun, import_price per ogni ora

---

### 4.2 tariff.py - Tariffe Elettriche

**Cosa fa:**
- Implementa la logica delle fasce orarie ARERA (F1, F2, F3)

| Fascia | Ore | Prezzo |
|--------|-----|--------|
| F1 | Lun-Ven 8-19 | 532.76 EUR/MWh |
| F2 | Lun-Ven 7-8, 19-23; Sab 7-23 | 548.58 EUR/MWh |
| F3 | Notte e Domenica | 468.68 EUR/MWh |

---

### 4.3 model.py - Modello di Ottimizzazione MILP

**Cosa fa:**
- Definisce e risolve il problema di ottimizzazione MPC
- Minimizza il costo totale di gestione energetica
- Rispetta i vincoli fisici del sistema

**Equazione di bilancio energetico:**
```
PV + Wind + Import + DG + FC = Load + Export + ELY + Curtailment
```

**Funzione obiettivo (da minimizzare):**
```
Costo = Import * Prezzo_import
      - Export * Prezzo_PUN
      + DG * Costo_combustibile / eta_dg
      + Curtailment * Penalita
```

**Vincoli principali:**

| Vincolo | Limite |
|---------|--------|
| Import | <= 20 MW |
| Export | <= 16 MW |
| DG (quando acceso) | 1-5 MW |
| ELY (quando acceso) | 0.7-7 MW |
| FC (quando acceso) | 0.7-7 MW |
| H2 Storage | 0-12 MWh |

---

### 4.4 run_mpc_full.py - Script Principale

**Cosa fa:**
- Esegue la simulazione MPC "receding horizon" per tutto l'anno
- Per ogni ora: ottimizza le prossime 24 ore, applica solo la prima decisione
- Genera due scenari con diverso costo combustibile

| Scenario | Costo Combustibile | Costo DG |
|----------|-------------------|----------|
| cf=0.45 | 0.45 EUR/kWh | 750 EUR/MWh |
| cf=0.60 | 0.60 EUR/kWh | 1000 EUR/MWh |

**Flusso di esecuzione:**
```
Per ogni ora t da 0 a 6527:
    1. Leggi stato attuale (SOC idrogeno)
    2. Ottimizza orizzonte [t, t+24]
    3. Estrai decisione per ora t
    4. Aggiorna stato
    5. Salva risultato
```

**Output:**
- mpc_2022_cf045.csv - Risultati orari scenario 1
- mpc_2022_cf060.csv - Risultati orari scenario 2

---

### 4.5 report.py - Generazione Report

**Cosa fa:**
- Calcola statistiche aggregate dai risultati MPC
- Genera file CSV con metriche annuali

**Metriche calcolate:**
- Energia totale: Load, PV, Wind, Import, Export, DG, ELY, FC
- Costi totali: Import, Export (ricavo), DG
- Costo netto annuale

---

### 4.6 plot_results.py - Grafici

**Cosa fa:**
- Genera grafici per visualizzare i risultati

**Grafici disponibili:**

| Grafico | Descrizione |
|---------|-------------|
| balance_*.png | Bilancio energetico stacked (fonti vs usi) |
| arbitrage_*.png | Analisi prezzi (spread import/export) |
| h2_system_*.png | Sistema idrogeno (ELY, FC, SOC) |
| daily_summary_*.png | Riepilogo energie giornaliere |
| hour_XXXX_*.png | Dettaglio singola ora |

**Comandi:**
```bash
# Grafici standard (1 settimana)
python src/plot_results.py --hours 168

# Intero anno
python src/plot_results.py --hours 6528

# Dettaglio ora specifica
python src/plot_results.py --hour-detail 5694

# Confronto scenari
python src/plot_results.py --scenario both
```

---

## 5. File di Configurazione: system.yaml

```yaml
project:
  timestep_h: 1          # Passo temporale: 1 ora
  horizon_h: 24          # Orizzonte ottimizzazione: 24 ore
  year: 2022             # Anno simulazione

system:
  pv_nom_mw: 4.0         # Potenza nominale PV
  wind_nom_mw: 11.34     # Potenza nominale eolico
  load_nom_mw: 20.0      # Carico nominale (picco)
  import_max_mw: 20.0    # Max import dalla rete
  export_max_mw: 16.0    # Max export alla rete
  dg_nom_mw: 5.0         # Potenza max diesel
  dg_min_mw: 1.0         # Potenza min diesel (quando acceso)
  ely_nom_mw: 7.0        # Potenza max elettrolizzatore
  fc_nom_mw: 7.0         # Potenza max fuel cell
  h2_storage_mwh: 12.0   # Capacita storage H2
  eta_ely: 0.7           # Efficienza elettrolizzatore (70%)
  eta_fc: 0.6            # Efficienza fuel cell (60%)
  eta_dg: 0.6            # Efficienza diesel (60%)

prices:
  import_f1_eur_per_kwh: 0.53276  # Tariffa F1
  import_f2_eur_per_kwh: 0.54858  # Tariffa F2
  import_f3_eur_per_kwh: 0.46868  # Tariffa F3
  fuel_eur_per_kwh: 0.45         # Costo combustibile (cf=0.45)
```

---

## 6. Flusso di Esecuzione Completo

```
+---------------------------+
|   1. CARICAMENTO DATI     |
|      (loader.py)          |
+---------------------------+
            |
            v
+---------------------------+
| 2. CONFIGURAZIONE TARIFFE |
|      (tariff.py)          |
+---------------------------+
            |
            v
+---------------------------+
| 3. SIMULAZIONE MPC ANNUALE|
|    (run_mpc_full.py)      |
|                           |
|  Per ogni ora t:          |
|  a) Costruisci MILP       |
|  b) Risolvi [t, t+24]     |
|  c) Estrai decisione t    |
|  d) Aggiorna SOC H2       |
|  e) Salva risultato       |
+---------------------------+
            |
            v
+---------------------------+
|  4. GENERAZIONE REPORT    |
|      (report.py)          |
+---------------------------+
            |
            v
+---------------------------+
|  5. GENERAZIONE GRAFICI   |
|    (plot_results.py)      |
+---------------------------+
```

---

## 7. Come Eseguire il Progetto

### 7.1 Installare dipendenze
```bash
pip install -r requirements.txt
```

### 7.2 Eseguire simulazione MPC
```bash
python src/run_mpc_full.py
```

Output generato:
- outputs/mpc_2022_cf045.csv
- outputs/mpc_2022_cf060.csv

### 7.3 Generare report
```bash
python src/report.py
```

### 7.4 Generare grafici
```bash
# Grafici per 72 ore
python src/plot_results.py --hours 72 --start 5680

# Grafici intero anno
python src/plot_results.py --hours 6528

# Dettaglio ora specifica
python src/plot_results.py --hour-detail 100
```

### 7.5 Scenario 2025 (PUN aggiornato)
```bash
# Se serve rigenerare il MAT dal file Excel
python test_2025/convert_pun.py

# Esegue gli scenari 2025
python test_2025/run_test_2025.py
```

Output principali:
- test_2025/outputs_2025/mpc_2025_cf014.csv
- test_2025/outputs_2025/mpc_2025_cf020.csv

---

## 8. Risultati Principali

### 8.1 Scenario cf=0.45 (costo DG = 750 EUR/MWh)

| Metrica | Valore |
|---------|--------|
| Ore simulate | 6528 |
| Energia Load totale | 47,741.58 MWh |
| Energia Import | 36,568.61 MWh |
| Energia Export | 518.76 MWh |
| Energia DG | 0.00 MWh |
| Energia ELY | 116.49 MWh |
| Energia FC | 48.93 MWh |
| Costo Import | 18.53 M EUR |
| Ricavo Export | 0.164 M EUR |
| Costo DG | 0 EUR |
| **Costo Netto** | **18.36 M EUR** |

### 8.2 Comportamenti chiave osservati

1. **Mutua esclusione import/export**: Nessun arbitraggio di rete (ore Import+Export = 0)
2. **DG mai usato**: 0 ore in entrambi gli scenari cf (import sempre piu conveniente)
3. **H2 usato solo su surplus**: Efficienza round-trip 42%, ~6.9 cicli equivalenti/anno
   - **NOTA**: I "7 cicli" sono CICLI EQUIVALENTI, non cicli completi 0%→100%→0%

Per il confronto 2022 vs 2025, vedi `outputs/tabella_comparativa_2022_2025.txt`.
   - Formula: (Energia_ELY + Energia_FC) / (2 × Capacita) = (119 + 50) / (2 × 12) = 7.1
   - In realta ci sono ~40 cariche parziali e ~30 scariche parziali
   - La somma di tutte le oscillazioni equivale a 7 cicli pieni
4. **Crisi energetica 2022**: Export massimo in agosto-settembre (PUN altissimo)

---

## 9. Concetti Chiave per la Presentazione

### 9.1 MPC (Model Predictive Control)
- Ottimizza guardando avanti (orizzonte 24h)
- Applica solo la prima decisione
- Ricalcola ogni ora con nuove informazioni

### 9.2 MILP (Mixed Integer Linear Programming)
- Permette di modellare vincoli ON/OFF
- Variabili binarie per minimi tecnici
- Solver: CBC (open source)

### 9.3 Arbitraggio e Ottimizzazione
- **NOTA IMPORTANTE**: Il modello corretto NON permette import+export simultaneo
- Import ed Export sono mutuamente esclusivi (vincolo fisico realistico)
- L'export avviene solo quando c'e surplus RES (PV + Wind > Load)
- L'ELY usa solo energia da surplus RES, non dalla rete
- NON c'e arbitraggio energetico puro (comprare per rivendere subito)
- C'e ottimizzazione dei costi: vendere surplus al miglior prezzo

### 9.4 Sistema Idrogeno
- Efficienza totale: ELY (70%) x FC (60%) = 42%
- Conviene solo per:
  - Energy shifting (spostare surplus RES)
  - Backup quando import al massimo
- NON conviene per arbitraggio (perdite 58%)

### 9.5 Bilancio Energetico
```
IN = OUT (sempre!)
PV + Wind + Import + DG + FC = Load + Export + ELY + Curtailment
```

---

## 10. Note Finali

- **Progetto**: Analisi gestione energetica distretto industriale
- **Dati**: Anno 2022, prezzi PUN reali (crisi energetica)
- **Solver**: CBC (open source) via PuLP/CVXPY
- **Linguaggio**: Python 3.x
