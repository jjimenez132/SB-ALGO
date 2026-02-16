#!/usr/bin/env python3
"""
================================================================================
WHALE HUNTER v2.0 - Polymarket NBA Whale Detection Discord Bot
================================================================================
Monitors Polymarket in real-time for large, high-conviction trades (≥$10K) 
specifically in NBA prediction markets. Sends instant Discord alerts in a 
professional "shark tank" trading style.

Features:
- 🐋 Standard Whale alerts ($10K+)
- 🦈 ULTRA WHALE alerts ($50K+) with @everyone ping
- 📊 Volume spike detection (>10% of 24h volume)
- ⏰ Fresh trade filter (last 30 min only)
- 📁 File + console logging

Author: SB-ALGO Team
Version: 2.0.0
================================================================================
"""

import os
import re
import json
import time
import logging
from logging.handlers import RotatingFileHandler
import requests
import threading
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

# ==============================================================================
# CONFIGURATION — EDIT THESE VALUES
# ==============================================================================

# Discord Bot Configuration
DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"  # Get from Discord Developer Portal
DISCORD_CHANNEL_ID = 123456789012345678            # Right-click channel -> Copy ID (int)

# Whale Detection Thresholds (TIERED)
WHALE_THRESHOLD_USD = 10000        # Standard whale ($10K+)
ULTRA_WHALE_THRESHOLD_USD = 50000  # ULTRA whale ($50K+) → @everyone ping
MIN_MARKET_VOLUME_24H = 25000      # Lowered to catch more live game markets

# Volume Spike Detection
VOLUME_SPIKE_THRESHOLD = 0.10      # Alert if single trade > 10% of 24h volume

# Fresh Trade Filter
FRESH_TRADE_MINUTES = 30           # Only alert trades from last 30 minutes

# Polling Configuration
POLL_INTERVAL_SECONDS = 12         # How often to check for new trades (10-15s optimal)
MAX_MARKETS_PER_CYCLE = 75         # Increased for more coverage during games

# Persistence
SEEN_TRADES_FILE = "seen_trades.json"  # File to store processed trade IDs
LOG_FILE = "whale_hunter.log"          # Log file path

# API Configuration
POLYMARKET_API_BASE = "https://gamma-api.polymarket.com"
API_TIMEOUT = 15  # seconds

# ==============================================================================
# NBA KEYWORDS (COMPREHENSIVE)
# ==============================================================================

# Primary keywords that definitively indicate NBA
NBA_PRIMARY_KEYWORDS = [
    "nba", "basketball", "wnba"
]

# All 30 NBA Teams (various formats for matching)
NBA_TEAMS = [
    # Team names
    "lakers", "celtics", "warriors", "nets", "bulls", "heat", "knicks", 
    "bucks", "suns", "76ers", "sixers", "mavericks", "mavs", "clippers",
    "nuggets", "grizzlies", "pelicans", "timberwolves", "wolves", "thunder",
    "blazers", "trail blazers", "rockets", "spurs", "jazz", "raptors",
    "hornets", "hawks", "pistons", "pacers", "magic", "cavaliers", "cavs",
    "kings", "wizards",
    # City names (for "Los Angeles vs Denver" style)
    "los angeles", "boston", "golden state", "brooklyn", "chicago", "miami", 
    "new york", "milwaukee", "phoenix", "philadelphia", "dallas", "denver", 
    "memphis", "new orleans", "minnesota", "oklahoma city", "oklahoma",
    "portland", "houston", "san antonio", "utah", "toronto", "charlotte",
    "atlanta", "detroit", "indiana", "orlando", "cleveland", "sacramento",
    "washington"
]

# Popular NBA Players (expanded list)
NBA_PLAYERS = [
    # Superstars
    "lebron", "curry", "stephen curry", "jokic", "giannis", "antetokounmpo",
    "doncic", "luka", "tatum", "jayson", "morant", "ja morant", "embiid",
    "durant", "kevin durant", "booker", "devin booker",
    # All-Stars
    "mitchell", "edwards", "anthony edwards", "brunson", "jalen brunson", 
    "harden", "lillard", "damian", "kawhi", "leonard", "paul george", "pg13",
    "beal", "bradley beal", "kyrie", "irving",
    # Rising Stars
    "wembanyama", "wemby", "victor", "chet", "holmgren", "shai", "gilgeous",
    "fox", "sabonis", "towns", "kat", "randle", "zion", "williamson", 
    "lamelo", "ball", "maxey", "tyrese", "garland", "mobley", "scottie", "barnes",
    # Veterans
    "chris paul", "cp3", "jimmy butler", "butler", "bam", "adebayo"
]

# ==============================================================================
# LOGGING SETUP (CONSOLE + FILE)
# ==============================================================================

logger = logging.getLogger("WhaleHunter")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', '%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# File handler with rotation (max 5MB, keep 3 backups)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', '%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

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
    """Save seen trade IDs to JSON file for persistence across restarts."""
    try:
        # Keep only last 10,000 trade IDs to prevent file bloat
        recent_ids = list(trade_ids)[-10000:]
        with open(SEEN_TRADES_FILE, 'w') as f:
            json.dump({
                "trade_ids": recent_ids,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "count": len(recent_ids)
            }, f, indent=2)
    except IOError as e:
        logger.error(f"Could not save seen trades: {e}")


# Global set for deduplication
seen_trades: set = load_seen_trades()

# ==============================================================================
# API HELPERS WITH EXPONENTIAL BACKOFF
# ==============================================================================

def api_request(url: str, params: dict = None, max_retries: int = 5) -> dict | list | None:
    """
    Make an API request with exponential backoff on errors.
    
    Handles:
    - Network errors
    - Rate limits (429)
    - Server errors (5xx)
    
    Returns None on failure after retries.
    """
    backoff = 5  # Start with 5 second delay
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=API_TIMEOUT)
            
            # Rate limited - back off
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", backoff))
                logger.warning(f"Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                backoff = min(backoff * 2, 60)
                continue
            
            # Server error - retry with backoff
            if response.status_code >= 500:
                logger.warning(f"Server error {response.status_code}. Retry in {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            
            # Success
            if response.status_code == 200:
                return response.json()
            
            # Client error - log and give up
            logger.error(f"API error {response.status_code}: {response.text[:200]}")
            return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout. Retry {attempt + 1}/{max_retries}...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}. Retry {attempt + 1}/{max_retries}...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
    
    logger.error(f"All {max_retries} retries failed for {url}")
    return None


# ==============================================================================
# MARKET DISCOVERY — NBA FILTERING (ENHANCED)
# ==============================================================================

def is_nba_market(market: dict) -> bool:
    """
    Determine if a market is NBA-related using comprehensive keyword matching.
    
    Uses strict word-boundary matching to avoid false positives like:
    - "Seahawks" matching "hawks" 
    - "LA Kings" (NHL) matching "kings"
    """
    slug = market.get("slug", "").lower()
    question = market.get("question", "").lower()
    tags = market.get("tags", []) or []
    
    # Combine all text for checking
    all_text = f"{slug} {question} {' '.join(str(t).lower() for t in tags)}"
    
    # EXCLUDE non-NBA sports explicitly (check first)
    non_nba_keywords = ["nfl", "nhl", "mlb", "mls", "super bowl", "stanley cup", 
                        "world series", "seahawks", "patriots", "chiefs", "eagles",
                        "cowboys", "49ers", "raiders", "hockey", "baseball", "football",
                        "soccer", "tennis", "golf", "ufc", "mma", "boxing"]
    for exclude in non_nba_keywords:
        if exclude in all_text:
            return False  # Definitely NOT NBA
    
    # 1. Check primary NBA keywords (word boundary)
    for keyword in NBA_PRIMARY_KEYWORDS:
        if re.search(rf'\b{re.escape(keyword)}\b', all_text):
            return True
    
    # 2. Check tags (exact or partial match)
    for tag in tags:
        if isinstance(tag, str):
            tag_lower = tag.lower()
            if tag_lower == "nba" or tag_lower == "basketball":
                return True
    
    # 3. Check team names (ALWAYS use word boundaries to avoid false positives)
    for team in NBA_TEAMS:
        if re.search(rf'\b{re.escape(team)}\b', all_text):
            return True
    
    # 4. Check player names (word boundaries)
    for player in NBA_PLAYERS:
        if re.search(rf'\b{re.escape(player)}\b', all_text):
            return True
    
    return False


def get_nba_markets() -> list:
    """
    Fetch all active NBA-related markets from Polymarket.
    
    Returns list of market dicts that:
    - Are active and not closed
    - Match NBA criteria
    - Have sufficient volume (≥ MIN_MARKET_VOLUME_24H)
    """
    logger.debug("Fetching active markets from Polymarket...")
    
    url = f"{POLYMARKET_API_BASE}/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": 200
    }
    
    markets = api_request(url, params)
    
    if not markets:
        logger.warning("No markets returned from API")
        return []
    
    nba_markets = []
    
    for market in markets:
        # Must be NBA-related
        if not is_nba_market(market):
            continue
        
        # Check volume threshold
        volume_24h = float(market.get("volume24hr", 0) or market.get("volume24h", 0) or 0)
        if volume_24h < MIN_MARKET_VOLUME_24H:
            continue
        
        # Add volume to market data for later use
        market["_volume_24h"] = volume_24h
        nba_markets.append(market)
    
    if nba_markets:
        logger.info(f"Found {len(nba_markets)} qualifying NBA markets (volume ≥ ${MIN_MARKET_VOLUME_24H:,})")
    
    return nba_markets[:MAX_MARKETS_PER_CYCLE]


# ==============================================================================
# ACTIVITY POLLING — WHALE DETECTION (ENHANCED)
# ==============================================================================

def get_market_activity(token_id: str) -> list:
    """Fetch recent trading activity for a specific token."""
    url = f"{POLYMARKET_API_BASE}/activity"
    params = {
        "token_id": token_id,
        "limit": 50
    }
    
    activity = api_request(url, params)
    
    if not activity:
        return []
    
    return activity if isinstance(activity, list) else []


def is_fresh_trade(timestamp_str: str) -> bool:
    """Check if trade is within FRESH_TRADE_MINUTES."""
    try:
        if not timestamp_str:
            return True  # If no timestamp, include it
        
        # Parse ISO format timestamp
        if "T" in str(timestamp_str):
            trade_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            # Try parsing as unix timestamp
            trade_time = datetime.fromtimestamp(float(timestamp_str), tz=timezone.utc)
        
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=FRESH_TRADE_MINUTES)
        return trade_time >= cutoff
    except Exception:
        return True  # If can't parse, include it


def detect_whales(market: dict) -> list:
    """
    Detect whale trades in a market.
    
    Returns list of whale trade dicts ready for alerting.
    Enhanced with:
    - Ultra whale detection
    - Volume spike detection
    - Fresh trade filtering
    """
    global seen_trades
    
    # Get token ID (usually first token is YES)
    tokens = market.get("tokens", [])
    if not tokens:
        return []
    
    # Try to get YES token, fallback to first token
    token_id = None
    for token in tokens:
        if token.get("outcome", "").upper() == "YES":
            token_id = token.get("token_id")
            break
    
    if not token_id and tokens:
        token_id = tokens[0].get("token_id")
    
    if not token_id:
        return []
    
    # Fetch activity
    activity = get_market_activity(token_id)
    
    # Get 24h volume for spike detection
    volume_24h = market.get("_volume_24h", float(market.get("volume24hr", 0) or 0))
    
    whale_trades = []
    
    for trade in activity:
        # Only process trades (not orders, etc.)
        if trade.get("action") != "TRADE":
            continue
        
        try:
            # Check if trade is fresh
            timestamp = trade.get("timestamp", "")
            if not is_fresh_trade(timestamp):
                continue
            
            # Calculate USD value
            size = float(trade.get("amount", 0) or 0)
            price = float(trade.get("price", 0) or 0)
            usd_value = size * price
            
            # Skip non-whales
            if usd_value < WHALE_THRESHOLD_USD:
                continue
            
            # Generate unique trade ID for deduplication
            trade_id = f"{market.get('id', 'unknown')}-{timestamp}-{trade.get('side', '')}-{size}"
            
            # Skip if already seen
            if trade_id in seen_trades:
                continue
            
            # New whale! Add to seen
            seen_trades.add(trade_id)
            
            # Determine whale tier
            is_ultra = usd_value >= ULTRA_WHALE_THRESHOLD_USD
            
            # Check for volume spike
            is_volume_spike = False
            if volume_24h > 0:
                volume_pct = usd_value / volume_24h
                is_volume_spike = volume_pct >= VOLUME_SPIKE_THRESHOLD
            
            # Build whale data
            whale_trades.append({
                "trade_id": trade_id,
                "market_id": market.get("id"),
                "market_question": market.get("question", "Unknown Market"),
                "market_slug": market.get("slug", ""),
                "timestamp": timestamp,
                "side": trade.get("side", "UNKNOWN").upper(),
                "outcome": trade.get("outcome", "YES").upper(),
                "size": size,
                "price": price,
                "usd_value": usd_value,
                "implied_prob": round(price * 100, 1),
                "volume_24h": volume_24h,
                "volume_pct": round((usd_value / volume_24h * 100) if volume_24h > 0 else 0, 1),
                "is_ultra": is_ultra,
                "is_volume_spike": is_volume_spike
            })
            
            tier = "🦈 ULTRA WHALE" if is_ultra else "🐋 WHALE"
            spike_tag = " [VOLUME SPIKE]" if is_volume_spike else ""
            logger.info(f"{tier}: ${usd_value:,.0f} on {market.get('question', '')[:50]}...{spike_tag}")
            
        except (ValueError, TypeError) as e:
            logger.debug(f"Error parsing trade: {e}")
            continue
    
    # Save updated seen trades
    if whale_trades:
        save_seen_trades(seen_trades)
    
    return whale_trades


# ==============================================================================
# ALERT FORMATTING — MILLIONAIRE CRYPTO TRADER STYLE
# ==============================================================================

def format_whale_alert(whale: dict) -> str:
    """
    Format a whale trade into a Discord-ready alert message.
    
    Style: Urgent, data-rich, professional crypto trader aesthetic.
    Tiered alerts: Ultra Whale ($50K+) gets @everyone ping.
    """
    # Determine LONG/SHORT based on side
    side = whale["side"]
    outcome = whale["outcome"]
    
    if side in ("BUY", "LONG"):
        position = "LONG"
        side_emoji = "📈"
    else:
        position = "SHORT"
        side_emoji = "📉"
    
    # Format timestamp
    try:
        ts = whale["timestamp"]
        if "T" in str(ts):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            time_str = ts
    except Exception:
        time_str = whale["timestamp"]
    
    # Build market link
    slug = whale.get("market_slug", "")
    market_link = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"
    
    # Truncate question if too long
    question = whale["market_question"]
    if len(question) > 80:
        question = question[:77] + "..."
    
    # ULTRA WHALE vs Standard Whale formatting
    is_ultra = whale.get("is_ultra", False)
    is_spike = whale.get("is_volume_spike", False)
    
    # Header based on whale tier
    if is_ultra:
        header = "🦈🦈🦈 **ULTRA WHALE SIGNAL — MASSIVE CONVICTION FLOW** 🦈🦈🦈"
        ping = "@everyone "  # Add ping for ultra whales
        conviction_note = "Institutional-sized position. This is a MAJOR signal."
    else:
        header = "🚨 **WHALE SIGNAL — HIGH-CONVICTION FLOW**"
        ping = ""
        conviction_note = "Sharp money stepping in. Model check recommended."
    
    # Volume spike indicator
    spike_indicator = ""
    if is_spike:
        spike_indicator = f"\n🔥 **VOLUME SPIKE:** This single trade = {whale.get('volume_pct', 0):.1f}% of 24h volume!"
    
    # Build the alert message
    alert = f"""{ping}{header}

⏰ **Time (UTC):** `{time_str}`
🏀 **Market:** {question}

{side_emoji} **Whale Move:** 💰 **${whale['usd_value']:,.0f}** on **{outcome}** ({position})
📊 **Entry:** `{whale['price']:.3f}` → **{whale['implied_prob']}%** implied{spike_indicator}

🔗 **Link:** {market_link}

> 💎 *{conviction_note} Tail, fade, or arb? Edge hunt activated.* 🔥"""
    
    return alert


# ==============================================================================
# DISCORD BOT
# ==============================================================================

# Bot setup with minimal intents
intents = discord.Intents.default()
intents.message_content = False  # We don't need to read messages

bot = commands.Bot(command_prefix="!", intents=intents)

# Alert queue for thread-safe communication
alert_queue = []
alert_lock = threading.Lock()


@bot.event
async def on_ready():
    """Called when bot successfully connects to Discord."""
    logger.info(f"✅ Discord bot connected as {bot.user.name} ({bot.user.id})")
    logger.info(f"📢 Alerts will be sent to channel ID: {DISCORD_CHANNEL_ID}")
    
    # Start the alert sender task
    if not send_alerts.is_running():
        send_alerts.start()


@tasks.loop(seconds=5)
async def send_alerts():
    """Send queued alerts to Discord channel."""
    global alert_queue
    
    with alert_lock:
        if not alert_queue:
            return
        alerts_to_send = alert_queue[:]
        alert_queue = []
    
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    
    if not channel:
        logger.error(f"Could not find channel {DISCORD_CHANNEL_ID}. Check the ID!")
        return
    
    for alert in alerts_to_send:
        try:
            await channel.send(alert)
            logger.info("📨 Alert sent to Discord successfully")
        except discord.HTTPException as e:
            logger.error(f"Failed to send Discord message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending alert: {e}")


def queue_alert(message: str):
    """Thread-safe function to queue an alert for sending."""
    with alert_lock:
        alert_queue.append(message)


# ==============================================================================
# MAIN POLLING LOOP
# ==============================================================================

def polling_loop():
    """
    Main polling loop that runs in a background thread.
    
    Continuously:
    1. Fetches NBA markets
    2. Checks each for whale trades
    3. Queues alerts for any detected whales
    4. Sleeps for POLL_INTERVAL_SECONDS
    """
    logger.info("🎯 Starting whale detection polling loop...")
    logger.info(f"   Standard Whale: ${WHALE_THRESHOLD_USD:,}+")
    logger.info(f"   ULTRA Whale: ${ULTRA_WHALE_THRESHOLD_USD:,}+ (with @everyone)")
    logger.info(f"   Volume Spike: >{VOLUME_SPIKE_THRESHOLD*100:.0f}% of 24h volume")
    logger.info(f"   Fresh trades only: last {FRESH_TRADE_MINUTES} min")
    logger.info(f"   Poll interval: {POLL_INTERVAL_SECONDS}s")
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        try:
            # Get NBA markets
            markets = get_nba_markets()
            
            if not markets:
                if cycle_count % 10 == 0:  # Only log every 10 cycles when no markets
                    logger.debug("No qualifying NBA markets found this cycle")
            else:
                # Check each market for whales
                total_whales = 0
                ultra_whales = 0
                
                for market in markets:
                    whales = detect_whales(market)
                    
                    for whale in whales:
                        alert = format_whale_alert(whale)
                        queue_alert(alert)
                        total_whales += 1
                        if whale.get("is_ultra"):
                            ultra_whales += 1
                
                if total_whales > 0:
                    ultra_msg = f" ({ultra_whales} ULTRA)" if ultra_whales else ""
                    logger.info(f"🐋 Detected {total_whales} new whale trade(s){ultra_msg} this cycle")
            
        except Exception as e:
            logger.error(f"Error in polling loop: {e}", exc_info=True)
        
        # Wait before next poll
        time.sleep(POLL_INTERVAL_SECONDS)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main():
    """
    Main entry point.
    
    1. Validates configuration
    2. Starts polling loop in background thread
    3. Runs Discord bot (blocking)
    """
    logger.info("=" * 60)
    logger.info("🐋 WHALE HUNTER v2.0 - Polymarket NBA Monitor")
    logger.info("=" * 60)
    
    # Validate configuration
    if DISCORD_BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
        logger.error("❌ Please set your DISCORD_BOT_TOKEN in the configuration section!")
        logger.error("   Get one at: https://discord.com/developers/applications")
        return
    
    if DISCORD_CHANNEL_ID == 123456789012345678:
        logger.warning("⚠️  Using placeholder DISCORD_CHANNEL_ID. Update this to your actual channel ID!")
    
    logger.info(f"📁 Seen trades: {SEEN_TRADES_FILE}")
    logger.info(f"📁 Log file: {LOG_FILE}")
    logger.info(f"📊 Loaded {len(seen_trades)} previously seen trades")
    
    # Start polling loop in background thread
    polling_thread = threading.Thread(target=polling_loop, daemon=True)
    polling_thread.start()
    logger.info("🔄 Background polling thread started")
    
    # Run Discord bot (blocking)
    logger.info("🤖 Starting Discord bot...")
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord token! Please check your DISCORD_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")


if __name__ == "__main__":
    main()
