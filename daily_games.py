#!/usr/bin/env python3
"""
Daily NBA Games Fetcher - Production Version with Multiple Sources
Works in GitHub Actions environment where external APIs are accessible
"""

import psycopg2
import requests
from datetime import datetime, timedelta
import time
import os
import json
import sys

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Create database connection"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    return psycopg2.connect(DATABASE_URL)

def log(message, level="INFO"):
    """Unified logging function"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def fetch_from_balldontlie(date_str):
    """Method 1: BallDontLie API (free tier)"""
    log(f"Attempting BallDontLie API for {date_str}...")
    
    try:
        url = "https://api.balldontlie.io/v1/games"
        params = {
            'dates[]': date_str,
            'per_page': 100
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            games = data.get('data', [])
            
            game_list = []
            for game in games:
                if game['status'] == 'Final':
                    game_info = {
                        'game_id': f"bdl_{game['id']}",
                        'date': datetime.strptime(game['date'][:10], '%Y-%m-%d').date(),
                        'home_team_name': game['home_team']['full_name'],
                        'away_team_name': game['visitor_team']['full_name'],
                        'home_team_abbr': game['home_team']['abbreviation'],
                        'away_team_abbr': game['visitor_team']['abbreviation'],
                        'home_score': game['home_team_score'],
                        'away_score': game['visitor_team_score'],
                        'status': game['status'],
                        'api_game_id': str(game['id'])
                    }
                    game_list.append(game_info)
            
            log(f"✅ Found {len(game_list)} games from BallDontLie", "SUCCESS")
            return game_list
        else:
            log(f"BallDontLie API returned status {response.status_code}", "WARNING")
            
    except Exception as e:
        log(f"BallDontLie error: {str(e)[:100]}", "WARNING")
    
    return []

def fetch_from_nba_api_library(date_str):
    """Method 2: Using nba_api Python library"""
    log(f"Attempting nba_api library for {date_str}...")
    
    try:
        from nba_api.stats.endpoints import scoreboardv2
        
        # nba_api expects MM/DD/YYYY format
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%m/%d/%Y')
        
        board = scoreboardv2.ScoreboardV2(game_date=formatted_date)
        time.sleep(1)  # Rate limiting
        
        games_data = board.get_normalized_dict()
        games = games_data.get('GameHeader', [])
        
        game_list = []
        for game in games:
            if 'Final' in game.get('GAME_STATUS_TEXT', ''):
                game_info = {
                    'game_id': game['GAME_ID'],
                    'date': date_obj.date(),
                    'home_team_name': game.get('HOME_TEAM_NAME', ''),
                    'away_team_name': game.get('VISITOR_TEAM_NAME', ''),
                    'status': game['GAME_STATUS_TEXT']
                }
                
                # Get scores from LineScore
                line_scores = games_data.get('LineScore', [])
                for score in line_scores:
                    if score['GAME_ID'] == game['GAME_ID']:
                        if score['TEAM_ID'] == game.get('HOME_TEAM_ID'):
                            game_info['home_score'] = score.get('PTS', 0)
                            game_info['home_team_abbr'] = score.get('TEAM_ABBREVIATION', '')
                        elif score['TEAM_ID'] == game.get('VISITOR_TEAM_ID'):
                            game_info['away_score'] = score.get('PTS', 0)
                            game_info['away_team_abbr'] = score.get('TEAM_ABBREVIATION', '')
                
                if 'home_score' in game_info and 'away_score' in game_info:
                    game_list.append(game_info)
        
        log(f"✅ Found {len(game_list)} games from nba_api", "SUCCESS")
        return game_list
        
    except Exception as e:
        log(f"nba_api error: {str(e)[:100]}", "WARNING")
        return []

def fetch_player_stats_balldontlie(game_id):
    """Fetch player stats from BallDontLie"""
    try:
        url = "https://api.balldontlie.io/v1/stats"
        params = {
            'game_ids[]': game_id,
            'per_page': 100
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get('data', [])
            
            player_stats = []
            for stat in stats:
                if stat.get('min'):
                    # Parse minutes
                    min_str = str(stat['min']) if stat['min'] else "0"
                    if ':' in min_str:
                        min_parts = min_str.split(':')
                        minutes = int(min_parts[0]) if min_parts[0] else 0
                    else:
                        try:
                            minutes = int(float(min_str))
                        except:
                            minutes = 0
                    
                    player_stat = {
                        'game_id': f"bdl_{game_id}",
                        'player_name': f"{stat['player']['first_name']} {stat['player']['last_name']}",
                        'team': stat['team']['abbreviation'],
                        'minutes': minutes,
                        'points': stat.get('pts', 0) or 0,
                        'rebounds': stat.get('reb', 0) or 0,
                        'assists': stat.get('ast', 0) or 0,
                        'steals': stat.get('stl', 0) or 0,
                        'blocks': stat.get('blk', 0) or 0,
                        'turnovers': stat.get('turnover', 0) or 0,
                        'fg_made': stat.get('fgm', 0) or 0,
                        'fg_attempted': stat.get('fga', 0) or 0,
                        'fg3_made': stat.get('fg3m', 0) or 0,
                        'fg3_attempted': stat.get('fg3a', 0) or 0,
                        'ft_made': stat.get('ftm', 0) or 0,
                        'ft_attempted': stat.get('fta', 0) or 0,
                        'fouls': stat.get('pf', 0) or 0
                    }
                    player_stats.append(player_stat)
            
            return player_stats
    except Exception as e:
        log(f"Stats fetch error: {str(e)[:100]}", "WARNING")
    
    return []

def fetch_player_stats_nba_api(game_id):
    """Fetch player stats using nba_api library"""
    try:
        from nba_api.stats.endpoints import boxscoretraditionalv2
        
        boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
        time.sleep(1)  # Rate limiting
        
        data = boxscore.get_normalized_dict()
        players = data.get('PlayerStats', [])
        
        player_stats = []
        for player in players:
            if player.get('MIN'):
                # Parse minutes
                min_str = player.get('MIN', '0:00')
                if ':' in str(min_str):
                    min_parts = min_str.split(':')
                    minutes = int(min_parts[0]) if min_parts[0] else 0
                else:
                    minutes = int(min_str) if min_str else 0
                
                stats = {
                    'game_id': game_id,
                    'player_name': player['PLAYER_NAME'],
                    'team': player['TEAM_ABBREVIATION'],
                    'minutes': minutes,
                    'points': player.get('PTS', 0) or 0,
                    'rebounds': player.get('REB', 0) or 0,
                    'assists': player.get('AST', 0) or 0,
                    'steals': player.get('STL', 0) or 0,
                    'blocks': player.get('BLK', 0) or 0,
                    'turnovers': player.get('TO', 0) or 0,
                    'fg_made': player.get('FGM', 0) or 0,
                    'fg_attempted': player.get('FGA', 0) or 0,
                    'fg3_made': player.get('FG3M', 0) or 0,
                    'fg3_attempted': player.get('FG3A', 0) or 0,
                    'ft_made': player.get('FTM', 0) or 0,
                    'ft_attempted': player.get('FTA', 0) or 0,
                    'fouls': player.get('PF', 0) or 0
                }
                player_stats.append(stats)
        
        return player_stats
    except Exception as e:
        log(f"NBA API stats error: {str(e)[:100]}", "WARNING")
        return []

def save_to_database(games, all_player_stats):
    """Save games and player stats to database"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    games_saved = 0
    stats_saved = 0
    
    try:
        # Save games
        for game in games:
            try:
                cur.execute("""
                    INSERT INTO games (game_id, game_date, home_team, away_team, 
                                     home_score, away_score, season, game_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_id) 
                    DO UPDATE SET 
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score
                """, (
                    game['game_id'],
                    game['date'],
                    game['home_team_name'],
                    game['away_team_name'],
                    game.get('home_score', 0),
                    game.get('away_score', 0),
                    '2024-25',
                    'Regular Season'
                ))
                games_saved += 1
            except Exception as e:
                log(f"Error saving game: {e}", "ERROR")
        
        # Save player stats
        for stats in all_player_stats:
            try:
                cur.execute("""
                    INSERT INTO player_boxscores 
                    (game_id, player_name, team, minutes, points, rebounds, assists, 
                     steals, blocks, turnovers, fg_made, fg_attempted, 
                     fg3_made, fg3_attempted, ft_made, ft_attempted, fouls)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_id, player_name) DO UPDATE SET
                        minutes = EXCLUDED.minutes,
                        points = EXCLUDED.points,
                        rebounds = EXCLUDED.rebounds,
                        assists = EXCLUDED.assists,
                        steals = EXCLUDED.steals,
                        blocks = EXCLUDED.blocks,
                        turnovers = EXCLUDED.turnovers,
                        fg_made = EXCLUDED.fg_made,
                        fg_attempted = EXCLUDED.fg_attempted,
                        fg3_made = EXCLUDED.fg3_made,
                        fg3_attempted = EXCLUDED.fg3_attempted,
                        ft_made = EXCLUDED.ft_made,
                        ft_attempted = EXCLUDED.ft_attempted,
                        fouls = EXCLUDED.fouls
                """, (
                    stats['game_id'],
                    stats['player_name'],
                    stats['team'],
                    stats['minutes'],
                    stats['points'],
                    stats['rebounds'],
                    stats['assists'],
                    stats['steals'],
                    stats['blocks'],
                    stats['turnovers'],
                    stats['fg_made'],
                    stats['fg_attempted'],
                    stats['fg3_made'],
                    stats['fg3_attempted'],
                    stats['ft_made'],
                    stats['ft_attempted'],
                    stats.get('fouls', 0)
                ))
                stats_saved += 1
            except Exception as e:
                log(f"Error saving player stats: {e}", "ERROR")
        
        conn.commit()
        log(f"✅ Database updated: {games_saved} games, {stats_saved} player stats", "SUCCESS")
        
    except Exception as e:
        log(f"Database transaction error: {e}", "ERROR")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    
    return games_saved, stats_saved

def main():
    """Main function with multiple data source attempts"""
    print("=" * 60)
    print("NBA DAILY GAMES FETCHER - MULTI-SOURCE VERSION 2.0")
    print("=" * 60)
    
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')
    
    log(f"Processing games for: {date_str}")
    
    # Try multiple sources in order of preference
    games = []
    source = None
    
    # Method 1: BallDontLie (most reliable for boxscores)
    if not games:
        games = fetch_from_balldontlie(date_str)
        if games:
            source = "BallDontLie"
    
    # Method 2: NBA API library
    if not games:
        games = fetch_from_nba_api_library(date_str)
        if games:
            source = "NBA API"
    
    if not games:
        log("❌ No games found from any source!", "ERROR")
        log("This could mean:", "INFO")
        log("  1. No games were played yesterday", "INFO")
        log("  2. All APIs are temporarily unavailable", "INFO")
        log("  3. Network/proxy issues in the environment", "INFO")
        return 1
    
    # Display found games
    log(f"📊 Found {len(games)} games from {source}:", "SUCCESS")
    for game in games:
        print(f"  {game['away_team_name']} {game.get('away_score', 0)} @ "
              f"{game['home_team_name']} {game.get('home_score', 0)}")
    
    # Fetch player stats
    log("📈 Fetching player statistics...")
    all_player_stats = []
    
    for i, game in enumerate(games, 1):
        log(f"  Game {i}/{len(games)}: {game.get('away_team_abbr', game['away_team_name'][:3])} @ "
            f"{game.get('home_team_abbr', game['home_team_name'][:3])}")
        
        # Use appropriate stats fetcher
        if 'api_game_id' in game:  # BallDontLie
            stats = fetch_player_stats_balldontlie(game['api_game_id'])
        elif source == "NBA API":  # NBA API
            stats = fetch_player_stats_nba_api(game['game_id'])
        else:
            stats = []
        
        all_player_stats.extend(stats)
        
        # Rate limiting
        if i < len(games):
            time.sleep(0.5)
    
    # Save to database
    log("💾 Saving to database...")
    games_saved, stats_saved = save_to_database(games, all_player_stats)
    
    # Display summary
    print("\n" + "=" * 60)
    print("✅ DAILY UPDATE COMPLETE")
    print("=" * 60)
    print(f"📅 Date: {date_str}")
    print(f"📊 Source: {source}")
    print(f"🏀 Games saved: {games_saved}/{len(games)}")
    print(f"👥 Player stats saved: {stats_saved}/{len(all_player_stats)}")
    
    # Show top performers if we have stats
    if all_player_stats:
        top_scorers = sorted(all_player_stats, key=lambda x: x['points'], reverse=True)[:5]
        print("\n🌟 TOP PERFORMERS:")
        for player in top_scorers:
            print(f"  {player['player_name']} ({player['team']}): "
                  f"{player['points']} pts, {player['rebounds']} reb, {player['assists']} ast")
    elif games_saved > 0:
        print("\n⚠️ Games saved but no player stats available from this source")
    
    # Return success if we saved any games
    return 0 if games_saved > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
