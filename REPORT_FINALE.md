# Report Finale - Project 4: Sistema Energetico Integrato con Idrogeno

---

## 1. Scopo del progetto

Progettare un sistema di ottimizzazione/controllo (MPC - Model Predictive Control) per un sistema energetico integrato che include:
- Fonti rinnovabili (PV + Wind)
- Carico elettrico non controllabile
- Sistema di stoccaggio a idrogeno (elettrolizzatore + storage + fuel cell)
- Generatore diesel di backup (DG)
- Scambio bidirezionale con la rete elettrica

**Obiettivi di ottimizzazione:**
- a) Minimizzare il costo / massimizzare il ricavo
- b) Soddisfare sempre il carico
- c) Minimizzare il curtailment delle rinnovabili

---

## 2. Schema del sistema

![Modello di sistema](assets/model_page1.png)

### Componenti e parametri tecnici

| Componente | Parametro | Valore | Unita |
|------------|-----------|--------|-------|
| **Fotovoltaico (PV)** | Potenza nominale | 4.0 | MW |
| **Eolico (Wind)** | Potenza nominale | 11.34 | MW |
| **Carico (Pul)** | Potenza nominale | 20 | MW |
| **Rete - Import** | Potenza massima | 20.0 | MW |
| **Rete - Export** | Potenza massima | 16.0 | MW |
| **Elettrolizzatore (ELY)** | Potenza nominale | 7.0 | MW |
| **Elettrolizzatore (ELY)** | Potenza minima | 0.7 | MW |
| **Elettrolizzatore (ELY)** | Efficienza | 70% | - |
| **Fuel Cell (FC)** | Potenza nominale | 7.0 | MW |
| **Fuel Cell (FC)** | Potenza minima | 0.7 | MW |
| **Fuel Cell (FC)** | Efficienza | 60% | - |
| **Storage H2 (HSS)** | Capacita | 12.0 | MWh |
| **Generatore Diesel (DG)** | Potenza nominale | 5.0 | MW |
| **Generatore Diesel (DG)** | Potenza minima | 1.0 | MW |
| **Generatore Diesel (DG)** | Efficienza | 60% | - |

---

## 3. Metodologia: MPC Rolling Horizon

### 3.1 Cos'e il Model Predictive Control (MPC)

Il MPC e una strategia di controllo che ripete ciclicamente 4 step:

```
STEP 1: Raccogli previsioni (PV, Wind, Load, Prezzi) per le prossime 24 ore
           |
           v
STEP 2: Risolvi il problema di ottimizzazione MILP sull'orizzonte di 24h
           |
           v
STEP 3: Applica SOLO la prima decisione (ora corrente)
           |
           v
STEP 4: Avanza di 1 ora e torna a STEP 1
```

### 3.2 Perche MILP e non LP?

Il modello usa **MILP (Mixed Integer Linear Programming)** invece di LP puro per rispettare i vincoli di potenza minima:

| Componente | Vincolo | Comportamento |
|------------|---------|---------------|
| ELY | P_min = 0.7 MW | O spento (0 MW) O acceso (0.7-7 MW) |
| FC | P_min = 0.7 MW | O spenta (0 MW) O accesa (0.7-7 MW) |
| DG | P_min = 1.0 MW | O spento (0 MW) O acceso (1-5 MW) |

Le variabili binarie (u_ely, u_fc, u_dg) permettono di modellare correttamente questo comportamento on/off.

### 3.3 Bilancio energetico

Il vincolo fondamentale e che **tutta l'energia IN = tutta l'energia OUT**:

```
ENERGIA IN                      ENERGIA OUT
-----------                     -----------
P_pv                            P_load
P_wind          ===             P_export
P_import                        P_ely
P_dg                            P_curtail
P_fc
```

Formula:
```
P_pv + P_wind + P_import + P_dg + P_fc = P_load + P_export + P_ely + P_curt
---

## 4. Prezzi e tariffe utilizzati

### 4.1 Costo energia importata (tariffe ARERA)

| Fascia | Orario | Prezzo (EUR/kWh) | Prezzo (EUR/MWh) |
|--------|--------|------------------|------------------|
| **F1** | Lun-Ven 08:00-19:00 | 0.53276 | 532.76 |
| **F2** | Lun-Ven 07-08, 19-23; Sab 07-23 | 0.54858 | 548.58 |
| **F3** | Notti, domeniche, festivita | 0.46868 | 468.68 |
| **Media ponderata** | - | ~0.515 | ~515 |

### 4.2 Prezzo energia esportata (PUN)

- **PUN 2022**: Prezzo Unico Nazionale, varia ora per ora
- Range: 10 - 870 EUR/MWh
- Media annuale (dataset 6,528 ore): ~324.22 EUR/MWh

#### Analisi statistica del PUN 2022

| Soglia | Ore | % del totale |
|--------|-----|--------------|
| PUN > 750 EUR/MWh | 47 ore | 0.72% |
| PUN > 700 EUR/MWh | 90 ore | 1.37% |
| PUN > 600 EUR/MWh | 315 ore | 4.81% |
| PUN > 500 EUR/MWh | 793 ore | 12.10% |

**Statistiche PUN 2022 (dataset 6,528 ore):**
- Minimo: 10 EUR/MWh
- Massimo: 870 EUR/MWh
- Media: 324.22 EUR/MWh
- Mediana: 275.14 EUR/MWh
- Deviazione standard: 136.65 EUR/MWh

**Nota operativa (modello aggiornato):**
Con il vincolo di mutua esclusione import/export, l'export avviene solo da surplus RES e il DG non viene attivato (0 ore) negli scenari 2022, anche nelle ore con PUN alto.

### 4.3 Costo carburante DG (scenari testati)

| Scenario | Costo carburante | Costo elettrico* | Confronto con rete |
|----------|------------------|------------------|-------------------|
| **cf = 0.45** | 0.45 EUR/kWh | 750 EUR/MWh | +46% vs import |
| **cf = 0.60** | 0.60 EUR/kWh | 1000 EUR/MWh | +94% vs import |

*Costo elettrico = costo_carburante / efficienza_DG = cf / 0.6

---

## 5. Strategia di controllo ottimale: decisioni ora per ora

### 5.1 Logica decisionale

Per ogni ora, il sistema decide la configurazione ottimale seguendo questa logica:

```
                    +------------------+
                    |  Calcola deficit |
                    |  o surplus RES   |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
        SURPLUS (RES > Load)          DEFICIT (RES < Load)
              |                             |
    +---------+---------+         +---------+---------+
    |                   |         |                   |
    v                   v         v                   v
Export a PUN?     Carica H2?   Scarica H2?      Import rete?
(solo surplus)    (se SOC<max) (se SOC>0)       (se <20MW)
    |                   |         |                   |
    +-------------------+         +-------------------+
              |                             |
              v                             v
    Se ancora surplus:              Se ancora deficit:
    -> CURTAILMENT                  -> USA DG (solo se necessario)
```

### 5.2 Arbitraggio sui prezzi (modello aggiornato)

Nel modello attuale import ed export sono **mutuamente esclusivi**: non si compra e non si vende nella stessa ora.
L'export avviene solo in presenza di **surplus rinnovabile**, quindi non c'e' arbitraggio puro di rete.
Nei risultati 2022 il DG non viene mai attivato.

### 5.3 Statistiche operative (6528 ore)

| Indicatore | cf=0.45 | cf=0.60 |
|-----------|--------:|--------:|
| Ore totali | 6528 | 6528 |
| Ore con Import | 6186 | 6186 |
| Ore con Export | 284 | 284 |
| Ore con ELY | 61 | 61 |
| Ore con FC | 28 | 28 |
| Ore con DG | 0 | 0 |
| Ore Import+Export | 0 | 0 |

**Osservazione chiave:** i due scenari risultano identici perche' il DG non viene mai usato.

---

## 6. Risultati delle simulazioni

### 6.1 Riepilogo scenari

Periodo simulato: **6528 ore** con MPC rolling horizon (orizzonte 24h)

| Voce | cf=0.45 | cf=0.60 | Differenza |
|------|--------:|--------:|------------|
| **ENERGIA** ||||
| Energia carico (MWh) | 47,741.58 | 47,741.58 | 0 |
| Energia PV (MWh) | 5,427.57 | 5,427.57 | 0 |
| Energia Wind (MWh) | 6,331.75 | 6,331.75 | 0 |
| Energia Import (MWh) | 36,568.61 | 36,568.61 | 0 |
| Energia Export (MWh) | 518.76 | 518.76 | 0 |
| **Energia DG (MWh)** | **0.00** | **0.00** | **0** |
| **SISTEMA H2** ||||
| Energia ELY (MWh) | 116.49 | 116.49 | 0 |
| Energia FC (MWh) | 48.93 | 48.93 | 0 |
| H2 prodotto (MWh) | 81.55 | 81.55 | 0 |
| **COSTI** ||||
| Costo Import (EUR) | 18,525,601 | 18,525,601 | 0 |
| Ricavo Export (EUR) | 163,700 | 163,700 | 0 |
| Costo DG (EUR) | 0 | 0 | 0 |
| **COSTO NETTO (EUR)** | **18,361,900** | **18,361,900** | **0** |

### 6.2 Breakdown costi

**cf=0.45:**
```
Costo Import:      +18,525,601 EUR  (100.0%)
Costo DG:                    0 EUR   (0.0%)
Ricavo Export:        -163,700 EUR  (-0.9%)
---------------------------------------------
COSTO NETTO:       18,361,900 EUR
Costo per MWh:     384.61 EUR/MWh
```

**cf=0.60:**
```
Costo Import:      +18,525,601 EUR (100.0%)
Costo DG:                    0 EUR   (0.0%)
Ricavo Export:        -163,700 EUR  (-0.9%)
---------------------------------------------
COSTO NETTO:       18,361,900 EUR
Costo per MWh:     384.61 EUR/MWh
---

## 7. Analisi economica: quando conviene ogni componente

### 7.1 Generatore Diesel (DG)

| Condizione | cf=0.45 | cf=0.60 |
|------------|---------|---------|
| Costo DG | 750 EUR/MWh | 1000 EUR/MWh |
| PUN max 2022 | 870 EUR/MWh | 870 EUR/MWh |
| **Conviene arbitraggio?** | **No (modello senza arbitraggio)** | **No (modello senza arbitraggio)** |
| Ore con DG attivo | 0 | 0 |

**Conclusione DG:**
- Il DG non viene mai attivato negli scenari 2022 (0 ore)
- Il vincolo di mutua esclusione import/export elimina l'arbitraggio di rete
- Il DG resta disponibile come backup, ma non risulta conveniente nei dati 2022

### 7.2 Sistema Idrogeno (ELY + FC)

| Metrica | Valore |
|---------|--------|
| Efficienza ELY | 70% |
| Efficienza FC | 60% |
| **Efficienza round-trip** | **42%** |
| Energia persa per ciclo | 58% |

**Quando conviene usare H2:**
```
Carica (ELY): quando c'e surplus RES e SOC < 100%
Scarica (FC): quando c'e deficit e SOC > 0% e Import al massimo
```

L'efficienza del 42% lo rende utile solo per:
- Energy shifting (spostare energia nel tempo)
- Evitare curtailment
- NON per arbitraggio puro (troppe perdite)

### 7.3 Import/Export rete

| Operazione | Condizione | Prezzo |
|------------|------------|--------|
| Import | Sempre disponibile | 469-549 EUR/MWh (ARERA) |
| Export | Surplus disponibile | PUN variabile (10-870) |

**Arbitraggio import/export:**
- Non consentito: import ed export sono mutuamente esclusivi
- Export solo in presenza di surplus RES

---

## 8. Decisioni ora per ora

### 8.1 File generati

I file `outputs/mpc_2022_cf045.csv` e `outputs/mpc_2022_cf060.csv` contengono per ogni ora:

| Colonna | Descrizione |
|---------|-------------|
| hour | Indice ora |
| p_import_mw | Potenza importata [MW] |
| p_export_mw | Potenza esportata [MW] |
| p_ely_mw | Potenza elettrolizzatore [MW] |
| p_fc_mw | Potenza fuel cell [MW] |
| p_dg_mw | Potenza diesel [MW] |
| p_curt_mw | Curtailment [MW] |
| soc_mwh | Stato di carica H2 [MWh] |
| objective_eur | Costo totale dell'orizzonte [EUR] |

### 8.2 Come leggere le decisioni

Per ogni ora, controlla i valori:

```
SE import_MW > 0    -> Compra dalla rete
SE export_MW > 0    -> Vendi alla rete
SE DG_MW > 0        -> Accendi il diesel (backup)
SE ELY_MW > 0       -> Carica storage H2 (surplus RES)
SE FC_MW > 0        -> Scarica storage H2 (deficit)
```

### 8.3 Esempi pratici

**Ora tipica - deficit (ora 15):**
```
Load: 18.21 MW, PV: 0.42 MW, Wind: 0 MW
Decisione: IMPORT 17.79 MW
```

**Ora con surplus RES (ora 34):**
```
Load: 9.29 MW, PV: 1.04 MW, Wind: 9.53 MW
RES totale: 10.57 MW > Load
Decisione: ELY 1.28 MW (carica H2)
```

```

---

## 9. Conclusioni e raccomandazioni

### 9.1 Sintesi risultati

1. **DG non utilizzato**
   - 0 ore in entrambi gli scenari
   - Rimane come backup, ma non risulta conveniente nei dati 2022

2. **Nessun arbitraggio di rete**
   - Import ed export sono mutuamente esclusivi
   - Export solo da surplus RES (284 ore)

3. **Lo storage H2 ha uso limitato**
   - Efficienza round-trip 42% (perdite elevate)
   - ~6.9 cicli equivalenti/anno (ELY 61 ore, FC 28 ore)

4. **La rete e la fonte principale**
   - Import copre la maggior parte del fabbisogno
   - Export genera ricavi marginali (~0.164 M EUR)

### 9.2 Raccomandazioni operative

| Componente | Raccomandazione |
|------------|-----------------|
| **DG** | Backup solo se necessario (nei dati 2022 non usato) |
| **ELY** | Attivare quando surplus RES e SOC < 100% |
| **FC** | Attivare quando deficit e import al max |
| **Import** | Fonte principale, sempre conveniente |
| **Export** | Vendere il surplus RES (senza import contemporaneo) |

### 9.3 Differenza tra scenari

La differenza tra cf=0.45 e cf=0.60 e **nulla** nei risultati 2022:
- Il DG non viene mai attivato in entrambi gli scenari
- Import, export e costi risultano identici

---

## 10. Appendice tecnica

### 10.1 File di output

| File | Descrizione |
|------|-------------|
| `outputs/mpc_2022_cf045.csv` | Schedule MPC completo (cf=0.45) |
| `outputs/mpc_2022_cf060.csv` | Schedule MPC completo (cf=0.60) |
| `outputs/tabella_comparativa_2022_2025.txt` | Confronto 2022 vs 2025 |
| `outputs/report_2022_cf045.csv` | Metriche aggregate (cf=0.45) |
| `outputs/report_2022_cf060.csv` | Metriche aggregate (cf=0.60) |
| `outputs/plots/*.png` | Grafici risultati |
| `outputs/vecchi/*` | Output legacy (decisioni ora per ora, report storici) |

### 10.2 Come riprodurre i risultati

```bash
# Installare dipendenze
pip install -r requirements.txt

# Eseguire MPC (genera schedule per entrambi gli scenari)
python src/run_mpc_full.py --horizon 24 --fuel-values 0.45,0.60 --out outputs/mpc_2022.csv

# Generare report
python src/report.py --schedule outputs/mpc_2022_cf045.csv --out outputs/report_2022_cf045.csv --fuel-cost 0.45 --plots
python src/report.py --schedule outputs/mpc_2022_cf060.csv --out outputs/report_2022_cf060.csv --fuel-cost 0.60

# Generare grafici dettagliati
python src/plot_results.py --hours 168 --start 0
```

### 10.3 Formule del modello

**Bilancio energetico:**
```
P_pv + P_wind + P_import + P_dg + P_fc = P_load + P_ely + P_export + P_curt
```

**Dinamica storage H2:**
```
SOC(t+1) = SOC(t) + dt * (eta_ely * P_ely - P_fc / eta_fc)
```

**Funzione obiettivo:**
```
min: sum( c_import * P_import - PUN * P_export + (c_fuel/eta_dg) * P_dg + lambda * P_curt )
```

**Vincoli on/off (MILP):**
```
P_ely <= P_ely_nom * u_ely
P_ely >= P_ely_min * u_ely
(analogo per FC e DG)
```

---

## 11. Come estendere il modello (guida per sviluppatori)

### 11.1 Struttura del codice

```
src/
├── model.py          <- MODELLO MPC (variabili, vincoli, obiettivo)
├── run_mpc_full.py   <- LOOP MPC (rolling horizon)
├── loader.py         <- Caricamento dati
├── tariff.py         <- Tariffe ARERA
├── report.py         <- Generazione report
└── plot_results.py   <- Grafici

configs/
└── system.yaml       <- PARAMETRI (potenze, efficienze, prezzi)
```

### 11.2 Dove aggiungere una nuova VARIABILE DECISIONALE

**File: `src/model.py`**

**STEP 1 - Dichiarare la variabile (linea ~158-168):**
```python
# Esempio: aggiungere una batteria
p_battery_ch = cp.Variable(horizon_h, nonneg=True)   # Carica batteria
p_battery_dis = cp.Variable(horizon_h, nonneg=True)  # Scarica batteria
u_battery = cp.Variable(horizon_h, boolean=True)     # On/off (opzionale)
soc_battery = cp.Variable(horizon_h + 1)             # Stato di carica
```

**STEP 2 - Aggiungere i vincoli (linea ~172-194):**
```python
# Limiti potenza
constraints += [p_battery_ch <= float(sys['battery_nom_mw'])]
constraints += [p_battery_dis <= float(sys['battery_nom_mw'])]

# Limiti SOC
constraints += [soc_battery >= 0.0]
constraints += [soc_battery <= float(sys['battery_capacity_mwh'])]

# Condizione iniziale
constraints += [soc_battery[0] == soc_battery_init]

# Dinamica batteria
constraints += [
    soc_battery[1:] == soc_battery[:-1] + dt * (
        eta_ch * p_battery_ch - p_battery_dis / eta_dis
    )
]

# Mutua esclusione carica/scarica (opzionale)
constraints += [p_battery_ch + p_battery_dis <= float(sys['battery_nom_mw']) * u_battery]
```

**STEP 3 - Aggiornare il bilancio energetico (linea ~186-189):**
```python
constraints += [
    pv + wind + p_import + p_dg + p_fc + p_battery_dis  # <- AGGIUNTO
    == load + p_ely + p_export + p_curt + p_battery_ch  # <- AGGIUNTO
]
```

**STEP 4 - Aggiornare la funzione obiettivo (linea ~199-202):**
```python
# Se la batteria ha un costo di degradazione:
cost += degradation_cost * cp.sum(p_battery_ch + p_battery_dis) * dt
```

**STEP 5 - Aggiungere al DataFrame di output (linea ~211-222):**
```python
schedule = pd.DataFrame({
    # ... variabili esistenti ...
    'p_battery_ch_mw': p_battery_ch.value,
    'p_battery_dis_mw': p_battery_dis.value,
    'soc_battery_mwh': soc_battery.value[1:],
})
```

### 11.3 Dove aggiungere un nuovo PARAMETRO

**File: `configs/system.yaml`**

```yaml
system:
  # ... parametri esistenti ...

  # Nuova batteria
  battery_nom_mw: 10.0
  battery_capacity_mwh: 40.0
  eta_battery_ch: 0.95
  eta_battery_dis: 0.95
```

**File: `src/model.py` - leggere il parametro:**
```python
battery_cap = float(sys['battery_capacity_mwh'])
eta_ch = float(sys['eta_battery_ch'])
eta_dis = float(sys['eta_battery_dis'])
```

### 11.4 Dove aggiungere un nuovo VINCOLO

**File: `src/model.py` (linea ~172-194)**

Esempi di vincoli comuni:

```python
# Vincolo rampa (variazione massima tra ore)
constraints += [cp.abs(p_dg[1:] - p_dg[:-1]) <= ramp_rate_mw]

# Vincolo mutua esclusione import/export
constraints += [p_import * p_export == 0]  # Non lineare! Usare binarie:
constraints += [p_import <= M * (1 - u_export)]
constraints += [p_export <= M * u_export]

# Vincolo minimo tempo accensione (DG acceso per almeno 3 ore)
for t in range(horizon_h - 2):
    constraints += [u_dg[t+1] + u_dg[t+2] >= 2 * (u_dg[t+1] - u_dg[t])]

# Vincolo SOC finale = SOC iniziale (ciclo completo)
constraints += [soc[-1] == soc[0]]
```

### 11.5 Dove modificare il LOOP MPC

**File: `src/run_mpc_full.py` (linea ~19-48)**

```python
def run_receding(...):
    results = []
    soc = 0.0                    # <- Stato iniziale H2
    soc_battery = 0.5            # <- Aggiungere stato iniziale batteria

    for hour in tqdm(...):
        res = solve_horizon(
            df, cfg, hour, horizon,
            soc,
            soc_battery,         # <- Passare nuovo stato
            fuel_eur_per_kwh=fuel_eur_per_kwh
        )

        first = res.schedule.iloc[0]
        soc = float(first['soc_mwh'])
        soc_battery = float(first['soc_battery_mwh'])  # <- Aggiornare

        results.append({
            # ... campi esistenti ...
            'soc_battery_mwh': soc_battery,  # <- Aggiungere output
        })
```

---

## 12. Teoria MPC per l'esame

### 12.1 Cos'e il Model Predictive Control?

Il **MPC (Model Predictive Control)** e una strategia di controllo ottimo che:

1. **Predice** il comportamento futuro del sistema su un orizzonte finito
2. **Ottimizza** le azioni future minimizzando una funzione costo
3. **Applica** solo la prima azione ottimale
4. **Ripete** il processo ad ogni passo temporale

### 12.2 Vantaggi del MPC

| Vantaggio | Spiegazione |
|-----------|-------------|
| **Gestisce vincoli** | Limiti fisici (potenza max, SOC min/max) |
| **Anticipa il futuro** | Usa previsioni per decisioni migliori |
| **Adattivo** | Si aggiorna ad ogni passo con nuove informazioni |
| **Multi-obiettivo** | Bilancia costi, emissioni, comfort |

### 12.3 Svantaggi del MPC

| Svantaggio | Spiegazione |
|------------|-------------|
| **Computazionalmente costoso** | Risolve ottimizzazione ad ogni passo |
| **Dipende da previsioni** | Errori di forecast degradano le prestazioni |
| **Tuning parametri** | Orizzonte, pesi obiettivo richiedono taratura |

### 12.4 Differenza tra MPC e controllo classico

| Aspetto | Controllo PID | MPC |
|---------|---------------|-----|
| Orizzonte | Istantaneo | Futuro (24h) |
| Vincoli | Difficili da gestire | Nativamente supportati |
| Modello | Non richiesto | Richiesto |
| Ottimalita | Locale | Globale (sull'orizzonte) |

### 12.5 Formulazione matematica

**Problema di ottimizzazione ad ogni passo k:**

```
min    J = sum_{t=0}^{N-1} [ c_import(t)*P_import(t) - PUN(t)*P_export(t)
 u(t)                        + c_fuel/eta_dg * P_dg(t) + lambda*P_curt(t) ]

s.t.   P_pv(t) + P_wind(t) + P_import(t) + P_dg(t) + P_fc(t)
       = P_load(t) + P_export(t) + P_ely(t) + P_curt(t)     [bilancio]

       SOC(t+1) = SOC(t) + dt*(eta_ely*P_ely(t) - P_fc(t)/eta_fc)  [dinamica]

       0 <= P_import(t) <= P_import_max                      [limiti]
       0 <= P_export(t) <= P_export_max
       P_ely_min * u_ely(t) <= P_ely(t) <= P_ely_max * u_ely(t)
       ...

       u_ely(t), u_fc(t), u_dg(t) in {0,1}                   [binarie]
```

Dove:
- **N** = orizzonte di previsione (24 ore)
- **u(t)** = variabili decisionali (P_import, P_export, P_ely, P_fc, P_dg)
- **J** = funzione obiettivo (costo da minimizzare)

---

## 13. Domande frequenti per l'esame

### 13.1 Domande sulla metodologia

**D: Perche si applica solo la prima decisione?**
> Perche le previsioni diventano meno accurate nel futuro. Applicando solo la prima decisione e ricalcolando, si usano sempre le previsioni piu aggiornate.

**D: Cosa succede se le previsioni sono sbagliate?**
> Il MPC e robusto agli errori grazie al feedback: ad ogni passo si ricalcola con i dati reali aggiornati. Errori grandi possono comunque degradare le prestazioni.

**D: Perche l'orizzonte e 24 ore?**
> Bilancia tra:
> - Vedere abbastanza avanti per anticipare i picchi di prezzo/carico
> - Non troppo avanti dove le previsioni sono inaffidabili
> - Tempo di calcolo ragionevole

**D: Perche MILP e non LP?**
> I vincoli di potenza minima (P_ely >= 0.7 MW quando acceso) richiedono variabili binarie. Con LP puro, l'elettrolizzatore potrebbe funzionare a 0.1 MW, irrealistico.

### 13.2 Domande sui risultati

**D: Perche il DG non viene quasi mai usato?**
> Nel modello aggiornato il DG non viene mai usato: l'import resta piu conveniente e l'arbitraggio di rete e' impedito dalla mutua esclusione import/export.

**D: Perche import e export possono essere contemporanei?**
> Non possono: il modello impone mutua esclusione. L'export avviene solo in presenza di surplus RES.

**D: Perche lo storage H2 e poco usato?**
> L'efficienza round-trip e solo 42% (= 0.7 * 0.6). Si perde il 58% dell'energia. Conviene solo per energy shifting, non per arbitraggio.

**D: Qual e l'impatto del parametro cf?**
> Nei risultati 2022 e' nullo: il DG non viene mai attivato in entrambi gli scenari.
> Di conseguenza costi e flussi risultano identici.

### 13.3 Domande sul codice

**D: Come si aggiunge una nuova variabile?**
> Vedi Sezione 11.2 - modificare `model.py` in 5 punti: dichiarazione, vincoli, bilancio, obiettivo, output.

**D: Dove sono definiti i parametri?**
> In `configs/system.yaml` - potenze nominali, efficienze, prezzi.

**D: Come si cambia l'orizzonte MPC?**
> Parametro `horizon_h` in `configs/system.yaml` oppure argomento `--horizon` da linea di comando.

---

## 14. Glossario dei termini

| Termine | Significato |
|---------|-------------|
| **MPC** | Model Predictive Control - controllo predittivo basato su modello |
| **MILP** | Mixed Integer Linear Programming - ottimizzazione con variabili intere e continue |
| **LP** | Linear Programming - ottimizzazione lineare (solo variabili continue) |
| **Rolling Horizon** | Orizzonte mobile - ripetere l'ottimizzazione ad ogni passo |
| **SOC** | State of Charge - stato di carica dello storage (0-100%) |
| **PUN** | Prezzo Unico Nazionale - prezzo energia all'ingrosso in Italia |
| **ARERA** | Autorita di Regolazione per Energia Reti e Ambiente |
| **F1/F2/F3** | Fasce orarie tariffarie italiane (punta/intermedia/fuori punta) |
| **ELY** | Elettrolizzatore - produce H2 da elettricita |
| **FC** | Fuel Cell - produce elettricita da H2 |
| **DG** | Diesel Generator - generatore a combustibile fossile |
| **RES** | Renewable Energy Sources - fonti rinnovabili (PV + Wind) |
| **Curtailment** | Taglio della produzione rinnovabile (energia sprecata) |
| **Arbitraggio** | Comprare a prezzo basso e vendere a prezzo alto |
| **Round-trip efficiency** | Efficienza ciclo completo (carica + scarica) |
| **Big-M** | Tecnica per linearizzare vincoli con variabili binarie |

---

## 15. Checklist per l'esame

### 15.1 Concetti da sapere spiegare

- [ ] Cos'e il MPC e come funziona (4 step)
- [ ] Differenza tra MILP e LP
- [ ] Perche servono variabili binarie
- [ ] Come si scrive il bilancio energetico
- [ ] Come funziona la dinamica dello storage
- [ ] Cosa rappresenta la funzione obiettivo
- [ ] Perche si usa rolling horizon
- [ ] Come interpretare i risultati

### 15.2 Formule da conoscere

```
Bilancio:   P_pv + P_wind + P_import + P_dg + P_fc = P_load + P_ely + P_export + P_curt

Dinamica:   SOC(t+1) = SOC(t) + dt * (eta_ely * P_ely - P_fc / eta_fc)

Obiettivo:  min sum( c_import*P_import - PUN*P_export + (c_fuel/eta_dg)*P_dg )

Vincolo on/off:  P_min * u <= P <= P_max * u,  u in {0,1}
```

### 15.3 Numeri chiave del progetto

| Parametro | Valore |
|-----------|--------|
| Potenza PV | 4 MW |
| Potenza Wind | 11.34 MW |
| Carico nominale | 20 MW |
| Import max | 20 MW |
| Export max | 16 MW |
| Storage H2 | 12 MWh |
| Efficienza ELY | 70% |
| Efficienza FC | 60% |
| Efficienza DG | 60% |
| Orizzonte MPC | 24 ore |
| Ore simulate | 6528 |
| Costo netto | ~18.36 M EUR |

---

*Report generato il 2026-01-30*
*Progetto: UCBM - Project 4 - Sistema Energetico con Idrogeno*
*Metodologia: MPC Rolling Horizon con ottimizzazione MILP*
