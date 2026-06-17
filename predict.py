"""
predict.py
----------
Lee wc2026_markets.json, aplica S_BASE y S_RICH,
genera predicciones para los 72 partidos bajo dos sistemas de puntos:
  - predictions_6_3.json  (exacto=6, resultado=3)
  - predictions_3_1.json  (exacto=3, resultado=1)
"""
import json
import numpy as np
from strategy import strategy_base, strategy_rich, best_score_max_ev, get_result

INPUT_FILE = "wc2026_markets.json"

SCORING_SYSTEMS = [
    {"exacto": 6, "resultado": 3, "output": "predictions_6_3.json"},
    {"exacto": 3, "resultado": 1, "output": "predictions_3_1.json"},
]


def predict_match(match, puntos_exacto, puntos_resultado):
    result_base = strategy_base(match)
    result_rich = strategy_rich(match)

    if result_base is None or result_rich is None:
        return None

    mat_base, lh_base, la_base = result_base
    mat_rich, lh_rich, la_rich = result_rich

    ph_base, pd_base, pa_base = map(float, [
        np.sum(np.tril(mat_base, -1)),
        np.sum(np.diag(mat_base)),
        np.sum(np.triu(mat_base, 1))
    ])

    ph_rich, pd_rich, pa_rich = map(float, [
        np.sum(np.tril(mat_rich, -1)),
        np.sum(np.diag(mat_rich)),
        np.sum(np.triu(mat_rich, 1))
    ])

    pred_h_base, pred_a_base = best_score_max_ev(mat_base, puntos_exacto, puntos_resultado)
    pred_h_rich, pred_a_rich = best_score_max_ev(mat_rich, puntos_exacto, puntos_resultado)

    same_score = (pred_h_base == pred_h_rich and pred_a_base == pred_a_rich)
    same_1x2   = (get_result(pred_h_base, pred_a_base) ==
                  get_result(pred_h_rich, pred_a_rich))

    def top_scores(mat, n=5):
        flat = [(int(i), int(j), float(mat[i, j]))
                for i in range(mat.shape[0])
                for j in range(mat.shape[1])]
        flat.sort(key=lambda x: -x[2])
        return [{"score": f"{i}-{j}", "prob": round(p, 4)}
                for i, j, p in flat[:n]]

    return {
        "matchup_id": match["matchup_id"],
        "home":       match["home"],
        "away":       match["away"],
        "start_time": match["start_time"],
        "has_cs":     bool(match.get("correct_score")),

        "base": {
            "lambda_home": round(lh_base, 3),
            "lambda_away": round(la_base, 3),
            "p_home":      round(ph_base, 4),
            "p_draw":      round(pd_base, 4),
            "p_away":      round(pa_base, 4),
            "prediction":  f"{pred_h_base}-{pred_a_base}",
            "top5":        top_scores(mat_base),
        },
        "rich": {
            "lambda_home": round(lh_rich, 3),
            "lambda_away": round(la_rich, 3),
            "p_home":      round(ph_rich, 4),
            "p_draw":      round(pd_rich, 4),
            "p_away":      round(pa_rich, 4),
            "prediction":  f"{pred_h_rich}-{pred_a_rich}",
            "top5":        top_scores(mat_rich),
        },

        "comparison": {
            "same_score":        same_score,
            "same_1x2":          same_1x2,
            "lambda_home_delta": round(lh_rich - lh_base, 3),
            "lambda_away_delta": round(la_rich - la_base, 3),
        }
    }


def main():
    with open(INPUT_FILE) as f:
        matches = json.load(f)

    print(f"Procesando {len(matches)} partidos...")

    # Calcular lambdas y matrices una sola vez por partido
    cached = {}
    for match in matches:
        mid = match["matchup_id"]
        rb = strategy_base(match)
        rr = strategy_rich(match)
        if rb and rr:
            cached[mid] = (match, rb, rr)

    print(f"Partidos con datos completos: {len(cached)}")

    for system in SCORING_SYSTEMS:
        pe, pr, outfile = system["exacto"], system["resultado"], system["output"]
        print(f"\n--- Sistema {pe}/{pr} → {outfile} ---")

        predictions = []
        skipped = 0

        for match in matches:
            mid = match["matchup_id"]
            if mid not in cached:
                skipped += 1
                continue
            match_data, result_base, result_rich = cached[mid]
            try:
                mat_base, lh_base, la_base = result_base
                mat_rich, lh_rich, la_rich = result_rich

                ph_base, pd_base, pa_base = map(float, [
                    np.sum(np.tril(mat_base, -1)),
                    np.sum(np.diag(mat_base)),
                    np.sum(np.triu(mat_base, 1))
                ])
                ph_rich, pd_rich, pa_rich = map(float, [
                    np.sum(np.tril(mat_rich, -1)),
                    np.sum(np.diag(mat_rich)),
                    np.sum(np.triu(mat_rich, 1))
                ])

                pred_h_base, pred_a_base = best_score_max_ev(mat_base, pe, pr)
                pred_h_rich, pred_a_rich = best_score_max_ev(mat_rich, pe, pr)

                same_score = (pred_h_base == pred_h_rich and pred_a_base == pred_a_rich)
                same_1x2   = (get_result(pred_h_base, pred_a_base) ==
                              get_result(pred_h_rich, pred_a_rich))

                def top_scores(mat, n=20):
                    flat = [(int(i), int(j), float(mat[i, j]))
                            for i in range(mat.shape[0])
                            for j in range(mat.shape[1])]
                    flat.sort(key=lambda x: -x[2])
                    return [{"score": f"{i}-{j}", "prob": round(p, 4)}
                            for i, j, p in flat[:n]]

                predictions.append({
                    "matchup_id": mid,
                    "home":       match["home"],
                    "away":       match["away"],
                    "start_time": match["start_time"],
                    "has_cs":     bool(match.get("correct_score")),
                    "moneyline":  match["markets"].get("moneyline"),

                    "base": {
                        "lambda_home": round(lh_base, 3),
                        "lambda_away": round(la_base, 3),
                        "p_home":      round(ph_base, 4),
                        "p_draw":      round(pd_base, 4),
                        "p_away":      round(pa_base, 4),
                        "prediction":  f"{pred_h_base}-{pred_a_base}",
                        "top20":       top_scores(mat_base),
                    },
                    "rich": {
                        "lambda_home": round(lh_rich, 3),
                        "lambda_away": round(la_rich, 3),
                        "p_home":      round(ph_rich, 4),
                        "p_draw":      round(pd_rich, 4),
                        "p_away":      round(pa_rich, 4),
                        "prediction":  f"{pred_h_rich}-{pred_a_rich}",
                        "top20":       top_scores(mat_rich),
                    },

                    "comparison": {
                        "same_score":         same_score,
                        "same_1x2":           same_1x2,
                        "lambda_home_delta":  round(lh_rich - lh_base, 3),
                        "lambda_away_delta":  round(la_rich - la_base, 3),
                        "lh_base":            round(lh_base, 3),
                        "la_base":            round(la_base, 3),
                        "lh_rich":            round(lh_rich, 3),
                        "la_rich":            round(la_rich, 3),
                    }
                })
            except Exception as e:
                skipped += 1
                print(f"  ERROR {match['home']} vs {match['away']}: {e}")

        predictions.sort(key=lambda x: x["start_time"])

        with open(outfile, "w") as f:
            json.dump(predictions, f, indent=2)

        print(f"Guardado: {outfile} ({len(predictions)} partidos, {skipped} skipped)")


if __name__ == "__main__":
    main()