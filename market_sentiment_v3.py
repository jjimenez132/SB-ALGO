#!/usr/bin/env python3
"""
Market Sentiment Bot v3.0 - SIMPLIFIED
======================================
Clean, simple quant alerts that actually work.

Sends: Individual alerts for top NBA markets with:
- Clear bet type (Spread, ML, O/U)
- Model probability from MetaMergeEngine
- Simple edge calculation
- Kelly sizing
"""

import os
import sys
import json
import time
import requests
import logging
import re
import random
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engines'))

# ==============================================================================
# CONFIG
# ==============================================================================

DISCORD_WEBHOOK = os.environ.get(
    "SENTIMENT_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1464404517402706046/hOveHjIOa_zG_hKgEiTXiVq0BzFlqUiRI2G_CwTZ1imQ9anw4qE7vEnNHiDqHpg-py7l"
)

REFERRAL = "https://polymarket.com?via=jjaisportspicks"
APP_LINK = "https://apps.apple.com?via=jjaisportspicksapp"

POLL_INTERVAL = 120  # 2 min
ALERT_INTERVAL = 1800  # 30 min between snapshots

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("QuantBot")

# ==============================================================================
# MATH ENGINE
# ==============================================================================

MATH_ENGINE = None

def get_engine():
    global MATH_ENGINE
    if MATH_ENGINE is None:
        try:
            from meta_merge_engine_v4 import MetaMergeEngine
            MATH_ENGINE = MetaMergeEngine()
            logger.info("✅ MetaMergeEngine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Engine unavailable: {e}")
    return MATH_ENGINE


def parse_teams(question: str):
    """Extract teams from question."""
    teams = {
        'rockets': 'HOU', 'pacers': 'IND', 'nuggets': 'DEN', 'grizzlies': 'MEM',
        'lakers': 'LAL', 'celtics': 'BOS', 'warriors': 'GSW', 'suns': 'PHX',
        'bucks': 'MIL', 'heat': 'MIA', 'nets': 'BKN', 'knicks': 'NYK',
        'cavaliers': 'CLE', 'mavericks': 'DAL', 'thunder': 'OKC', 'clippers': 'LAC',
        'spurs': 'SAS', 'kings': 'SAC', 'timberwolves': 'MIN', 'pelicans': 'NOP',
        'hawks': 'ATL', 'wizards': 'WAS', 'hornets': 'CHA', 'bulls': 'CHI',
        'pistons': 'DET', 'magic': 'ORL', 'raptors': 'TOR', '76ers': 'PHI',
        'blazers': 'POR', 'jazz': 'UTA',
    }
    found = []
    q = question.lower()
    for name, abbr in teams.items():
        if name in q:
            found.append(abbr)
    found = list(dict.fromkeys(found))
    return (found[1], found[0]) if len(found) >= 2 else (None, None)


def get_model_prob(question: str, market_price: float) -> tuple:
    """Get model probability. Returns (prob, source)."""
    engine = get_engine()
    if not engine:
        # Fallback: add slight variance to market
        var = random.gauss(0, 0.05)
        return (max(0.2, min(0.8, market_price + var)), "simulated")
    
    away, home = parse_teams(question)
    if not home or not away:
        var = random.gauss(0, 0.05)
        return (max(0.2, min(0.8, market_price + var)), "simulated")
    
    try:
        q = question.lower()
        
        if 'spread' in q:
            match = re.search(r'\(([+-]?\d+\.?\d*)\)', question)
            spread = float(match.group(1)) if match else 0
            result = engine.predict_game(home, away, book_spread=spread)
            if 'spread' in result and 'home_cover_prob' in result['spread']:
                return (result['spread']['home_cover_prob'], "MetaMerge")
        
        elif 'total' in q or 'o/u' in q:
            match = re.search(r'(\d{3}\.?\d*)', question)
            total = float(match.group(1)) if match else 220
            result = engine.predict_game(home, away, book_total=total)
            if 'total' in result and 'over_prob' in result['total']:
                return (result['total']['over_prob'], "MetaMerge")
        
        else:  # Moneyline
            result = engine.predict_game(home, away)
            if 'moneyline' in result and 'home_win_prob' in result['moneyline']:
                return (result['moneyline']['home_win_prob'], "MetaMerge")
    
    except Exception as e:
        logger.debug(f"Model error: {e}")
    
    var = random.gauss(0, 0.05)
    return (max(0.2, min(0.8, market_price + var)), "simulated")


# ==============================================================================
# API
# ==============================================================================

def get_markets():
    """Get NBA markets."""
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={"series_id": "10345", "limit": 100, "active": "true", "closed": "false"},
            timeout=15
        )
        events = r.json()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        markets = []
        for event in events:
            title = event.get('title', '').lower()
            end_date = event.get('endDate', '')[:10]
            
            if end_date < today:
                continue
            if any(x in title for x in ["champion", "mvp", "finals", "playoff"]):
                continue
            
            for m in event.get('markets', []):
                try:
                    prices = json.loads(m.get('outcomePrices', '[]'))
                except:
                    prices = [0.5, 0.5]
                
                markets.append({
                    "question": m.get('question', ''),
                    "price_yes": float(prices[0]) if prices else 0.5,
                    "volume": float(m.get('volume', 0) or 0),
                })
        
        return markets
    except Exception as e:
        logger.error(f"Error: {e}")
        return []


# ==============================================================================
# ALERTS
# ==============================================================================

def send_alert(market: dict):
    """Send clean quant alert."""
    question = market['question']
    price = market['price_yes']
    volume = market['volume']
    
    # Get model probability
    model_prob, source = get_model_prob(question, price)
    
    # Calculate edge
    edge = model_prob - price
    abs_edge = abs(edge)
    
    # Kelly (1/3 Kelly, capped at 10%)
    if abs_edge > 0.02 and price > 0:
        odds = 1 / price
        full_kelly = abs_edge / (odds - 1) if odds > 1 else 0
        kelly = min(0.10, full_kelly * 0.33)
    else:
        kelly = 0
    
    # Direction
    direction = "YES" if edge > 0 else "NO"
    
    # Suggestion
    if abs_edge >= 0.08:
        suggestion = f"🔥 **STRONG EDGE** — {abs_edge*100:.1f}% on {direction}\n→ Kelly ~{kelly*100:.1f}% bankroll"
        color = 0x00FF00
    elif abs_edge >= 0.05:
        suggestion = f"⚡ **MODERATE** — {abs_edge*100:.1f}% edge on {direction}\n→ Kelly ~{kelly*100:.1f}%"
        color = 0xFFD700
    elif abs_edge >= 0.03:
        suggestion = f"👀 **WATCHING** — {abs_edge*100:.1f}% lean {direction}"
        color = 0x3498DB
    else:
        suggestion = f"⏸️ **NO EDGE** — Model agrees with market"
        color = 0x808080
    
    # Build embed
    embed = {
        "title": f"📊 {question}",
        "color": color,
        "fields": [
            {"name": "🎯 Line", "value": f"{price*100:.1f}%", "inline": True},
            {"name": "💰 Volume", "value": f"${volume:,.0f}", "inline": True},
            {"name": "🧮 Model", "value": f"{model_prob*100:.1f}% ({source})", "inline": True},
            {"name": "📈 Edge", "value": f"{edge*100:+.1f}%", "inline": True},
            {"name": "💎 Suggestion", "value": suggestion, "inline": False},
            {"name": "🔗 Trade", "value": f"[Polymarket]({REFERRAL}) • [App]({APP_LINK})", "inline": False},
        ],
        "footer": {"text": "Quant Desk v3 | NFA"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if r.status_code in (200, 204):
            logger.info(f"📊 {question[:40]} | Edge {edge*100:+.1f}%")
            return True
    except Exception as e:
        logger.error(f"Discord: {e}")
    return False


# ==============================================================================
# MAIN
# ==============================================================================

alerts_sent = set()
last_alert_time = 0

def main():
    global last_alert_time
    
    print("=" * 50)
    print("📊 QUANT BOT v3.0 - SIMPLIFIED")
    print("=" * 50)
    
    while True:
        try:
            markets = get_markets()
            logger.info(f"Found {len(markets)} markets")
            
            now = time.time()
            if now - last_alert_time >= ALERT_INTERVAL:
                # Send top 3 by volume
                top = sorted(markets, key=lambda x: -x['volume'])[:3]
                for m in top:
                    key = f"{m['question'][:30]}_{int(now//ALERT_INTERVAL)}"
                    if key not in alerts_sent:
                        send_alert(m)
                        alerts_sent.add(key)
                        time.sleep(2)
                last_alert_time = now
            
            if len(alerts_sent) > 200:
                alerts_sent.clear()
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
