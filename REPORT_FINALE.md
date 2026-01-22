Report finale

Scopo del progetto

- Progettare un workflow di ottimizzazione/controllo per un sistema energetico integrato con PV, wind, carico, elettrolizzatore, H2 storage, fuel cell, DG non rinnovabile e scambio con rete.

Cosa include il modello

![Modello di sistema](assets/model_page1.png)

Cosa include il sistema (componenti)

- PV (fotovoltaico): genera energia in presenza di sole.
- Wind (eolico): genera energia in presenza di vento.
- Carico (Pul): richiesta di energia elettrica degli edifici.
- Rete: import (acquisto energia) ed export (vendita energia).
- Elettrolizzatore (ELY): converte elettricita in idrogeno.
- H2 storage (HSS): accumula idrogeno per uso futuro.
- Fuel cell (FC): riconverte idrogeno in elettricita.
- DG non rinnovabile: generatore di backup a combustibile.

Criterio decisionale (strategia ottima)

- Priorita alle rinnovabili (PV/Wind) perche hanno costo marginale nullo.
- Se c’e surplus:
  - prima si carica H2 con l’elettrolizzatore;
  - se H2 e pieno, si esporta in rete.
- Se manca energia:
  - si usa la fuel cell (se H2 disponibile);
  - in alternativa si importa dalla rete;
  - il DG entra solo se economicamente migliore o necessario per coprire la domanda.
- Export si effettua solo se e piu conveniente che immagazzinare o usare internamente.

Cosa abbiamo fatto (passi principali)

1) Raccolta e ispezione dati:
   - Profili PV e wind in p.u. (forecast/actual).
   - Carico edificio (forecast/actual) in kWh.
   - Prezzi PUN per export.
2) Allineamento temporale:
   - Conversione ore del carico e sincronizzazione con le 8760 ore disponibili.
   - Analisi limitata alle 6528 ore presenti in Pul.
3) Conversione unita:
   - PV e wind convertiti da p.u. a MW con nominali 4 MW e 11.34 MW.
   - Carico convertito da kWh a MW e scalato al nominale scelto.
4) Prezzi e tariffe:
   - Export valorizzato con PUN.
   - Import valorizzato con tariffe F1/F2/F3 (schema ARERA con festivita italiane).
5) Modello MPC:
   - Bilancio energetico orario con vincoli di potenza.
   - Dinamica H2 con efficienze di elettrolizzatore e fuel cell.
   - Funzione obiettivo: costo import + costo DG - ricavo export + penalita curtailment.
6) Simulazione receding-horizon (24h):
   - Esecuzione su tutte le 6528 ore.
   - Generazione report sintetici e grafici.

Perche queste scelte

- Scenari 16 MW e 20 MW:
  - In letteratura e nel materiale fornito compaiono entrambi i valori; si e scelto di confrontarli.
  - Lo scaling del profilo mantiene la forma reale del carico e cambia solo il livello di consumo.
- Tariffe F1/F2/F3:
  - Rappresentano la struttura reale dei prezzi orari ARERA in Italia.
  - Permettono una valutazione coerente dei costi di import.
- MPC con orizzonte 24h:
  - Riflette un controllo giornaliero con informazioni previsionali disponibili.
  - E utile per valutare strategie di gestione H2 e scambio rete.

Risultati sintetici (6528 ore)

Scenario 16 MW
- Energia carico: 47,650.79 MWh
- Import: 15,761.13 MWh
- Export: 13,056.57 MWh
- DG: 23,779.96 MWh
- Costo netto: 11,220,135.38 EUR

Scenario 20 MW
- Energia carico: 47,650.79 MWh
- Import: 21,524.93 MWh
- Export: 12,204.95 MWh
- DG: 26,695.43 MWh
- Costo netto: 15,858,373.25 EUR

Interpretazione dei risultati

- A 20 MW il sistema deve coprire un fabbisogno maggiore: cresce l’import dalla rete e aumenta l’uso del DG.
- Il costo netto aumenta sensibilmente rispetto allo scenario 16 MW.
- La produzione rinnovabile e identica in entrambi gli scenari; la differenza deriva dal livello di carico.

Tabella comparativa (16 vs 20 MW)

| Voce | 16 MW | 20 MW |
| --- | ---: | ---: |
| Energia carico (MWh) | 47,650.79 | 47,650.79 |
| Import (MWh) | 15,761.13 | 21,524.93 |
| Export (MWh) | 13,056.57 | 12,204.95 |
| DG (MWh) | 23,779.96 | 26,695.43 |
| Costo netto (EUR) | 11,220,135.38 | 15,858,373.25 |

Limiti e note

- Il profilo Pul copre 6528 ore; l’analisi non include l’intero anno.
- I minimi tecnici di DG, elettrolizzatore e fuel cell sono modellati con variabili binarie.
- Alcune assunzioni tariffarie possono essere aggiornate con un calendario ufficiale piu dettagliato.

Prossimi passi consigliati

- Inserire vincoli di minimo tecnico con modello MIP.
- Aggiungere costi di avviamento/accensione e manutenzione.
- Estendere a 8760 ore se si dispone di un profilo completo del carico.

F1, F2, F3 (spiegazione semplice)

- F1: fascia di punta nei giorni feriali (tipicamente 08-19).
- F2: fascia intermedia (mattina presto e sera feriale, e sabato diurno).
- F3: fascia fuori punta (notti, domeniche e festivita).

Legenda dei file e uso nel progetto

- data/res_1_year_pu.mat: profili PV e wind in p.u. (forecast/actual), convertiti in MW con i nominali.
- data/buildings_load.mat: carico edificio in kWh, convertito in MW e scalato ai nominali 16/20 MW.
- data/PUN_2022.mat: prezzi PUN per il ricavo da export.
- data/Projects.pdf: dati di impianto, limiti e assunzioni tariffarie.
- configs/system.yaml: parametri di sistema e scenari (nominali, efficienze, tariffe).
- src/loader.py: caricamento dati, conversioni e allineamento orario.
- src/tariff.py: regole F1/F2/F3 e calendario festivita.
- src/model.py: modello MPC con vincoli e funzione obiettivo.
- src/run_mpc.py: test MPC su orizzonte singolo.
- src/run_mpc_full.py: simulazione receding-horizon su tutto il periodo.
- src/report.py: report sintetici e grafici.
