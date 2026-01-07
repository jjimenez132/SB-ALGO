#!/usr/bin/env python3
"""
Hourly Injuries Auto - Fetch NBA injuries from Tank01 API
"""

import os
import re
import requests
from sqlalchemy import create_engine, text
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL', 
    'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db')

RAPIDAPI_KEY = 'ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653'

engine = create_engine(DATABASE_URL)

def extract_player_name(description):
    """Extract player name from injury description"""
    skip_words = ['Portland', 'Head', 'The', 'Boston', 'Miami', 'Lakers', 'Warriors', 
                  'Celtics', 'Heat', 'Bulls', 'Knicks', 'Nets', 'Coach', 'Monday',
                  'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
                  'X-rays', 'MRI', 'CT']
    
    # Pattern 1: "Date: Name (injury)" or "Date: Name won't/is/has"
    match = re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+:\s+([A-Z][a-z\'\-]+(?:\s+[A-Z][a-z\'\-]+)?)', description)
    if match:
        name = match.group(1)
        first_word = name.split()[0]
        
        # If first word is a skip word, try other patterns
        if first_word in skip_words:
            # Try: "that Name's" or "on Name's"
            match2 = re.search(r"(?:that|on)\s+([A-Z][a-z\'\-]+)(?:'s)?", description)
            if match2 and match2.group(1) not in skip_words:
                return match2.group(1)
            
            # Try: "Name (injury)"
            match3 = re.search(r'([A-Z][a-z\'\-]+)\s*\([a-z]+\)', description)
            if match3 and match3.group(1) not in skip_words:
                return match3.group(1)
            
            return None
        
        # Return just last name (first word after date)
        return first_word
    
    # Pattern 2: "Name (injury)" anywhere
    match = re.search(r'([A-Z][a-z\'\-]+)\s*\([a-z]+\)', description)
    if match and match.group(1) not in skip_words:
        return match.group(1)
    
    return None

def extract_injury_type(description):
    """Extract injury type from parentheses"""
    match = re.search(r'\(([a-z]+)\)', description)
    if match:
        return match.group(1)
    
    # Common injury keywords
    injury_keywords = ['ankle', 'knee', 'shoulder', 'hamstring', 'back', 'hip', 
                       'toe', 'thumb', 'wrist', 'calf', 'groin', 'quad', 'foot']
    desc_lower = description.lower()
    for keyword in injury_keywords:
        if keyword in desc_lower:
            return keyword
    
    return 'Unknown'

print("🏥 Fetching NBA injury reports from Tank01 API...")

url = 'https://tank01-fantasy-stats.p.rapidapi.com/getNBAInjuryList'
headers = {
    'x-rapidapi-host': 'tank01-fantasy-stats.p.rapidapi.com',
    'x-rapidapi-key': RAPIDAPI_KEY
}

try:
    response = requests.get(url, headers=headers, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch injuries: {response.status_code}")
        exit(1)
    
    data = response.json()
    injuries_list = data.get('body', [])
    
    print(f"   Found {len(injuries_list)} injury entries")
    
    # Create/update table
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS injuries (
                id SERIAL PRIMARY KEY,
                player_id VARCHAR(50),
                player_name VARCHAR(255),
                status VARCHAR(50),
                injury_type VARCHAR(100),
                description TEXT,
                injury_date VARCHAR(20),
                return_date VARCHAR(20),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_id, injury_date)
            )
        """))
        conn.commit()
    
    # Clear old injuries
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM injuries"))
        conn.commit()
    
    total_injuries = 0
    seen_players = set()
    
    for injury in injuries_list:
        try:
            player_id = injury.get('playerID', '')
            status = injury.get('designation', 'Unknown')
            description = injury.get('description', '')
            injury_date = injury.get('injDate', '')
            return_date = injury.get('injReturnDate', '')
            
            # Extract player name
            player_name = extract_player_name(description)
            if not player_name:
                continue  # Skip if we can't identify the player
            
            # Extract injury type
            injury_type = extract_injury_type(description)
            
            # Skip duplicates (same player + status, keep most recent)
            player_key = f"{player_name}_{status}"
            if player_key in seen_players:
                continue
            seen_players.add(player_key)
            
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO injuries (player_id, player_name, status, injury_type, description, injury_date, return_date)
                    VALUES (:player_id, :player_name, :status, :injury_type, :description, :injury_date, :return_date)
                    ON CONFLICT (player_id, injury_date) DO UPDATE SET
                        status = EXCLUDED.status,
                        description = EXCLUDED.description,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    'player_id': player_id,
                    'player_name': player_name,
                    'status': status,
                    'injury_type': injury_type,
                    'description': description[:500],
                    'injury_date': injury_date,
                    'return_date': return_date
                })
                conn.commit()
                total_injuries += 1
                
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            continue
    
    print(f"✅ Updated {total_injuries} unique injury reports")
    print(f"🎉 Hourly injury update complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
