import os
from datetime import datetime
import pytz
import requests
import pandas as pd
from sqlalchemy import create_engine, text

# ===== Config =====
WEBHOOK = os.getenv("DISCORD_TOP_EDGES_WEBHOOK") or "PASTE_WEBHOOK_HERE"
DB_URL = os.getenv("DATABASE_URL")  # should already exist in your Render/Local env

def eastern_today():
    eastern = pytz.timezone("US/Eastern")
    return datetime.now(eastern).date()

def main():
    if not DB_URL:
        raise SystemExit("Missing DATABASE_URL env var")

    engine = create_engine(DB_URL)

    today = eastern_today()

    # TODO: adjust table/column names to YOUR schema
    # This query assumes you have a table that stores computed edges per game/date.
    q = text("""
        SELECT *
        FROM top_edges
        WHERE game_date = :d
        ORDER BY ev DESC
        LIMIT 5
    """)

    df = pd.read_sql(q, engine, params={"d": str(today)})

    if df.empty:
        requests.post(WEBHOOK, json={"content": f"⚠️ No edges found for {today} (ET)."}, timeout=10)
        print("No edges found.")
        return

    # Build one embed per pick (clean terminal feed)
    embeds = []
    for _, r in df.iterrows():
        embeds.append({
            "title": "TOP EDGE — NBA (Today)",
            "description": f"**{r.get('pick', 'Unknown Pick')}**",
            "color": 0x00FF00,
            "fields": [
                {"name": "EV", "value": f"{r.get('ev', '—')}", "inline": True},
                {"name": "Win Prob", "value": f"{r.get('win_prob', '—')}", "inline": True},
                {"name": "Line", "value": f"{r.get('market_line', '—')}", "inline": True},
            ],
            "footer": {"text": f"SB-ALGO Terminal • {today} ET"}
        })

    payload = {"username": "SB-ALGO | Top Edges", "embeds": embeds[:10]}
    resp = requests.post(WEBHOOK, json=payload, timeout=10)
    print("status:", resp.status_code)

if __name__ == "__main__":
    main()
