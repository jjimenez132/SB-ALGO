#!/usr/bin/env python3
"""
================================================================================
WHALE HUNTER v4.0 - Authenticated Polymarket Trade Tracker
================================================================================
Monitors Polymarket NBA markets for trades >$1,000 using authenticated CLOB API.

Version: 4.0.0
================================================================================
"""

import time
import logging
import os
from datetime import datetime, timezone

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, TradeParams
from py_clob_client.constants import POLYGON
import requests

# ==============================================================================
# 🔐 YOUR SETTINGS (EDIT THESE)
# ==============================================================================

# Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1466964097672286290/nxe5059sXEJVoBTXCvjXM_4q-mBsCSZHgiC2Ek_8M6HnMXvMIAjFWTa2psxWl7Yjkdfe"

# Referral Code
REFERRAL_CODE = "YOUR_REFERRAL_CODE"

# Private Key (needed for signing - from MetaMask)
PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "9ed8768335eaac8d7d328b52e66dc0d0079ec1d0ceae21d48e8fcb558e60a8f0")

# CLOB API Keys (from generate_key.py)
CLOB_API_KEY = "dad7669c-858d-0d25-e9f0-a894211b7099"
CLOB_SECRET  = "T6DJa1or7sGbqVdM2R-b6isiy-ILMRSSHIlvfw1rYfE="
CLOB_PASS    = "85a8408195abb5b26bfeb940d7358bf095313c73fe66fb61414a2a84d86d2db9"

# ==============================================================================
# ⚙️ BOT CONFIGURATION
# ==============================================================================

WHALE_THRESHOLD = 1000   # Minimum trade size ($1,000)
POLL_INTERVAL = 10       # Check every 10 seconds

BASKETBALL_KEYWORDS = ["nba", "basketball", "lakers", "celtics", "warriors", "thunder", "bucks", "heat"]
EXCLUDE_KEYWORDS = ["nfl", "nhl", "mlb", "super bowl", "football", "hockey"]

# ==============================================================================
# LOGGING
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("WhaleHunterV4")

SEEN_TRADE_IDS = set()

# ==============================================================================
# INITIALIZE AUTHENTICATED CLIENT
# ==============================================================================

creds = ApiCreds(
    api_key=CLOB_API_KEY,
    api_secret=CLOB_SECRET,
    api_passphrase=CLOB_PASS
)

client = ClobClient(
    "https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=POLYGON,
    creds=creds
)

# ==============================================================================
# API FUNCTIONS
# ==============================================================================

def get_nba_markets():
    """Find active NBA markets from Gamma API."""
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={"limit": 100, "active": "true", "closed": "false"},
            timeout=15
        )
        events = r.json()
        
        markets = []
        for event in events:
            title = event.get('title', '').lower()
            if any(kw in title for kw in BASKETBALL_KEYWORDS) and not any(ex in title for ex in EXCLUDE_KEYWORDS):
                for m in event.get('markets', []):
                    clob_ids = m.get('clobTokenIds', [])
                    if clob_ids:
                        markets.append({
                            "token_id": clob_ids[0],
                            "question": m.get('question', 'Unknown'),
                            "slug": event.get('slug', '')
                        })
        return markets
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return []


def get_trades_for_token(token_id):
    """Get trades using authenticated CLOB client."""
    try:
        params = TradeParams(asset_id=token_id)
        trades = client.get_trades(params)
        return trades if isinstance(trades, list) else []
    except Exception as e:
        logger.debug(f"Error fetching trades: {e}")
        return []


def scan_for_whales(markets):
    """Scan markets for whale trades."""
    global SEEN_TRADE_IDS
    whale_count = 0
    
    for market in markets:
        trades = get_trades_for_token(market["token_id"])
        
        for trade in trades:
            trade_id = trade.get("id") or trade.get("match_id") or trade.get("transaction_hash")
            if not trade_id or trade_id in SEEN_TRADE_IDS:
                continue
            
            SEEN_TRADE_IDS.add(trade_id)
            
            try:
                price = float(trade.get("price", 0))
                size = float(trade.get("size", 0))
                usd_value = size * price
            except:
                continue
            
            if usd_value >= WHALE_THRESHOLD:
                side = trade.get("side", "BUY").upper()
                send_alert(market, usd_value, price, side)
                whale_count += 1
    
    return whale_count


def send_alert(market, amount, price, side):
    """Send Discord webhook alert."""
    color = 0x00FF00 if side == "BUY" else 0xFF0000
    link = f"https://polymarket.com/event/{market['slug']}?r={REFERRAL_CODE}"
    
    question = market['question'][:100] + "..." if len(market['question']) > 100 else market['question']
    
    embed = {
        "title": "🐋 WHALE TRADE DETECTED",
        "description": f"**{question}**",
        "color": color,
        "fields": [
            {"name": "💰 Size", "value": f"**${amount:,.0f}**", "inline": True},
            {"name": "⚡ Side", "value": f"**{side}**", "inline": True},
            {"name": "📊 Price", "value": f"**{price*100:.1f}%**", "inline": True}
        ],
        "footer": {"text": "Whale Hunter v4.0 | Authenticated"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    payload = {
        "embeds": [embed],
        "components": [{
            "type": 1,
            "components": [{
                "type": 2,
                "style": 5,
                "label": "🔗 Trade on Polymarket",
                "url": link
            }]
        }]
    }
    
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code in (200, 204):
            logger.info(f"🚀 ALERT: ${amount:,.0f} on {market['question'][:40]}...")
    except Exception as e:
        logger.error(f"Webhook error: {e}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("=" * 60)
    print("🐋 WHALE HUNTER v4.0 - Authenticated CLOB API")
    print("=" * 60)
    print(f"💰 Threshold: ${WHALE_THRESHOLD:,}+")
    print(f"🔁 Poll: {POLL_INTERVAL}s")
    print(f"🔐 API: {CLOB_API_KEY[:8]}...")
    print()
    
    cycle = 0
    while True:
        cycle += 1
        try:
            markets = get_nba_markets()
            if cycle == 1:
                print(f"✅ Found {len(markets)} NBA markets")
            
            if markets:
                whale_count = scan_for_whales(markets)
                if whale_count > 0:
                    logger.info(f"🐋 {whale_count} whale(s) detected")
                    
        except KeyboardInterrupt:
            print("\n👋 Bye!")
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
        
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
