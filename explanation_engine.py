#!/usr/bin/env python3
"""
SB-ALGO Explanation Engine v5.0
===============================
Generates institutional-grade bet explanations using REAL model data.
NOW WITH: Scoring breakdown, defense matchup analysis, play-type data.
"""

import os
import google.generativeai as genai
from sqlalchemy import create_engine, text

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

SYSTEM_PROMPT = """You are SB-ALGO's Explanation Engine — an institutional-grade NBA betting analyst.
You write like a professional sports analytics firm defending a position.

CRITICAL RULES:
1. ONLY use the exact numbers provided in the prompt
2. DO NOT invent any statistics, rankings, or percentages
3. Every number you cite MUST come from the data provided
4. Be specific, quantitative, and structural
5. Focus on MATCHUP ADVANTAGES - how the player's tendencies exploit the opponent's weaknesses
6. No hype, no fluff, no "trust me bro"

STYLE: Write like @propsedge on Twitter - direct, data-heavy, matchup-focused."""


def get_player_scoring_breakdown(player_name: str) -> dict:
    """Get player's scoring distribution from nba_player_scoring"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text('''
                SELECT "PCT_PTS_2PT", "PCT_PTS_3PT", "PCT_PTS_FB", "PCT_PTS_PAINT", 
                       "PCT_PTS_FT", "PCT_PTS_2PT_MR", "PCT_AST_FGM", "PCT_UAST_FGM"
                FROM nba_player_scoring 
                WHERE "PLAYER_NAME" = :player
                ORDER BY pull_date DESC LIMIT 1
            '''), {"player": player_name}).fetchone()
            
            if result:
                return {
                    'pct_2pt': round(float(result[0] or 0) * 100, 1),
                    'pct_3pt': round(float(result[1] or 0) * 100, 1),
                    'pct_fastbreak': round(float(result[2] or 0) * 100, 1),
                    'pct_paint': round(float(result[3] or 0) * 100, 1),
                    'pct_ft': round(float(result[4] or 0) * 100, 1),
                    'pct_midrange': round(float(result[5] or 0) * 100, 1),
                    'pct_assisted': round(float(result[6] or 0) * 100, 1),
                    'pct_unassisted': round(float(result[7] or 0) * 100, 1),
                }
    except Exception as e:
        print(f"   ⚠️ Scoring breakdown error: {e}")
    return {}


def get_team_defense_stats(team_abbr: str) -> dict:
    """Get team defensive stats"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Get team opponent stats (how teams score AGAINST them)
            result = conn.execute(text('''
                SELECT "OPP_PTS", "OPP_FG_PCT", "OPP_FG3_PCT"
                FROM nba_team_opponent_stats 
                WHERE "TEAM_NAME" LIKE :team
                ORDER BY pull_date DESC LIMIT 1
            '''), {"team": f"%{team_abbr}%"}).fetchone()
            
            # Get advanced defensive rating
            adv = conn.execute(text('''
                SELECT "DEF_RATING", "NET_RATING"
                FROM nba_team_advanced_stats 
                WHERE "TEAM_NAME" LIKE :team
                ORDER BY pull_date DESC LIMIT 1
            '''), {"team": f"%{team_abbr}%"}).fetchone()
            
            # Get defensive ranking
            rankings = conn.execute(text('''
                SELECT "TEAM_NAME", "DEF_RATING",
                       RANK() OVER (ORDER BY "DEF_RATING" ASC) as def_rank
                FROM nba_team_advanced_stats
                WHERE pull_date = (SELECT MAX(pull_date) FROM nba_team_advanced_stats)
            ''')).fetchall()
            
            def_rank = 15
            for r in rankings:
                if team_abbr.upper() in str(r[0]).upper():
                    def_rank = r[2]
                    break
            
            return {
                'opp_pts': float(result[0]) if result and result[0] else 0,
                'opp_fg_pct': float(result[1]) if result and result[1] else 0,
                'opp_fg3_pct': float(result[2]) if result and result[2] else 0,
                'def_rating': float(adv[0]) if adv and adv[0] else 110,
                'pace': float(adv[1]) if adv and adv[1] else 100,
                'def_rank': int(def_rank)
            }
    except Exception as e:
        print(f"   ⚠️ Defense stats error: {e}")
    return {'def_rating': 110, 'pace': 100, 'def_rank': 15}


def get_player_advanced_stats(player_name: str) -> dict:
    """Get player usage, efficiency stats"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text('''
                SELECT "USG_PCT", "TS_PCT", "AST_PCT", "REB_PCT"
                FROM nba_player_advanced_stats 
                WHERE "PLAYER_NAME" = :player
                ORDER BY pull_date DESC LIMIT 1
            '''), {"player": player_name}).fetchone()
            
            if result:
                return {
                    'usg_pct': round(float(result[0] or 0) * 100, 1),
                    'ts_pct': round(float(result[1] or 0) * 100, 1),
                    'ast_pct': round(float(result[2] or 0) * 100, 1),
                    'reb_pct': round(float(result[3] or 0) * 100, 1),
                }
    except Exception as e:
        print(f"   ⚠️ Advanced stats error: {e}")
    return {}


def extract_opponent_from_matchup(matchup: str, player_team: str = None) -> str:
    """Extract opponent team abbreviation from matchup string"""
    # Format: "Atlanta Hawks @ Los Angeles Lakers" or "ATL @ LAL"
    try:
        team_map = {
            'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
            'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
            'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
            'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
            'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
            'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
            'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
            'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
            'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
        }
        
        if '@' in matchup:
            parts = matchup.split('@')
            away = parts[0].strip()
            home = parts[1].strip()
            
            away_abbr = team_map.get(away, away[:3].upper())
            home_abbr = team_map.get(home, home[:3].upper())
            
            # Return the opponent (not the player's team)
            # For now just return home team as opponent (most common case for props)
            return home_abbr
    except:
        pass
    return 'UNK'


def generate_game_explanation(pick_data: dict) -> str:
    """Generate institutional explanation by fetching team stats from DB"""
    try:
        model = genai.GenerativeModel(
            'gemini-2.0-flash',
            system_instruction=SYSTEM_PROMPT
        )
        
        # Extract basic data we have
        matchup = pick_data.get('matchup', pick_data.get('game_id', 'Unknown'))
        pick = pick_data.get('pick', '')
        subtype = pick_data.get('subtype', pick_data.get('type', 'ML'))
        edge = pick_data.get('edge', 0)
        if isinstance(edge, str):
            edge = float(edge.replace('+', '').replace('%', ''))
        odds = pick_data.get('odds', -110)
        
        # Parse teams from matchup (e.g., "BOS @ BKN")
        import re
        
        # Try to parse from matchup first
        if '@' in matchup:
            teams = matchup.replace(' ', '').split('@')
            away_team = teams[0] if len(teams) >= 1 else 'Away'
            home_team = teams[1] if len(teams) >= 2 else 'Home'
        else:
            # Fallback: try to extract teams from pick string
            # Pick format examples: "BOS ML", "UNDER 228.5", "UTA +10.5"
            pick_parts = pick.upper().split()
            team_abbrs = {'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 
                         'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN',
                         'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS',
                         'TOR', 'UTA', 'WAS'}
            found_teams = [p for p in pick_parts if p in team_abbrs]
            if found_teams:
                away_team = found_teams[0]
                home_team = found_teams[0]  # Use same if only one found
            else:
                away_team = 'Away'
                home_team = 'Home'
        
        # FETCH REAL TEAM STATS FROM DATABASE
        home_stats = get_team_advanced_stats(home_team)
        away_stats = get_team_advanced_stats(away_team)
        home_def = get_team_defense_stats(home_team)
        away_def = get_team_defense_stats(away_team)
        
        # Build context based on bet type
        if subtype == 'ML':
            # Moneyline bet
            # Determine which team we're betting on
            if home_team in pick:
                bet_team = home_team
                bet_stats = home_stats
                opp_team = away_team
                opp_stats = away_stats
                opp_def = away_def
            else:
                bet_team = away_team
                bet_stats = away_stats
                opp_team = home_team
                opp_stats = home_stats
                opp_def = home_def
            
            prompt = f"""Write 4-5 bullet points explaining this NBA moneyline bet.

=== BET ===
{matchup}: {pick} (odds: {odds})
Net Rating Edge: {edge:.1f} points

=== TEAM STATS (from database) ===
{bet_team}:
- Net Rating: {bet_stats.get('net_rating', 'N/A')}
- Offensive Rating: {bet_stats.get('off_rating', 'N/A')}
- Defensive Rating: {bet_stats.get('def_rating', 'N/A')}
- Pace: {bet_stats.get('pace', 'N/A')}

{opp_team}:
- Net Rating: {opp_stats.get('net_rating', 'N/A')}
- Offensive Rating: {opp_stats.get('off_rating', 'N/A')}
- Defensive Rating: {opp_stats.get('def_rating', 'N/A')}
- Opp 3PT%: {opp_def.get('opp_3pt_pct', 'N/A')}

=== YOUR TASK ===
Explain why {bet_team} ML has edge. Focus on:
1. Net rating differential ({edge:.1f} pts)
2. Offensive vs defensive matchup
3. Why opponent's defense is exploitable
4. Brief risk factor

Be direct, data-focused, no fluff."""

        elif subtype == 'UNDER':
            # Under bet
            line_match = re.search(r'[\d.]+', pick)
            line = float(line_match.group()) if line_match else 0
            
            prompt = f"""Write 4-5 bullet points explaining this NBA UNDER bet.

=== BET ===
{matchup}: UNDER {line}
Edge: {edge:.1f} points

=== TEAM STATS (from database) ===
{home_team}:
- Defensive Rating: {home_stats.get('def_rating', 'N/A')}
- Pace: {home_stats.get('pace', 'N/A')}

{away_team}:
- Defensive Rating: {away_stats.get('def_rating', 'N/A')}
- Pace: {away_stats.get('pace', 'N/A')}

Combined Pace: {(home_stats.get('pace', 100) + away_stats.get('pace', 100)) / 2:.1f}
Combined Def Rating: {(home_stats.get('def_rating', 110) + away_stats.get('def_rating', 110)):.1f}

=== YOUR TASK ===
Explain why UNDER {line} has edge. Focus on:
1. Combined defensive strength
2. Pace factors limiting possessions
3. Book line vs expected scoring
4. Brief risk factor

Be direct, data-focused, no fluff."""

        elif subtype == 'SPREAD':
            # Spread dog bet
            line_match = re.search(r'[\d.]+', pick)
            spread = float(line_match.group()) if line_match else 0
            
            # Determine underdog
            if '+' in pick:
                dog_team = home_team if home_team in pick else away_team
                fav_team = away_team if dog_team == home_team else home_team
                dog_stats = home_stats if dog_team == home_team else away_stats
                fav_stats = away_stats if dog_team == home_team else home_stats
            else:
                dog_team = away_team
                fav_team = home_team
                dog_stats = away_stats
                fav_stats = home_stats
            
            prompt = f"""Write 4-5 bullet points explaining this NBA spread bet.

=== BET ===
{matchup}: {pick}
Edge: {edge:.1f} points

=== TEAM STATS (from database) ===
{dog_team} (underdog):
- Net Rating: {dog_stats.get('net_rating', 'N/A')}
- Offensive Rating: {dog_stats.get('off_rating', 'N/A')}

{fav_team} (favorite):
- Net Rating: {fav_stats.get('net_rating', 'N/A')}
- Defensive Rating: {fav_stats.get('def_rating', 'N/A')}

=== YOUR TASK ===
Explain why {dog_team} +{spread} has edge. Focus on:
1. Spread too large vs actual net rating gap
2. Underdog's offensive capability
3. Favorite's limitations
4. Brief risk factor

Be direct, data-focused, no fluff."""

        else:
            # Generic fallback
            prompt = f"""Write 3-4 bullet points explaining this bet: {matchup} {pick} with {edge:.1f}% edge."""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=400,
                temperature=0.2
            )
        )
        
        explanation = response.text.strip()
        lines = []
        for line in explanation.split('\n'):
            line = line.strip()
            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                clean_line = '• ' + line.lstrip('•-* ').strip()
                if len(clean_line) > 15:
                    lines.append(clean_line)
        
        return '\n'.join(lines[:5]) if lines else f"• Net rating edge: +{edge:.1f} points"
        
    except Exception as e:
        print(f"   ⚠️ Game explanation error: {e}")
        return f"• Net rating edge: +{edge:.1f} points"


def get_team_advanced_stats(team_abbr: str) -> dict:
    """Get team advanced stats from nba_team_advanced_stats"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Map abbreviation to full name
            team_map = {
                'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
                'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
                'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
                'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
                'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
                'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
                'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
                'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
                'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
                'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
            }
            team_name = team_map.get(team_abbr, team_abbr)
            
            result = conn.execute(text('''
                SELECT "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE"
                FROM nba_team_advanced_stats 
                WHERE "TEAM_NAME" = :team
                ORDER BY pull_date DESC LIMIT 1
            '''), {"team": team_name}).fetchone()
            
            if result:
                return {
                    'off_rating': round(float(result[0] or 0), 1),
                    'def_rating': round(float(result[1] or 0), 1),
                    'net_rating': round(float(result[2] or 0), 1),
                    'pace': round(float(result[3] or 0), 1),
                }
    except Exception as e:
        print(f"   ⚠️ Team stats error: {e}")
    return {'off_rating': 110, 'def_rating': 110, 'net_rating': 0, 'pace': 100}

def generate_prop_explanation(pick_data: dict) -> str:
    """Generate institutional explanation for player prop using REAL data + advanced stats"""
    try:
        model = genai.GenerativeModel(
            'gemini-2.0-flash',
            system_instruction=SYSTEM_PROMPT
        )
        
        player = pick_data.get('player', 'Unknown')
        stat = pick_data.get('stat', 'pts').upper()
        line = pick_data.get('book_line', pick_data.get('line', 0))
        matchup = pick_data.get('matchup', '')
        projection = pick_data.get('projection', {})
        side = pick_data.get('best_side', 'OVER')
        edge = pick_data.get('edge_pct', pick_data.get('edge', 0))
        if isinstance(edge, str):
            edge = float(edge.replace('+', '').replace('%', ''))
        filters = pick_data.get('filters', {})
        probs = pick_data.get('probabilities', {})
        
        # Extract projections
        proj_l5 = projection.get('l5', 0) if isinstance(projection, dict) else 0
        proj_l10 = projection.get('l10', 0) if isinstance(projection, dict) else 0
        proj_l15 = projection.get('l15', 0) if isinstance(projection, dict) else 0
        proj_weighted = projection.get('weighted', 0) if isinstance(projection, dict) else 0
        
        # Extract filters
        games_played = filters.get('gp', 0)
        mpg = filters.get('mpg', 0)
        hit_rate_data = filters.get('hit_rate', {})
        hit_rate = hit_rate_data.get('hit_rate', 0) if isinstance(hit_rate_data, dict) else 0
        hits = hit_rate_data.get('hits', 0) if isinstance(hit_rate_data, dict) else 0
        
        adj_prob = probs.get('adjusted', 0) if isinstance(probs, dict) else 0
        cushion = abs(proj_weighted - line)
        
        # GET ADVANCED DATA
        scoring = get_player_scoring_breakdown(player)
        advanced = get_player_advanced_stats(player)
        opponent = extract_opponent_from_matchup(matchup)
        opp_defense = get_team_defense_stats(opponent)
        
        # Trend analysis
        if proj_l5 < proj_l10 < proj_l15:
            trend = "declining"
            trend_direction = "downward"
        elif proj_l5 > proj_l10 > proj_l15:
            trend = "rising"
            trend_direction = "upward"
        else:
            trend = "stable"
            trend_direction = "stable"

        # Build scoring profile string
        scoring_profile = ""
        if scoring:
            if stat == 'PTS':
                scoring_profile = f"""
Scoring Distribution:
- Paint: {scoring.get('pct_paint', 0)}% of points
- 3PT: {scoring.get('pct_3pt', 0)}% of points  
- Mid-Range: {scoring.get('pct_midrange', 0)}% of points
- Free Throws: {scoring.get('pct_ft', 0)}% of points
- Fast Break: {scoring.get('pct_fastbreak', 0)}% of points
- Unassisted: {scoring.get('pct_unassisted', 0)}% (self-created)"""
            elif stat == 'REB':
                scoring_profile = f"""
Rebounding Profile:
- Rebound %: {advanced.get('reb_pct', 0)}%
- Usage: {advanced.get('usg_pct', 0)}%"""
            elif stat == 'AST':
                scoring_profile = f"""
Playmaking Profile:
- Assist %: {advanced.get('ast_pct', 0)}%
- Usage: {advanced.get('usg_pct', 0)}%"""

        # Build opponent defense string
        opp_profile = f"""
Opponent Defense ({opponent}):
- Defensive Rating: {opp_defense.get('def_rating', 'N/A')} (Rank #{opp_defense.get('def_rank', 'N/A')})
- Pace: {opp_defense.get('pace', 'N/A')}
- Points Allowed: {opp_defense.get('opp_pts', 'N/A')} PPG
- Opponent FG%: {opp_defense.get('opp_fg_pct', 'N/A')}%
- Opponent 3P%: {opp_defense.get('opp_fg3_pct', 'N/A')}%"""

        prompt = f"""Write an institutional explanation for this NBA player prop using ONLY the data below.
Write like @propsedge - direct matchup analysis with specific percentages.

=== PROP ===
{player}: {stat} {side} {line}
Matchup: {matchup}

=== PLAYER PROJECTION ===
Weighted Projection: {proj_weighted}
Book Line: {line}
Cushion: {cushion:.1f} {stat.lower()} {'below' if side == 'UNDER' else 'above'} line

Recent Trend ({trend}):
- Last 5: {proj_l5}
- Last 10: {proj_l10}
- Last 15: {proj_l15}
{scoring_profile}
{opp_profile}

=== FILTERS ===
- Games Played: {games_played}
- Minutes Per Game: {mpg}
- Hit Rate: {hit_rate*100:.0f}% ({hits} qualifying games)
- Edge: {edge:.1f}%
- Probability: {adj_prob*100:.1f}%

=== YOUR TASK ===
Write 5-6 bullets explaining why {player} {stat} {side} {line} has edge.

REQUIRED APPROACH (like @propsedge):
1. Start with how player scores/performs - cite specific percentages from scoring distribution
2. Explain how opponent's defense matches up - cite their defensive rating/rank
3. Reference the trend ({trend_direction}) and recent averages
4. Note the cushion ({cushion:.1f}) and hit rate ({hit_rate*100:.0f}%)
5. Probability assessment
6. Risk factor

EXAMPLE STYLE:
"Powell scores 70% of his points in the paint, where the Suns rank 8th BEST defensively..."

CRITICAL: Use ONLY the numbers provided. Make it read like professional matchup analysis."""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=600,
                temperature=0.3
            )
        )
        
        explanation = response.text.strip()
        lines = []
        for line_text in explanation.split('\n'):
            line_text = line_text.strip()
            if line_text.startswith('•') or line_text.startswith('-') or line_text.startswith('*'):
                clean_line = '• ' + line_text.lstrip('•-* ').strip()
                if len(clean_line) > 15:
                    lines.append(clean_line)
        
        return '\n'.join(lines[:6]) if lines else f"• Projection {proj_weighted} vs line {line}, {hit_rate*100:.0f}% hit rate"
        
    except Exception as e:
        print(f"   ⚠️ Prop explanation error: {e}")
        import traceback
        traceback.print_exc()
        return f"• {cushion:.1f} {stat} cushion, {hit_rate*100:.0f}% hit rate"


def generate_explanation(pick_data: dict, pick_type: str) -> str:
    """Main function"""
    if pick_type == 'game':
        return generate_game_explanation(pick_data)
    elif pick_type == 'prop':
        return generate_prop_explanation(pick_data)
    return "• Edge detected"


# Test
if __name__ == "__main__":
    import os
    if not os.environ.get('GOOGLE_API_KEY'):
        print("❌ Set GOOGLE_API_KEY environment variable first")
        print("   export GOOGLE_API_KEY='your-key-here'")
        exit(1)
    
    print("🧠 Testing Explanation Engine v5.0 with ADVANCED DATA...\n")
    
    # Test with sample prop
    test_prop = {
        'player': 'Marcus Smart',
        'stat': 'pts',
        'book_line': 12.5,
        'matchup': 'Atlanta Hawks @ Los Angeles Lakers',
        'projection': {'l5': 6.2, 'l10': 7.0, 'l15': 8.9, 'weighted': 7.0},
        'best_side': 'UNDER',
        'edge_pct': 44.1,
        'filters': {'gp': 20, 'mpg': 28.4, 'hit_rate': {'hit_rate': 0.67, 'hits': 10}},
        'probabilities': {'adjusted': 0.789}
    }
    
    print("=== TESTING PROP EXPLANATION ===")
    print(f"Player: {test_prop['player']}")
    print(f"Prop: {test_prop['stat'].upper()} {test_prop['best_side']} {test_prop['book_line']}")
    print(f"Matchup: {test_prop['matchup']}\n")
    
    explanation = generate_prop_explanation(test_prop)
    print(explanation)
