#!/usr/bin/env python3
"""
Trend Analyzer Engine
Analyzes player and team trends for prop betting
"""

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")


class TrendAnalyzer:
    """
    Analyzes trends including:
    - Hit rates at various lines
    - Hot/cold streaks
    - Performance trends (improving/declining)
    - Situational patterns
    - Consistency metrics
    """
    
    def __init__(self, engine=None):
        self.engine = engine or create_engine(DATABASE_URL)
    
    def get_player_game_log(self, player_name, stat='pts', games=20):
        """Get player's recent game log for a stat"""
        stat_col = 'TO' if stat == 'tov' else stat
        
        query = text(f"""
            SELECT 
                game_date,
                {stat_col} as stat_value,
                team_abbreviation,
                min
            FROM player_boxscores
            WHERE player_name ILIKE :name
            AND {stat_col} IS NOT NULL
            ORDER BY game_date DESC
            LIMIT :games
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"name": f"%{player_name}%", "games": games})
            return [{'date': r[0], 'value': float(r[1]), 'team': r[2], 'min': r[3]} for r in result]
    
    def calculate_hit_rates(self, player_name, stat, line):
        """
        Calculate hit rates at a specific line
        
        Returns:
            Hit rates for L5, L10, L15, Season
        """
        game_log = self.get_player_game_log(player_name, stat, 82)  # Full season
        
        if not game_log:
            return None
        
        def hit_rate(games):
            if not games:
                return None
            hits = sum(1 for g in games if g['value'] > line)
            return {
                'hits': hits,
                'games': len(games),
                'rate': round(hits / len(games), 3),
                'percentage': round((hits / len(games)) * 100, 1)
            }
        
        return {
            'L5': hit_rate(game_log[:5]),
            'L10': hit_rate(game_log[:10]),
            'L15': hit_rate(game_log[:15]),
            'L20': hit_rate(game_log[:20]),
            'season': hit_rate(game_log)
        }
    
    def detect_streak(self, player_name, stat='pts', direction='over', line=None):
        """
        Detect current streak (consecutive overs or unders)
        
        Returns:
            Streak length and details
        """
        game_log = self.get_player_game_log(player_name, stat, 20)
        
        if not game_log:
            return None
        
        # If no line provided, use player's average
        if line is None:
            line = sum(g['value'] for g in game_log) / len(game_log)
        
        streak = 0
        streak_values = []
        
        for game in game_log:
            if direction == 'over':
                if game['value'] > line:
                    streak += 1
                    streak_values.append(game['value'])
                else:
                    break
            else:
                if game['value'] < line:
                    streak += 1
                    streak_values.append(game['value'])
                else:
                    break
        
        return {
            'direction': direction,
            'line': round(line, 1),
            'streak_length': streak,
            'streak_values': streak_values,
            'is_hot': streak >= 5,
            'is_cold': streak <= -5 if direction == 'under' else False
        }
    
    def analyze_trend_direction(self, player_name, stat='pts', games=10):
        """
        Analyze if player is trending up or down
        
        Uses linear regression concept (simplified)
        """
        game_log = self.get_player_game_log(player_name, stat, games)
        
        if not game_log or len(game_log) < 5:
            return None
        
        # Reverse to chronological order
        values = [g['value'] for g in reversed(game_log)]
        
        # Calculate simple trend
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        diff = second_avg - first_avg
        pct_change = (diff / first_avg * 100) if first_avg > 0 else 0
        
        # Recent 3 game trend
        recent_3 = values[-3:] if len(values) >= 3 else values
        recent_avg = sum(recent_3) / len(recent_3)
        overall_avg = sum(values) / len(values)
        
        recent_diff = recent_avg - overall_avg
        
        # Determine trend
        if pct_change >= 10 and recent_diff > 0:
            trend = 'STRONG_UP'
        elif pct_change >= 5 or recent_diff > 1:
            trend = 'UP'
        elif pct_change <= -10 and recent_diff < 0:
            trend = 'STRONG_DOWN'
        elif pct_change <= -5 or recent_diff < -1:
            trend = 'DOWN'
        else:
            trend = 'STABLE'
        
        return {
            'trend': trend,
            'first_half_avg': round(first_avg, 1),
            'second_half_avg': round(second_avg, 1),
            'change': round(diff, 1),
            'pct_change': round(pct_change, 1),
            'recent_3_avg': round(recent_avg, 1),
            'overall_avg': round(overall_avg, 1),
            'values': values
        }
    
    def calculate_consistency(self, player_name, stat='pts', games=15):
        """
        Calculate consistency score
        
        Low variance = high consistency
        """
        game_log = self.get_player_game_log(player_name, stat, games)
        
        if not game_log or len(game_log) < 5:
            return None
        
        values = [g['value'] for g in game_log]
        avg = sum(values) / len(values)
        
        # Calculate standard deviation
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5
        
        # Coefficient of variation (CV)
        cv = (std_dev / avg) if avg > 0 else 0
        
        # Consistency score (inverse of CV, scaled)
        # Lower CV = higher consistency
        consistency_score = max(0, min(100, int((1 - cv) * 100)))
        
        # Find floor and ceiling
        floor = min(values)
        ceiling = max(values)
        
        return {
            'average': round(avg, 1),
            'std_dev': round(std_dev, 2),
            'cv': round(cv, 3),
            'consistency_score': consistency_score,
            'floor': floor,
            'ceiling': ceiling,
            'range': ceiling - floor,
            'games': len(values)
        }
    
    def find_patterns(self, player_name, stat='pts', games=20):
        """
        Find patterns in player performance
        
        Looks for:
        - Bounce back games (after bad game)
        - Letdown games (after big game)
        - Rest day impact
        """
        game_log = self.get_player_game_log(player_name, stat, games)
        
        if not game_log or len(game_log) < 10:
            return None
        
        values = [g['value'] for g in reversed(game_log)]
        avg = sum(values) / len(values)
        
        # Analyze patterns
        bounce_backs = []
        letdowns = []
        
        for i in range(1, len(values)):
            prev = values[i-1]
            curr = values[i]
            
            # Bounce back: bad game followed by good game
            if prev < avg * 0.7 and curr > avg:
                bounce_backs.append({'after': prev, 'result': curr})
            
            # Letdown: great game followed by below average
            if prev > avg * 1.3 and curr < avg:
                letdowns.append({'after': prev, 'result': curr})
        
        # Calculate pattern rates
        bad_games = sum(1 for v in values if v < avg * 0.7)
        great_games = sum(1 for v in values if v > avg * 1.3)
        
        return {
            'bounce_back_rate': len(bounce_backs) / bad_games if bad_games > 0 else 0,
            'letdown_rate': len(letdowns) / great_games if great_games > 0 else 0,
            'bounce_backs': len(bounce_backs),
            'letdowns': len(letdowns),
            'bad_games': bad_games,
            'great_games': great_games,
            'average': round(avg, 1)
        }
    
    def get_trend_summary(self, player_name, stat='pts', line=None):
        """
        Complete trend summary for a player prop
        """
        game_log = self.get_player_game_log(player_name, stat, 20)
        
        if not game_log:
            return None
        
        if line is None:
            line = sum(g['value'] for g in game_log) / len(game_log)
        
        hit_rates = self.calculate_hit_rates(player_name, stat, line)
        streak = self.detect_streak(player_name, stat, 'over', line)
        trend = self.analyze_trend_direction(player_name, stat)
        consistency = self.calculate_consistency(player_name, stat)
        
        # Generate insights
        insights = []
        
        if hit_rates and hit_rates['L5'] and hit_rates['L5']['percentage'] >= 80:
            insights.append(f"Hot: {hit_rates['L5']['percentage']}% hit rate L5 games")
        
        if streak and streak['streak_length'] >= 3:
            insights.append(f"{streak['streak_length']} game {streak['direction']} streak")
        
        if trend and trend['trend'] in ['STRONG_UP', 'UP']:
            insights.append(f"Trending up: +{trend['pct_change']}% vs first half")
        elif trend and trend['trend'] in ['STRONG_DOWN', 'DOWN']:
            insights.append(f"Trending down: {trend['pct_change']}% vs first half")
        
        if consistency and consistency['consistency_score'] >= 75:
            insights.append(f"High consistency: {consistency['consistency_score']} score")
        elif consistency and consistency['consistency_score'] <= 40:
            insights.append(f"Volatile: floor {consistency['floor']}, ceiling {consistency['ceiling']}")
        
        return {
            'player': player_name,
            'stat': stat,
            'line': round(line, 1),
            'hit_rates': hit_rates,
            'streak': streak,
            'trend': trend,
            'consistency': consistency,
            'insights': insights,
            'game_log': game_log[:10]  # Last 10 for display
        }


if __name__ == "__main__":
    analyzer = TrendAnalyzer()
    
    print("Trend Analyzer Tests")
    print("=" * 50)
    
    # Find a player with data
    query = text("""
        SELECT DISTINCT player_name 
        FROM player_boxscores 
        WHERE game_date >= CURRENT_DATE - 30
        LIMIT 1
    """)
    
    with analyzer.engine.connect() as conn:
        result = conn.execute(query).fetchone()
    
    if result:
        player = result[0]
        print(f"\nAnalyzing: {player}")
        
        summary = analyzer.get_trend_summary(player, 'pts', 20)
        
        if summary:
            print(f"\nLine: {summary['line']}")
            
            if summary['hit_rates'] and summary['hit_rates']['L10']:
                print(f"L10 Hit Rate: {summary['hit_rates']['L10']['percentage']}%")
            
            if summary['consistency']:
                print(f"Consistency: {summary['consistency']['consistency_score']}")
            
            print(f"\nInsights:")
            for insight in summary['insights']:
                print(f"  • {insight}")
    else:
        print("No player data found")
