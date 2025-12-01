#!/usr/bin/env python3
"""
Import Kaggle NBA Dataset into PostgreSQL
"""

import pandas as pd
from sqlalchemy import create_engine, text
import os

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
    """Convert team name or city to 3-letter abbreviation"""
    if team_name in TEAM_ABBREVS:
        return TEAM_ABBREVS[team_name]
    if city in TEAM_ABBREVS:
        return TEAM_ABBREVS[city]
    # Handle LA Clippers vs LA Lakers
    if city == "LA":
        return "LAC"
    if city == "Los Angeles":
        return "LAL"
    return team_name[:3].upper() if team_name else "UNK"


def import_games(engine):
    """Import Games.csv into games table"""
    print("\n📊 IMPORTING GAMES...")
    print("=" * 60)
    
    # Read CSV
    df = pd.read_csv(f"{KAGGLE_PATH}/Games.csv")
    print(f"   Read {len(df)} games from CSV")
    
    # Filter only regular season and playoffs (exclude preseason)
    df = df[df['gameType'].isin(['Regular Season', 'Playoffs', 'PlayIn', 'Emirates NBA Cup'])]
    print(f"   Filtered to {len(df)} regular/playoff games")
    
    # Transform columns to match our schema
    games_df = pd.DataFrame({
        'date': pd.to_datetime(df['gameDateTimeEst']).dt.date,
        'home_team': df.apply(lambda r: get_team_abbrev(r['hometeamName'], r['hometeamCity']), axis=1),
        'visitor_team': df.apply(lambda r: get_team_abbrev(r['awayteamName'], r['awayteamCity']), axis=1),
        'home_pts': df['homeScore'].fillna(0).astype(int),
        'visitor_pts': df['awayScore'].fillna(0).astype(int),
        'home_team_std': df.apply(lambda r: get_team_abbrev(r['hometeamName'], r['hometeamCity']), axis=1),
        'visitor_team_std': df.apply(lambda r: get_team_abbrev(r['awayteamName'], r['awayteamCity']), axis=1),
    })
    
    # Calculate derived fields
    games_df['total_points'] = games_df['home_pts'] + games_df['visitor_pts']
    games_df['margin_home'] = games_df['home_pts'] - games_df['visitor_pts']
    games_df['home_win'] = (games_df['home_pts'] > games_df['visitor_pts']).astype(int)
    
    # Remove duplicates (keep first)
    games_df = games_df.drop_duplicates(subset=['date', 'home_team', 'visitor_team'], keep='first')
    print(f"   After dedup: {len(games_df)} games")
    
    # Import to database
    games_df.to_sql('games', engine, if_exists='append', index=False, method='multi', chunksize=1000)
    
    print(f"   ✅ Imported {len(games_df)} games")
    return len(games_df)


def import_player_stats(engine):
    """Import PlayerStatistics.csv into player_boxscores table"""
    print("\n📊 IMPORTING PLAYER STATS...")
    print("=" * 60)
    
    # Read CSV in chunks (it's large)
    chunk_size = 50000
    total_imported = 0
    
    for i, chunk in enumerate(pd.read_csv(f"{KAGGLE_PATH}/PlayerStatistics.csv", chunksize=chunk_size)):
        print(f"   Processing chunk {i+1}...")
        
        # Transform columns to match our schema
        players_df = pd.DataFrame({
            'game_id': chunk['gameId'],
            'player_id': chunk['personId'],
            'player_name': chunk['firstName'] + ' ' + chunk['lastName'],
            'team_abbreviation': chunk.apply(lambda r: get_team_abbrev(r['playerteamName'], r['playerteamCity']), axis=1),
            'team_city': chunk['playerteamCity'],
            'game_date': pd.to_datetime(chunk['gameDateTimeEst']).dt.date,
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
            'season': '2024-25',  # Will be calculated properly below
        })
        
        # Calculate season based on game date
        def get_season(game_date):
            if pd.isna(game_date):
                return '2024-25'
            if game_date.month >= 10:
                return f"{game_date.year}-{str(game_date.year + 1)[2:]}"
            else:
                return f"{game_date.year - 1}-{str(game_date.year)[2:]}"
        
        players_df['season'] = players_df['game_date'].apply(get_season)
        
        # Import to database
        players_df.to_sql('player_boxscores', engine, if_exists='append', index=False, method='multi', chunksize=1000)
        
        total_imported += len(players_df)
        print(f"      Imported {len(players_df)} records (total: {total_imported})")
    
    print(f"   ✅ Imported {total_imported} player stats")
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
        
        # Check recent games
        recent = conn.execute(text("""
            SELECT date, home_team, visitor_team, home_pts, visitor_pts 
            FROM games 
            ORDER BY date DESC 
            LIMIT 5
        """)).fetchall()
        
        print("\n   Recent games:")
        for r in recent:
            print(f"      {r[0]}: {r[2]} @ {r[1]} ({r[4]}-{r[3]})")
        
        # Check sample player
        player = conn.execute(text("""
            SELECT player_name, game_date, pts, reb, ast 
            FROM player_boxscores 
            WHERE player_name LIKE '%LeBron%'
            ORDER BY game_date DESC 
            LIMIT 3
        """)).fetchall()
        
        print("\n   Sample player (LeBron):")
        for r in player:
            print(f"      {r[1]}: {r[0]} - {r[2]} PTS, {r[3]} REB, {r[4]} AST")


def main():
    print("=" * 60)
    print("🏀 KAGGLE NBA DATA IMPORT")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    
    # Import games
    games_count = import_games(engine)
    
    # Import player stats
    players_count = import_player_stats(engine)
    
    # Verify
    verify_import(engine)
    
    print("\n" + "=" * 60)
    print("✅ IMPORT COMPLETE!")
    print(f"   Games: {games_count:,}")
    print(f"   Player Stats: {players_count:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
