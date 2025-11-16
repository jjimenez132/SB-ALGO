#!/usr/bin/env python3
"""
Simple NBA data fetcher - Gets games and boxscores from ESPN API and inserts into PostgreSQL
"""

import requests
import psycopg2
from datetime import datetime, timedelta
import sys

# Database connection
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require"

def get_yesterday_date():
    """Get yesterday's date in YYYYMMDD format"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y%m%d')

def fetch_games(date_str):
    """Fetch games from ESPN API for a specific date"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching games: {e}")
        return None

def fetch_boxscore(game_id):
    """Fetch boxscore for a specific game"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching boxscore for game {game_id}: {e}")
        return None

def insert_game(cursor, game_data, date_str):
    """Insert game into database"""
    try:
        # Parse date from YYYYMMDD to YYYY-MM-DD
        date_obj = datetime.strptime(date_str, '%Y%m%d')
        formatted_date = date_obj.strftime('%Y-%m-%d')
        
        # Get current season (2024-25 for Nov 2025)
        season = "2024-25"
        
        # Get team names and scores
        competitions = game_data.get('competitions', [])
        if not competitions:
            return None
            
        competition = competitions[0]
        competitors = competition.get('competitors', [])
        
        if len(competitors) != 2:
            return None
        
        # ESPN lists away team first, home team second
        away_team = competitors[0]['team']['displayName']
        away_score = int(competitors[0]['score'])
        home_team = competitors[1]['team']['displayName']
        home_score = int(competitors[1]['score'])
        
        # Insert into games table
        insert_query = """
            INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts, season)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """
        
        cursor.execute(insert_query, (formatted_date, away_team, away_score, home_team, home_score, season))
        result = cursor.fetchone()
        
        if result:
            print(f"Inserted game: {away_team} @ {home_team}")
            return result[0]
        else:
            # Game already exists, try to get its ID
            select_query = """
                SELECT id FROM games 
                WHERE date = %s AND visitor_team = %s AND home_team = %s
            """
            cursor.execute(select_query, (formatted_date, away_team, home_team))
            result = cursor.fetchone()
            return result[0] if result else None
            
    except Exception as e:
        print(f"Error inserting game: {e}")
        return None

def safe_int(value, default=0):
    """Safely convert to int with default"""
    try:
        return int(value) if value else default
    except:
        return default

def safe_float(value, default=0.0):
    """Safely convert to float with default"""
    try:
        return float(value) if value else default
    except:
        return default

def insert_boxscores(cursor, boxscore_data, game_id):
    """Insert all player boxscores for a game"""
    try:
        # Get current season
        season = "2024-25"
        
        # Get boxscore data
        boxscore = boxscore_data.get('boxscore', {})
        players = boxscore.get('players', [])
        
        inserted_count = 0
        
        for team in players:
            team_name = team.get('team', {}).get('displayName', '')
            team_abbr = team.get('team', {}).get('abbreviation', '')
            team_id = team.get('team', {}).get('id', '')
            
            # Get ALL players from statistics
            statistics = team.get('statistics', [])
            
            for stat_group in statistics:
                athletes = stat_group.get('athletes', [])
                
                for player in athletes:
                    try:
                        athlete = player.get('athlete', {})
                        player_id = athlete.get('id', '')
                        player_name = athlete.get('displayName', '')
                        
                        # Skip if no player name
                        if not player_name:
                            continue
                        
                        stats = player.get('stats', [])
                        
                        # Initialize all stats with defaults
                        min_played = "0"
                        pts = 0
                        reb = 0
                        ast = 0
                        stl = 0
                        blk = 0
                        to = 0
                        fgm = 0
                        fga = 0
                        fg3m = 0
                        fg3a = 0
                        ftm = 0
                        fta = 0
                        plus_minus = 0
                        
                        # Parse stats if available
                        if len(stats) >= 15:
                            min_played = stats[0] if stats[0] else "0"
                            fgm_fga = stats[1].split('-') if stats[1] else ['0', '0']
                            fgm = safe_int(fgm_fga[0])
                            fga = safe_int(fgm_fga[1]) if len(fgm_fga) > 1 else 0
                            
                            fg3m_fg3a = stats[2].split('-') if stats[2] else ['0', '0']
                            fg3m = safe_int(fg3m_fg3a[0])
                            fg3a = safe_int(fg3m_fg3a[1]) if len(fg3m_fg3a) > 1 else 0
                            
                            ftm_fta = stats[3].split('-') if stats[3] else ['0', '0']
                            ftm = safe_int(ftm_fta[0])
                            fta = safe_int(ftm_fta[1]) if len(ftm_fta) > 1 else 0
                            
                            reb = safe_int(stats[6])
                            ast = safe_int(stats[7])
                            blk = safe_int(stats[8])
                            stl = safe_int(stats[9])
                            to = safe_int(stats[11])
                            pts = safe_int(stats[12])
                            plus_minus = safe_int(stats[14])
                        
                        # Insert player boxscore
                        insert_query = """
                            INSERT INTO player_boxscores 
                            (game_id, player_id, team_id, team_abbreviation, player_name, 
                             min, pts, reb, ast, stl, blk, "TO", fgm, fga, fg3m, fg3a, 
                             ftm, fta, plus_minus, season)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                                    %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """
                        
                        cursor.execute(insert_query, (
                            game_id, player_id, team_id, team_abbr, player_name,
                            min_played, pts, reb, ast, stl, blk, to, fgm, fga,
                            fg3m, fg3a, ftm, fta, plus_minus, season
                        ))
                        
                        if cursor.rowcount > 0:
                            inserted_count += 1
                            
                    except Exception as e:
                        print(f"Error inserting player {player_name}: {e}")
                        continue
        
        print(f"  Inserted {inserted_count} player boxscores")
        return inserted_count
        
    except Exception as e:
        print(f"Error processing boxscores: {e}")
        return 0

def main():
    """Main function to fetch and insert NBA data"""
    print(f"Starting NBA data fetch for {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get yesterday's date
    date_str = get_yesterday_date()
    print(f"Fetching games for date: {date_str}")
    
    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)
    
    try:
        # Fetch games
        games_data = fetch_games(date_str)
        if not games_data:
            print("No games data fetched")
            return
        
        events = games_data.get('events', [])
        print(f"Found {len(events)} games")
        
        # Process each game
        for game in events:
            game_id = game.get('id')
            if not game_id:
                continue
            
            # Insert game
            db_game_id = insert_game(cursor, game, date_str)
            
            if db_game_id:
                # Fetch and insert boxscores
                boxscore_data = fetch_boxscore(game_id)
                if boxscore_data:
                    insert_boxscores(cursor, boxscore_data, db_game_id)
            
            # Commit after each game
            conn.commit()
        
        print("Data fetch completed successfully!")
        
    except Exception as e:
        print(f"Error in main process: {e}")
        conn.rollback()
        sys.exit(1)
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
