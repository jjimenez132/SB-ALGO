"""
Props Memory - Track prop predictions vs results for self-learning
"""

from sqlalchemy import text
from datetime import datetime

class PropsMemory:
    """Track prop predictions vs results for self-learning"""
    
    def __init__(self, engine=None):
        self.engine = engine
        self._ensure_table()
    
    def _ensure_table(self):
        """Create props tracking table if not exists"""
        if not self.engine:
            return
            
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS algo_prop_predictions (
                    id SERIAL PRIMARY KEY,
                    game_date DATE,
                    player_name VARCHAR(100),
                    team VARCHAR(10),
                    opponent VARCHAR(10),
                    market VARCHAR(50),
                    pick VARCHAR(20),
                    line FLOAT,
                    projected_value FLOAT,
                    edge FLOAT,
                    confidence FLOAT,
                    hit_rate_l5 FLOAT,
                    hit_rate_l10 FLOAT,
                    sportsbook VARCHAR(50),
                    odds INTEGER,
                    actual_value FLOAT,
                    hit BOOLEAN,
                    units_bet FLOAT,
                    units_result FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    graded_at TIMESTAMP,
                    UNIQUE(game_date, player_name, market)
                )
            """))
            conn.commit()
    
    def save_prop_prediction(self, game_date, player_name, team, opponent, market, 
                            pick, line, projected_value, edge, confidence,
                            hit_rate_l5, hit_rate_l10, sportsbook, odds, units_bet):
        """Save a prop prediction for later grading"""
        if not self.engine:
            return
            
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO algo_prop_predictions 
                (game_date, player_name, team, opponent, market, pick, line,
                 projected_value, edge, confidence, hit_rate_l5, hit_rate_l10,
                 sportsbook, odds, units_bet)
                VALUES (:gd, :pn, :team, :opp, :mkt, :pick, :line, :pv, :edge, 
                        :conf, :hr5, :hr10, :sb, :odds, :units)
                ON CONFLICT (game_date, player_name, market) 
                DO UPDATE SET 
                    pick = :pick, line = :line, projected_value = :pv,
                    edge = :edge, confidence = :conf, hit_rate_l5 = :hr5,
                    hit_rate_l10 = :hr10, sportsbook = :sb, odds = :odds,
                    units_bet = :units, created_at = NOW()
            """), {
                'gd': game_date, 'pn': player_name, 'team': team, 'opp': opponent,
                'mkt': market, 'pick': pick, 'line': line, 'pv': projected_value,
                'edge': edge, 'conf': confidence, 'hr5': hit_rate_l5,
                'hr10': hit_rate_l10, 'sb': sportsbook, 'odds': odds, 'units': units_bet
            })
            conn.commit()
    
    def grade_prop_predictions(self, game_date):
        """Grade prop predictions against actual box score results"""
        if not self.engine:
            return 0
        
        # Market to stat column mapping
        market_to_stat = {
            'player_points': 'pts',
            'player_rebounds': 'reb',
            'player_assists': 'ast',
            'player_threes': 'fg3m',
            'player_steals': 'stl',
            'player_blocks': 'blk',
            'player_pts_rebs': ['pts', 'reb'],
            'player_pts_asts': ['pts', 'ast'],
            'player_rebs_asts': ['reb', 'ast'],
            'player_pts_rebs_asts': ['pts', 'reb', 'ast']
        }
            
        with self.engine.connect() as conn:
            # Get ungraded predictions
            preds = conn.execute(text("""
                SELECT id, player_name, market, pick, line, odds, units_bet
                FROM algo_prop_predictions
                WHERE game_date = :gd AND graded_at IS NULL
            """), {"gd": game_date}).fetchall()
            
            graded = 0
            for pred in preds:
                pred_id, player_name, market, pick, line, odds, units_bet = pred
                
                # Get stat column(s) for this market
                stat_cols = market_to_stat.get(market)
                if not stat_cols:
                    continue
                
                # Build query for actual stats
                if isinstance(stat_cols, list):
                    stat_select = " + ".join([f"COALESCE({col}, 0)" for col in stat_cols])
                else:
                    stat_select = f"COALESCE({stat_cols}, 0)"
                
                # Get actual value from boxscore
                result = conn.execute(text(f"""
                    SELECT {stat_select} as actual
                    FROM player_boxscores
                    WHERE game_date = :gd 
                    AND player_name ILIKE :pn
                    LIMIT 1
                """), {"gd": game_date, "pn": f"%{player_name}%"}).fetchone()
                
                if not result:
                    continue
                
                actual = float(result[0])
                
                # Determine if hit
                if pick == 'OVER':
                    hit = actual > line
                else:
                    hit = actual < line
                
                # Calculate units result
                if hit:
                    if odds > 0:
                        units_result = units_bet * (odds / 100)
                    else:
                        units_result = units_bet * (100 / abs(odds))
                else:
                    units_result = -units_bet
                
                # Update prediction
                conn.execute(text("""
                    UPDATE algo_prop_predictions 
                    SET actual_value = :actual, hit = :hit, 
                        units_result = :units_result, graded_at = NOW()
                    WHERE id = :id
                """), {"actual": actual, "hit": hit, "units_result": units_result, "id": pred_id})
                
                graded += 1
            
            conn.commit()
            return graded
    
    def get_performance_stats(self, days=30):
        """Get prop betting performance statistics"""
        if not self.engine:
            return {}
            
        with self.engine.connect() as conn:
            # Overall stats
            overall = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_bet) as total_units_bet,
                    SUM(units_result) as total_units_result,
                    AVG(edge) as avg_edge,
                    AVG(confidence) as avg_confidence
                FROM algo_prop_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
            """), {"days": f"{days} days"}).fetchone()
            
            # By market
            by_market = conn.execute(text("""
                SELECT 
                    market,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_result) as units_profit,
                    AVG(edge) as avg_edge
                FROM algo_prop_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                GROUP BY market
                ORDER BY SUM(units_result) DESC
            """), {"days": f"{days} days"}).fetchall()
            
            # By edge threshold
            by_edge = conn.execute(text("""
                SELECT 
                    CASE 
                        WHEN edge >= 15 THEN '15%+'
                        WHEN edge >= 10 THEN '10-15%'
                        WHEN edge >= 5 THEN '5-10%'
                        ELSE '<5%'
                    END as edge_tier,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_result) as units_profit
                FROM algo_prop_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                GROUP BY edge_tier
                ORDER BY MIN(edge) DESC
            """), {"days": f"{days} days"}).fetchall()
            
            # By confidence threshold
            by_confidence = conn.execute(text("""
                SELECT 
                    CASE 
                        WHEN confidence >= 80 THEN 'A (80%+)'
                        WHEN confidence >= 70 THEN 'B (70-80%)'
                        WHEN confidence >= 60 THEN 'C (60-70%)'
                        ELSE 'D (<60%)'
                    END as conf_tier,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_result) as units_profit
                FROM algo_prop_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                GROUP BY conf_tier
                ORDER BY MIN(confidence) DESC
            """), {"days": f"{days} days"}).fetchall()
            
            total = overall[0] or 0
            wins = overall[1] or 0
            
            return {
                'overall': {
                    'total': total,
                    'wins': wins,
                    'losses': total - wins,
                    'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
                    'units_bet': round(overall[2] or 0, 2),
                    'units_profit': round(overall[3] or 0, 2),
                    'roi': round((overall[3] or 0) / (overall[2] or 1) * 100, 1),
                    'avg_edge': round(overall[4] or 0, 1),
                    'avg_confidence': round(overall[5] or 0, 1)
                },
                'by_market': [
                    {
                        'market': row[0],
                        'total': row[1],
                        'wins': row[2],
                        'win_rate': round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
                        'units_profit': round(row[3] or 0, 2),
                        'avg_edge': round(row[4] or 0, 1)
                    } for row in by_market
                ],
                'by_edge': [
                    {
                        'tier': row[0],
                        'total': row[1],
                        'wins': row[2],
                        'win_rate': round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
                        'units_profit': round(row[3] or 0, 2)
                    } for row in by_edge
                ],
                'by_confidence': [
                    {
                        'tier': row[0],
                        'total': row[1],
                        'wins': row[2],
                        'win_rate': round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
                        'units_profit': round(row[3] or 0, 2)
                    } for row in by_confidence
                ]
            }
    
    def get_player_performance(self, days=30, min_picks=3):
        """See which players the algo does best/worst on"""
        if not self.engine:
            return {}
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    player_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_result) as units_profit,
                    AVG(edge) as avg_edge
                FROM algo_prop_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                GROUP BY player_name
                HAVING COUNT(*) >= :min
                ORDER BY SUM(units_result) DESC
            """), {"days": f"{days} days", "min": min_picks}).fetchall()
            
            return {
                'best': [
                    {
                        'player': row[0],
                        'total': row[1],
                        'wins': row[2],
                        'win_rate': round(row[2] / row[1] * 100, 1),
                        'units_profit': round(row[3] or 0, 2)
                    } for row in result[:10]
                ],
                'worst': [
                    {
                        'player': row[0],
                        'total': row[1],
                        'wins': row[2],
                        'win_rate': round(row[2] / row[1] * 100, 1),
                        'units_profit': round(row[3] or 0, 2)
                    } for row in result[-10:][::-1]
                ]
            }
    
    def get_insights(self):
        """Generate actionable insights from historical performance"""
        stats = self.get_performance_stats(days=60)
        insights = []
        
        if not stats.get('overall') or stats['overall']['total'] < 20:
            return ["📊 Need more data (20+ graded picks) to generate insights"]
        
        overall = stats['overall']
        
        # Overall performance
        if overall['win_rate'] >= 55:
            insights.append(f"🔥 PROFITABLE: {overall['win_rate']}% win rate, +{overall['units_profit']}u profit")
        elif overall['win_rate'] >= 52:
            insights.append(f"📈 BREAK-EVEN+: {overall['win_rate']}% win rate, {overall['units_profit']:+.1f}u")
        else:
            insights.append(f"⚠️ LOSING: {overall['win_rate']}% win rate, {overall['units_profit']:.1f}u loss")
        
        # Best markets
        for mkt in stats.get('by_market', [])[:2]:
            if mkt['win_rate'] >= 55 and mkt['total'] >= 10:
                insights.append(f"✅ Best market: {mkt['market']} ({mkt['win_rate']}% on {mkt['total']} picks)")
        
        # Worst markets
        for mkt in stats.get('by_market', [])[-2:]:
            if mkt['win_rate'] < 48 and mkt['total'] >= 10:
                insights.append(f"❌ Avoid: {mkt['market']} ({mkt['win_rate']}% on {mkt['total']} picks)")
        
        # Edge analysis
        for tier in stats.get('by_edge', []):
            if tier['tier'] == '15%+' and tier['total'] >= 5:
                insights.append(f"💎 High edge (15%+): {tier['win_rate']}% hit rate - PRIORITIZE THESE")
            if tier['tier'] == '<5%' and tier['total'] >= 10 and tier['win_rate'] < 50:
                insights.append(f"🚫 Low edge (<5%): Only {tier['win_rate']}% - SKIP THESE")
        
        # Confidence analysis
        for tier in stats.get('by_confidence', []):
            if 'A' in tier['tier'] and tier['total'] >= 5 and tier['win_rate'] >= 58:
                insights.append(f"⭐ A-rated picks crushing it: {tier['win_rate']}%")
        
        return insights
    
    def get_recommended_filters(self):
        """Based on performance, recommend minimum thresholds"""
        stats = self.get_performance_stats(days=60)
        
        recommendations = {
            'min_edge': 5.0,
            'min_confidence': 60,
            'preferred_markets': [],
            'avoid_markets': []
        }
        
        # Find optimal edge threshold
        for tier in stats.get('by_edge', []):
            if tier['win_rate'] >= 55 and tier['total'] >= 10:
                if '15%+' in tier['tier']:
                    recommendations['min_edge'] = 15.0
                elif '10-15%' in tier['tier']:
                    recommendations['min_edge'] = 10.0
                break
        
        # Find best/worst markets
        for mkt in stats.get('by_market', []):
            if mkt['win_rate'] >= 55 and mkt['total'] >= 10:
                recommendations['preferred_markets'].append(mkt['market'])
            elif mkt['win_rate'] < 48 and mkt['total'] >= 10:
                recommendations['avoid_markets'].append(mkt['market'])
        
        return recommendations
