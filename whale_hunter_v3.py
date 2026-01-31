#!/usr/bin/env python3
"""
================================================================================
WHALE HUNTER v3.0 - Polymarket Basketball Whale Alerts
================================================================================
Monitors Polymarket for basketball/NBA trades >$1,000 and sends Discord
webhook alerts with affiliate monetization.

FIXES FROM v2.0:
- Universal keyword search (not relying on "nba" in slug)
- Discord Webhook instead of Bot (simpler, no token needed)
- Lower threshold ($1K for more signals)
- Affiliate link monetization

Author: SB-ALGO Team
Version: 3.0.0
================================================================================
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone, timedelta

# ==============================================================================
# CONFIGURATION — EDIT THESE VALUES OR SET ENVIRONMENT VARIABLES
# ==============================================================================

# Discord Webhook URL
# Set as DISCORD_WEBHOOK_URL environment variable on Render, or edit here:
DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1466964097672286290/nxe5059sXEJVoBTXCvjXM_4q-mBsCSZHgiC2Ek_8M6HnMXvMIAjFWTa2psxWl7Yjkdfe"
)

# Polymarket Affiliate Referral Code
# Set as REFERRAL_CODE environment variable on Render, or edit here:
REFERRAL_CODE = os.getenv("REFERRAL_CODE", "YOUR_REFERRAL_CODE")

# Whale Detection Threshold
WHALE_THRESHOLD_USD = int(os.getenv("WHALE_THRESHOLD_USD", "1000"))

# Polling Configuration
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))

# Persistence (to avoid duplicate alerts)
SEEN_TRADES_FILE = "seen_trades_v3.json"

# API Configuration
POLYMARKET_API_BASE = "https://gamma-api.polymarket.com"
API_TIMEOUT = 15

# ==============================================================================
# BASKETBALL KEYWORDS (UNIVERSAL SEARCH)
# ==============================================================================

# Keywords to identify basketball markets (case-insensitive)
BASKETBALL_KEYWORDS = [
    # League & Sport
    "nba", "basketball", "wnba",
    # Teams (major markets)
    "lakers", "celtics", "warriors", "knicks", "thunder", "bucks",
    "heat", "nets", "bulls", "76ers", "sixers", "suns", "nuggets",
    "clippers", "mavericks", "mavs", "grizzlies", "pelicans", "raptors",
    "hawks", "pacers", "magic", "cavaliers", "cavs", "kings", "wizards",
    "rockets", "spurs", "jazz", "blazers", "pistons", "hornets", "wolves",
    # Star Players
    "lebron", "curry", "jokic", "giannis", "doncic", "luka", "tatum",
    "embiid", "durant", "wembanyama", "wemby", "morant", "booker"
]

# Keywords to EXCLUDE (avoid false positives from other sports)
EXCLUDE_KEYWORDS = [
    "nfl", "nhl", "mlb", "mls", "super bowl", "stanley cup", "world series",
    "football", "soccer", "hockey", "baseball", "tennis", "golf", "ufc", "mma"
]

# ==============================================================================
# LOGGING
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WhaleHunterV3")

# ==============================================================================
# SEEN TRADES PERSISTENCE
# ==============================================================================

def load_seen_trades() -> set:
    """Load previously seen trade IDs from JSON file."""
    if os.path.exists(SEEN_TRADES_FILE):
        try:
            with open(SEEN_TRADES_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get("trade_ids", []))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load seen trades: {e}")
    return set()


def save_seen_trades(trade_ids: set) -> None:
    """Save seen trade IDs to JSON file."""
    try:
        # Keep only last 5000 to prevent bloat
        recent = list(trade_ids)[-5000:]
        with open(SEEN_TRADES_FILE, 'w') as f:
            json.dump({
                "trade_ids": recent,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    except IOError as e:
        logger.error(f"Could not save seen trades: {e}")


# Global set
seen_trades: set = load_seen_trades()

# ==============================================================================
# MARKET DISCOVERY — UNIVERSAL SEARCH
# ==============================================================================

def is_basketball_market(market: dict) -> bool:
    """
    Check if a market is basketball-related using keyword matching.
    
    This is the FIX for v2.0's "0 markets" bug - we don't rely on slug structure,
    we just search ALL text fields for basketball keywords.
    """
    # Gather all searchable text
    slug = market.get("slug", "").lower()
    question = market.get("question", "").lower()
    description = market.get("description", "").lower()
    tags = market.get("tags", []) or []
    tags_text = " ".join(str(t).lower() for t in tags)
    
    all_text = f"{slug} {question} {description} {tags_text}"
    
    # First, EXCLUDE non-basketball sports
    for exclude in EXCLUDE_KEYWORDS:
        if exclude in all_text:
            return False
    
    # Then, check for basketball keywords
    for keyword in BASKETBALL_KEYWORDS:
        if keyword in all_text:
            return True
    
    return False


def get_basketball_markets() -> list:
    """
    Fetch ALL active markets and filter for basketball in Python.
    
    This is the UNIVERSAL SEARCH approach that fixes the v2.0 bug.
    We fetch 500 markets because NBA markets may be further down the list.
    """
    logger.info("Fetching active markets from Polymarket...")
    
    try:
        response = requests.get(
            f"{POLYMARKET_API_BASE}/markets",
            params={"active": "true", "closed": "false", "limit": 500},  # Increased to 500
            timeout=API_TIMEOUT
        )
        
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            return []
        
        all_markets = response.json()
        
        # Filter for basketball
        basketball_markets = [m for m in all_markets if is_basketball_market(m)]
        
        # DEBUG OUTPUT - Critical for troubleshooting
        print(f"✅ DEBUG: Found {len(basketball_markets)} Basketball Markets (out of {len(all_markets)} total)")
        
        if basketball_markets:
            logger.info(f"🏀 Active basketball markets: {len(basketball_markets)}")
        
        return basketball_markets
        
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []


# ==============================================================================
# ACTIVITY POLLING — WHALE DETECTION
# ==============================================================================

def get_market_activity(token_id: str) -> list:
    """Fetch recent trading activity for a token."""
    try:
        response = requests.get(
            f"{POLYMARKET_API_BASE}/activity",
            params={"token_id": token_id, "limit": 50},
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []
        return []
        
    except requests.RequestException:
        return []


def detect_whales(market: dict) -> list:
    """
    Detect whale trades (>$1K) in a market.
    
    Returns list of whale trade dicts ready for Discord.
    """
    global seen_trades
    
    # Get token(s)
    tokens = market.get("tokens", [])
    if not tokens:
        return []
    
    whale_trades = []
    
    # Check both YES and NO tokens
    for token in tokens:
        token_id = token.get("token_id")
        outcome = token.get("outcome", "YES").upper()
        
        if not token_id:
            continue
        
        activity = get_market_activity(token_id)
        
        for trade in activity:
            # Only process BUY trades (not LP/redemptions)
            action = trade.get("action", "").upper()
            side = trade.get("side", "").upper()
            
            if action != "TRADE":
                continue
            
            if side not in ("BUY", "LONG"):
                continue  # Exclude sells, LP, redemptions
            
            try:
                size = float(trade.get("amount", 0) or 0)
                price = float(trade.get("price", 0) or 0)
                usd_value = size * price
                
                if usd_value < WHALE_THRESHOLD_USD:
                    continue
                
                # Unique trade ID
                timestamp = trade.get("timestamp", "")
                trade_id = f"{market.get('id')}-{timestamp}-{outcome}-{size}"
                
                if trade_id in seen_trades:
                    continue
                
                seen_trades.add(trade_id)
                
                whale_trades.append({
                    "market_question": market.get("question", "Unknown Market"),
                    "market_slug": market.get("slug", ""),
                    "outcome": outcome,
                    "usd_value": usd_value,
                    "price": price,
                    "implied_prob": round(price * 100, 1),
                    "timestamp": timestamp
                })
                
                logger.info(f"🐋 WHALE: ${usd_value:,.0f} on {outcome} - {market.get('question', '')[:40]}...")
                
            except (ValueError, TypeError):
                continue
    
    if whale_trades:
        save_seen_trades(seen_trades)
    
    return whale_trades


# ==============================================================================
# DISCORD WEBHOOK — EMBED ALERTS
# ==============================================================================

def send_discord_alert(whale: dict) -> bool:
    """
    Send a beautiful Discord embed alert via webhook.
    
    Features:
    - Green for YES, Red for NO
    - Affiliate link button
    - Professional formatting
    """
    # Color based on outcome
    color = 0x00FF00 if whale["outcome"] == "YES" else 0xFF0000  # Green or Red
    
    # Build affiliate link
    slug = whale.get("market_slug", "")
    affiliate_link = f"https://polymarket.com/event/{slug}?r={REFERRAL_CODE}" if slug else "https://polymarket.com"
    
    # Truncate question
    question = whale["market_question"]
    if len(question) > 100:
        question = question[:97] + "..."
    
    # Timestamp
    try:
        ts = whale.get("timestamp", "")
        if "T" in str(ts):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M:%S UTC")
        else:
            time_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    except Exception:
        time_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    
    # Build Discord Embed
    embed = {
        "title": "🐋 WHALE ALERT — BASKETBALL MARKET",
        "description": f"**{question}**",
        "color": color,
        "fields": [
            {
                "name": "💰 Trade Size",
                "value": f"**${whale['usd_value']:,.0f}**",
                "inline": True
            },
            {
                "name": f"{'📈' if whale['outcome'] == 'YES' else '📉'} Position",
                "value": f"**{whale['outcome']}** (BUY)",
                "inline": True
            },
            {
                "name": "📊 Entry / Implied",
                "value": f"`{whale['price']:.3f}` → **{whale['implied_prob']}%**",
                "inline": True
            }
        ],
        "footer": {
            "text": f"⏰ {time_str} | Sharp money detected 🦈"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Webhook payload with button
    payload = {
        "embeds": [embed],
        "components": [
            {
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 2,  # Button
                        "style": 5,  # Link
                        "label": "🔗 Trade on Polymarket (+Bonus)",
                        "url": affiliate_link
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        
        if response.status_code in (200, 204):
            logger.info("📨 Webhook sent successfully!")
            return True
        else:
            logger.error(f"Webhook failed: {response.status_code} - {response.text[:100]}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Webhook error: {e}")
        return False


# ==============================================================================
# MAIN LOOP
# ==============================================================================

def main():
    """Main entry point."""
    print("=" * 60)
    print("🐋 WHALE HUNTER v3.0 - Polymarket Basketball Monitor")
    print("=" * 60)
    
    # Validate config
    if "YOUR_WEBHOOK" in DISCORD_WEBHOOK_URL:
        print("❌ Please set your DISCORD_WEBHOOK_URL!")
        print("   Get one from: Discord Server Settings → Integrations → Webhooks")
        return
    
    if REFERRAL_CODE == "YOUR_REFERRAL_CODE":
        print("⚠️  No referral code set. Affiliate links will not earn commission.")
    
    print(f"💰 Threshold: ${WHALE_THRESHOLD_USD:,}+")
    print(f"🔁 Poll interval: {POLL_INTERVAL_SECONDS}s")
    print(f"📁 Seen trades: {len(seen_trades)} loaded")
    print()
    
    cycle = 0
    while True:
        cycle += 1
        
        try:
            # Get basketball markets
            markets = get_basketball_markets()
            
            if not markets:
                if cycle == 1:
                    print("⚠️  No basketball markets found. Will keep checking...")
            else:
                # Check each for whales
                total_whales = 0
                for market in markets:
                    whales = detect_whales(market)
                    for whale in whales:
                        send_discord_alert(whale)
                        total_whales += 1
                
                if total_whales > 0:
                    logger.info(f"🐋 Sent {total_whales} whale alert(s) this cycle")
            
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
