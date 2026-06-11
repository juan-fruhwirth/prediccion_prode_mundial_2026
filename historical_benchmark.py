import pandas as pd
import glob

BASE = "C:/Users/Usuario/historical_football_data"
archivos = [f for f in glob.glob(f"{BASE}/*.csv") if "combined" not in f]

dfs = []
for path in archivos:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)

data["Date"] = pd.to_datetime(data["Date"], dayfirst=True)

print("Partidos por año:")
print(data["Date"].dt.year.value_counts().sort_index())

print("\nPartidos post-2023:")
print(len(data[data["Date"].dt.year > 2023]))