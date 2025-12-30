#!/usr/bin/env python3
"""
================================================================================
LIVE ODDS CONNECTOR v1.0
================================================================================
Connects engines to EXISTING odds data from your database.
NO API CALLS - Uses data from your twice-daily Tank01 and OddsAPI pulls.

DATA SOURCES:
-------------
1. betting_odds table (1,160+ rows)
   - Game lines from: FanDuel, DraftKings, BetMGM, Caesars, Bet365, Fanatics, HardRock
   - Spreads, Totals, Moneylines

2. player_props table (161,601+ rows)
   - Props from OddsAPI
   - Markets: points, rebounds, assists, pra, threes

================================================================================
"""

from sqlalchemy import create_engine, text
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import numpy as np

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# Team name normalization
TEAM_ABBR_TO_FULL = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'GS': 'Golden State Warriors',
    'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'LA': 'Los Angeles Lakers',
    'MEM': 'Memphis Grizzlies', 'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks',
    'MIN': 'Minnesota Timberwolves', 'NOP': 'New Orleans Pelicans', 'NO': 'New Orleans Pelicans',
    'NYK': 'New York Knicks', 'NY': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic',
    'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns', 'PHO': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings',
    'SAS': 'San Antonio Spurs', 'SA': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards',
}

FULL_TO_ABBR = {v: k for k, v in TEAM_ABBR_TO_FULL.items()}
# Add common variations
FULL_TO_ABBR.update({
    'Celtics': 'BOS', 'Lakers': 'LAL', 'Warriors': 'GSW', 'Heat': 'MIA',
    'Knicks': 'NYK', 'Nets': 'BKN', 'Bulls': 'CHI', 'Cavs': 'CLE',
    'Cavaliers': 'CLE', 'Thunder': 'OKC', 'Suns': 'PHX', 'Spurs': 'SAS',
    'Bucks': 'MIL', 'Hawks': 'ATL', 'Hornets': 'CHA', 'Pistons': 'DET',
    'Pacers': 'IND', 'Grizzlies': 'MEM', 'Timberwolves': 'MIN', 'Wolves': 'MIN',
    'Pelicans': 'NOP', 'Magic': 'ORL', '76ers': 'PHI', 'Sixers': 'PHI',
    'Blazers': 'POR', 'Trail Blazers': 'POR', 'Kings': 'SAC',
    'Raptors': 'TOR', 'Jazz': 'UTA', 'Wizards': 'WAS',
    'Mavericks': 'DAL', 'Mavs': 'DAL', 'Nuggets': 'DEN', 'Rockets': 'HOU',
    'Clippers': 'LAC',
})


class LiveOddsConnector:
    """
    Connects to your existing odds database.
    NO API CALLS - reads from your twice-daily pulls.
    """
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.preferred_books = ['fanduel', 'draftkings', 'caesars', 'betmgm', 'bet365']
    
    def _normalize_team(self, team: str) -> str:
        """Normalize team name to abbreviation"""
        if not team:
            return ''
        team = team.strip()
        if len(team) <= 3:
            return team.upper()
        return FULL_TO_ABBR.get(team, FULL_TO_ABBR.get(team.split()[-1], team[:3].upper()))
    
    # ==========================================================================
    # GAME ODDS
    # ==========================================================================
    
    def get_todays_games(self, target_date: date = None) -> List[Dict]:
        """
        Get all games with odds for a specific date.
        
        Returns list of games with consensus/best lines from multiple books.
        """
        if target_date is None:
            target_date = date.today()
        
        games = {}
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT game_id, home_team, away_team, sportsbook,
                       home_spread, home_spread_odds, away_spread, away_spread_odds,
                       total, over_odds, under_odds, home_ml, away_ml, updated_at
                FROM betting_odds
                WHERE game_date = :d
                ORDER BY game_id, sportsbook
            """), {"d": target_date})
            
            for row in result:
                r = dict(row._mapping)
                game_id = r['game_id']
                
                if game_id not in games:
                    games[game_id] = {
                        'game_id': game_id,
                        'home_team': r['home_team'],
                        'away_team': r['away_team'],
                        'game_date': target_date.isoformat(),
                        'books': {},
                        'spreads': [],
                        'totals': [],
                        'home_mls': [],
                        'away_mls': [],
                    }
                
                book = r['sportsbook']
                games[game_id]['books'][book] = {
                    'spread': float(r['home_spread']) if r['home_spread'] else None,
                    'spread_odds': int(r['home_spread_odds']) if r['home_spread_odds'] else -110,
                    'total': float(r['total']) if r['total'] else None,
                    'over_odds': int(r['over_odds']) if r['over_odds'] else -110,
                    'under_odds': int(r['under_odds']) if r['under_odds'] else -110,
                    'home_ml': int(r['home_ml']) if r['home_ml'] else None,
                    'away_ml': int(r['away_ml']) if r['away_ml'] else None,
                }
                
                if r['home_spread']:
                    games[game_id]['spreads'].append(float(r['home_spread']))
                if r['total']:
                    games[game_id]['totals'].append(float(r['total']))
                if r['home_ml']:
                    games[game_id]['home_mls'].append(int(r['home_ml']))
                if r['away_ml']:
                    games[game_id]['away_mls'].append(int(r['away_ml']))
        
        # Calculate consensus lines
        result = []
        for game_id, game in games.items():
            # Consensus = median of all books
            consensus = {
                'spread': np.median(game['spreads']) if game['spreads'] else None,
                'total': np.median(game['totals']) if game['totals'] else None,
                'home_ml': int(np.median(game['home_mls'])) if game['home_mls'] else None,
                'away_ml': int(np.median(game['away_mls'])) if game['away_mls'] else None,
            }
            
            # Best line = most favorable to bettor
            best_lines = {
                'spread_home': max(game['spreads']) if game['spreads'] else None,  # Highest spread for home
                'spread_away': min(game['spreads']) if game['spreads'] else None,  # Lowest for away (more points)
                'total_over': min(game['totals']) if game['totals'] else None,     # Lowest total for over
                'total_under': max(game['totals']) if game['totals'] else None,    # Highest total for under
            }
            
            game['consensus'] = consensus
            game['best_lines'] = best_lines
            game['num_books'] = len(game['books'])
            
            result.append(game)
        
        return result
    
    def get_game_odds(self, home_team: str, away_team: str, 
                      target_date: date = None,
                      preferred_book: str = 'fanduel') -> Dict:
        """
        Get odds for a specific game.
        
        Args:
            home_team: Home team name or abbreviation
            away_team: Away team name or abbreviation
            target_date: Date (defaults to today)
            preferred_book: Which sportsbook to use
            
        Returns:
            Game odds dict with spread, total, MLs
        """
        if target_date is None:
            target_date = date.today()
        
        home_abbr = self._normalize_team(home_team)
        away_abbr = self._normalize_team(away_team)
        
        with self.engine.connect() as conn:
            # Try to find the game
            result = conn.execute(text("""
                SELECT game_id, home_team, away_team, sportsbook,
                       home_spread, home_spread_odds, away_spread, away_spread_odds,
                       total, over_odds, under_odds, home_ml, away_ml
                FROM betting_odds
                WHERE game_date = :d
                  AND (home_team = :h OR home_team = :h2)
                  AND (away_team = :a OR away_team = :a2)
                ORDER BY 
                    CASE sportsbook 
                        WHEN 'fanduel' THEN 1
                        WHEN 'draftkings' THEN 2
                        WHEN 'caesars' THEN 3
                        WHEN 'betmgm' THEN 4
                        ELSE 5
                    END
            """), {
                "d": target_date,
                "h": home_abbr,
                "h2": home_team,
                "a": away_abbr,
                "a2": away_team,
            })
            
            rows = result.fetchall()
            
            if not rows:
                return {'error': f'No odds found for {away_team} @ {home_team} on {target_date}'}
            
            # Get preferred book or first available
            selected = None
            for row in rows:
                r = dict(row._mapping)
                if r['sportsbook'] == preferred_book:
                    selected = r
                    break
            
            if not selected:
                selected = dict(rows[0]._mapping)
            
            return {
                'game_id': selected['game_id'],
                'home_team': selected['home_team'],
                'away_team': selected['away_team'],
                'sportsbook': selected['sportsbook'],
                'spread': float(selected['home_spread']) if selected['home_spread'] else None,
                'spread_odds': int(selected['home_spread_odds']) if selected['home_spread_odds'] else -110,
                'total': float(selected['total']) if selected['total'] else None,
                'over_odds': int(selected['over_odds']) if selected['over_odds'] else -110,
                'under_odds': int(selected['under_odds']) if selected['under_odds'] else -110,
                'home_ml': int(selected['home_ml']) if selected['home_ml'] else None,
                'away_ml': int(selected['away_ml']) if selected['away_ml'] else None,
                'books_available': len(rows),
            }
    
    # ==========================================================================
    # PLAYER PROPS
    # ==========================================================================
    
    def get_player_props(self, player_name: str, target_date: date = None,
                         market: str = None) -> List[Dict]:
        """
        Get all props for a player.
        
        Args:
            player_name: Player name
            target_date: Date (defaults to today)
            market: Specific market (points, rebounds, assists, pra, threes)
            
        Returns:
            List of prop lines
        """
        if target_date is None:
            target_date = date.today()
        
        # Map short names to full market names
        market_map = {
            'pts': 'player_points',
            'points': 'player_points',
            'reb': 'player_rebounds',
            'rebounds': 'player_rebounds',
            'ast': 'player_assists',
            'assists': 'player_assists',
            'pra': 'player_points_rebounds_assists',
            '3pm': 'player_threes',
            'threes': 'player_threes',
            'stl': 'player_steals',
            'steals': 'player_steals',
            'blk': 'player_blocks',
            'blocks': 'player_blocks',
            'to': 'player_turnovers',
            'turnovers': 'player_turnovers',
        }
        
        with self.engine.connect() as conn:
            query = """
                SELECT player_name, market, line, over_odds, under_odds,
                       sportsbook, home_team, away_team, updated_at
                FROM player_props
                WHERE game_date = :d
                  AND LOWER(player_name) LIKE LOWER(:p)
            """
            params = {"d": target_date, "p": f"%{player_name}%"}
            
            if market:
                full_market = market_map.get(market.lower(), market)
                query += " AND market = :m"
                params["m"] = full_market
            
            query += " ORDER BY market, sportsbook"
            
            result = conn.execute(text(query), params)
            
            props = []
            for row in result:
                r = dict(row._mapping)
                props.append({
                    'player': r['player_name'],
                    'market': r['market'],
                    'line': float(r['line']) if r['line'] else None,
                    'over_odds': int(r['over_odds']) if r['over_odds'] else -110,
                    'under_odds': int(r['under_odds']) if r['under_odds'] else -110,
                    'sportsbook': r['sportsbook'],
                    'matchup': f"{r['away_team']} @ {r['home_team']}",
                })
            
            return props
    
    def get_prop_line(self, player_name: str, stat: str,
                      target_date: date = None,
                      preferred_book: str = 'FANDUEL') -> Dict:
        """
        Get specific prop line for a player.
        
        Args:
            player_name: Player name
            stat: Stat type (pts, reb, ast, pra, threes)
            target_date: Date
            preferred_book: Preferred sportsbook
            
        Returns:
            Prop line dict
        """
        # Map stat to full market name
        stat_map = {
            'pts': 'player_points',
            'points': 'player_points',
            'reb': 'player_rebounds',
            'rebounds': 'player_rebounds',
            'ast': 'player_assists',
            'assists': 'player_assists',
            'pra': 'player_points_rebounds_assists',
            'points_rebounds_assists': 'player_points_rebounds_assists',
            '3pm': 'player_threes',
            'threes': 'player_threes',
            '3pt': 'player_threes',
            'stl': 'player_steals',
            'steals': 'player_steals',
            'blk': 'player_blocks',
            'blocks': 'player_blocks',
        }
        
        market = stat_map.get(stat.lower(), f'player_{stat.lower()}')
        
        if target_date is None:
            target_date = date.today()
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_name, market, line, over_odds, under_odds,
                       sportsbook, home_team, away_team
                FROM player_props
                WHERE game_date = :d
                  AND LOWER(player_name) LIKE LOWER(:p)
                  AND market = :m
                ORDER BY 
                    CASE UPPER(sportsbook)
                        WHEN 'FANDUEL' THEN 1
                        WHEN 'DRAFTKINGS' THEN 2
                        ELSE 3
                    END
            """), {"d": target_date, "p": f"%{player_name}%", "m": market})
            
            rows = result.fetchall()
            
            if not rows:
                return {'error': f'No {stat} prop found for {player_name} on {target_date}'}
            
            # Get preferred or first
            selected = None
            for row in rows:
                r = dict(row._mapping)
                if r['sportsbook'].upper() == preferred_book.upper():
                    selected = r
                    break
            
            if not selected:
                selected = dict(rows[0]._mapping)
            
            return {
                'player': selected['player_name'],
                'stat': stat,
                'market': selected['market'],
                'line': float(selected['line']) if selected['line'] else None,
                'over_odds': int(selected['over_odds']) if selected['over_odds'] else -110,
                'under_odds': int(selected['under_odds']) if selected['under_odds'] else -110,
                'sportsbook': selected['sportsbook'],
                'matchup': f"{selected['away_team']} @ {selected['home_team']}",
                'books_available': len(rows),
            }
    
    def get_all_props_for_game(self, home_team: str, away_team: str,
                                target_date: date = None) -> List[Dict]:
        """
        Get all player props for a specific game.
        """
        if target_date is None:
            target_date = date.today()
        
        home_abbr = self._normalize_team(home_team)
        away_abbr = self._normalize_team(away_team)
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_name, market, line, over_odds, under_odds, sportsbook
                FROM player_props
                WHERE game_date = :d
                  AND ((home_team = :h OR home_team = :h2)
                       OR (away_team = :a OR away_team = :a2))
                ORDER BY player_name, market
            """), {
                "d": target_date,
                "h": home_abbr, "h2": home_team,
                "a": away_abbr, "a2": away_team,
            })
            
            props = []
            for row in result:
                r = dict(row._mapping)
                props.append({
                    'player': r['player_name'],
                    'market': r['market'],
                    'line': float(r['line']) if r['line'] else None,
                    'over_odds': int(r['over_odds']) if r['over_odds'] else -110,
                    'under_odds': int(r['under_odds']) if r['under_odds'] else -110,
                    'sportsbook': r['sportsbook'],
                })
            
            return props
    
    # ==========================================================================
    # LINE SHOPPING
    # ==========================================================================
    
    def find_best_line(self, home_team: str, away_team: str,
                       bet_type: str, side: str,
                       target_date: date = None) -> Dict:
        """
        Find the best available line across all books.
        
        Args:
            home_team: Home team
            away_team: Away team
            bet_type: 'spread', 'total', 'ml'
            side: 'home', 'away', 'over', 'under'
            
        Returns:
            Best line with sportsbook info
        """
        if target_date is None:
            target_date = date.today()
        
        home_abbr = self._normalize_team(home_team)
        away_abbr = self._normalize_team(away_team)
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT sportsbook, home_spread, away_spread, total,
                       home_spread_odds, away_spread_odds,
                       over_odds, under_odds, home_ml, away_ml
                FROM betting_odds
                WHERE game_date = :d
                  AND (home_team = :h OR home_team = :h2)
            """), {"d": target_date, "h": home_abbr, "h2": home_team})
            
            rows = result.fetchall()
            
            if not rows:
                return {'error': 'No odds found'}
            
            best = None
            best_value = None
            
            for row in rows:
                r = dict(row._mapping)
                
                if bet_type == 'spread':
                    if side == 'home':
                        value = float(r['home_spread']) if r['home_spread'] else None
                        odds = r['home_spread_odds']
                    else:
                        value = float(r['away_spread']) if r['away_spread'] else None
                        odds = r['away_spread_odds']
                    
                    # Higher spread is better for favorite, lower for underdog
                    if value is not None:
                        if best_value is None or (side == 'away' and value > best_value) or (side == 'home' and value > best_value):
                            best_value = value
                            best = {'sportsbook': r['sportsbook'], 'line': value, 'odds': odds}
                
                elif bet_type == 'total':
                    value = float(r['total']) if r['total'] else None
                    if side == 'over':
                        odds = r['over_odds']
                        # Lower total is better for over
                        if value and (best_value is None or value < best_value):
                            best_value = value
                            best = {'sportsbook': r['sportsbook'], 'line': value, 'odds': odds}
                    else:
                        odds = r['under_odds']
                        # Higher total is better for under
                        if value and (best_value is None or value > best_value):
                            best_value = value
                            best = {'sportsbook': r['sportsbook'], 'line': value, 'odds': odds}
                
                elif bet_type == 'ml':
                    if side == 'home':
                        value = int(r['home_ml']) if r['home_ml'] else None
                    else:
                        value = int(r['away_ml']) if r['away_ml'] else None
                    
                    # Higher ML is always better
                    if value and (best_value is None or value > best_value):
                        best_value = value
                        best = {'sportsbook': r['sportsbook'], 'line': value, 'odds': value}
            
            if best:
                best['bet_type'] = bet_type
                best['side'] = side
            
            return best or {'error': 'Could not determine best line'}
    
    # ==========================================================================
    # FORMATTED OUTPUT FOR ENGINES
    # ==========================================================================
    
    def get_games_for_daily_runner(self, target_date: date = None) -> List[Dict]:
        """
        Get games formatted for the daily runner / meta merge engine.
        
        Returns games with all needed fields for engine analysis.
        """
        games = self.get_todays_games(target_date)
        
        formatted = []
        for game in games:
            consensus = game.get('consensus', {})
            
            formatted.append({
                'home_team': game['home_team'],
                'away_team': game['away_team'],
                'spread': consensus.get('spread'),
                'total': consensus.get('total'),
                'home_ml': consensus.get('home_ml'),
                'away_ml': consensus.get('away_ml'),
                'game_id': game['game_id'],
                'num_books': game['num_books'],
                'all_books': game['books'],
            })
        
        return formatted


# ==============================================================================
# TEST
# ==============================================================================
if __name__ == "__main__":
    from datetime import date
    
    print("=" * 70)
    print("LIVE ODDS CONNECTOR - TEST")
    print("=" * 70)
    
    connector = LiveOddsConnector()
    today = date.today()
    
    # Test 1: Get today's games
    print(f"\n📅 GAMES FOR {today}:")
    print("-" * 70)
    
    games = connector.get_todays_games(today)
    
    if games:
        for game in games:
            consensus = game.get('consensus', {})
            print(f"\n  🏀 {game['away_team']} @ {game['home_team']}")
            print(f"     Spread: {consensus.get('spread')}")
            print(f"     Total: {consensus.get('total')}")
            print(f"     ML: {consensus.get('home_ml')} / {consensus.get('away_ml')}")
            print(f"     Books: {game['num_books']}")
    else:
        print("  No games found for today")
    
    # Test 2: Get specific game
    print("\n" + "-" * 70)
    print("🎯 SPECIFIC GAME LOOKUP:")
    print("-" * 70)
    
    if games:
        first_game = games[0]
        odds = connector.get_game_odds(first_game['home_team'], first_game['away_team'], today)
        print(f"\n  {odds}")
    
    # Test 3: Player props
    print("\n" + "-" * 70)
    print(f"🏀 PLAYER PROPS FOR {today}:")
    print("-" * 70)
    
    # Test a few players
    test_players = ['Anthony Davis', 'LeBron James', 'Shai Gilgeous-Alexander', 'Zion Williamson']
    
    for player in test_players:
        props = connector.get_player_props(player, today)
        if props:
            print(f"\n  {player}:")
            # Group by market and show first of each
            seen_markets = set()
            for p in props:
                if p['market'] not in seen_markets:
                    print(f"    {p['market']}: {p['line']} ({p['sportsbook']})")
                    seen_markets.add(p['market'])
                if len(seen_markets) >= 4:
                    break
    
    # Test 4: Get specific prop line
    print("\n" + "-" * 70)
    print("🎯 SPECIFIC PROP LOOKUP:")
    print("-" * 70)
    
    prop = connector.get_prop_line('Anthony Davis', 'pts', today)
    if 'error' not in prop:
        print(f"\n  {prop['player']} {prop['stat'].upper()}")
        print(f"  Line: {prop['line']}")
        print(f"  Over: {prop['over_odds']} | Under: {prop['under_odds']}")
        print(f"  Book: {prop['sportsbook']} ({prop['books_available']} books)")
    else:
        print(f"  {prop}")
    
    # Test 5: Format for daily runner
    print("\n" + "-" * 70)
    print("📋 FORMATTED FOR DAILY RUNNER:")
    print("-" * 70)
    
    formatted = connector.get_games_for_daily_runner(today)
    for g in formatted[:3]:
        print(f"\n  {g['away_team']} @ {g['home_team']}: spread {g['spread']}, total {g['total']}")
    
    print("\n" + "=" * 70)
    print("✅ LIVE ODDS CONNECTOR - TESTS COMPLETE")
    print("=" * 70)
