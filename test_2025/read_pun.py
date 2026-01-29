import pandas as pd

# Leggi il file Excel
df = pd.read_excel('20250101_20260101_PUN.xlsx')

print("=" * 60)
print("ANALISI FILE PUN 2025")
print("=" * 60)
print(f"\nColonne: {df.columns.tolist()}")
print(f"Numero righe: {len(df)}")
print(f"\nPrime 10 righe:")
print(df.head(10))
print(f"\nUltime 5 righe:")
print(df.tail(5))
print(f"\nStatistiche:")
print(df.describe())
