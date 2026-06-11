"""
compare.py
----------
Lee predictions.json y muestra:
1. Tabla de predicciones lado a lado (BASE vs RICH)
2. Comparación de lambdas
3. Resumen: cuántos partidos difieren en score / en 1X2
4. (Opcional) Si pasás resultados reales, calcula puntos bajo 6/3/0
"""
import json
import sys

PUNTOS_EXACTO    = 3
PUNTOS_RESULTADO = 1


def get_result(score_str):
    h, a = map(int, score_str.split("-"))
    if h > a: return "home"
    if h == a: return "draw"
    return "away"


def score_points(pred, real):
    if pred == real:
        return PUNTOS_EXACTO
    if get_result(pred) == get_result(real):
        return PUNTOS_RESULTADO
    return 0


def print_predictions(predictions):
    print(f"\n{'='*95}")
    print(f"{'Partido':<35} {'Fecha':<12} {'BASE pred':^12} {'RICH pred':^12} {'Mismo?':^8} {'ΔλH':>6} {'ΔλA':>6}")
    print(f"{'='*95}")

    diff_score = 0
    diff_1x2   = 0

    for p in predictions:
        name     = f"{p['home']} vs {p['away']}"[:34]
        date     = p["start_time"][:10]
        base_p   = p["base"]["prediction"]
        rich_p   = p["rich"]["prediction"]
        same     = "✓" if p["comparison"]["same_score"] else "≠"
        dlh      = p["comparison"]["lambda_home_delta"]
        dla      = p["comparison"]["lambda_away_delta"]
        cs_flag  = " [CS]" if p["has_cs"] else ""

        print(f"{name+cs_flag:<35} {date:<12} {base_p:^12} {rich_p:^12} {same:^8} {dlh:>+6.3f} {dla:>+6.3f}")

        if not p["comparison"]["same_score"]:
            diff_score += 1
        if not p["comparison"]["same_1x2"]:
            diff_1x2 += 1

    print(f"{'='*95}")
    print(f"\nResumen:")
    print(f"  Total partidos:              {len(predictions)}")
    print(f"  Predicción de score difiere: {diff_score} ({diff_score/len(predictions)*100:.1f}%)")
    print(f"  Predicción 1X2 difiere:      {diff_1x2} ({diff_1x2/len(predictions)*100:.1f}%)")
    print(f"  [CS] = tiene Correct Score de Pinnacle disponible")


def print_top5(predictions):
    print(f"\n{'─'*60}")
    print("TOP 5 SCORES POR PARTIDO")
    print(f"{'─'*60}")
    for p in predictions:
        print(f"\n{p['home']} vs {p['away']} ({p['start_time'][:10]})")
        print(f"  {'Score':<8} {'BASE':>8} {'RICH':>8}")
        base_dict = {s["score"]: s["prob"] for s in p["base"]["top5"]}
        rich_dict = {s["score"]: s["prob"] for s in p["rich"]["top5"]}
        all_scores = sorted(set(list(base_dict) + list(rich_dict)),
                            key=lambda s: -max(base_dict.get(s,0), rich_dict.get(s,0)))
        for score in all_scores[:6]:
            b = base_dict.get(score, 0)
            r = rich_dict.get(score, 0)
            flag = " ←" if abs(b-r) > 0.01 else ""
            print(f"  {score:<8} {b*100:>7.2f}% {r*100:>7.2f}%{flag}")


def score_results(predictions, results_file):
    """
    results_file: JSON con lista de {"matchup_id": X, "result": "H-A"}
    Calcula puntos bajo 6/3/0 para BASE y RICH.
    """
    with open(results_file) as f:
        results = {r["matchup_id"]: r["result"] for r in json.load(f)}

    pts_base = pts_rich = n = 0
    print(f"\n{'─'*70}")
    print(f"{'Partido':<35} {'Real':^8} {'BASE':^10} {'RICH':^10}")
    print(f"{'─'*70}")

    for p in predictions:
        mid = p["matchup_id"]
        if mid not in results:
            continue
        real = results[mid]
        pb   = score_points(p["base"]["prediction"], real)
        pr   = score_points(p["rich"]["prediction"], real)
        pts_base += pb
        pts_rich += pr
        n += 1
        name = f"{p['home']} vs {p['away']}"[:34]
        print(f"{name:<35} {real:^8} {pb:^10} {pr:^10}")

    if n > 0:
        print(f"{'─'*70}")
        print(f"{'TOTAL':.<35} {'':^8} {pts_base:^10} {pts_rich:^10}")
        print(f"{'PTS/PARTIDO':.<35} {'':^8} {pts_base/n:^10.3f} {pts_rich/n:^10.3f}")


def main():
    with open("predictions_sin_DC.json") as f:
        predictions = json.load(f)

    print_predictions(predictions)

    # Top 5 scores — descomentar si querés verlo
    # print_top5(predictions)

    # Scoring contra resultados reales:
    # python compare.py results.json
    if len(sys.argv) > 1:
        score_results(predictions, sys.argv[1])
    else:
        print("\nTip: cuando se jueguen los partidos, creá results.json y corré:")
        print("     python compare.py results.json")
        print("\nFormato de results.json:")
        print('     [{"matchup_id": 1620858185, "result": "2-1"}, ...]')


if __name__ == "__main__":
    main()