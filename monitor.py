"""
monitor.py
----------
1. Rescrapea Pinnacle → wc2026_markets.json         (pinnacle_full.process_all_matches)
2. Regenera predicciones → predictions_6_3.json      (predict.main)
3. Compara con predictions_last.json
4. Manda diff por Discord si algo cambió (predicción o lambda > 0.05)
5. Una vez al día manda tabla completa de partidos próximos
6. Guarda predictions_6_3.json como predictions_last.json
"""

import json
import os
import shutil
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pinnacle_full import process_all_matches
import predict  # llama predict.main() para generar los JSONs

# ─── Config ───────────────────────────────────────────────────────────────────

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
CURRENT_FILE    = "predictions_6_3.json"
LAST_FILE       = "predictions_last.json"
LOCKED_FILE     = "predictions_locked.json"
DAILY_FLAG      = "last_daily_report.txt"
TZ_AR           = timezone(timedelta(hours=-3))
LOCK_HOURS      = 2 # congelar predicción N horas antes del pitazo

# ─── Discord ──────────────────────────────────────────────────────────────────

def send_discord(content: str):
    chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
    for chunk in chunks:
        r = requests.post(DISCORD_WEBHOOK, json={"content": chunk})
        r.raise_for_status()

def fmt_1x2(ml):
    if not ml:
        return "—"
    return f"{ml['home']*100:.1f}% / {ml['draw']*100:.1f}% / {ml['away']*100:.1f}%"

# ─── Comparación ──────────────────────────────────────────────────────────────

def compare(old: list, new: list) -> list:
    old_d = {d["matchup_id"]: d for d in old}
    changes = []
    for n in new:
        o = old_d.get(n["matchup_id"])
        if not o:
            continue
        lh_delta_b = n["base"]["lambda_home"] - o["base"]["lambda_home"]
        la_delta_b = n["base"]["lambda_away"] - o["base"]["lambda_away"]
        lh_delta_r = n["rich"]["lambda_home"] - o["rich"]["lambda_home"]
        la_delta_r = n["rich"]["lambda_away"] - o["rich"]["lambda_away"]
        base_changed = n["base"]["prediction"] != o["base"]["prediction"]
        rich_changed = n["rich"]["prediction"] != o["rich"]["prediction"]
        if base_changed or rich_changed or abs(lh_delta_b) > 0.05 or abs(la_delta_b) > 0.05 or abs(lh_delta_r) > 0.05 or abs(la_delta_r) > 0.05:
            changes.append({
                "home":         n["home"],
                "away":         n["away"],
                "start_time":   n["start_time"],
                "base_old":     o["base"]["prediction"],
                "base_new":     n["base"]["prediction"],
                "rich_old":     o["rich"]["prediction"],
                "rich_new":     n["rich"]["prediction"],
                "lhb_old":      o["base"]["lambda_home"],
                "lab_old":      o["base"]["lambda_away"],
                "lhb_new":      n["base"]["lambda_home"],
                "lab_new":      n["base"]["lambda_away"],
                "lhb_delta":    round(lh_delta_b, 3),
                "lab_delta":    round(la_delta_b, 3),
                "lhr_old":      o["rich"]["lambda_home"],
                "lar_old":      o["rich"]["lambda_away"],
                "lhr_new":      n["rich"]["lambda_home"],
                "lar_new":      n["rich"]["lambda_away"],
                "lhr_delta":    round(lh_delta_r, 3),
                "lar_delta":    round(la_delta_r, 3),
                "base_changed": base_changed,
                "rich_changed": rich_changed,
                "moneyline":    n.get("moneyline"),
            })
    return changes

# ─── Mensajes ─────────────────────────────────────────────────────────────────

def format_diff(changes: list, timestamp: str) -> str:
    if not changes:
        return f"✅ **[{timestamp}]** Sin cambios significativos."
    lines = [f"🔄 **Cambios detectados** — {timestamp}\n"]
    for c in changes:
        date = c["start_time"][:10]
        base_str = f"BASE: `{c['base_old']}` → `{c['base_new']}`" if c["base_changed"] else f"BASE: `{c['base_new']}` *(sin cambio)*"
        rich_str = f"RICH: `{c['rich_old']}` → `{c['rich_new']}`" if c["rich_changed"] else f"RICH: `{c['rich_new']}` *(sin cambio)*"
        lhb_sym = "↑" if c["lhb_delta"] > 0 else ("↓" if c["lhb_delta"] < 0 else "=")
        lab_sym = "↑" if c["lab_delta"] > 0 else ("↓" if c["lab_delta"] < 0 else "=")
        lhr_sym = "↑" if c["lhr_delta"] > 0 else ("↓" if c["lhr_delta"] < 0 else "=")
        lar_sym = "↑" if c["lar_delta"] > 0 else ("↓" if c["lar_delta"] < 0 else "=")
        lambdas_b = f"BASE λH: {c['lhb_old']:.3f}→{c['lhb_new']:.3f}{lhb_sym} | λA: {c['lab_old']:.3f}→{c['lab_new']:.3f}{lab_sym}"
        lambdas_r = f"RICH λH: {c['lhr_old']:.3f}→{c['lhr_new']:.3f}{lhr_sym} | λA: {c['lar_old']:.3f}→{c['lar_new']:.3f}{lar_sym}"
        odds = f"1X2 Pinnacle: {fmt_1x2(c.get('moneyline'))}"
        lines.append(f"**{c['home']} vs {c['away']}** ({date})\n  {base_str} | {rich_str}\n  {lambdas_b}\n  {lambdas_r}\n  {odds}\n")
    return "\n".join(lines)


def format_full(predictions: list, timestamp: str) -> str:
    now_ar = datetime.now(TZ_AR)
    upcoming = [
        p for p in predictions
        if datetime.fromisoformat(p["start_time"].replace("Z", "+00:00")).astimezone(TZ_AR).date() >= now_ar.date()
    ][:20]

    lines = [f"📋 **Reporte diario** — {timestamp}\n"]
    header = f"{'Partido':<28} {'Fecha':<11} {'BASE':^6} {'RICH':^6}  1X2"
    lines.append(header)
    lines.append("─" * 75)
    for p in upcoming:
        dt_ar = datetime.fromisoformat(p["start_time"].replace("Z", "+00:00")).astimezone(TZ_AR)
        match = f"{p['home'][:12]} vs {p['away'][:12]}"
        ml = p.get("moneyline")
        odds_str = fmt_1x2(ml) if ml else "—"
        lines.append(f"{match:<28} {dt_ar.strftime('%d/%m %H:%M'):<11} {p['base']['prediction']:^6} {p['rich']['prediction']:^6}  {odds_str}")
    return "```\n" + "\n".join(lines) + "\n```"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def should_send_daily() -> bool:
    today = datetime.now(TZ_AR).date().isoformat()
    if not Path(DAILY_FLAG).exists():
        return True
    return Path(DAILY_FLAG).read_text().strip() != today

def mark_daily_sent():
    Path(DAILY_FLAG).write_text(datetime.now(TZ_AR).date().isoformat())

# ─── Lock predicciones ────────────────────────────────────────────────────────

def lock_predictions(current: list) -> list:
    """
    Congela la predicción de partidos que están a menos de LOCK_HOURS del pitazo.
    Solo se guarda una vez — si ya está en locked no se sobreescribe.
    Retorna la lista de partidos recién bloqueados.
    """
    now = datetime.now(timezone.utc)

    # Cargar locked existente
    if Path(LOCKED_FILE).exists():
        with open(LOCKED_FILE) as f:
            locked = json.load(f)
    else:
        locked = []

    locked_ids = {p["matchup_id"] for p in locked}
    newly_locked = []

    for p in current:
        if p["matchup_id"] in locked_ids:
            continue
        start = datetime.fromisoformat(p["start_time"].replace("Z", "+00:00"))
        time_to_kick = (start - now).total_seconds() / 3600
        if 0 <= time_to_kick <= LOCK_HOURS:
            locked.append({
                "matchup_id":  p["matchup_id"],
                "home":        p["home"],
                "away":        p["away"],
                "start_time":  p["start_time"],
                "locked_at":   now.isoformat(),
                "moneyline":   p.get("moneyline"),
                "base":        p["base"],
                "rich":        p["rich"],
            })
            locked_ids.add(p["matchup_id"])
            newly_locked.append(p)

    if newly_locked:
        with open(LOCKED_FILE, "w") as f:
            json.dump(locked, f, indent=2)

    return newly_locked


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    timestamp = datetime.now(TZ_AR).strftime("%d/%m/%Y %H:%M ART")
    print(f"\n[{timestamp}] Iniciando monitor...")

    # 1. Rescrapear Pinnacle
    print("Scrapeando Pinnacle...")
    try:
        process_all_matches()
    except Exception as e:
        send_discord(f"❌ **Error scrapeando Pinnacle** — {timestamp}\n{e}")
        raise

    # 2. Regenerar predicciones usando predict.main()
    print("Generando predicciones...")
    predict.main()

    # 3. Comparar con last
    with open(CURRENT_FILE) as f:
        current = json.load(f)

    if Path(LAST_FILE).exists():
        with open(LAST_FILE) as f:
            last = json.load(f)
        changes = compare(last, current)
        send_discord(format_diff(changes, timestamp))
        print(f"Diff enviado: {len(changes)} cambios.")
    else:
        send_discord(f"🚀 **Primera corrida** — {timestamp}\nPredicciones generadas, sin comparación previa.")

    # 4. Congelar predicciones a 1 hora del pitazo
    newly_locked = lock_predictions(current)
    if newly_locked:
        lines = [f"🔒 **Predicciones congeladas** — {timestamp}\n"]
        for p in newly_locked:
            lines.append(f"**{p['home']} vs {p['away']}** ({p['start_time'][:10]})")
            lines.append(f"  BASE: `{p['base']['prediction']}` | RICH: `{p['rich']['prediction']}`")
            lines.append(f"  1X2: {fmt_1x2(p.get('moneyline'))}\n")
        send_discord("\n".join(lines))
        print(f"Congelados: {len(newly_locked)} partidos.")

    # 5. Reporte diario
    if should_send_daily():
        send_discord(format_full(current, timestamp))
        mark_daily_sent()
        print("Reporte diario enviado.")

    # 6. Rotar
    shutil.copy(CURRENT_FILE, LAST_FILE)
    print("predictions_last.json actualizado.")


if __name__ == "__main__":
    main()