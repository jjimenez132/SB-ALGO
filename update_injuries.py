#!/usr/bin/env python3
"""ESPN NBA Injury Scraper - Fixed Version"""

import requests
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import sys

def get_espn_injuries():
    """Fetch injury data from ESPN API"""
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
                    
                    # CRITICAL FIX: Extract string from injury_type dict
                    injury_type_raw = injury.get('type', {})
                    if isinstance(injury_type_raw, dict):
                        injury_type_str = injury_type_raw.get('description', 'unknown')
                    else:
                        injury_type_str = str(injury_type_raw) if injury_type_raw else 'unknown'
                    
                    # Get date as string
                    date_raw = injury.get('date', datetime.now().isoformat())
                    if isinstance(date_raw, dict):
                        date_str = str(date_raw.get('date', datetime.now().isoformat()))
                    else:
                        date_str = str(date_raw)
                    
                    injuries.append({
                        'player_name': str(athlete.get('displayName', 'Unknown')),
                        'team_name': str(team_name),
                        'team_abbr': str(team_abbr),
                        'status': str(injury.get('status', 'Out')),
                        'description': str(injury.get('longComment', injury.get('shortComment', 'No details'))),
                        'injury_type': injury_type_str,
                        'date': date_str,
                        'updated_at': datetime.now()
                    })
        
        print(f"✅ Found {len(injuries)} injury reports")
        return injuries
        
    except Exception as e:
        print(f"❌ Error fetching from ESPN: {str(e)}")
        return []

def create_injuries_table(engine):
    """Create injuries table if it doesn't exist"""
    create_table_sql = text("""
        CREATE TABLE IF NOT EXISTS injuries (
            id SERIAL PRIMARY KEY,
            player_name VARCHAR(255) NOT NULL,
            team_name VARCHAR(255),
            team_abbr VARCHAR(10),
            status VARCHAR(50),
            description TEXT,
            injury_type VARCHAR(100),
            date VARCHAR(100),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    with engine.connect() as conn:
        conn.execute(create_table_sql)
        conn.commit()
    
    print("✅ Injuries table ready")

def update_database(injuries):
    """Update PostgreSQL database with injury data"""
    
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    
    try:
        engine = create_engine(database_url)
        
        create_injuries_table(engine)
        
        if not injuries:
            print("⚠️ No injuries to update")
            return
        
        # Clear old data
        clear_old = text("DELETE FROM injuries WHERE updated_at < NOW() - INTERVAL '7 days'")
        
        with engine.connect() as conn:
            conn.execute(clear_old)
            conn.commit()
        
        # Convert to DataFrame and insert
        df = pd.DataFrame(injuries)
        
        # Insert one by one to avoid issues
        count = 0
        with engine.connect() as conn:
            for _, row in df.iterrows():
                try:
                    insert_sql = text("""
                        INSERT INTO injuries (player_name, team_name, team_abbr, status, description, injury_type, date, updated_at)
                        VALUES (:player_name, :team_name, :team_abbr, :status, :description, :injury_type, :date, :updated_at)
                    """)
                    conn.execute(insert_sql, row.to_dict())
                    count += 1
                except Exception as e:
                    print(f"⚠️ Skipped {row['player_name']}: {str(e)[:100]}")
                    continue
            conn.commit()
        
        print(f"✅ Successfully updated {count} injury reports in database")
        
        # Show total
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM injuries")).fetchone()
            total = result[0]
            print(f"📊 Total injuries in database: {total}")
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        sys.exit(1)

def main():
    """Main execution"""
    print("=" * 60)
    print("🏀 NBA INJURY REPORT UPDATER")
    print(f"⏰ Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    injuries = get_espn_injuries()
    update_database(injuries)
    
    print("=" * 60)
    print("🎉 Injury update complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
