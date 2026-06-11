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
DAILY_FLAG      = "last_daily_report.txt"
TZ_AR           = timezone(timedelta(hours=-3))

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
        lh_delta = n["base"]["lambda_home"] - o["base"]["lambda_home"]
        la_delta = n["base"]["lambda_away"] - o["base"]["lambda_away"]
        base_changed = n["base"]["prediction"] != o["base"]["prediction"]
        rich_changed = n["rich"]["prediction"] != o["rich"]["prediction"]
        if base_changed or rich_changed or abs(lh_delta) > 0.05 or abs(la_delta) > 0.05:
            changes.append({
                "home":         n["home"],
                "away":         n["away"],
                "start_time":   n["start_time"],
                "base_old":     o["base"]["prediction"],
                "base_new":     n["base"]["prediction"],
                "rich_old":     o["rich"]["prediction"],
                "rich_new":     n["rich"]["prediction"],
                "lh_old":       o["base"]["lambda_home"],
                "la_old":       o["base"]["lambda_away"],
                "lh_new":       n["base"]["lambda_home"],
                "la_new":       n["base"]["lambda_away"],
                "lh_delta":     round(lh_delta, 3),
                "la_delta":     round(la_delta, 3),
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
        lh_sym = "↑" if c["lh_delta"] > 0 else ("↓" if c["lh_delta"] < 0 else "=")
        la_sym = "↑" if c["la_delta"] > 0 else ("↓" if c["la_delta"] < 0 else "=")
        lambdas = f"λH: {c['lh_old']:.3f}→{c['lh_new']:.3f} {lh_sym} | λA: {c['la_old']:.3f}→{c['la_new']:.3f} {la_sym}"
        odds = f"1X2: {fmt_1x2(c.get('moneyline'))}"
        lines.append(f"**{c['home']} vs {c['away']}** ({date})\n  {base_str} | {rich_str}\n  {lambdas}\n  {odds}\n")
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
        lines.append(f"{match:<28} {dt_ar.strftime('%d/%m %H:%M'):<11} {p['base']['prediction']:^6} {p['rich']['prediction']:^6}  {fmt_1x2(p.get('moneyline'))}")
    return "```\n" + "\n".join(lines) + "\n```"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def should_send_daily() -> bool:
    today = datetime.now(TZ_AR).date().isoformat()
    if not Path(DAILY_FLAG).exists():
        return True
    return Path(DAILY_FLAG).read_text().strip() != today

def mark_daily_sent():
    Path(DAILY_FLAG).write_text(datetime.now(TZ_AR).date().isoformat())

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

    # 4. Reporte diario
    if should_send_daily():
        send_discord(format_full(current, timestamp))
        mark_daily_sent()
        print("Reporte diario enviado.")

    # 5. Rotar
    shutil.copy(CURRENT_FILE, LAST_FILE)
    print("predictions_last.json actualizado.")


if __name__ == "__main__":
    main()