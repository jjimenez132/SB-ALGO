#!/usr/bin/env python3
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import sys

def get_espn_injuries():
    print("🏥 Fetching NBA injury reports from ESPN...")
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        injuries = []
        
        if 'injuries' in data:
            for team_data in data['injuries']:
                team_name = team_data.get('team', {}).get('displayName', 'Unknown')
                team_abbr = team_data.get('team', {}).get('abbreviation', 'UNK')
                
                for injury in team_data.get('injuries', []):
                    athlete = injury.get('athlete', {})
                    injuries.append({
                        'player_name': athlete.get('displayName', 'Unknown'),
                        'team_name': team_name,
                        'team_abbr': team_abbr,
                        'status': injury.get('status', 'Out'),
                        'description': injury.get('longComment', injury.get('shortComment', 'No details')),
                        'injury_type': injury.get('type', 'Unknown'),
                        'date': injury.get('date', datetime.now().isoformat()),
                        'updated_at': datetime.now()
                    })
        
        print(f"✅ Found {len(injuries)} injury reports")
        return injuries
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return []

def create_injuries_table(engine):
    create_table_sql = text("""
        CREATE TABLE IF NOT EXISTS injuries (
            id SERIAL PRIMARY KEY,
            player_name VARCHAR(255) NOT NULL,
            team_name VARCHAR(255),
            team_abbr VARCHAR(10),
            status VARCHAR(50),
            description TEXT,
            injury_type VARCHAR(100),
            date TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_name, updated_at)
        )
    """)
    with engine.connect() as conn:
        conn.execute(create_table_sql)
        conn.commit()
    print("✅ Injuries table ready")

def update_database(injuries):
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)
    
    try:
        engine = create_engine(database_url)
        create_injuries_table(engine)
        
        if not injuries:
            print("⚠️ No injuries to update")
            return
        
        df = pd.DataFrame(injuries)
        df.to_sql('injuries', engine, if_exists='append', index=False)
        
        print(f"✅ Updated {len(injuries)} injury reports")
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM injuries")).fetchone()
            print(f"📊 Total injuries in database: {result[0]}")
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("🏀 NBA INJURY REPORT UPDATER")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    injuries = get_espn_injuries()
    update_database(injuries)
    
    print("=" * 60)
    print("🎉 Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
