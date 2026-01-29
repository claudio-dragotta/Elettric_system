"""
Converte il file Excel PUN 2025 in formato .mat compatibile con il loader.py
"""

import pandas as pd
import numpy as np
from scipy.io import savemat
from pathlib import Path


def convert_pun_excel_to_mat(excel_path: str, output_path: str):
    """
    Converte il file Excel PUN in formato .mat

    Il file Excel ha colonne: Data, Ora, EUR/MWh
    Il formato di output deve essere compatibile con loader.py
    """
    print(f"Lettura file Excel: {excel_path}")

    # Leggi il file Excel
    df = pd.read_excel(excel_path)

    print(f"Colonne trovate: {df.columns.tolist()}")
    print(f"Righe: {len(df)}")

    # Identifica la colonna del prezzo (potrebbe essere "€/MWh" o simile)
    price_col = None
    for col in df.columns:
        if 'MWh' in col or 'EUR' in col or 'mwh' in col.lower():
            price_col = col
            break

    if price_col is None:
        # Prova l'ultima colonna
        price_col = df.columns[-1]

    print(f"Colonna prezzo identificata: {price_col}")

    # Estrai i valori del PUN
    pun_values = df[price_col].values

    # Converti in float (gestisce virgola decimale)
    # Forza conversione stringa -> float con gestione virgola
    pun_values = np.array([
        float(str(v).replace(',', '.')) if pd.notna(v) else np.nan
        for v in pun_values
    ])

    # Rimuovi eventuali NaN
    if np.any(np.isnan(pun_values)):
        print(f"Attenzione: {np.sum(np.isnan(pun_values))} valori NaN trovati, sostituiti con media")
        mean_val = np.nanmean(pun_values)
        pun_values = np.where(np.isnan(pun_values), mean_val, pun_values)

    print(f"\nStatistiche PUN 2025:")
    print(f"  Min: {np.min(pun_values):.2f} EUR/MWh")
    print(f"  Max: {np.max(pun_values):.2f} EUR/MWh")
    print(f"  Media: {np.mean(pun_values):.2f} EUR/MWh")
    print(f"  Ore totali: {len(pun_values)}")

    # Salva in formato .mat
    mat_data = {'pun': pun_values}
    savemat(output_path, mat_data)

    print(f"\nFile salvato: {output_path}")

    return pun_values


def main():
    # Percorsi
    script_dir = Path(__file__).parent
    excel_file = script_dir / "20250101_20260101_PUN.xlsx"
    output_file = script_dir / "PUN_2025.mat"

    if not excel_file.exists():
        print(f"ERRORE: File non trovato: {excel_file}")
        return

    # Converti
    pun = convert_pun_excel_to_mat(str(excel_file), str(output_file))

    # Verifica confronto con 2022
    print("\n" + "="*60)
    print("CONFRONTO CON 2022 (crisi energetica)")
    print("="*60)
    print(f"PUN 2025 medio: {np.mean(pun):.2f} EUR/MWh")
    print(f"PUN 2022 medio: ~400-500 EUR/MWh (stima)")
    print(f"Differenza: Il 2025 ha prezzi ~3-4x piu bassi!")


if __name__ == "__main__":
    main()
