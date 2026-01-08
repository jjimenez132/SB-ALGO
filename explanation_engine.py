#!/usr/bin/env python3
"""
SB-ALGO Explanation Engine v4.0
===============================
Generates institutional-grade bet explanations using REAL model data.
NO INVENTING STATS - only uses what the math engine calculated.
"""

import os
import google.generativeai as genai

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', 'AIzaSyBm1hzqUFKI_vzFQPSibVoeeEirD1LYNT4')
genai.configure(api_key=GOOGLE_API_KEY)

SYSTEM_PROMPT = """You are SB-ALGO's Explanation Engine — an institutional-grade NBA betting analyst.
You write like a Goldman Sachs quant defending a position to an investment committee.

CRITICAL RULES:
1. ONLY use the exact numbers provided in the prompt
2. DO NOT invent any statistics, rankings, or percentages
3. Every number you cite MUST come from the data provided
4. Be specific, quantitative, and structural
5. No hype, no fluff, no "trust me bro"

TONE: Clinical, confident, precise. Like explaining to an investment committee."""


def generate_game_explanation(pick_data: dict) -> str:
    """Generate institutional explanation using REAL model data"""
    try:
        model = genai.GenerativeModel(
            'gemini-2.0-flash',
            system_instruction=SYSTEM_PROMPT
        )
        
        game_id = pick_data.get('game_id', pick_data.get('matchup', 'Unknown'))
        pick = pick_data.get('pick', '')
        edge = pick_data.get('edge', 0)
        if isinstance(edge, str):
            edge = float(edge.replace('+', '').replace('%', ''))
        
        confidence = pick_data.get('confidence', 0)
        if isinstance(confidence, str):
            confidence = float(confidence.replace('%', ''))
        
        # REAL MODEL DATA
        model_total = pick_data.get('model_total')
        model_home_pts = pick_data.get('model_home_pts')
        model_away_pts = pick_data.get('model_away_pts')
        model_pace = pick_data.get('model_pace')
        model_margin = pick_data.get('model_margin')
        regime_status = pick_data.get('regime_status', 'NORMAL')
        regime_confidence = pick_data.get('regime_confidence', 0)
        injury_adjustment = pick_data.get('injury_adjustment', 0)
        injury_edge = pick_data.get('injury_edge', 'NEUTRAL')
        
        import re
        line_match = re.search(r'[\d.]+', str(pick))
        line_value = float(line_match.group()) if line_match else 0
        
        direction = 'UNDER' if 'UNDER' in str(pick).upper() else 'OVER'
        
        # Calculate cushion
        cushion = abs(line_value - model_total) if model_total else edge / 3
        
        # Parse teams
        teams = game_id.replace(' ', '').split('@')
        away_team = teams[0] if len(teams) == 2 else 'Away'
        home_team = teams[1] if len(teams) == 2 else 'Home'

        prompt = f"""Write an institutional-grade explanation for this NBA totals bet using ONLY the model data below.

=== BET ===
{game_id}: {direction} {line_value}

=== REAL MODEL PREDICTIONS (USE THESE EXACT NUMBERS) ===
Model Projected Total: {model_total} points
Book Line: {line_value} points
Cushion: {cushion:.1f} points {direction.lower()}

Team Projections:
- {home_team}: {model_home_pts} points
- {away_team}: {model_away_pts} points
- Projected Pace: {model_pace}
- Projected Margin: {model_margin:+.1f} ({away_team} {'wins' if model_margin < 0 else 'loses'} by {abs(model_margin):.1f})

Model Assessment:
- Edge: {edge:.1f}%
- Confidence: {confidence:.1f}%
- Regime: {regime_status} ({regime_confidence}% regime confidence)
- Injury Impact: {injury_adjustment} point adjustment ({injury_edge})

=== YOUR TASK ===
Write 5-6 bullets explaining why {direction} {line_value} has edge. 

REQUIRED STRUCTURE:
1. Lead with projection vs line gap: Model projects {model_total} total, {cushion:.1f} points {direction.lower()} the {line_value} line
2. Break down team totals: {home_team} ({model_home_pts}) + {away_team} ({model_away_pts}) = {model_total}
3. Note projected pace of {model_pace} and what it means
4. Reference regime status ({regime_status}) and {confidence:.1f}% confidence
5. Risk acknowledgment

CRITICAL: Use ONLY the numbers above. Do not invent pace rankings, historical rates, or any other stats."""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=500,
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
        
        return '\n'.join(lines[:6]) if lines else f"• Model projects {model_total} total, {cushion:.1f} pts {direction.lower()} the {line_value} line"
        
    except Exception as e:
        print(f"   ⚠️ Game explanation error: {e}")
        return f"• Model projects {cushion:.1f} point cushion on {direction}"


def generate_prop_explanation(pick_data: dict) -> str:
    """Generate institutional explanation for player prop using REAL data"""
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
        
        # Trend analysis
        if proj_l5 < proj_l10 < proj_l15:
            trend = "declining"
            trend_str = f"L5 ({proj_l5}) < L10 ({proj_l10}) < L15 ({proj_l15})"
        elif proj_l5 > proj_l10 > proj_l15:
            trend = "rising" 
            trend_str = f"L5 ({proj_l5}) > L10 ({proj_l10}) > L15 ({proj_l15})"
        else:
            trend = "stable"
            trend_str = f"L5 ({proj_l5}), L10 ({proj_l10}), L15 ({proj_l15})"

        prompt = f"""Write an institutional explanation for this NBA player prop using ONLY the data below.

=== PROP ===
{player}: {stat} {side} {line}
Matchup: {matchup}

=== REAL MODEL DATA (USE THESE EXACT NUMBERS) ===
Weighted Projection: {proj_weighted}
Book Line: {line}
Cushion: {cushion:.1f} {stat.lower()} {'below' if side == 'UNDER' else 'above'} line

Recent Performance Trend ({trend}):
{trend_str}

Filters:
- Games Played: {games_played}
- Minutes Per Game: {mpg}
- Hit Rate: {hit_rate*100:.0f}% ({hits} qualifying games)

Model Assessment:
- Edge: {edge:.1f}%
- Adjusted Probability: {adj_prob*100:.1f}%

=== YOUR TASK ===
Write 5-6 bullets explaining why {player} {stat} {side} {line} has edge.

REQUIRED STRUCTURE:
1. Cushion: Projection of {proj_weighted} is {cushion:.1f} {stat.lower()} {'below' if side == 'UNDER' else 'above'} the {line} line
2. Trend: {trend_str}
3. Hit rate: {hit_rate*100:.0f}% across {hits} games
4. Minutes: {mpg} MPG provides role stability
5. Probability: {adj_prob*100:.1f}% adjusted probability
6. Risk factor

CRITICAL: Use ONLY the numbers above. Do not invent any statistics."""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=500,
                temperature=0.2
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
    print("🧠 Testing Explanation Engine v4.0 with REAL MODEL DATA...\n")
    
    try:
        from sb_algo_api import SBAlgoAPI
        api = SBAlgoAPI()
        picks = api.get_all_picks()
        
        if picks.get('game_picks'):
            print("=" * 60)
            print("GAME PICK EXPLANATION (REAL MODEL DATA)")
            print("=" * 60)
            game = picks['game_picks'][0]
            print(f"BET: {game.get('game_id')} {game.get('pick')}")
            print(f"MODEL TOTAL: {game.get('model_total')} | LINE: {game.get('pick')}")
            print(f"CUSHION: {abs(240.5 - game.get('model_total', 0)):.1f} pts")
            print(f"PACE: {game.get('model_pace')} | REGIME: {game.get('regime_status')}\n")
            explanation = generate_game_explanation(game)
            print(explanation)
        
        print("\n")
        
        if picks.get('prop_picks'):
            print("=" * 60)
            print("PROP PICK EXPLANATION (REAL MODEL DATA)")
            print("=" * 60)
            prop = picks['prop_picks'][0]
            proj = prop.get('projection', {})
            filters = prop.get('filters', {})
            hr = filters.get('hit_rate', {})
            print(f"BET: {prop.get('player')} {prop.get('stat').upper()} {prop.get('best_side')} {prop.get('book_line')}")
            print(f"PROJECTION: {proj.get('weighted')} | LINE: {prop.get('book_line')}")
            print(f"TREND: L5={proj.get('l5')} | L10={proj.get('l10')} | L15={proj.get('l15')}")
            print(f"HIT RATE: {hr.get('hit_rate', 0)*100:.0f}% ({hr.get('hits')} games) | MPG: {filters.get('mpg')}\n")
            explanation = generate_prop_explanation(prop)
            print(explanation)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
