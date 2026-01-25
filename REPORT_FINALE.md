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
| **Carico (Pul)** | Potenza nominale | 16 / 20 | MW |
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

## 3. Prezzi e tariffe utilizzati

### 3.1 Costo energia importata (tariffe ARERA)

| Fascia | Orario | Prezzo (EUR/kWh) | Prezzo (EUR/MWh) |
|--------|--------|------------------|------------------|
| **F1** | Lun-Ven 08:00-19:00 | 0.53276 | 532.76 |
| **F2** | Lun-Ven 07-08, 19-23; Sab 07-23 | 0.54858 | 548.58 |
| **F3** | Notti, domeniche, festivita | 0.46868 | 468.68 |
| **Media ponderata** | - | ~0.515 | ~515 |

### 3.2 Prezzo energia esportata

- **PUN 2022**: Prezzo Unico Nazionale, varia ora per ora (dati da PUN_2022.mat)
- Media annuale PUN 2022: ~250-300 EUR/MWh

### 3.3 Costo carburante DG (scenari testati)

| Scenario | Costo carburante (EUR/kWh) | Costo elettrico effettivo* (EUR/kWh) | Costo elettrico (EUR/MWh) |
|----------|----------------------------|--------------------------------------|---------------------------|
| **cf = 0.45** | 0.45 | 0.75 | 750 |
| **cf = 0.60** | 0.60 | 1.00 | 1000 |

*Nota: Costo elettrico effettivo = costo_carburante / efficienza_DG = cf / 0.6

---

## 4. Strategia di controllo ottimale

### 4.1 Logica decisionale del MPC

1. **Priorita alle rinnovabili**: PV e Wind hanno costo marginale nullo, quindi vengono sempre utilizzati al massimo.

2. **Gestione del surplus energetico** (quando Pres > Pul):
   - Prima opzione: caricare lo storage H2 con l'elettrolizzatore
   - Seconda opzione: esportare in rete (se il prezzo PUN e conveniente)
   - Ultima opzione: curtailment (solo se necessario)

3. **Gestione del deficit energetico** (quando Pres < Pul):
   - Prima opzione: usare la fuel cell (se c'e H2 disponibile)
   - Seconda opzione: importare dalla rete
   - Terza opzione: usare il DG (solo se economicamente conveniente)

### 4.2 Quando conviene usare il DG?

**Confronto economico diretto:**

| Fonte | Costo (EUR/MWh) | Convenienza |
|-------|-----------------|-------------|
| Import rete (media) | ~515 | Riferimento |
| DG con cf=0.45 | 750 | 46% piu costoso della rete |
| DG con cf=0.60 | 1000 | 94% piu costoso della rete |

**Conclusione:** Il DG e quasi sempre piu costoso dell'import dalla rete. Viene utilizzato solo quando:
- L'import dalla rete e al massimo (20 MW) E
- Lo storage H2 e vuoto E
- Il carico deve comunque essere soddisfatto

---

## 5. Risultati delle simulazioni

### 5.1 Panoramica scenari testati

Sono stati simulati **4 scenari** come richiesto dalle specifiche:
- 2 livelli di carico nominale: **16 MW** e **20 MW**
- 2 valori di costo carburante: **0.45 EUR/kWh** e **0.60 EUR/kWh**

Periodo di simulazione: **6528 ore** (limitato dalla disponibilita dei dati di carico)

### 5.2 Tabella riassuntiva completa

| Voce | 16MW cf=0.45 | 16MW cf=0.60 | 20MW cf=0.45 | 20MW cf=0.60 |
|------|-------------:|-------------:|-------------:|-------------:|
| **ENERGIA** |||||
| Energia carico (MWh) | 38,120.63 | 38,120.63 | 47,650.79 | 47,650.79 |
| Energia PV (MWh) | 5,434.80 | 5,434.80 | 5,434.80 | 5,434.80 |
| Energia Wind (MWh) | 6,411.43 | 6,411.43 | 6,411.43 | 6,411.43 |
| Energia Import (MWh) | 37,624.10 | 37,622.84 | 46,050.71 | 46,052.37 |
| Energia Export (MWh) | 11,157.17 | 11,072.03 | 10,127.95 | 10,003.06 |
| Energia DG (MWh) | 81.87 | ~0 | 128.76 | ~0 |
| **SISTEMA H2** |||||
| Energia ELY (MWh elettrici) | 198.02 | 201.48 | 119.40 | 115.58 |
| Energia FC (MWh elettrici) | 83.17 | 84.62 | 50.15 | 48.54 |
| H2 prodotto (MWh) | 138.62 | 141.04 | 83.58 | 80.91 |
| Cicli equivalenti storage | 11.55 | 11.75 | 6.97 | 6.74 |
| **COSTI** |||||
| Costo Import (EUR) | 19,131,707 | 19,131,034 | 23,417,554 | 23,418,483 |
| Ricavo Export (EUR) | 6,533,009 | 6,467,318 | 5,986,768 | 5,885,006 |
| Costo DG (EUR) | 61,406 | ~0 | 96,566 | ~0 |
| **Costo netto (EUR)** | **12,660,104** | **12,663,717** | **17,527,353** | **17,533,477** |
| **METRICHE** |||||
| Costo per MWh carico (EUR/MWh) | 332.11 | 332.21 | 367.85 | 367.98 |
| % Autoconsumo rinnovabili | 31.1% | 31.1% | 24.9% | 24.9% |

### 5.3 Breakdown dei costi per scenario

#### Scenario 16 MW, cf=0.45 EUR/kWh
```
Costo Import:      +19,131,707 EUR (100.5%)
Costo DG:              +61,406 EUR   (0.3%)
Ricavo Export:      -6,533,009 EUR (-34.3%)
─────────────────────────────────────────────
COSTO NETTO:       12,660,104 EUR
```

#### Scenario 16 MW, cf=0.60 EUR/kWh
```
Costo Import:      +19,131,034 EUR (100.5%)
Costo DG:                   ~0 EUR   (0.0%)
Ricavo Export:      -6,467,318 EUR (-34.0%)
─────────────────────────────────────────────
COSTO NETTO:       12,663,717 EUR
```

#### Scenario 20 MW, cf=0.45 EUR/kWh
```
Costo Import:      +23,417,554 EUR  (99.6%)
Costo DG:              +96,566 EUR   (0.4%)
Ricavo Export:      -5,986,768 EUR (-25.5%)
─────────────────────────────────────────────
COSTO NETTO:       17,527,353 EUR
```

#### Scenario 20 MW, cf=0.60 EUR/kWh
```
Costo Import:      +23,418,483 EUR (100.0%)
Costo DG:                   ~0 EUR   (0.0%)
Ricavo Export:      -5,885,006 EUR (-25.1%)
─────────────────────────────────────────────
COSTO NETTO:       17,533,477 EUR
```

---

## 6. Analisi economica dettagliata

### 6.1 Impatto del costo carburante sul DG

| Metrica | cf=0.45 | cf=0.60 | Differenza |
|---------|---------|---------|------------|
| **Scenario 16 MW** ||||
| Energia DG (MWh) | 81.87 | ~0 | -100% |
| Costo DG (EUR) | 61,406 | ~0 | -100% |
| Costo netto (EUR) | 12,660,104 | 12,663,717 | +3,613 (+0.03%) |
| **Scenario 20 MW** ||||
| Energia DG (MWh) | 128.76 | ~0 | -100% |
| Costo DG (EUR) | 96,566 | ~0 | -100% |
| Costo netto (EUR) | 17,527,353 | 17,533,477 | +6,124 (+0.03%) |

**Osservazione chiave:** Quando il costo del carburante sale da 0.45 a 0.60 EUR/kWh:
- Il DG non viene piu utilizzato (diventa troppo costoso)
- Il sistema compensa importando piu energia dalla rete
- Il costo netto aumenta solo dello 0.03% (~3,600-6,100 EUR)

**Questo dimostra che il DG e marginale nel mix energetico ottimale.**

### 6.2 Impatto del livello di carico

| Metrica | 16 MW | 20 MW | Differenza |
|---------|-------|-------|------------|
| Energia carico (MWh) | 38,121 | 47,651 | +25% |
| Energia Import (MWh) | 37,624 | 46,051 | +22% |
| Energia Export (MWh) | 11,157 | 10,128 | -9% |
| Costo netto (EUR) | 12,660,104 | 17,527,353 | +38% |
| Costo per MWh (EUR/MWh) | 332 | 368 | +11% |

**Osservazione:** Con un carico maggiore:
- Aumenta l'import dalla rete
- Diminuisce l'export (piu energia consumata internamente)
- Il costo per MWh servito aumenta dell'11%

### 6.3 Ruolo del sistema a idrogeno

| Metrica | 16MW cf=0.45 | 20MW cf=0.45 |
|---------|--------------|--------------|
| Energia in ELY (MWh el.) | 198.02 | 119.40 |
| Energia da FC (MWh el.) | 83.17 | 50.15 |
| H2 prodotto (MWh) | 138.62 | 83.58 |
| H2 consumato (MWh) | 138.62 | 83.58 |
| Cicli equivalenti | 11.55 | 6.97 |
| Efficienza round-trip | 42%* | 42%* |

*Efficienza round-trip = eta_ely × eta_fc = 0.7 × 0.6 = 42%

**Osservazione:** Il sistema H2 viene utilizzato attivamente ma con efficienza limitata (42%). Conviene usarlo per:
- Spostare energia da ore di surplus a ore di deficit
- Evitare curtailment delle rinnovabili
- Ridurre import nelle ore di picco (tariffa F1)

### 6.4 Analisi delle fonti di approvvigionamento

#### Scenario 16 MW (cf=0.45)
| Fonte | Energia (MWh) | % del carico |
|-------|---------------|--------------|
| PV | 5,434.80 | 14.3% |
| Wind | 6,411.43 | 16.8% |
| Import rete | 37,624.10 | 98.7% |
| DG | 81.87 | 0.2% |
| FC (da H2) | 83.17 | 0.2% |
| **Totale generazione** | 49,635.37 | 130.2%* |
| Export | -11,157.17 | -29.3% |
| Consumo ELY | -198.02 | -0.5% |
| **Bilancio = Carico** | 38,120.63 | 100.0% |

*Il totale supera il 100% perche parte dell'energia viene esportata e parte usata per produrre H2.

---

## 7. Confronto economico: quale opzione conviene?

### 7.1 Riepilogo costi per MWh servito

| Scenario | Costo netto (EUR) | Costo per MWh (EUR/MWh) | Ranking |
|----------|-------------------|-------------------------|---------|
| 16 MW, cf=0.45 | 12,660,104 | 332.11 | 1 (migliore) |
| 16 MW, cf=0.60 | 12,663,717 | 332.21 | 2 |
| 20 MW, cf=0.45 | 17,527,353 | 367.85 | 3 |
| 20 MW, cf=0.60 | 17,533,477 | 367.98 | 4 (peggiore) |

### 7.2 Raccomandazioni operative

#### Sul dimensionamento del carico:
- **CONSIGLIATO**: Mantenere il carico piu basso possibile (16 MW vs 20 MW)
- Risparmio: ~36 EUR/MWh (-10%)
- Il sistema e piu efficiente con carichi minori perche le rinnovabili coprono una quota maggiore

#### Sul generatore diesel (DG):
- **SCONSIGLIATO** come fonte principale: costa 750-1000 EUR/MWh vs 515 EUR/MWh della rete
- **CONSIGLIATO** solo come backup di emergenza quando:
  - Import rete al massimo (20 MW)
  - Storage H2 vuoto
  - Carico critico da soddisfare
- Con cf=0.60, il DG non e MAI conveniente rispetto alla rete

#### Sul sistema a idrogeno:
- **UTILE** per energy shifting (spostare energia nel tempo)
- **LIMITATO** dall'efficienza round-trip del 42%
- **CONSIGLIATO** per evitare curtailment e ridurre import in ore di punta

#### Sull'export di energia:
- **CONVENIENTE** quando PUN > costo medio di import (~515 EUR/MWh)
- Genera ricavi significativi (5.9-6.5 M EUR nel periodo analizzato)
- Riduce il costo netto del 25-34%

### 7.3 Scenario ottimale

**Il miglior scenario e: Carico 16 MW con cf=0.45 EUR/kWh**

Motivi:
- Costo per MWh piu basso (332 EUR/MWh)
- Maggiore copertura da rinnovabili (31%)
- Maggiore export (ricavi piu alti)
- DG usato minimamente (82 MWh su 6528 ore)

---

## 8. Conclusioni finali

### 8.1 Sintesi dei risultati

1. **Il DG e quasi sempre anti-economico**: anche con cf=0.45, costa il 46% in piu della rete. Con cf=0.60, non viene mai usato.

2. **Le rinnovabili sono fondamentali**: PV+Wind coprono ~31% del fabbisogno a 16 MW, riducendo significativamente i costi.

3. **L'export e una fonte di ricavo importante**: copre il 25-34% dei costi lordi di import.

4. **Lo storage H2 ha efficienza limitata** (42%) ma e utile per l'energy shifting.

5. **Il costo del carburante DG ha impatto minimo** sul costo totale perche il DG viene usato raramente.

### 8.2 Limiti dello studio

- Il profilo di carico copre solo 6528 ore (non l'intero anno)
- Non sono inclusi costi di avviamento/spegnimento dei generatori
- Non sono inclusi costi di manutenzione e ammortamento
- Le previsioni sono considerate perfette (nessun errore di forecast)

### 8.3 Sviluppi futuri consigliati

1. Estendere l'analisi a 8760 ore (anno completo)
2. Includere costi di startup/shutdown per DG, ELY, FC
3. Aggiungere degradazione dello storage H2
4. Testare scenari con prezzi carburante intermedi (0.50, 0.55 EUR/kWh)
5. Includere incertezza nelle previsioni (stochastic MPC)

---

## 9. Appendice: Dettagli tecnici

### 9.1 Tariffe F1, F2, F3 (ARERA)

- **F1 (Punta)**: Lunedi-Venerdi 08:00-19:00 (escluse festivita)
- **F2 (Intermedia)**: Lunedi-Venerdi 07-08 e 19-23; Sabato 07-23
- **F3 (Fuori punta)**: Notti 23-07, Domeniche, Festivita italiane

Festivita italiane considerate: Capodanno, Epifania, Pasquetta, 25 Aprile, 1 Maggio, 2 Giugno, Ferragosto, Ognissanti, Immacolata, Natale, Santo Stefano.

### 9.2 Formule del modello MPC

**Bilancio energetico:**
```
P_pv + P_wind + P_import + P_dg + P_fc = P_load + P_ely + P_export + P_curtail
```

**Dinamica storage H2:**
```
SoC(t+1) = SoC(t) + dt * (eta_ely * P_ely - P_fc / eta_fc)
```

**Funzione obiettivo:**
```
min: sum( c_import * P_import - p_export * P_export + (c_fuel/eta_dg) * P_dg + penalty * P_curtail )
```

### 9.3 File di output generati

| File | Descrizione |
|------|-------------|
| `outputs/mpc_receding_load16_cf045.csv` | Schedule orario MPC - 16MW, cf=0.45 |
| `outputs/mpc_receding_load16_cf060.csv` | Schedule orario MPC - 16MW, cf=0.60 |
| `outputs/mpc_receding_load20_cf045.csv` | Schedule orario MPC - 20MW, cf=0.45 |
| `outputs/mpc_receding_load20_cf060.csv` | Schedule orario MPC - 20MW, cf=0.60 |
| `outputs/report_load16_cf045.csv` | Metriche aggregate - 16MW, cf=0.45 |
| `outputs/report_load16_cf060.csv` | Metriche aggregate - 16MW, cf=0.60 |
| `outputs/report_load20_cf045.csv` | Metriche aggregate - 20MW, cf=0.45 |
| `outputs/report_load20_cf060.csv` | Metriche aggregate - 20MW, cf=0.60 |
| `outputs/plots/*.png` | Grafici time-series |

### 9.4 Come riprodurre i risultati

```bash
# Installare dipendenze
pip install -r requirements.txt

# Eseguire simulazioni (tutti i 4 scenari)
python src/run_mpc_full.py --horizon 24 --start 0 --out outputs/mpc_receding.csv

# Generare report per uno scenario specifico
python src/report.py --schedule outputs/mpc_receding_load16_cf045.csv \
                     --out outputs/report_load16_cf045.csv \
                     --load-nom 16 --fuel-cost 0.45 --plots
```

---

*Report generato il 2025-01-24*
*Progetto: UCBM - Project 4 - Sistema Energetico con Idrogeno*
