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

if __name__ == "__main__":
    main()
