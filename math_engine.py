

# --- CODEX UPDATE: ON-DEMAND PLAYER PROJECTION ---
from scipy.stats import norm

class PlayerSimulator:
    def __init__(self, engine):
        self.engine = engine

    def run_projection(self, player_name, stat_type, line):
        """
        Runs a Monte Carlo simulation for a specific player/line on demand.
        """
        with self.engine.connect() as conn:
            # 1. Get recent stats (Last 20 games)
            query = text("""
                SELECT pts, reb, ast, fg3m, blk, stl
                FROM player_boxscores 
                WHERE player_name = :p 
                ORDER BY game_date DESC LIMIT 20
            """)
            data = conn.execute(query, {"p": player_name}).fetchall()
            
            if not data or len(data) < 5:
                return {"error": "Not enough data"}

            # 2. Extract the specific stat
            stat_map = {'points': 0, 'rebounds': 1, 'assists': 2, 'threes': 3, 'blocks': 4, 'steals': 5}
            idx = stat_map.get(stat_type.lower(), 0)
            values = [row[idx] for row in data if row[idx] is not None]
            
            if not values: return {"error": "No stats found"}

            # 3. Calculate metrics
            avg = sum(values) / len(values)
            std_dev = np.std(values)
            
            # 4. Monte Carlo (10,000 runs)
            simulations = np.random.normal(avg, std_dev, 10000)
            
            # 5. Analyze Results
            overs = np.sum(simulations > line)
            unders = np.sum(simulations < line)
            prob_over = (overs / 10000) * 100
            prob_under = (unders / 10000) * 100
            
            projection = avg
            
            # 6. Determine Edge
            if prob_over > 53:
                edge = prob_over - 50
                pick = "OVER"
                confidence = prob_over
            elif prob_under > 53:
                edge = prob_under - 50
                pick = "UNDER"
                confidence = prob_under
            else:
                edge = 0
                pick = "NEUTRAL"
                confidence = 50
                
            return {
                "player": player_name,
                "stat": stat_type,
                "line": line,
                "projected": round(projection, 1),
                "confidence": round(confidence, 1),
                "pick": pick,
                "edge": round(edge, 1)
            }
