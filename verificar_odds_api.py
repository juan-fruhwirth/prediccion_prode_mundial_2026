"""
Verificación de datos disponibles en The Odds API para el Mundial 2026.
Costo: 0 créditos (sports + events son gratis) + 3 créditos (1 llamada a /odds)
"""

import requests
import json

API_KEY = "2e9755c5f8904af9503226b9f8c20df6"
BASE = "https://api.the-odds-api.com/v4"
SPORT = "soccer_fifa_world_cup"

def print_credits(headers):
    print(f"  Créditos usados: {headers.get('x-requests-used')}")
    print(f"  Créditos restantes: {headers.get('x-requests-remaining')}")
    print(f"  Costo última llamada: {headers.get('x-requests-last')}")

# ----------------------------------------------------------------
# PASO 1: Verificar que el Mundial existe (GRATIS)
# ----------------------------------------------------------------
print("=" * 60)
print("PASO 1 — Deportes disponibles (gratis)")
print("=" * 60)

r = requests.get(f"{BASE}/sports/", params={"apiKey": API_KEY, "all": "true"})
sports = r.json()

world_cup = [s for s in sports if "world_cup" in s["key"].lower() or "fifa" in s["key"].lower()]
if world_cup:
    for s in world_cup:
        print(f"  ✅ {s['key']} | active={s['active']} | {s['title']}")
else:
    print("  ❌ No se encontró ningún Mundial en los deportes disponibles")
    # Mostrar todos los soccer por si acaso
    print("\n  Todos los soccer disponibles:")
    for s in sports:
        if "soccer" in s["key"]:
            print(f"    {s['key']} | active={s['active']}")

# ----------------------------------------------------------------
# PASO 2: Listar eventos/partidos (GRATIS)
# ----------------------------------------------------------------
print("\n" + "=" * 60)
print("PASO 2 — Partidos disponibles (gratis)")
print("=" * 60)

r = requests.get(f"{BASE}/sports/{SPORT}/events", params={"apiKey": API_KEY})

if r.status_code != 200:
    print(f"  ❌ Error {r.status_code}: {r.text}")
else:
    events = r.json()
    print(f"  Total partidos encontrados: {len(events)}")
    print()
    for e in events:
        print(f"  {e['commence_time'][:10]}  {e['home_team']} vs {e['away_team']}")

# ----------------------------------------------------------------
# PASO 3: Cuotas reales — 1X2 + OU + AH (cuesta 3 créditos)
# ----------------------------------------------------------------
print("\n" + "=" * 60)
print("PASO 3 — Cuotas disponibles (cuesta 3 créditos)")
print("=" * 60)
input("  Presioná Enter para continuar y gastar 3 créditos...")

r = requests.get(
    f"{BASE}/sports/{SPORT}/odds",
    params={
        "apiKey": API_KEY,
        "regions": "eu",
        "markets": "h2h,totals,spreads",
        "oddsFormat": "decimal",
        "bookmakers": "pinnacle",   # Solo Pinnacle para ver si está disponible
    }
)
print_credits(r.headers)

if r.status_code != 200:
    print(f"  ❌ Error {r.status_code}: {r.text}")
else:
    events = r.json()
    print(f"\n  Partidos con cuotas: {len(events)}")

    for e in events:
        print(f"\n  {'─'*50}")
        print(f"  {e['commence_time'][:10]}  {e['home_team']} vs {e['away_team']}")

        for bookie in e.get("bookmakers", []):
            print(f"    Bookmaker: {bookie['title']}")
            for market in bookie.get("markets", []):
                key = market["key"]
                outcomes = market["outcomes"]
                if key == "h2h":
                    probs = {o["name"]: round(1/o["price"], 3) for o in outcomes}
                    print(f"      1X2:     {json.dumps(probs)}")
                elif key == "totals":
                    for o in outcomes:
                        print(f"      OU {o.get('point','?')}: {o['name']} @ {o['price']}")
                elif key == "spreads":
                    for o in outcomes:
                        print(f"      AH {o.get('point','?')}: {o['name']} @ {o['price']}")

    # Si Pinnacle no apareció, repetir sin filtro de bookmaker
    if all(len(e.get("bookmakers", [])) == 0 for e in events):
        print("\n  ⚠️  Pinnacle no tiene cuotas. Probando sin filtro de bookmaker...")
        r2 = requests.get(
            f"{BASE}/sports/{SPORT}/odds",
            params={
                "apiKey": API_KEY,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal",
            }
        )
        events2 = r2.json()
        bookmakers_vistos = set()
        for e in events2:
            for b in e.get("bookmakers", []):
                bookmakers_vistos.add(b["key"])
        print(f"  Bookmakers disponibles para el Mundial: {sorted(bookmakers_vistos)}")