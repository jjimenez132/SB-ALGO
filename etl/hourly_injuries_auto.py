#!/usr/bin/env python3
"""
Hourly Injuries Auto - Fetch NBA injuries from ESPN API
"""

import os
import requests
from sqlalchemy import create_engine, text
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL', 
    'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db')

engine = create_engine(DATABASE_URL)

print("🏥 Fetching NBA injury reports from ESPN API...")

url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'

try:
    response = requests.get(url, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch injuries: {response.status_code}")
        exit(1)
    
    data = response.json()
    teams = data.get('injuries', data.get('teams', []))
    
    print(f"   Found {len(teams)} teams with injury data")
    
    # Clear old injuries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM injuries"))
        conn.commit()
    
    total_injuries = 0
    
    for team in teams:
        team_name = team.get('displayName', team.get('team', {}).get('displayName', 'Unknown'))
        team_abbr = team.get('abbreviation', team.get('team', {}).get('abbreviation', ''))
        injuries = team.get('injuries', [])
        
        for inj in injuries:
            try:
                athlete = inj.get('athlete', {})
                player_name = athlete.get('displayName', 'Unknown')
                status = inj.get('status', 'Unknown')
                description = inj.get('longComment', inj.get('shortComment', ''))
                injury_type = inj.get('type', {}).get('name', 'Unknown') if isinstance(inj.get('type'), dict) else inj.get('type', 'Unknown')
                injury_date = inj.get('date', '')
                
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO injuries (player_name, team_name, team_abbr, status, description, injury_type, date, updated_at)
                        VALUES (:player_name, :team_name, :team_abbr, :status, :description, :injury_type, :date, NOW())
                    """), {
                        'player_name': player_name,
                        'team_name': team_name,
                        'team_abbr': team_abbr,
                        'status': status,
                        'description': description[:500] if description else '',
                        'injury_type': injury_type or 'Unknown',
                        'date': injury_date
                    })
                    conn.commit()
                    total_injuries += 1
                    
            except Exception as e:
                print(f"   ⚠️ Error: {e}")
                continue
    
    print(f"✅ Updated {total_injuries} injury reports from {len(teams)} teams")
    print(f"🎉 Hourly injury update complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
