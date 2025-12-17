import requests

webhook_url = "https://discord.com/api/webhooks/1450986467949023233/M6AFfpa-zJH50ZXIDEoFaIb170bYORXfHUgLHDBboeYnmNKfFeVRJGGMrmutFoTvadqp"

payload = {
    "content": "✅ SB-ALGO Terminal online. Webhook working."
}

r = requests.post(webhook_url, json=payload, timeout=10)
print("status:", r.status_code)
