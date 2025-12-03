#!/usr/bin/env python3
"""
Matchup Analyzer Engine
Analyzes team matchups and defensive impacts on player props
"""

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")


class MatchupAnalyzer:
    """
    Analyzes matchups including:
    - Team defensive ratings vs position
    - Pace factors
    - Player vs team history
    - Rest and travel impact
    """
    
    def __init__(self, engine=None):
        self.engine = engine or create_engine(DATABASE_URL)
    
    def get_team_defensive_stats(self, team, days=30):
        """Get team's defensive stats (points allowed)"""
        query = text("""
            WITH team_games AS (
                SELECT 
                    CASE WHEN home_team = :team THEN visitor_pts ELSE home_pts END as pts_allowed,
                    total_points
                FROM games
                WHERE (home_team = :team OR visitor_team = :team)
                AND date >= CURRENT_DATE - :days
                AND date < CURRENT_DATE
                AND home_pts > 0
            )
            SELECT 
                COUNT(*) as games,
                ROUND(AVG(pts_allowed)::numeric, 1) as avg_pts_allowed,
                ROUND(AVG(total_points)::numeric, 1) as avg_total
            FROM team_games
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"team": team, "days": days}).fetchone()
            if result and result[0] > 0:
                return {
                    'games': result[0],
                    'avg_pts_allowed': float(result[1]),
                    'avg_total': float(result[2])
                }
        return None
    
    def get_team_pace(self, team, days=30):
        """Calculate team's pace (total points per game)"""
        query = text("""
            SELECT ROUND(AVG(total_points)::numeric, 1) as pace
            FROM games
            WHERE (home_team = :team OR visitor_team = :team)
            AND date >= CURRENT_DATE - :days
            AND date < CURRENT_DATE
            AND total_points > 0
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"team": team, "days": days}).fetchone()
            return float(result[0]) if result and result[0] else None
    
    def get_player_vs_team(self, player_name, opponent, games=5):
        """Get player's historical stats vs specific team"""
        query = text("""
            SELECT 
                pb.game_date, pb.pts, pb.reb, pb.ast, pb.fg3m
            FROM player_boxscores pb
            JOIN games g ON pb.game_date = g.date
            WHERE pb.player_name ILIKE :player
            AND (g.home_team = :opp OR g.visitor_team = :opp)
            AND pb.team_abbreviation != :opp
            ORDER BY pb.game_date DESC
            LIMIT :games
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {
                "player": f"%{player_name}%",
                "opp": opponent,
                "games": games
            }).fetchall()
            
            if result:
                pts = [float(r[1]) for r in result if r[1]]
                reb = [float(r[2]) for r in result if r[2]]
                ast = [float(r[3]) for r in result if r[3]]
                
                return {
                    'games': len(result),
                    'avg_pts': round(sum(pts)/len(pts), 1) if pts else 0,
                    'avg_reb': round(sum(reb)/len(reb), 1) if reb else 0,
                    'avg_ast': round(sum(ast)/len(ast), 1) if ast else 0
                }
        return None
    
    def get_rest_days(self, team, game_date=None):
        """Calculate days since team's last game"""
        if game_date is None:
            game_date = datetime.now().date()
        
        query = text("""
            SELECT MAX(date) as last_game
            FROM games
            WHERE (home_team = :team OR visitor_team = :team)
            AND date < :game_date
            AND home_pts > 0
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"team": team, "game_date": game_date}).fetchone()
            if result and result[0]:
                delta = game_date - result[0]
                return delta.days
        return None
    
    def calculate_pace_adjustment(self, team1_pace, team2_pace, league_avg=230):
        """Calculate pace adjustment factor"""
        if not team1_pace or not team2_pace:
            return 0
        
        combined_pace = (team1_pace + team2_pace) / 2
        adjustment = (combined_pace - league_avg) / league_avg
        
        return round(adjustment, 3)
    
    def analyze_matchup(self, home_team, away_team, game_date=None):
        """Complete matchup analysis"""
        if game_date is None:
            game_date = datetime.now().date()
        
        home_def = self.get_team_defensive_stats(home_team)
        away_def = self.get_team_defensive_stats(away_team)
        home_pace = self.get_team_pace(home_team)
        away_pace = self.get_team_pace(away_team)
        home_rest = self.get_rest_days(home_team, game_date)
        away_rest = self.get_rest_days(away_team, game_date)
        
        pace_adj = self.calculate_pace_adjustment(home_pace, away_pace)
        
        # Determine advantages
        insights = []
        
        if home_rest and away_rest:
            if home_rest > away_rest + 1:
                insights.append(f"Home rest advantage: {home_rest} vs {away_rest} days")
            elif away_rest > home_rest + 1:
                insights.append(f"Away rest advantage: {away_rest} vs {home_rest} days")
            
            if home_rest == 1:
                insights.append("Home team on back-to-back")
            if away_rest == 1:
                insights.append("Away team on back-to-back")
        
        if pace_adj > 0.03:
            insights.append(f"High pace game (+{pace_adj*100:.1f}%)")
        elif pace_adj < -0.03:
            insights.append(f"Low pace game ({pace_adj*100:.1f}%)")
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_defense': home_def,
            'away_defense': away_def,
            'home_pace': home_pace,
            'away_pace': away_pace,
            'combined_pace': round((home_pace + away_pace) / 2, 1) if home_pace and away_pace else None,
            'pace_adjustment': pace_adj,
            'home_rest': home_rest,
            'away_rest': away_rest,
            'insights': insights
        }
    
    def get_stat_adjustment(self, opponent, stat='pts'):
        """Get adjustment factor for a stat vs opponent"""
        def_stats = self.get_team_defensive_stats(opponent)
        if not def_stats:
            return 0
        
        # League average points allowed ~115
        league_avg = 115
        diff = def_stats['avg_pts_allowed'] - league_avg
        
        # Convert to adjustment percentage
        adjustment = diff / league_avg
        
        return round(adjustment, 3)
