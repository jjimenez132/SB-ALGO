#!/usr/bin/env python3
"""
SB-ALGO RECHECK ENGINE
======================
Analyzes a specific bet at CURRENT line to determine if it still has value.
Used for line movement checks and member alerts.
"""

import os
import re
import sys
import requests
from datetime import datetime

# Import SB-ALGO engines
from engines.meta_merge_engine_v4 import MetaMergeEngine
from engines.prop_analyzer_pro import PropAnalyzerPro

RECHECK_WEBHOOK = "https://discord.com/api/webhooks/1459382671225655408/q0uR3Oo8OVrIk5VUZtO6F_PAhYE8oxUWVIfusrATWhLD-T0jQIIC8DwKvG7elryawHSe"

DATABASE_URL = os.environ.get('DATABASE_URL', 
    'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db')


class RecheckEngine:
    def __init__(self):
        print("🔧 Initializing Recheck Engine...")
        self.meta_engine = MetaMergeEngine()
        self.prop_engine = PropAnalyzerPro()
        print("   ✅ Recheck Engine ready")
    
    def parse_request(self, message: str) -> dict:
        """Parse natural language request into structured query"""
        message = message.lower().strip()
        
        result = {
            'bet_type': None,
            'player': None,
            'stat': None,
            'side': None,
            'line': None,
            'odds': -110,  # Default
            'matchup': None,
            'original_line': None,
            'assumptions': [],
            'opponent': None
        }
        
        # Detect bet type
        if any(word in message for word in ['pts', 'points', 'reb', 'rebounds', 'ast', 'assists', 'pra', '3pt', 'threes', 'stl', 'blk']):
            result['bet_type'] = 'prop'
        elif any(word in message for word in ['under', 'over', 'total']):
            if '@' in message or 'vs' in message:
                result['bet_type'] = 'total'
            else:
                result['bet_type'] = 'prop'
        elif 'spread' in message or any(c in message for c in ['+', '-']) and '@' in message:
            result['bet_type'] = 'spread'
        elif 'ml' in message or 'moneyline' in message:
            result['bet_type'] = 'moneyline'
        
        # Extract line (number)
        line_match = re.search(r'(\d+\.?\d*)', message)
        if line_match:
            result['line'] = float(line_match.group(1))
        
        # Extract odds if present
        odds_match = re.search(r'([+-]\d{3})', message)
        if odds_match:
            result['odds'] = int(odds_match.group(1))
        else:
            result['assumptions'].append('Odds assumed -110')
        
        # Extract side (over/under)
        if 'over' in message:
            result['side'] = 'OVER'
        elif 'under' in message:
            result['side'] = 'UNDER'
        
        # Extract stat type
        stat_patterns = {
            'pts': ['pts', 'points', 'point'],
            'reb': ['reb', 'rebounds', 'rebound', 'boards'],
            'ast': ['ast', 'assists', 'assist', 'dimes'],
            'pra': ['pra', 'pts+reb+ast'],
            '3pt': ['3pt', 'threes', '3s', 'three'],
            'stl': ['stl', 'steals', 'steal'],
            'blk': ['blk', 'blocks', 'block']
        }
        
        for stat, patterns in stat_patterns.items():
            if any(p in message for p in patterns):
                result['stat'] = stat
                break
        
        # Extract opponent (vs XXX or against XXX)
        opponent_match = re.search(r'(?:vs|against)\s+([A-Za-z]{2,3})', message, re.IGNORECASE)
        if opponent_match:
            result['opponent'] = opponent_match.group(1).upper()
        
        # Extract player name (everything before stat keywords)
        if result['bet_type'] == 'prop':
            # Remove common words and extract player name
            cleaned = message
            for word in ['recheck', 'check', 'over', 'under', 'pts', 'points', 'reb', 'rebounds', 
                        'ast', 'assists', 'pra', '3pt', 'threes', 'stl', 'blk', 'still', 'good',
                        'value', 'at', 'the', 'line', 'is', 'odds', '-110', '-115', '-105', 'vs', 'against', 'lal', 'lac', 'gsw', 'bos', 'nyk', 'mia', 'chi', 'dal', 'hou', 'phx', 'den', 'min', 'mem', 'okc', 'cle', 'mil', 'phi', 'atl', 'tor', 'bkn', 'sas', 'por', 'sac', 'orl', 'ind', 'cha', 'det', 'was', 'nop', 'uta']:
                cleaned = re.sub(r'\b' + word + r'\b', ' ', cleaned)
            
            # Remove numbers and extra spaces
            cleaned = re.sub(r'\d+\.?\d*', '', cleaned)
            cleaned = re.sub(r'[+-]\d{3}', '', cleaned)
            cleaned = ' '.join(cleaned.split()).strip()
            
            if cleaned:
                result['player'] = cleaned.title()
        
        # Extract matchup for game bets
        matchup_match = re.search(r'([A-Z]{2,3})\s*@\s*([A-Z]{2,3})', message.upper())
        if matchup_match:
            result['matchup'] = f"{matchup_match.group(1)} @ {matchup_match.group(2)}"
        
        # Extract original line if mentioned
        orig_match = re.search(r'from\s+(\d+\.?\d*)', message)
        if orig_match:
            result['original_line'] = float(orig_match.group(1))
        
        return result
    
    def recheck_prop(self, player: str, stat: str, line: float, side: str, odds: int = -110, opponent: str = None) -> dict:
        """Recheck a player prop at current line"""
        print(f"\n🔍 Rechecking: {player} {stat.upper()} {side} {line} ({odds})")
        
        # Get projection from prop engine
        try:
            projection = self.prop_engine.analyze_prop_full(player, stat, line, opponent)
        except Exception as e:
            print(f"   ⚠️ Prop engine error: {e}")
            projection = None
        
        if not projection or projection.get('error'):
            return {
                'error': f"Could not analyze {player} {stat}",
                'verdict': '❌ NO DATA'
            }
        
        # Extract key metrics
        proj_value = projection.get('projection', {}).get('projection', 0)
        hit_rate = projection.get('filters', {}).get('hit_rate', {}).get('hit_rate', 0.5)
        games_played = projection.get('filters', {}).get('gp', {}).get('gp', 0)
        mpg = projection.get('filters', {}).get('mpg', {}).get('mpg', 0)
        
        # Calculate edge at THIS line
        if side == 'OVER':
            cushion = proj_value - line
            edge_direction = 'above'
        else:
            cushion = line - proj_value
            edge_direction = 'below'
        
        # Edge calculation
        edge_pct = (cushion / line) * 100 if line > 0 else 0
        
        # Win probability (simplified)
        if side == 'OVER':
            win_prob = hit_rate if hit_rate > 0 else 0.5 + (edge_pct / 200)
        else:
            win_prob = hit_rate if hit_rate > 0 else 0.5 + (edge_pct / 200)
        
        win_prob = max(0.1, min(0.95, win_prob))
        
        # EV calculation
        if odds < 0:
            decimal_odds = 1 + (100 / abs(odds))
        else:
            decimal_odds = 1 + (odds / 100)
        
        ev_pct = (win_prob * decimal_odds - 1) * 100
        
        # Calculate playable threshold (where EV = 0)
        if side == 'OVER':
            playable_up_to = proj_value - (proj_value * 0.02)  # 2% buffer
        else:
            playable_up_to = proj_value + (proj_value * 0.02)
        
        # Determine verdict
        risk_notes = []
        if games_played < 10:
            risk_notes.append("Small sample size")
        if mpg < 20:
            risk_notes.append("Limited minutes")
        
        # Verdict logic
        if edge_pct >= 3 or ev_pct >= 2:
            if risk_notes:
                verdict = '⚠️ THIN EDGE'
                stake = 0.5
            else:
                verdict = '✅ STILL VALUE'
                stake = 1.0
        elif edge_pct >= 1 and ev_pct >= 0:
            verdict = '⚠️ THIN EDGE'
            stake = 0.5
        else:
            verdict = '❌ NO VALUE'
            stake = 0
        
        return {
            'player': player,
            'stat': stat.upper(),
            'side': side,
            'line': line,
            'odds': odds,
            'projection': proj_value,
            'cushion': cushion,
            'edge_pct': edge_pct,
            'ev_pct': ev_pct,
            'win_prob': win_prob * 100,
            'hit_rate': hit_rate * 100,
            'games_played': games_played,
            'mpg': mpg,
            'risk_notes': risk_notes,
            'playable_up_to': round(playable_up_to, 1),
            'stake': stake,
            'verdict': verdict
        }
    
    def recheck_total(self, matchup: str, line: float, side: str, odds: int = -110) -> dict:
        """Recheck a game total at current line"""
        print(f"\n🔍 Rechecking: {matchup} {side} {line} ({odds})")
        
        # Parse teams
        teams = matchup.replace(' ', '').split('@')
        if len(teams) != 2:
            return {'error': 'Invalid matchup format', 'verdict': '❌ NO DATA'}
        
        away_team, home_team = teams[0], teams[1]
        
        # Get game analysis from meta engine
        try:
            game_result = self.meta_engine.predict_game(
                home_team=home_team,
                away_team=away_team,
                book_spread=0,
                book_total=line
            )
        except Exception as e:
            print(f"   ⚠️ Meta engine error: {e}")
            return {'error': str(e), 'verdict': '❌ NO DATA'}
        
        if not game_result or game_result.get('error'):
            return {'error': 'Could not analyze game', 'verdict': '❌ NO DATA'}
        
        # Extract predictions
        predictions = game_result.get('predictions', {})
        model_total = predictions.get('total', 0)
        model_pace = predictions.get('pace', 0)
        regime = game_result.get('regime', {})
        regime_status = regime.get('status', 'NORMAL')
        regime_confidence = regime.get('confidence', 0)
        
        # Calculate edge at THIS line
        if side == 'UNDER':
            cushion = line - model_total
        else:
            cushion = model_total - line
        
        edge_pct = (cushion / line) * 100 if line > 0 else 0
        
        # Win probability
        base_prob = 0.5 + (edge_pct / 100)
        win_prob = max(0.1, min(0.95, base_prob))
        
        # EV calculation
        if odds < 0:
            decimal_odds = 1 + (100 / abs(odds))
        else:
            decimal_odds = 1 + (odds / 100)
        
        ev_pct = (win_prob * decimal_odds - 1) * 100
        
        # Playable threshold
        if side == 'UNDER':
            playable_up_to = model_total + (model_total * 0.02)
        else:
            playable_up_to = model_total - (model_total * 0.02)
        
        # Risk notes
        risk_notes = []
        if regime_status == 'HIGH_VARIANCE':
            risk_notes.append("High variance regime")
        if regime_confidence < 80:
            risk_notes.append(f"Regime confidence {regime_confidence:.0f}%")
        
        # Verdict
        if edge_pct >= 2 or ev_pct >= 1.5:
            if risk_notes:
                verdict = '⚠️ THIN EDGE'
                stake = 0.5
            else:
                verdict = '✅ STILL VALUE'
                stake = 1.5
        elif edge_pct >= 1:
            verdict = '⚠️ THIN EDGE'
            stake = 0.5
        else:
            verdict = '❌ NO VALUE'
            stake = 0
        
        return {
            'matchup': matchup,
            'side': side,
            'line': line,
            'odds': odds,
            'model_total': model_total,
            'model_pace': model_pace,
            'cushion': cushion,
            'edge_pct': edge_pct,
            'ev_pct': ev_pct,
            'win_prob': win_prob * 100,
            'regime_status': regime_status,
            'regime_confidence': regime_confidence,
            'risk_notes': risk_notes,
            'playable_up_to': round(playable_up_to, 1),
            'stake': stake,
            'verdict': verdict
        }
    
    def recheck(self, message: str) -> str:
        """Main recheck function - parses message and runs analysis"""
        parsed = self.parse_request(message)
        
        if not parsed['line']:
            return "❌ Could not extract line from request. Please include the line number."
        
        timestamp = datetime.now().strftime("%I:%M %p ET")
        
        # Route to appropriate analyzer
        if parsed['bet_type'] == 'prop':
            if not parsed['player']:
                return "❌ Could not extract player name. Example: 'recheck Herro over 20.5 pts'"
            if not parsed['stat']:
                return "❌ Could not extract stat type. Use: pts, reb, ast, pra, 3pt"
            if not parsed['side']:
                return "❌ Could not determine over/under."
            
            result = self.recheck_prop(
                player=parsed['player'],
                stat=parsed['stat'],
                line=parsed['line'],
                side=parsed['side'],
                odds=parsed['odds'],
                opponent=parsed.get('opponent')
            )
            
            if result.get('error'):
                return f"❌ {result['error']}"
            
            # Format output
            output = f"""
━━━━━━━━━━━━━━━━━━━━━━
PRIVATE ANALYSIS (INTERNAL)
━━━━━━━━━━━━━━━━━━━━━━
**{result['player']} {result['stat']} {result['side']} {result['line']}** @ {result['odds']}
{' | '.join(parsed['assumptions']) if parsed['assumptions'] else ''}

- Projection: **{result['projection']:.1f}** ({result['cushion']:+.1f} cushion)
- Edge: **{result['edge_pct']:+.1f}%**
- EV: **{result['ev_pct']:+.1f}%**
- Win Prob: **{result['win_prob']:.0f}%**
- Hit Rate: **{result['hit_rate']:.0f}%** ({result['games_played']} games)
- MPG: **{result['mpg']:.1f}**
- Risk: {', '.join(result['risk_notes']) if result['risk_notes'] else 'None flagged'}
- Stake: **{result['stake']}u**
- Playable Up To: **{result['side']} {result['playable_up_to']}**

**VERDICT: {result['verdict']}**

━━━━━━━━━━━━━━━━━━━━━━
PUBLIC-READY BLURB
━━━━━━━━━━━━━━━━━━━━━━
"""
            if '✅' in result['verdict']:
                output += f"""• **{result['player']} {result['stat']} {result['side']} {result['line']}** still has value
- Projection: {result['projection']:.1f} | Edge: {result['edge_pct']:+.1f}%
- {result['hit_rate']:.0f}% hit rate over last {result['games_played']} games
- Playable up to **{result['side']} {result['playable_up_to']}**
- Suggested: {result['stake']}u"""
            elif '⚠️' in result['verdict']:
                output += f"""• **{result['player']} {result['stat']} {result['side']} {result['line']}** — thin edge
- Projection: {result['projection']:.1f} | Edge: {result['edge_pct']:+.1f}%
- Only play if you can get it at {result['side']} {result['playable_up_to']} or better
- Max 0.5u if taking"""
            else:
                output += f"""• **{result['player']} {result['stat']} {result['side']} {result['line']}** — NO VALUE
- Line moved past projection ({result['projection']:.1f})
- Pass on this one"""
            
            # Add personal recommendation
            if '✅' in result['verdict'] and result['edge_pct'] >= 5 and result['hit_rate'] >= 55:
                algo_rec = "🟢 **ALGO SAYS: YES, TAKE IT** - Strong edge confirmed"
            elif '✅' in result['verdict']:
                algo_rec = "🟡 **ALGO SAYS: LEAN YES** - Edge exists but proceed with caution"
            elif '⚠️' in result['verdict']:
                algo_rec = "🟠 **ALGO SAYS: BORDERLINE** - Only if you get better number"
            else:
                algo_rec = "🔴 **ALGO SAYS: PASS** - No value at this line"
            output += f"\n\n{algo_rec}\n\n*Recheck @ {timestamp}*"
            return output
        
        elif parsed['bet_type'] == 'total':
            if not parsed['matchup']:
                return "❌ Could not extract matchup. Example: 'recheck DAL@UTA under 237.5'"
            if not parsed['side']:
                return "❌ Could not determine over/under."
            
            result = self.recheck_total(
                matchup=parsed['matchup'],
                line=parsed['line'],
                side=parsed['side'],
                odds=parsed['odds'],
                opponent=parsed.get('opponent')
            )
            
            if result.get('error'):
                return f"❌ {result['error']}"
            
            output = f"""
━━━━━━━━━━━━━━━━━━━━━━
PRIVATE ANALYSIS (INTERNAL)
━━━━━━━━━━━━━━━━━━━━━━
**{result['matchup']} {result['side']} {result['line']}** @ {result['odds']}
{' | '.join(parsed['assumptions']) if parsed['assumptions'] else ''}

- Model Total: **{result['model_total']:.1f}** ({result['cushion']:+.1f} cushion)
- Edge: **{result['edge_pct']:+.1f}%**
- EV: **{result['ev_pct']:+.1f}%**
- Win Prob: **{result['win_prob']:.0f}%**
- Pace: **{result['model_pace']:.1f}**
- Regime: **{result['regime_status']}** ({result['regime_confidence']:.0f}% conf)
- Risk: {', '.join(result['risk_notes']) if result['risk_notes'] else 'None flagged'}
- Stake: **{result['stake']}u**
- Playable Up To: **{result['side']} {result['playable_up_to']}**

**VERDICT: {result['verdict']}**

━━━━━━━━━━━━━━━━━━━━━━
PUBLIC-READY BLURB
━━━━━━━━━━━━━━━━━━━━━━
"""
            if '✅' in result['verdict']:
                output += f"""• **{result['matchup']} {result['side']} {result['line']}** still has value
- Model projects {result['model_total']:.1f} total | Edge: {result['edge_pct']:+.1f}%
- Playable up to **{result['side']} {result['playable_up_to']}**
- Suggested: {result['stake']}u"""
            elif '⚠️' in result['verdict']:
                output += f"""• **{result['matchup']} {result['side']} {result['line']}** — thin edge
- Model projects {result['model_total']:.1f} | Cushion narrowed
- Only take if you get {result['side']} {result['playable_up_to']} or better"""
            else:
                output += f"""• **{result['matchup']} {result['side']} {result['line']}** — NO VALUE
- Line moved past model projection ({result['model_total']:.1f})
- Pass"""
            
            output += f"\n\n*Recheck @ {timestamp}*"
            return output
        
        else:
            return "❌ Could not determine bet type. Supported: props (pts/reb/ast), game totals"


def send_to_discord(message: str) -> bool:
    """Send recheck result to Discord webhook"""
    try:
        response = requests.post(RECHECK_WEBHOOK, json={"content": message})
        return response.status_code == 204
    except Exception as e:
        print(f"❌ Discord send failed: {e}")
        return False


def main():
    """CLI interface for recheck"""
    if len(sys.argv) < 2:
        print("Usage: python recheck_engine.py '<request>' [--discord]")
        print("Examples:")
        print("  python recheck_engine.py 'Edwards over 25.5 pts'")
        print("  python recheck_engine.py 'Edwards over 25.5 pts' --discord")
        print("  python recheck_engine.py 'DAL@UTA under 237.5'")
        sys.exit(1)
    
    # Check for --discord flag
    send_discord = '--discord' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--discord']
    request = ' '.join(args)
    
    engine = RecheckEngine()
    result = engine.recheck(request)
    print(result)
    
    if send_discord:
        print("\n📤 Sending to Discord...")
        if send_to_discord(result):
            print("✅ Sent to Discord!")
        else:
            print("❌ Failed to send to Discord")


if __name__ == "__main__":
    main()
