#!/usr/bin/env python3
"""
Player Projections Engine
Calculates projected stats for each player based on historical performance
"""

from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")


class PlayerProjections:
    """
    Calculates player stat projections using:
    - Weighted recent performance (L5, L10, L15, Season)
    - Home/Away splits
    - Rest days impact
    """
    
    def __init__(self, engine=None):
        self.engine = engine or create_engine(DATABASE_URL)
        
        self.RECENCY_WEIGHTS = {
            'L5': 0.40,
            'L10': 0.30,
            'L15': 0.20,
            'season': 0.10
        }
        
        self.STAT_COLUMNS = ['pts', 'reb', 'ast', 'fg3m', 'stl', 'blk']
    
    def get_player_averages(self, player_name, games=30):
        """Get player's recent averages for all stats"""
        query = text("""
            SELECT 
                COUNT(*) as games,
                ROUND(AVG(pts)::numeric, 2) as avg_pts,
                ROUND(AVG(reb)::numeric, 2) as avg_reb,
                ROUND(AVG(ast)::numeric, 2) as avg_ast,
                ROUND(AVG(fg3m)::numeric, 2) as avg_fg3m,
                ROUND(AVG(stl)::numeric, 2) as avg_stl,
                ROUND(AVG(blk)::numeric, 2) as avg_blk,
                ROUND(STDDEV(pts)::numeric, 2) as std_pts,
                ROUND(STDDEV(reb)::numeric, 2) as std_reb,
                ROUND(STDDEV(ast)::numeric, 2) as std_ast,
                ROUND(STDDEV(fg3m)::numeric, 2) as std_fg3m
            FROM player_boxscores
            WHERE player_name ILIKE :name
            AND game_date >= CURRENT_DATE - :days
            AND pts IS NOT NULL
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"name": f"%{player_name}%", "days": games}).fetchone()
            
            if result and result[0] > 0:
                return {
                    'games': result[0],
                    'pts': float(result[1] or 0),
                    'reb': float(result[2] or 0),
                    'ast': float(result[3] or 0),
                    'fg3m': float(result[4] or 0),
                    'stl': float(result[5] or 0),
                    'blk': float(result[6] or 0),
                    'std_pts': float(result[7] or 0),
                    'std_reb': float(result[8] or 0),
                    'std_ast': float(result[9] or 0),
                    'std_fg3m': float(result[10] or 0)
                }
        return None
    
    def get_weighted_average(self, player_name, stat='pts'):
        """Calculate weighted average using L5, L10, L15, Season"""
        periods = {'L5': 5, 'L10': 10, 'L15': 15, 'season': 90}
        
        weighted_sum = 0
        total_weight = 0
        
        for period_name, days in periods.items():
            avg = self._get_stat_average(player_name, stat, days)
            if avg is not None:
                weight = self.RECENCY_WEIGHTS[period_name]
                weighted_sum += avg * weight
                total_weight += weight
        
        if total_weight > 0:
            return round(weighted_sum / total_weight, 2)
        return None
    
    def _get_stat_average(self, player_name, stat, days):
        """Get average for a specific stat over N days"""
        query = text(f"""
            SELECT ROUND(AVG({stat})::numeric, 2)
            FROM player_boxscores
            WHERE player_name ILIKE :name
            AND game_date >= CURRENT_DATE - :days
            AND {stat} IS NOT NULL
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"name": f"%{player_name}%", "days": days}).fetchone()
            return float(result[0]) if result and result[0] else None
    
    def calculate_projection(self, player_name, stat='pts', is_home=True, rest_days=1):
        """Calculate full projection with adjustments"""
        base_projection = self.get_weighted_average(player_name, stat)
        
        if base_projection is None:
            return None
        
        adjustments = {}
        final_projection = base_projection
        
        # B2B adjustment
        if rest_days == 0:
            adjustment = -0.08
            final_projection *= (1 + adjustment)
            adjustments['b2b'] = adjustment
        elif rest_days >= 3:
            adjustment = 0.03
            final_projection *= (1 + adjustment)
            adjustments['rest'] = adjustment
        
        # Road adjustment
        if not is_home:
            adjustment = -0.02
            final_projection *= (1 + adjustment)
            adjustments['road'] = adjustment
        
        return {
            'player': player_name,
            'stat': stat,
            'base': base_projection,
            'projection': round(final_projection, 2),
            'adjustments': adjustments,
            'confidence': self._calculate_confidence(player_name, stat)
        }
    
    def _calculate_confidence(self, player_name, stat):
        """Calculate confidence based on sample size and consistency"""
        averages = self.get_player_averages(player_name)
        
        if not averages:
            return 50
        
        games = averages['games']
        std = averages.get(f'std_{stat}', 0) or 0
        avg = averages.get(stat, 0) or 1
        
        cv = std / avg if avg > 0 else 1
        games_conf = min(games / 15, 1) * 30
        consistency_conf = max(0, (1 - cv) * 40)
        base_conf = 30
        
        confidence = int(base_conf + games_conf + consistency_conf)
        return min(95, max(50, confidence))
    
    def project_all_stats(self, player_name, is_home=True, rest_days=1):
        """Get projections for all stat categories"""
        projections = {}
        
        for stat in self.STAT_COLUMNS:
            proj = self.calculate_projection(player_name, stat, is_home, rest_days)
            if proj:
                projections[stat] = proj
        
        return projections
