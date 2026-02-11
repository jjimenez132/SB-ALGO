#!/usr/bin/env python3
"""
================================================================================
WHALE HUNTER v4.2 - Daily Games Only (Data API)
================================================================================
Monitors Polymarket NBA DAILY GAMES for trades >$1,000.
Filters out futures (Finals, MVP, Championship, etc.)
Uses the public Data API for trade history.

Version: 4.2.0
================================================================================
"""

import time
import logging
import json
from datetime import datetime, timezone
import requests

# ==============================================================================
# 🔐 YOUR SETTINGS
# ==============================================================================

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1466964097672286290/nxe5059sXEJVoBTXCvjXM_4q-mBsCSZHgiC2Ek_8M6HnMXvMIAjFWTa2psxWl7Yjkdfe"
REFERRAL_CODE = "YOUR_REFERRAL_CODE"

# ==============================================================================
# ⚙️ BOT CONFIG
# ==============================================================================

WHALE_THRESHOLD = 25000  # Only alert on $25k+ trades
POLL_INTERVAL = 10

# 🚫 BANNED WORDS - Filter out futures/season-long markets
BANNED_WORDS = ["final", "champion", "mvp", "rookie", "conference", "winner 202", "playoff", "all-star", "will win the 202"]

# ✅ DAILY GAME INDICATORS - Look for these patterns
DAILY_INDICATORS = ["vs", "vs.", "@", "beat", "over", "under", "spread", "points"]

# ==============================================================================
# LOGGING
# ==============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("WhaleHunterV4")

SEEN_TRADE_IDS = set()

# ==============================================================================
# API FUNCTIONS
# ==============================================================================

def get_nba_markets():
    """
    Find ONLY daily NBA games.
    Uses series_id=10345 to get NBA directly.
    Filters out futures (Finals, MVP, Championship).
    Only includes games ending TODAY or later.
    """
    from datetime import datetime, timezone
    
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={
                "series_id": "10345",  # NBA series ID
                "limit": 100,
                "active": "true",
                "closed": "false"
            },
            timeout=15
        )
        events = r.json()
        
        # Get today's date in UTC for filtering
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        markets = []
        for event in events:
            title = event.get('title', '').lower()
            
            # 🚫 Skip old/resolved games (endDate before today)
            end_date = event.get('endDate', '')[:10]  # Get YYYY-MM-DD
            if end_date < today:
                continue
            
            # 🚫 Skip futures/season-long markets
            if any(ban in title for ban in BANNED_WORDS):
                continue
            
            # ✅ Detect daily game patterns (vs, spread, etc.)
            is_daily = any(indicator in title for indicator in DAILY_INDICATORS)
            
            for m in event.get('markets', []):
                question = m.get('question', '').lower()
                
                # Also check question for banned words
                if any(ban in question for ban in BANNED_WORDS):
                    continue
                
                # Parse clobTokenIds (it's a JSON string)
                clob_ids_raw = m.get('clobTokenIds', '[]')
                try:
                    clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                except:
                    clob_ids = []
                
                condition_id = m.get('conditionId', '')
                if clob_ids and condition_id:
                    markets.append({
                        "token_id": clob_ids[0],
                        "condition_id": condition_id,
                        "question": m.get('question', 'Unknown'),
                        "slug": event.get('slug', ''),
                        "is_daily": is_daily
                    })
        
        return markets
        
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return []


def get_trades_for_market(condition_id):
    """Get trades using the Data API (public, no auth required)."""
    try:
        # Data API returns public trade history
        r = requests.get(
            "https://data-api.polymarket.com/trades",
            params={
                "market": condition_id,
                "limit": 50  # Get last 50 trades
            },
            timeout=15
        )
        if r.status_code == 200:
            return r.json() if isinstance(r.json(), list) else []
        return []
    except Exception as e:
        logger.debug(f"Error fetching trades: {e}")
        return []


def scan_for_whales(markets):
    """Scan markets for whale trades."""
    global SEEN_TRADE_IDS
    whale_count = 0
    
    for market in markets:
        # Use the Data API with condition_id
        trades = get_trades_for_market(market["condition_id"])
        
        for trade in trades:
            # Data API uses timestamp + proxyWallet as unique ID
            trade_id = f"{trade.get('timestamp', '')}_{trade.get('proxyWallet', '')}"
            if not trade_id or trade_id in SEEN_TRADE_IDS:
                continue
            
            SEEN_TRADE_IDS.add(trade_id)
            
            try:
                price = float(trade.get("price", 0))
                size = float(trade.get("size", 0))
                usd_value = size * price
            except:
                continue
            
            # 🚫 Skip redemption trades (resolved markets cashing out)
            if price >= 0.98 or price <= 0.02:
                continue
            
            if usd_value >= WHALE_THRESHOLD:
                side = trade.get("side", "BUY").upper()
                send_alert(market, usd_value, price, side)
                whale_count += 1
    
    return whale_count


def send_alert(market, amount, price, side):
    """
    Send premium Discord whale alert with tiered embeds.
    
    Tiers:
    - 🟡 $25k-$49k: Whale Flow (gold)
    - 🔴 $50k+: Heavy Whale (red)
    """
    import random
    
    # Determine tier
    is_heavy = amount >= 50000
    
    if is_heavy:
        color = 0xFF4444  # Bright red
        title = "🔴 HEAVY WHALE ALERT 🚨"
        footer_text = "Heavy Whale | Sharp money detected"
        # Random context for heavy
        contexts = [
            "🔥 Price pressure building",
            "⚡ Aggressive capital hit this market",
            "🧠 Smart money alert",
            "📊 Follow-up flow likely"
        ]
    else:
        color = 0xFFD700  # Gold
        title = "🟡 WHALE FLOW DETECTED 👀"
        footer_text = "Whale Flow | Notable capital entering"
        contexts = [
            "💰 Watch for price movement",
            "📈 Sharp action incoming",
            "🎯 Money moving the line"
        ]
    
    context = random.choice(contexts)
    question = market['question']
    
    # Determine if it's a spread, O/U, or moneyline
    if "spread" in question.lower():
        market_type = "Spread"
    elif "o/u" in question.lower() or "over" in question.lower():
        market_type = "O/U"
    else:
        market_type = "Moneyline"
    
    embed = {
        "title": title,
        "description": f"**{question}**",
        "color": color,
        "fields": [
            {"name": "💰 Whale Size", "value": f"**${amount:,.0f}**", "inline": True},
            {"name": "⚡ Side", "value": f"**{side}**", "inline": True},
            {"name": "📊 Entry", "value": f"**{price*100:.1f}%**", "inline": True},
            {"name": "📋 Type", "value": f"{market_type}", "inline": True},
            {"name": "🔗 Trade Now", "value": f"[Web](https://polymarket.com?via=jjaisportspicks) • [App](https://apps.apple.com?via=jjaisportspicksapp)", "inline": False},
        ],
        "footer": {"text": f"{footer_text} • {context}"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    payload = {"embeds": [embed]}
    
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
    print("🐋 WHALE HUNTER v4.2 - Daily Games Mode (Data API)")
    print("=" * 60)
    print(f"💰 Threshold: ${WHALE_THRESHOLD:,}+")
    print(f"🚫 Filtering out: Finals, MVP, Championship, etc.")
    print()
    
    cycle = 0
    while True:
        cycle += 1
        try:
            markets = get_nba_markets()
            
            if cycle == 1:
                daily = sum(1 for m in markets if m.get('is_daily'))
                print(f"✅ Found {len(markets)} NBA markets ({daily} daily games)")
                if markets:
                    print(f"   Example: {markets[0]['question'][:50]}...")
            
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
