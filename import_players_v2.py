#!/usr/bin/env python3
"""
Import PlayerStatistics.csv into PostgreSQL - FIXED v2
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require"

# Path to Kaggle data
KAGGLE_PATH = "/Users/javierjimenez/.cache/kagglehub/datasets/eoinamoore/historical-nba-data-and-player-box-scores/versions/288"

# Team name to abbreviation mapping
TEAM_ABBREVS = {
    "Hawks": "ATL", "Atlanta": "ATL",
    "Celtics": "BOS", "Boston": "BOS",
    "Nets": "BKN", "Brooklyn": "BKN",
    "Hornets": "CHA", "Charlotte": "CHA",
    "Bulls": "CHI", "Chicago": "CHI",
    "Cavaliers": "CLE", "Cleveland": "CLE",
    "Mavericks": "DAL", "Dallas": "DAL",
    "Nuggets": "DEN", "Denver": "DEN",
    "Pistons": "DET", "Detroit": "DET",
    "Warriors": "GSW", "Golden State": "GSW",
    "Rockets": "HOU", "Houston": "HOU",
    "Pacers": "IND", "Indiana": "IND",
    "Clippers": "LAC", "LA": "LAC",
    "Lakers": "LAL", "Los Angeles": "LAL",
    "Grizzlies": "MEM", "Memphis": "MEM",
    "Heat": "MIA", "Miami": "MIA",
    "Bucks": "MIL", "Milwaukee": "MIL",
    "Timberwolves": "MIN", "Minnesota": "MIN",
    "Pelicans": "NOP", "New Orleans": "NOP",
    "Knicks": "NYK", "New York": "NYK",
    "Thunder": "OKC", "Oklahoma City": "OKC",
    "Magic": "ORL", "Orlando": "ORL",
    "76ers": "PHI", "Philadelphia": "PHI",
    "Suns": "PHX", "Phoenix": "PHX",
    "Trail Blazers": "POR", "Portland": "POR",
    "Kings": "SAC", "Sacramento": "SAC",
    "Spurs": "SAS", "San Antonio": "SAS",
    "Raptors": "TOR", "Toronto": "TOR",
    "Jazz": "UTA", "Utah": "UTA",
    "Wizards": "WAS", "Washington": "WAS",
}

def get_team_abbrev(team_name, city=None):
    if pd.isna(team_name):
        return "UNK"
    if team_name in TEAM_ABBREVS:
        return TEAM_ABBREVS[team_name]
    if city in TEAM_ABBREVS:
        return TEAM_ABBREVS[city]
    if city == "LA":
        return "LAC"
    if city == "Los Angeles":
        return "LAL"
    return str(team_name)[:3].upper() if team_name else "UNK"


def parse_date(date_str):
    """Parse date string to date object"""
    if pd.isna(date_str):
        return None
    try:
        # Try parsing just the date part (first 10 chars: YYYY-MM-DD)
        return datetime.strptime(str(date_str)[:10], '%Y-%m-%d').date()
    except:
        return None


def get_season(game_date):
    """Calculate season from date"""
    if game_date is None:
        return '2024-25'
    year = game_date.year
    month = game_date.month
    if month >= 10:
        return f"{year}-{str(year + 1)[2:]}"
    else:
        return f"{year - 1}-{str(year)[2:]}"


def import_player_stats(engine):
    """Import PlayerStatistics.csv into player_boxscores table"""
    print("\n📊 IMPORTING PLAYER STATS...")
    print("=" * 60)
    
    chunk_size = 50000
    total_imported = 0
    
    for i, chunk in enumerate(pd.read_csv(f"{KAGGLE_PATH}/PlayerStatistics.csv", chunksize=chunk_size, low_memory=False)):
        print(f"   Processing chunk {i+1}...")
        
        # Parse dates manually
        chunk['parsed_date'] = chunk['gameDateTimeEst'].apply(parse_date)
        
        # Build dataframe
        players_df = pd.DataFrame({
            'game_id': chunk['gameId'],
            'player_id': chunk['personId'],
            'player_name': (chunk['firstName'].fillna('') + ' ' + chunk['lastName'].fillna('')).str.strip(),
            'team_abbreviation': [get_team_abbrev(row['playerteamName'], row['playerteamCity']) for _, row in chunk.iterrows()],
            'team_city': chunk['playerteamCity'],
            'game_date': chunk['parsed_date'],
            'min': chunk['numMinutes'].apply(lambda x: f"{int(x)}:00" if pd.notna(x) else None),
            'pts': chunk['points'],
            'ast': chunk['assists'],
            'reb': chunk['reboundsTotal'],
            'oreb': chunk['reboundsOffensive'],
            'dreb': chunk['reboundsDefensive'],
            'stl': chunk['steals'],
            'blk': chunk['blocks'],
            'fgm': chunk['fieldGoalsMade'],
            'fga': chunk['fieldGoalsAttempted'],
            'fg_pct': chunk['fieldGoalsPercentage'],
            'fg3m': chunk['threePointersMade'],
            'fg3a': chunk['threePointersAttempted'],
            'fg3_pct': chunk['threePointersPercentage'],
            'ftm': chunk['freeThrowsMade'],
            'fta': chunk['freeThrowsAttempted'],
            'ft_pct': chunk['freeThrowsPercentage'],
            'pf': chunk['foulsPersonal'],
            'TO': chunk['turnovers'],
            'plus_minus': chunk['plusMinusPoints'],
            'season': chunk['parsed_date'].apply(get_season),
        })
        
        # Import to database
        players_df.to_sql('player_boxscores', engine, if_exists='append', index=False, method='multi', chunksize=1000)
        
        total_imported += len(players_df)
        print(f"      ✅ Chunk {i+1}: {len(players_df):,} records (total: {total_imported:,})")
    
    print(f"\n   ✅ TOTAL IMPORTED: {total_imported:,} player stats")
    return total_imported


def verify_import(engine):
    """Verify the import"""
    print("\n✅ VERIFICATION...")
    print("=" * 60)
    
    with engine.connect() as conn:
        games = conn.execute(text("SELECT COUNT(*) FROM games")).fetchone()[0]
        players = conn.execute(text("SELECT COUNT(*) FROM player_boxscores")).fetchone()[0]
        
        print(f"   Games: {games:,}")
        print(f"   Player Stats: {players:,}")
        
        # Check Brandon Ingram
        player = conn.execute(text("""
            SELECT player_name, game_date, team_abbreviation, pts, reb, ast 
            FROM player_boxscores 
            WHERE player_name ILIKE '%Brandon Ingram%'
            ORDER BY game_date DESC NULLS LAST
            LIMIT 5
        """)).fetchall()
        
        print("\n   Brandon Ingram:")
        for r in player:
            print(f"      {r[1]}: {r[0]} ({r[2]}) - {r[3]} PTS, {r[4]} REB, {r[5]} AST")
        
        # Check LeBron
        player2 = conn.execute(text("""
            SELECT player_name, game_date, team_abbreviation, pts, reb, ast 
            FROM player_boxscores 
            WHERE player_name ILIKE '%LeBron%'
            ORDER BY game_date DESC NULLS LAST
            LIMIT 5
        """)).fetchall()
        
        print("\n   LeBron James:")
        for r in player2:
            print(f"      {r[1]}: {r[0]} ({r[2]}) - {r[3]} PTS, {r[4]} REB, {r[5]} AST")


def main():
    print("=" * 60)
    print("🏀 IMPORT PLAYER STATISTICS v2")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    
    players_count = import_player_stats(engine)
    verify_import(engine)
    
    print("\n" + "=" * 60)
    print("✅ IMPORT COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
