# ========================================
# ADD THESE FUNCTIONS AFTER get_dashboard_metrics() 
# (around line 40, before the page config)
# ========================================

def get_todays_games(engine):
    """Fetch today's games from database"""
    if not engine:
        return []
    
    try:
        with engine.connect() as conn:
            today = datetime.now().strftime('%Y-%m-%d')
            query = text("""
                SELECT 
                    date,
                    home_team,
                    visitor_team,
                    home_pts,
                    visitor_pts,
                    start_time,
                    home_win,
                    home_days_rest,
                    visitor_days_rest,
                    home_is_b2b,
                    visitor_is_b2b,
                    season_avg_total,
                    total_points,
                    margin_home
                FROM games 
                WHERE date = :today
                ORDER BY start_time
            """)
            result = conn.execute(query, {"today": today})
            columns = result.keys()
            games = [dict(zip(columns, row)) for row in result.fetchall()]
            return games
    except Exception as e:
        print(f"Error fetching today's games: {e}")
        return []

def get_hot_teams(engine, limit=5):
    """Get teams with best record in last 10 games"""
    if not engine:
        return pd.DataFrame()
    
    try:
        with engine.connect() as conn:
            query = text("""
                WITH recent_games AS (
                    SELECT 
                        home_team as team,
                        CASE WHEN home_win = true THEN 1 ELSE 0 END as win,
                        margin_home as margin,
                        date
                    FROM games 
                    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                    
                    UNION ALL
                    
                    SELECT 
                        visitor_team as team,
                        CASE WHEN home_win = false THEN 1 ELSE 0 END as win,
                        -margin_home as margin,
                        date
                    FROM games 
                    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                ),
                team_stats AS (
                    SELECT 
                        team,
                        COUNT(*) as games,
                        SUM(win) as wins,
                        ROUND(AVG(margin)::numeric, 1) as avg_margin
                    FROM recent_games
                    GROUP BY team
                    HAVING COUNT(*) >= 5
                )
                SELECT 
                    team as "Team",
                    wins || '-' || (games - wins) as "Record",
                    ROUND((wins::numeric / games) * 100) || '%' as "Win%",
                    CASE WHEN avg_margin > 0 THEN '+' || avg_margin ELSE avg_margin::text END as "Avg Margin"
                FROM team_stats
                ORDER BY (wins::numeric / games) DESC, avg_margin DESC
                LIMIT :limit
            """)
            df = pd.read_sql(query, conn, params={"limit": limit})
            return df
    except Exception as e:
        print(f"Error fetching hot teams: {e}")
        return pd.DataFrame()

def get_cold_teams(engine, limit=5):
    """Get teams with worst record in last 10 games"""
    if not engine:
        return pd.DataFrame()
    
    try:
        with engine.connect() as conn:
            query = text("""
                WITH recent_games AS (
                    SELECT 
                        home_team as team,
                        CASE WHEN home_win = true THEN 1 ELSE 0 END as win,
                        margin_home as margin,
                        date
                    FROM games 
                    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                    
                    UNION ALL
                    
                    SELECT 
                        visitor_team as team,
                        CASE WHEN home_win = false THEN 1 ELSE 0 END as win,
                        -margin_home as margin,
                        date
                    FROM games 
                    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                ),
                team_stats AS (
                    SELECT 
                        team,
                        COUNT(*) as games,
                        SUM(win) as wins,
                        ROUND(AVG(margin)::numeric, 1) as avg_margin
                    FROM recent_games
                    GROUP BY team
                    HAVING COUNT(*) >= 5
                )
                SELECT 
                    team as "Team",
                    wins || '-' || (games - wins) as "Record",
                    ROUND((wins::numeric / games) * 100) || '%' as "Win%",
                    CASE WHEN avg_margin > 0 THEN '+' || avg_margin ELSE avg_margin::text END as "Avg Margin"
                FROM team_stats
                ORDER BY (wins::numeric / games) ASC, avg_margin ASC
                LIMIT :limit
            """)
            df = pd.read_sql(query, conn, params={"limit": limit})
            return df
    except Exception as e:
        print(f"Error fetching cold teams: {e}")
        return pd.DataFrame()

def get_totals_trends(engine, limit=6):
    """Get teams sorted by average total points"""
    if not engine:
        return pd.DataFrame()
    
    try:
        with engine.connect() as conn:
            query = text("""
                WITH team_totals AS (
                    SELECT 
                        home_team as team,
                        total_points,
                        season_avg_total,
                        CASE WHEN total_points > season_avg_total THEN 1 ELSE 0 END as over_hit
                    FROM games 
                    WHERE date >= CURRENT_DATE - INTERVAL '60 days'
                    AND total_points IS NOT NULL
                    
                    UNION ALL
                    
                    SELECT 
                        visitor_team as team,
                        total_points,
                        season_avg_total,
                        CASE WHEN total_points > season_avg_total THEN 1 ELSE 0 END as over_hit
                    FROM games 
                    WHERE date >= CURRENT_DATE - INTERVAL '60 days'
                    AND total_points IS NOT NULL
                ),
                team_stats AS (
                    SELECT 
                        team,
                        ROUND(AVG(total_points)::numeric, 1) as avg_total,
                        ROUND((SUM(over_hit)::numeric / COUNT(*)) * 100) as over_pct,
                        COUNT(*) as games
                    FROM team_totals
                    GROUP BY team
                    HAVING COUNT(*) >= 5
                )
                SELECT 
                    team as "Team",
                    avg_total as "Avg Total",
                    over_pct || '%' as "Over %",
                    CASE 
                        WHEN over_pct >= 60 THEN '🔥 Over Team'
                        WHEN over_pct >= 50 THEN '📈 Trending Over'
                        WHEN over_pct <= 40 THEN '❄️ Under Team'
                        ELSE '➡️ Neutral'
                    END as "Trend"
                FROM team_stats
                ORDER BY avg_total DESC
                LIMIT :limit
            """)
            df = pd.read_sql(query, conn, params={"limit": limit})
            return df
    except Exception as e:
        print(f"Error fetching totals trends: {e}")
        return pd.DataFrame()

def get_recent_team_record(engine, team, days=30):
    """Get a specific team's recent record"""
    if not engine:
        return {"wins": 0, "losses": 0, "home_record": "0-0", "away_record": "0-0"}
    
    try:
        with engine.connect() as conn:
            query = text("""
                WITH team_games AS (
                    SELECT 
                        home_team as team,
                        'home' as location,
                        CASE WHEN home_win = true THEN 1 ELSE 0 END as win
                    FROM games 
                    WHERE home_team = :team AND date >= CURRENT_DATE - INTERVAL '30 days'
                    
                    UNION ALL
                    
                    SELECT 
                        visitor_team as team,
                        'away' as location,
                        CASE WHEN home_win = false THEN 1 ELSE 0 END as win
                    FROM games 
                    WHERE visitor_team = :team AND date >= CURRENT_DATE - INTERVAL '30 days'
                )
                SELECT 
                    SUM(win) as wins,
                    COUNT(*) - SUM(win) as losses,
                    SUM(CASE WHEN location = 'home' THEN win ELSE 0 END) as home_wins,
                    SUM(CASE WHEN location = 'home' THEN 1 ELSE 0 END) as home_games,
                    SUM(CASE WHEN location = 'away' THEN win ELSE 0 END) as away_wins,
                    SUM(CASE WHEN location = 'away' THEN 1 ELSE 0 END) as away_games
                FROM team_games
            """)
            result = conn.execute(query, {"team": team}).fetchone()
            if result:
                return {
                    "wins": result[0] or 0,
                    "losses": result[1] or 0,
                    "home_record": f"{result[2] or 0}-{(result[3] or 0) - (result[2] or 0)}",
                    "away_record": f"{result[4] or 0}-{(result[5] or 0) - (result[4] or 0)}"
                }
            return {"wins": 0, "losses": 0, "home_record": "0-0", "away_record": "0-0"}
    except Exception as e:
        print(f"Error fetching team record: {e}")
        return {"wins": 0, "losses": 0, "home_record": "0-0", "away_record": "0-0"}
