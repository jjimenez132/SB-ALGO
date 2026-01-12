#!/usr/bin/env python3
"""
Fetch NBA News from Tank01 API
Runs hourly
"""

import requests
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz
import os

API_KEY = "ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653"

DISCORD_NEWS_WEBHOOK = "https://discord.com/api/webhooks/1459395253936328746/V4E1hQkIPqucYfzrgJIlTCWLskRJ-6Q5q8j547mbIJ5yQ_Mw_6JcguDJM3F1e1KPL-J3"

def send_news_to_discord(news_items):
    """Send only NEW news headlines to Discord (not already sent)"""
    import time
    from sqlalchemy import create_engine, text
    
    if not news_items:
        return
    
    engine = create_engine(DATABASE_URL)
    
    # Get news that hasn't been sent to Discord yet
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, title, link, source FROM nba_news 
            WHERE discord_sent = FALSE OR discord_sent IS NULL
            ORDER BY fetched_at DESC
            LIMIT 10
        """)).fetchall()
        
        unsent = [{'id': r[0], 'title': r[1], 'link': r[2], 'source': r[3]} for r in result]
    
    if not unsent:
        print("\n📤 No new news to send to Discord")
        return
    
    print(f"\n📤 Sending {len(unsent)} NEW news to Discord...")
    sent = 0
    
    for item in unsent:
        title = item.get("title", "")
        link = item.get("link", "")
        source = item.get("source", "NBA News")
        news_id = item.get("id")
        
        embed = {
            "title": f"📰 {title[:200]}",
            "url": link,
            "color": 0x667eea,
            "footer": {"text": f"Source: {source} | SB-ALGO News"}
        }
        
        try:
            r = requests.post(DISCORD_NEWS_WEBHOOK, json={"embeds": [embed]}, timeout=10)
            if r.status_code in [200, 204]:
                # Mark as sent in database
                with engine.connect() as conn:
                    conn.execute(text("UPDATE nba_news SET discord_sent = TRUE WHERE id = :id"), {"id": news_id})
                    conn.commit()
                sent += 1
            elif r.status_code == 429:
                time.sleep(2)
            time.sleep(0.5)
        except Exception as e:
            print(f"   ⚠️ Discord error: {e}")
    
    print(f"   ✅ Sent {sent} news items to Discord")
DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

HEADERS = {
    "x-rapidapi-host": "tank01-fantasy-stats.p.rapidapi.com",
    "x-rapidapi-key": API_KEY
}

def main():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    print(f"{'='*60}")
    print(f"📰 NBA NEWS FETCHER")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"{'='*60}")
    
    # Fetch news
    print("\n📥 Fetching news...")
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBANews"
    response = requests.get(url, headers=HEADERS, params={"recentNews": "true", "maxItems": "10"})
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        return
    
    data = response.json().get('body', [])
    
    if not data:
        print("⚠️ No news data")
        return
    
    print(f"✅ Got {len(data)} news items")
    
    # Store in database
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Create table if not exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS nba_news (
                id SERIAL PRIMARY KEY,
                title TEXT,
                link TEXT,
                source VARCHAR(100),
                published_at TIMESTAMP,
                fetched_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(link)
            )
        """))
        conn.commit()
        
        inserted = 0
        for item in data:
            try:
                conn.execute(text("""
                    INSERT INTO nba_news (title, link, source, published_at, fetched_at)
                    VALUES (:title, :link, :source, :pub, NOW())
                    ON CONFLICT (link) DO UPDATE SET fetched_at = NOW()
                """), {
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'source': item.get('source', ''),
                    'pub': item.get('publishedAt', None)
                })
                inserted += 1
            except Exception as e:
                print(f"   ⚠️ {e}")
        
        conn.commit()
    
    # Count total
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM nba_news")).fetchone()
        total = result[0]
    
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE: {inserted} processed, {total} total in DB")
    print(f"{'='*60}")

    # Send NEW news to Discord
    send_news_to_discord(data)

if __name__ == "__main__":
    main()
