#!/usr/bin/env python3
"""
Daily NBA Data Update Script
Runs at 5:00 AM ET to pull:
1. Yesterday's final game scores
2. Yesterday's player box scores  
3. Today's schedule and odds
"""

import requests
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import hashlib
import os

API_KEY = "ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653"
DATABASE_URL = os.environ.get('DATABASE_URL', 
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

HEADERS = {
    "x-rapidapi-host": "tank01-fantasy-stats.p.rapidapi.com",
    "x-rapidapi-key": API_KEY
}

TEAM_MAP = {
    "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "CHA": "CHA", "CHI": "CHI",
    "CLE": "CLE", "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GS": "GSW", "GSW": "GSW",
    "HOU": "HOU", "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MEM": "MEM",
    "MIA": "MIA", "MIL": "MIL", "MIN": "MIN", "NO": "NOP", "NOP": "NOP",
    "NY": "NYK", "NYK": "NYK", "OKC": "OKC", "ORL": "ORL", "PHI": "PHI",
    "PHO": "PHX", "PHX": "PHX", "POR": "POR", "SA": "SAS", "SAS": "SAS",
    "SAC": "SAC", "TOR": "TOR", "UTA": "UTA", "WAS": "WAS"
}

def game_string_to_bigint(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:15], 16)

def safe_float(val):
    try:
        return float(val) if val else 0.0
    except:
        return 0.0

def fetch_games_for_date(date_str):
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBAGamesForDate"
    response = requests.get(url, headers=HEADERS, params={"gameDate": date_str})
    if response.status_code != 200:
        return []
    return response.json().get('body', [])

def fetch_boxscore(game_id):
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBABoxScore"
    response = requests.get(url, headers=HEADERS, params={"gameID": game_id})
    if response.status_code != 200:
        return None
    return response.json().get('body', {})

def fetch_odds(date_str):
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBABettingOdds"
    response = requests.get(url, headers=HEADERS, params={"gameDate": date_str})
    if response.status_code != 200:
        return {}
    return response.json().get('body', {})

def update_games_with_scores(engine, date_str, date_obj):
    print(f"\n📥 Fetching games for {date_str}...")
    games = fetch_games_for_date(date_str)
    if not games:
        print("   No games found")
        return 0
    
    updated = 0
    for game in games:
        game_id = game.get('gameID') or game.get('gameId')
        home = TEAM_MAP.get(game.get('home'), game.get('home'))
        away = TEAM_MAP.get(game.get('away'), game.get('away'))
        
        box_data = fetch_boxscore(game_id)
        if not box_data:
            continue
        
        home_pts = int(box_data.get('homePts', 0) or 0)
        away_pts = int(box_data.get('awayPts', 0) or 0)
        
        if home_pts == 0 and away_pts == 0:
            continue
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                UPDATE games SET home_pts=:hp, visitor_pts=:ap, total_points=:tp, margin_home=:mh, home_win=:hw
                WHERE date=:d AND home_team=:h AND visitor_team=:a
            """), {"hp": home_pts, "ap": away_pts, "tp": home_pts+away_pts, 
                   "mh": home_pts-away_pts, "hw": 1 if home_pts>away_pts else 0,
                   "d": date_obj, "h": home, "a": away})
            
            if result.rowcount == 0:
                conn.execute(text("""
                    INSERT INTO games (date, home_team, visitor_team, home_pts, visitor_pts, total_points, margin_home, home_win)
                    VALUES (:d, :h, :a, :hp, :ap, :tp, :mh, :hw)
                """), {"d": date_obj, "h": home, "a": away, "hp": home_pts, "ap": away_pts,
                       "tp": home_pts+away_pts, "mh": home_pts-away_pts, "hw": 1 if home_pts>away_pts else 0})
            conn.commit()
            updated += 1
            print(f"   ✅ {away} @ {home}: {away_pts}-{home_pts}")
    return updated

def update_player_stats(engine, date_str, date_obj):
    print(f"\n📥 Fetching player stats for {date_str}...")
    games = fetch_games_for_date(date_str)
    if not games:
        return 0
    
    inserted = 0
    for game in games:
        game_id_str = game.get('gameID') or game.get('gameId')
        game_id_int = game_string_to_bigint(game_id_str)
        
        box_data = fetch_boxscore(game_id_str)
        if not box_data:
            continue
        
        player_stats = box_data.get('playerStats', {})
        for player_id_str, stats in player_stats.items():
            team = TEAM_MAP.get(stats.get('team'), stats.get('team'))
            fgm, fga = safe_float(stats.get('fgm')), safe_float(stats.get('fga'))
            fg3m = safe_float(stats.get('tptfgm') or stats.get('threePtMade'))
            fg3a = safe_float(stats.get('tptfga') or stats.get('threePtAtt'))
            ftm, fta = safe_float(stats.get('ftm')), safe_float(stats.get('fta'))
            
            p = {
                'game_id': game_id_int, 'player_id': int(player_id_str),
                'player_name': stats.get('longName', 'Unknown'), 'team_abbreviation': team,
                'game_date': date_obj, 'pts': safe_float(stats.get('pts')),
                'reb': safe_float(stats.get('reb')), 'ast': safe_float(stats.get('ast')),
                'stl': safe_float(stats.get('stl')), 'blk': safe_float(stats.get('blk')),
                'fgm': fgm, 'fga': fga, 'fg_pct': round(fgm/fga,3) if fga>0 else None,
                'fg3m': fg3m, 'fg3a': fg3a, 'fg3_pct': round(fg3m/fg3a,3) if fg3a>0 else None,
                'ftm': ftm, 'fta': fta, 'ft_pct': round(ftm/fta,3) if fta>0 else None,
                'oreb': safe_float(stats.get('offReb')), 'dreb': safe_float(stats.get('defReb')),
                'pf': safe_float(stats.get('pf')), 'tov': safe_float(stats.get('TOV')),
                'plus_minus': safe_float(stats.get('plusMinus')),
                'min': str(stats.get('mins', '0'))
            }
            
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO player_boxscores 
                        (game_id, player_id, player_name, team_abbreviation, game_date, 
                         pts, reb, ast, stl, blk, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                         ftm, fta, ft_pct, oreb, dreb, pf, "TO", plus_minus, min, season)
                        VALUES (:game_id, :player_id, :player_name, :team_abbreviation, :game_date,
                         :pts, :reb, :ast, :stl, :blk, :fgm, :fga, :fg_pct, :fg3m, :fg3a, :fg3_pct,
                         :ftm, :fta, :ft_pct, :oreb, :dreb, :pf, :tov, :plus_minus, :min, '2025-26')
                    """), p)
                    conn.commit()
                    inserted += 1
            except:
                pass
    
    print(f"   ✅ Inserted {inserted} player stats")
    return inserted

def update_odds(engine, date_str, date_obj):
    print(f"\n📥 Fetching odds for {date_str}...")
    odds_data = fetch_odds(date_str)
    if not odds_data:
        print("   No odds found")
        return 0
    
    def parse_odds(s):
        if not s or s == 'N/A': return None
        try: return int(s.replace('+', ''))
        except: return None
    
    def parse_spread(s):
        if not s or s == 'N/A': return None
        try: return float(s.replace('+', ''))
        except: return None
    
    sportsbooks = ['fanduel', 'draftkings', 'betmgm', 'caesars', 'bet365', 'fanatics', 'hardrock']
    inserted = 0
    
    with engine.connect() as conn:
        for game_id, data in odds_data.items():
            home = data.get('homeTeam')
            away = data.get('awayTeam')
            
            for book in sportsbooks:
                if book not in data:
                    continue
                b = data[book]
                try:
                    conn.execute(text("""
                        INSERT INTO betting_odds 
                        (game_id, game_date, home_team, away_team, sportsbook,
                         home_spread, home_spread_odds, away_spread, away_spread_odds,
                         total, over_odds, under_odds, home_ml, away_ml, updated_at)
                        VALUES (:gid, :gd, :h, :a, :book, :hs, :hso, :as, :aso, :t, :oo, :uo, :hm, :am, NOW())
                        ON CONFLICT (game_id, sportsbook) DO UPDATE SET
                        home_spread=:hs, home_spread_odds=:hso, away_spread=:as, away_spread_odds=:aso,
                        total=:t, over_odds=:oo, under_odds=:uo, home_ml=:hm, away_ml=:am, updated_at=NOW()
                    """), {
                        'gid': game_id, 'gd': date_obj, 'h': home, 'a': away, 'book': book,
                        'hs': parse_spread(b.get('homeTeamSpread')),
                        'hso': parse_odds(b.get('homeTeamSpreadOdds')),
                        'as': parse_spread(b.get('awayTeamSpread')),
                        'aso': parse_odds(b.get('awayTeamSpreadOdds')),
                        't': parse_spread(b.get('totalOver')),
                        'oo': parse_odds(b.get('totalOverOdds')),
                        'uo': parse_odds(b.get('totalUnderOdds')),
                        'hm': parse_odds(b.get('homeTeamMLOdds')),
                        'am': parse_odds(b.get('awayTeamMLOdds'))
                    })
                    inserted += 1
                except Exception as e:
                    pass
        conn.commit()
    
    print(f"   ✅ Inserted {inserted} odds records")
    return inserted

def add_todays_schedule(engine, date_str, date_obj):
    print(f"\n📅 Adding today's schedule ({date_str})...")
    games = fetch_games_for_date(date_str)
    if not games:
        print("   No games scheduled")
        return 0
    
    added = 0
    for game in games:
        home = TEAM_MAP.get(game.get('home'), game.get('home'))
        away = TEAM_MAP.get(game.get('away'), game.get('away'))
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1 FROM games WHERE date=:d AND home_team=:h AND visitor_team=:a
            """), {"d": date_obj, "h": home, "a": away})
            
            if not result.fetchone():
                conn.execute(text("""
                    INSERT INTO games (date, home_team, visitor_team, home_pts, visitor_pts, total_points, margin_home, home_win)
                    VALUES (:d, :h, :a, 0, 0, 0, 0, 0)
                """), {"d": date_obj, "h": home, "a": away})
                conn.commit()
                added += 1
                print(f"   📅 {away} @ {home}")
    
    print(f"   ✅ Added {added} games to schedule")
    return added


def main():
    print("=" * 60)
    print("🏀 NBA DAILY DATA UPDATE")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    today_str = today.strftime("%Y%m%d")
    yesterday_str = yesterday.strftime("%Y%m%d")
    today_date = today.date()
    yesterday_date = yesterday.date()
    
    # 1. Yesterday's scores
    update_games_with_scores(engine, yesterday_str, yesterday_date)
    
    # 2. Yesterday's player stats
    update_player_stats(engine, yesterday_str, yesterday_date)
    
    # 3. Today's schedule
    add_todays_schedule(engine, today_str, today_date)
    
    # 4. Today's odds
    update_odds(engine, today_str, today_date)
    
    print("\n" + "=" * 60)
    print("✅ DAILY UPDATE COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
