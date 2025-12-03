#!/usr/bin/env python3
"""
Prop Analyzer Engine
Compares player projections vs sportsbook lines to find edges
"""

from sqlalchemy import create_engine, text
from datetime import datetime
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")


class PropAnalyzer:
    """
    Analyzes player props by:
    - Comparing projections vs lines
    - Finding best available lines across books
    - Calculating expected value
    - Identifying market inefficiencies
    """
    
    def __init__(self, engine=None):
        self.engine = engine or create_engine(DATABASE_URL)
        
        # Market to stat mapping
        self.MARKET_TO_STAT = {
            'player_points': 'pts',
            'player_rebounds': 'reb',
            'player_assists': 'ast',
            'player_threes': 'fg3m',
            'player_blocks': 'blk',
            'player_steals': 'stl',
            'player_turnovers': 'tov',
            'player_points_rebounds_assists': 'pra'
        }
        
        # Minimum edge thresholds by market
        self.MIN_EDGE_THRESHOLD = {
            'player_points': 1.5,
            'player_rebounds': 1.0,
            'player_assists': 0.8,
            'player_threes': 0.5,
            'player_blocks': 0.3,
            'player_steals': 0.3,
            'player_turnovers': 0.5,
            'player_points_rebounds_assists': 2.5
        }
    
    def get_props_for_player(self, player_name, game_date=None):
        """Get all props for a player from all sportsbooks"""
        if not game_date:
            game_date = datetime.now().date()
        
        query = text("""
            SELECT 
                player_name,
                market,
                sportsbook,
                line,
                over_odds,
                under_odds,
                home_team,
                away_team
            FROM player_props
            WHERE player_name ILIKE :name
            AND game_date = :game_date
            ORDER BY market, line
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"name": f"%{player_name}%", "game_date": game_date})
            props = []
            for row in result:
                props.append({
                    'player': row[0],
                    'market': row[1],
                    'sportsbook': row[2],
                    'line': float(row[3]) if row[3] else None,
                    'over_odds': int(row[4]) if row[4] else None,
                    'under_odds': int(row[5]) if row[5] else None,
                    'home_team': row[6],
                    'away_team': row[7]
                })
            return props
    
    def get_market_summary(self, player_name, market, game_date=None):
        """Get summary of a specific market across all books"""
        if not game_date:
            game_date = datetime.now().date()
        
        query = text("""
            SELECT 
                MIN(line) as min_line,
                MAX(line) as max_line,
                ROUND(AVG(line)::numeric, 2) as avg_line,
                COUNT(DISTINCT sportsbook) as num_books
            FROM player_props
            WHERE player_name ILIKE :name
            AND market = :market
            AND game_date = :game_date
            AND line IS NOT NULL
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {
                "name": f"%{player_name}%",
                "market": market,
                "game_date": game_date
            }).fetchone()
            
            if result and result[0]:
                return {
                    'min_line': float(result[0]),
                    'max_line': float(result[1]),
                    'avg_line': float(result[2]),
                    'spread': float(result[1]) - float(result[0]),
                    'num_books': result[3]
                }
        return None
    
    def get_best_lines(self, player_name, market, game_date=None):
        """Get best over and under lines across all books"""
        if not game_date:
            game_date = datetime.now().date()
        
        query = text("""
            SELECT sportsbook, line, over_odds, under_odds
            FROM player_props
            WHERE player_name ILIKE :name
            AND market = :market
            AND game_date = :game_date
            AND line IS NOT NULL
            ORDER BY line
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {
                "name": f"%{player_name}%",
                "market": market,
                "game_date": game_date
            }).fetchall()
            
            if not result:
                return None
            
            # Best over = highest line (more room to go over)
            # Best under = lowest line (more room to stay under)
            lines = [{'sportsbook': r[0], 'line': float(r[1]), 
                     'over_odds': r[2], 'under_odds': r[3]} for r in result]
            
            best_over = max(lines, key=lambda x: x['line'])
            best_under = min(lines, key=lambda x: x['line'])
            
            return {
                'best_over': best_over,
                'best_under': best_under,
                'all_lines': lines
            }
    
    def calculate_edge(self, projection, line, direction='over'):
        """
        Calculate edge between projection and line
        
        Args:
            projection: Our projected value
            line: Sportsbook line
            direction: 'over' or 'under'
        
        Returns:
            Edge value (positive = good bet)
        """
        if projection is None or line is None:
            return None
        
        if direction == 'over':
            edge = projection - line
        else:
            edge = line - projection
        
        return round(edge, 2)
    
    def calculate_edge_percentage(self, projection, line):
        """Calculate edge as percentage of line"""
        if not line or line == 0:
            return 0
        
        edge = abs(projection - line)
        return round((edge / line) * 100, 2)
    
    def analyze_prop(self, player_name, market, projection, game_date=None):
        """
        Full analysis of a prop
        
        Returns:
            dict with recommendation, edge, confidence, best books
        """
        if not game_date:
            game_date = datetime.now().date()
        
        # Get market data
        summary = self.get_market_summary(player_name, market, game_date)
        best_lines = self.get_best_lines(player_name, market, game_date)
        
        if not summary or not best_lines:
            return None
        
        consensus_line = summary['avg_line']
        
        # Calculate edge vs consensus
        edge = self.calculate_edge(projection, consensus_line, 'over')
        edge_pct = self.calculate_edge_percentage(projection, consensus_line)
        
        # Determine direction
        min_threshold = self.MIN_EDGE_THRESHOLD.get(market, 1.0)
        
        if edge >= min_threshold:
            direction = 'OVER'
            best_book = best_lines['best_over']
            play_edge = self.calculate_edge(projection, best_book['line'], 'over')
        elif edge <= -min_threshold:
            direction = 'UNDER'
            best_book = best_lines['best_under']
            play_edge = self.calculate_edge(projection, best_book['line'], 'under')
        else:
            direction = 'NO PLAY'
            best_book = None
            play_edge = 0
        
        # Calculate confidence
        confidence = self._calculate_prop_confidence(
            edge=abs(edge),
            spread=summary['spread'],
            num_books=summary['num_books'],
            threshold=min_threshold
        )
        
        # Calculate units
        units = self._calculate_units(confidence, abs(play_edge) if play_edge else 0)
        
        return {
            'player': player_name,
            'market': market,
            'projection': projection,
            'consensus_line': consensus_line,
            'edge': edge,
            'edge_pct': edge_pct,
            'direction': direction,
            'best_book': best_book,
            'play_edge': play_edge,
            'confidence': confidence,
            'units': units,
            'market_spread': summary['spread'],
            'num_books': summary['num_books']
        }
    
    def _calculate_prop_confidence(self, edge, spread, num_books, threshold):
        """Calculate confidence score for a prop play"""
        # Base confidence from edge size
        edge_ratio = edge / threshold if threshold > 0 else 1
        edge_conf = min(edge_ratio * 25, 35)  # Max 35 from edge
        
        # Confidence from book coverage
        book_conf = min(num_books * 3, 20)  # Max 20 from books
        
        # Confidence from market agreement (lower spread = more agreement)
        if spread <= 1:
            spread_conf = 15
        elif spread <= 2:
            spread_conf = 10
        elif spread <= 3:
            spread_conf = 5
        else:
            spread_conf = 0
        
        # Base confidence
        base = 40
        
        total = int(base + edge_conf + book_conf + spread_conf)
        return min(95, max(50, total))
    
    def _calculate_units(self, confidence, edge):
        """Calculate recommended units based on confidence and edge"""
        if confidence >= 85 and edge >= 2:
            return 2.0
        elif confidence >= 75 and edge >= 1.5:
            return 1.5
        elif confidence >= 65 and edge >= 1:
            return 1.0
        elif confidence >= 55:
            return 0.5
        else:
            return 0
    
    def find_all_edges(self, projections_dict, game_date=None):
        """
        Find all edges given a dictionary of player projections
        
        Args:
            projections_dict: {player_name: {market: projection_value}}
        
        Returns:
            List of analyzed props with edges
        """
        if not game_date:
            game_date = datetime.now().date()
        
        edges = []
        
        for player, markets in projections_dict.items():
            for market, projection in markets.items():
                analysis = self.analyze_prop(player, market, projection, game_date)
                if analysis and analysis['direction'] != 'NO PLAY':
                    edges.append(analysis)
        
        # Sort by confidence then edge
        edges.sort(key=lambda x: (x['confidence'], abs(x['edge'])), reverse=True)
        
        return edges


if __name__ == "__main__":
    # Test
    analyzer = PropAnalyzer()
    
    print("Testing PropAnalyzer")
    print("=" * 50)
    
    # Get today's date
    from datetime import datetime
    today = datetime.now().date()
    
    # Get sample props
    query = text("""
        SELECT DISTINCT player_name 
        FROM player_props 
        WHERE game_date = :today 
        LIMIT 5
    """)
    
    with analyzer.engine.connect() as conn:
        players = conn.execute(query, {"today": today}).fetchall()
    
    for (player,) in players:
        print(f"\n{player}:")
        summary = analyzer.get_market_summary(player, 'player_points', today)
        if summary:
            print(f"  Points line: {summary['avg_line']} (spread: {summary['spread']})")
            
            # Simulate a projection
            projection = summary['avg_line'] + 2  # Fake edge
            analysis = analyzer.analyze_prop(player, 'player_points', projection, today)
            if analysis:
                print(f"  Projection: {projection}")
                print(f"  Direction: {analysis['direction']}")
                print(f"  Edge: {analysis['edge']}")
                print(f"  Confidence: {analysis['confidence']}%")
