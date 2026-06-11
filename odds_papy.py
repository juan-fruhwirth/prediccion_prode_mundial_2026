import requests, time

API_KEY = "2d191854-749e-4e8c-855a-691778cda7b4"

# Probar con Liverpool vs Leeds, betfair-ex, outcomeId home (101 es típico para home en OddsPapi)
for outcome_id in ["101", "102", "103"]:
    r = requests.get(
        "https://api.oddspapi.io/v4/historical-odds",
        params={
            "apiKey": API_KEY,
            "fixtureId": "id1000000769348410",
            "bookmakers": "betfair-ex",
            "outcomeId": outcome_id
        }
    )
    print(f"outcomeId={outcome_id} — Status: {r.status_code}")
    print(r.json())
    print()
    time.sleep(5.1)