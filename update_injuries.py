#!/usr/bin/env python3
"""
ESPN NBA Injury Report Scraper
Fetches real-time injury data from ESPN and stores in PostgreSQL
Runs hourly via Render Cron Job
"""

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
        # ESPN's public injury API endpoint
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        injuries = []
        
        # Parse the response
        if 'injuries' in data:
            for team_data in data['injuries']:
                team_name = team_data.get('team', {}).get('displayName', 'Unknown')
                team_abbr = team_data.get('team', {}).get('abbreviation', 'UNK')
                
                for injury in team_data.get('injuries', []):
                    athlete = injury.get('athlete', {})
                    
                    # Extract injury type - it comes as a dict, we need just the description
                    injury_type_data = injury.get('type', {})
                    if isinstance(injury_type_data, dict):
                        injury_type = injury_type_data.get('description', 'Unknown')
                    else:
                        injury_type = str(injury_type_data)
                    
                    injuries.append({
                        'player_name': athlete.get('displayName', 'Unknown'),
                        'team_name': team_name,
                        'team_abbr': team_abbr,
                        'status': injury.get('status', 'Out'),
                        'description': injury.get('longComment', injury.get('shortComment', 'No details')),
                        'injury_type': injury_type,
                        'date': injury.get('date', datetime.now().isoformat()),
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
    """Update PostgreSQL database with injury data"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    
    try:
        engine = create_engine(database_url)
        
        # Create table if needed
        create_injuries_table(engine)
        
        if not injuries:
            print("⚠️ No injuries to update")
            return
        
        # Clear old data (keep last 7 days only)
        clear_old = text("""
            DELETE FROM injuries 
            WHERE updated_at < NOW() - INTERVAL '7 days'
        """)
        
        with engine.connect() as conn:
            conn.execute(clear_old)
            conn.commit()
        
        # Convert to DataFrame
        df = pd.DataFrame(injuries)
        
        # Insert new data (ignore duplicates)
        df.to_sql('injuries', engine, if_exists='append', index=False, method='multi')
        
        print(f"✅ Successfully updated {len(injuries)} injury reports in database")
        
        # Show sample
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
    
    # Fetch injuries from ESPN
    injuries = get_espn_injuries()
    
    # Update database
    update_database(injuries)
    
    print("=" * 60)
    print("🎉 Injury update complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
