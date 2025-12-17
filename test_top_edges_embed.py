import requests

WEBHOOK = "https://discord.com/api/webhooks/1450986467949023233/M6AFfpa-zJH50ZXIDEoFaIb170bYORXfHUgLHDBboeYnmNKfFeVRJGGMrmutFoTvadqp"

embed = {
    "title": "TOP EDGE — NBA",
    "description": "**LAL -4.5**",
    "color": 0x00FF00,
    "fields": [
        {"name": "Expected Value", "value": "+12.4%", "inline": True},
        {"name": "Win Probability", "value": "58.1%", "inline": True},
        {"name": "Market Line", "value": "-4.5 @ -110", "inline": True},
        {"name": "AI Stake", "value": "1.7% bankroll", "inline": True},
        {"name": "Risk Class", "value": "Medium", "inline": True},
        {"name": "Notes", "value": "No injury flags. Line stable.", "inline": False},
    ],
    "footer": {
        "text": "SB-ALGO Terminal • Automated"
    }
}

payload = {
    "username": "SB-ALGO | Top Edges",
    "embeds": [embed]
}

r = requests.post(WEBHOOK, json=payload, timeout=10)
print("status:", r.status_code)
