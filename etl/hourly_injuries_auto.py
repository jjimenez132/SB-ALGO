import os
import requests
from sqlalchemy import create_engine, text
from datetime import datetime

DATABASE_URL = os.environ['DATABASE_URL']
engine = create_engine(DATABASE_URL)

print("🏥 Fetching NBA injury reports...")

url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"

try:
    response = requests.get(url, timeout=15)
    
    if response.status_code != 200:
        print("❌ Failed to fetch injuries")
        exit(1)
    
    data = response.json()
    teams = data.get('team', [])
    
    total_injuries = 0
    
    # Create table if doesn't exist
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS injuries (
                id SERIAL PRIMARY KEY,
                player_name VARCHAR(255),
                team_abbreviation VARCHAR(10),
                status VARCHAR(50),
                injury_description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_name, team_abbreviation)
            )
        """))
        conn.commit()
    
    # Clear old injuries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM injuries"))
        conn.commit()
    
    # Insert new injuries
    for team in teams:
        team_abbr = team['team']['abbreviation']
        injuries = team.get('injuries', [])
        
        for injury in injuries:
            try:
                player_name = injury['athlete']['displayName']
                status = injury.get('status', 'Unknown')
                description = injury.get('details', {}).get('detail', 'No details')
                
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO injuries (player_name, team_abbreviation, status, injury_description)
                        VALUES (:player_name, :team_abbreviation, :status, :injury_description)
                        ON CONFLICT (player_name, team_abbreviation) DO UPDATE SET
                            status = EXCLUDED.status,
                            injury_description = EXCLUDED.injury_description,
                            updated_at = CURRENT_TIMESTAMP
                    """), {
                        'player_name': player_name,
                        'team_abbreviation': team_abbr,
                        'status': status,
                        'injury_description': description
                    })
                    conn.commit()
                    total_injuries += 1
            
            except Exception as e:
                continue
    
    print(f"✅ Updated {total_injuries} injury reports")
    print(f"🎉 Hourly injury update complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
