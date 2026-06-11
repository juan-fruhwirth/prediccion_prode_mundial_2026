import json, os

all_fixtures = []
for fname in os.listdir("data"):
    if fname.startswith("oddspapi_fixtures_") and fname != "oddspapi_fixtures_all.json":
        with open(f"data/{fname}") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_fixtures.extend(data)

fixtures_2026 = [f for f in all_fixtures if f.get("trueEndTime") and f.get("startTime", "") >= "2026-01-01"]
print(f"Total fixtures 2026 terminados: {len(fixtures_2026)}")
print(f"Con hasOdds=True: {len([f for f in fixtures_2026 if f.get('hasOdds')])}")