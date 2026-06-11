import requests
import time
import re
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.pinnacle.com/",
    "X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R",
    "Accept": "application/json",
}

def american_to_decimal(p):
    return (p/100)+1 if p > 0 else (100/abs(p))+1

def devig(probs):
    t = sum(probs.values())
    return {k: round(v/t, 4) for k, v in probs.items()}

def margin(probs):
    """Margen = suma de probabilidades implícitas - 1, en porcentaje."""
    return round((sum(probs.values()) - 1) * 100, 4)


def get_straight_markets(matchup_id: int) -> dict:
    """Trae 1X2, O/U múltiples líneas, AH, team totals. Guarda márgenes."""
    url = f"https://guest.api.arcadia.pinnacle.com/0.1/matchups/{matchup_id}/markets/related/straight"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()

    result = {
        "moneyline": None, "total_main": None, "totals_alt": [],
        "spread_main": None, "spreads_alt": [], "tt_home": None, "tt_away": None,
        "margins": {
            "moneyline": None,
            "total_main": None,
            "totals_alt": [],
            "spread_main": None,
            "spreads_alt": [],
            "tt_home": None,
            "tt_away": None,
        }
    }

    for m in data:
        if m.get("matchupId") != matchup_id or m.get("period") != 0:
            continue
        if any("participantId" in p for p in m.get("prices", [])):
            continue

        mtype = m["type"]
        is_alt = m.get("isAlternate", False)
        prices = m["prices"]

        if mtype == "moneyline" and not is_alt:
            raw = {}
            for p in prices:
                raw[p["designation"]] = 1/american_to_decimal(p["price"])
            if len(raw) == 3:
                result["margins"]["moneyline"] = margin(raw)
                result["moneyline"] = devig(raw)

        elif mtype == "total":
            over = under = line = None
            for p in prices:
                if p["designation"] == "over":
                    over = 1/american_to_decimal(p["price"]); line = p["points"]
                else:
                    under = 1/american_to_decimal(p["price"])
            if over and under:
                raw = {"over": over, "under": under}
                m_val = margin(raw)
                entry = {"line": line, **devig(raw)}
                margin_entry = {"line": line, "margin": m_val}
                if not is_alt:
                    result["total_main"] = entry
                    result["margins"]["total_main"] = margin_entry
                else:
                    result["totals_alt"].append(entry)
                    result["margins"]["totals_alt"].append(margin_entry)

        elif mtype == "spread":
            home = away = line = None
            for p in prices:
                if p["designation"] == "home":
                    home = 1/american_to_decimal(p["price"]); line = p["points"]
                else:
                    away = 1/american_to_decimal(p["price"])
            if home and away:
                raw = {"home": home, "away": away}
                m_val = margin(raw)
                entry = {"line": line, **devig(raw)}
                margin_entry = {"line": line, "margin": m_val}
                if not is_alt:
                    result["spread_main"] = entry
                    result["margins"]["spread_main"] = margin_entry
                else:
                    result["spreads_alt"].append(entry)
                    result["margins"]["spreads_alt"].append(margin_entry)

        elif mtype == "team_total":
            side = m.get("side")
            over = under = line = None
            for p in prices:
                if p["designation"] == "over":
                    over = 1/american_to_decimal(p["price"]); line = p["points"]
                else:
                    under = 1/american_to_decimal(p["price"])
            if over and under:
                raw = {"over": over, "under": under}
                m_val = margin(raw)
                entry = {"line": line, **devig(raw)}
                margin_entry = {"line": line, "margin": m_val}
                if side == "home" and (result["tt_home"] is None or not is_alt):
                    result["tt_home"] = entry
                    result["margins"]["tt_home"] = margin_entry
                elif side == "away" and (result["tt_away"] is None or not is_alt):
                    result["tt_away"] = entry
                    result["margins"]["tt_away"] = margin_entry

    result["totals_alt"].sort(key=lambda x: x["line"])
    result["spreads_alt"].sort(key=lambda x: x["line"])
    result["margins"]["totals_alt"].sort(key=lambda x: x["line"])
    result["margins"]["spreads_alt"].sort(key=lambda x: x["line"])
    return result


def get_correct_score(matchup_id: int, specials: list) -> tuple[dict, float | None]:
    """
    Extrae el Correct Score del response de la liga.
    Retorna (scores_desvigiados, margen).
    """
    cs_special = None
    for item in specials:
        if (item.get("type") == "special"
                and item.get("parentId") == matchup_id
                and item.get("special", {}).get("description") == "Correct Score"
                and item.get("periods", [{}])[0].get("period") == 0):
            cs_special = item
            break

    if not cs_special:
        return {}, None

    id_to_name = {p["id"]: p["name"] for p in cs_special.get("participants", [])}

    special_id = cs_special["id"]
    url = f"https://guest.api.arcadia.pinnacle.com/0.1/matchups/{special_id}/markets/related/straight"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return {}, None

    raw_probs = {}
    for m in r.json():
        if m.get("matchupId") != special_id:
            continue
        for p in m.get("prices", []):
            pid = p.get("participantId")
            if pid and pid in id_to_name:
                name = id_to_name[pid]
                match = re.match(r".+? (\d+), .+? (\d+)$", name)
                if match:
                    score = (int(match.group(1)), int(match.group(2)))
                    raw_probs[score] = 1/american_to_decimal(p["price"])

    if not raw_probs:
        return {}, None

    cs_margin = margin(raw_probs)
    cs_devigged = {f"{h}-{a}": round(p, 4) for (h,a), p in devig(raw_probs).items()}
    return cs_devigged, cs_margin


def get_all_wc_matchups():
    """Trae todos los partidos del Mundial (solo type='matchup', no specials)."""
    url = "https://guest.api.arcadia.pinnacle.com/0.1/leagues/2686/matchups"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    all_data = r.json()

    matchups = [m for m in all_data
                if m.get("type") == "matchup"
                and m.get("parentId") is None
                and m.get("status") == "pending"]

    return matchups, all_data


def process_all_matches():
    print("Obteniendo partidos del Mundial...")
    matchups, all_specials = get_all_wc_matchups()
    print(f"Partidos encontrados: {len(matchups)}")

    results = []
    for m in matchups:
        mid = m["id"]
        home = m["participants"][0]["name"]
        away = m["participants"][1]["name"]
        start = m["startTime"]

        print(f"\n{'='*55}")
        print(f"{home} vs {away} ({start[:10]})")

        time.sleep(1.5)
        try:
            straight = get_straight_markets(mid)
        except Exception as e:
            print(f"  Error straight: {e}")
            continue

        time.sleep(1.5)
        cs, cs_margin = get_correct_score(mid, all_specials)

        match_data = {
            "matchup_id": mid,
            "home": home,
            "away": away,
            "start_time": start,
            "markets": {k: v for k, v in straight.items() if k != "margins"},
            "margins": {
                **straight["margins"],
                "correct_score": cs_margin,
            },
            "correct_score": cs,
        }
        results.append(match_data)

        # Print resumen con márgenes
        mg = straight["margins"]
        if straight["moneyline"]:
            ml = straight["moneyline"]
            print(f"  1X2:  {home} {ml['home']*100:.1f}% | X {ml['draw']*100:.1f}% | {away} {ml['away']*100:.1f}%  [margen: {mg['moneyline']:.2f}%]")
        if straight["total_main"]:
            tm = straight["total_main"]
            print(f"  O/U {tm['line']}: Over {tm['over']*100:.1f}%  [margen: {mg['total_main']['margin']:.2f}%]")
        if straight["spread_main"]:
            print(f"  AH main {straight['spread_main']['line']}  [margen: {mg['spread_main']['margin']:.2f}%]")
        if straight["tt_home"]:
            print(f"  TT {home} O/U {straight['tt_home']['line']}  [margen: {mg['tt_home']['margin']:.2f}%]")
        if straight["tt_away"]:
            print(f"  TT {away} O/U {straight['tt_away']['line']}  [margen: {mg['tt_away']['margin']:.2f}%]")
        n_alt_ou = len(mg["totals_alt"])
        n_alt_ah = len(mg["spreads_alt"])
        if n_alt_ou:
            avg_ou = sum(x["margin"] for x in mg["totals_alt"]) / n_alt_ou
            print(f"  O/U alt ({n_alt_ou} líneas): margen promedio {avg_ou:.2f}%")
        if n_alt_ah:
            avg_ah = sum(x["margin"] for x in mg["spreads_alt"]) / n_alt_ah
            print(f"  AH alt ({n_alt_ah} líneas): margen promedio {avg_ah:.2f}%")
        if cs_margin is not None:
            print(f"  Correct Score ({len(cs)} scores): margen {cs_margin:.2f}%")

    with open("wc2026_markets.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nGuardado en wc2026_markets.json ({len(results)} partidos)")
    return results


if __name__ == "__main__":
    process_all_matches()