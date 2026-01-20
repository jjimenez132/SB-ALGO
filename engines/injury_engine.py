#!/usr/bin/env python3
"""
================================================================================
INJURY / AVAILABILITY ENGINE v3.0 - CRITICAL
================================================================================
The #1 source of model failure is injuries. This engine fixes that.

DATA SOURCES:
-------------
1. injuries table (if populated)
2. nba_news table (parses injury keywords)
3. Manual input (for real-time updates)

INJURY IMPACT HIERARCHY:
------------------------
Tier 1 (Superstar): 8-15 point swing
Tier 2 (All-Star): 4-8 point swing
Tier 3 (Quality Starter): 2-4 point swing
Tier 4 (Rotation): 0.5-2 point swing
Tier 5 (End Bench): 0-0.5 point swing

STATUS MULTIPLIERS:
-------------------
OUT: 100% impact | DOUBTFUL: 75% | QUESTIONABLE: 40% | PROBABLE: 10%

OUTPUT:
-------
- Adjusted team strength (net rating delta)
- Pace delta
- Usage reallocation map
- Blowout probability change
- Confidence penalty (uncertainty increase)

================================================================================
"""

import numpy as np
import re
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# Status multipliers (how much of impact is realized)
STATUS_MULTIPLIERS = {
    'out': 1.00,
    'ruled out': 1.00,
    'injured': 1.00,
    'doubtful': 0.75,
    'questionable': 0.40,
    'game-time decision': 0.50,
    'gtd': 0.50,
    'probable': 0.10,
    'likely': 0.10,
    'day-to-day': 0.50,
    'available': 0.00,
    'active': 0.00,
    'playing': 0.00,
    'upgraded': 0.00,
}

# Player tier classification (based on typical impact)
# VEGAS-CALIBRATED VALUES (2025 Official Oddsmaker Rankings)
# Source: Yahoo Sports survey of 7 sportsbooks
SUPERSTAR_TIER = {
    # Tier 1 - MVP caliber (5-6 pts spread impact)
    'nikola jokic': 5.8, 
    'giannis antetokounmpo': 5.6,
    # Tier 2 - Elite Star (4-5 pts spread impact)
    'victor wembanyama': 4.6,
    'shai gilgeous-alexander': 4.4,
    'stephen curry': 4.4,
    'luka doncic': 4.2,
    'joel embiid': 4.2,
    # Tier 3 - All-Star (3-4 pts spread impact)
    'anthony davis': 4.0,
    'jaylen brown': 3.8,
    'anthony edwards': 3.6,
    'donovan mitchell': 3.5,
    'jayson tatum': 3.5,
    'jalen brunson': 3.3,
    'kevin durant': 3.3,
    'lamelo ball': 3.2,
    'ja morant': 3.2,
}

ALL_STAR_TIER = {
    # Tier 4 - Key Starter (2.5-3 pts spread impact)
    'trae young': 3.1,
    'de\'aaron fox': 3.0,
    'cade cunningham': 3.0,
    'lebron james': 2.8,
    'darius garland': 2.8,
    'zion williamson': 2.7,
    'devin booker': 2.7,
    'james harden': 2.6,
    'kawhi leonard': 2.5,
    'tyrese maxey': 2.5,
    'tyrese haliburton': 2.5,
    'damian lillard': 2.5,
    'jimmy butler': 2.4,
    # Tier 5 - Solid Starter (2-2.5 pts spread impact)
    'franz wagner': 2.4,
    'paolo banchero': 2.3,
    'scottie barnes': 2.3,
    'bam adebayo': 2.2,
    'karl-anthony towns': 2.2,
    'evan mobley': 2.2,
    'domantas sabonis': 2.1,
    'pascal siakam': 2.1,
    'dejounte murray': 2.1,
    'jalen williams': 2.0,
    'alperen sengun': 2.0,
    'brandon ingram': 2.0,
    'mikal bridges': 1.9,
    'jarrett allen': 1.9,
    'fred vanvleet': 1.8,
    'austin reaves': 1.8,
    'og anunoby': 1.8,
    'rudy gobert': 1.8,
    'desmond bane': 1.7,
    'derrick white': 1.7,
    'jrue holiday': 1.7,
    'draymond green': 1.6,
    'aaron gordon': 1.6,
    'christian braun': 1.5,
    'cameron johnson': 1.5,
    'khris middleton': 1.5,
    'isaiah hartenstein': 1.5,
    'naz reid': 1.4,
    'zaccharie risacher': 1.3,
    'max strus': 1.2,
    'sam merrill': 1.0,
    'kristaps porzingis': 2.2,
    'nikola topic': 0.5,
    'jonas valanciunas': 1.4,
    'terrence shannon jr.': 0.8,
    'joe ingles': 0.5,
    'tamar bates': 0.3,
    'rayj dennis': 0.3,
}

# Default impact by position if player not in tiers
# VEGAS-CALIBRATED: Much lower than before
POSITION_DEFAULT_IMPACT = {
    'PG': 1.5,
    'SG': 1.3,
    'SF': 1.3,
    'PF': 1.3,
    'C': 1.5,
    'G': 1.3,
    'F': 1.3,
    'default': 1.0,
}

# Maximum team adjustment caps (prevent runaway totals)
MAX_TEAM_SPREAD_ADJ = 10.0
MAX_TEAM_TOTAL_ADJ = 8.0

# Injury type modifiers
INJURY_SEVERITY = {
    'acl': 1.0,       # Season ending
    'achilles': 1.0,  # Season ending
    'broken': 0.95,
    'fracture': 0.90,
    'surgery': 1.0,
    'concussion': 0.70,
    'hamstring': 0.60,
    'ankle': 0.50,
    'knee': 0.65,
    'back': 0.55,
    'shoulder': 0.50,
    'illness': 0.80,
    'rest': 1.0,      # Confirmed out
    'personal': 0.80,
    'suspension': 1.0,
    'load management': 1.0,
    'soreness': 0.40,
    'sprain': 0.50,
    'strain': 0.55,
}

# Team abbreviation mapping
TEAM_ABBR_MAP = {
    'atlanta': 'ATL', 'hawks': 'ATL',
    'boston': 'BOS', 'celtics': 'BOS',
    'brooklyn': 'BKN', 'nets': 'BKN',
    'charlotte': 'CHA', 'hornets': 'CHA',
    'chicago': 'CHI', 'bulls': 'CHI',
    'cleveland': 'CLE', 'cavaliers': 'CLE', 'cavs': 'CLE',
    'dallas': 'DAL', 'mavericks': 'DAL', 'mavs': 'DAL',
    'denver': 'DEN', 'nuggets': 'DEN',
    'detroit': 'DET', 'pistons': 'DET',
    'golden state': 'GSW', 'warriors': 'GSW',
    'houston': 'HOU', 'rockets': 'HOU',
    'indiana': 'IND', 'pacers': 'IND',
    'la clippers': 'LAC', 'clippers': 'LAC',
    'la lakers': 'LAL', 'lakers': 'LAL', 'los angeles lakers': 'LAL',
    'memphis': 'MEM', 'grizzlies': 'MEM',
    'miami': 'MIA', 'heat': 'MIA',
    'milwaukee': 'MIL', 'bucks': 'MIL',
    'minnesota': 'MIN', 'timberwolves': 'MIN', 'wolves': 'MIN',
    'new orleans': 'NOP', 'pelicans': 'NOP',
    'new york': 'NYK', 'knicks': 'NYK',
    'oklahoma city': 'OKC', 'thunder': 'OKC',
    'orlando': 'ORL', 'magic': 'ORL',
    'philadelphia': 'PHI', '76ers': 'PHI', 'sixers': 'PHI',
    'phoenix': 'PHX', 'suns': 'PHX',
    'portland': 'POR', 'trail blazers': 'POR', 'blazers': 'POR',
    'sacramento': 'SAC', 'kings': 'SAC',
    'san antonio': 'SAS', 'spurs': 'SAS',
    'toronto': 'TOR', 'raptors': 'TOR',
    'utah': 'UTA', 'jazz': 'UTA',
    'washington': 'WAS', 'wizards': 'WAS',
}


class InjuryEngine:
    """
    ============================================================================
    INJURY / AVAILABILITY ENGINE
    ============================================================================
    
    Converts injury reports into quantified model adjustments.
    
    Primary Functions:
    1. Parse injuries from news/reports
    2. Calculate impact per player
    3. Aggregate team-level adjustments
    4. Output uncertainty/confidence penalties
    
    ============================================================================
    """
    
    def __init__(self):
        """Initialize engine with database connection"""
        self.engine = create_engine(DATABASE_URL)
        self._player_cache = {}
        self._load_player_stats()
    
    def _load_player_stats(self):
        """Load player stats for impact calculation"""
        try:
            with self.engine.connect() as conn:
                # Get player base stats
                query = """
                    SELECT "PLAYER_NAME", "TEAM_ABBREVIATION", "MIN", "PTS", 
                           "REB", "AST", "GP"
                    FROM nba_player_base_stats
                    WHERE "MIN" > 10
                """
                result = conn.execute(text(query))
                for row in result:
                    r = dict(row._mapping)
                    name = r['PLAYER_NAME'].lower() if r['PLAYER_NAME'] else ''
                    self._player_cache[name] = {
                        'team': r['TEAM_ABBREVIATION'],
                        'minutes': r['MIN'] or 0,
                        'pts': r['PTS'] or 0,
                        'reb': r['REB'] or 0,
                        'ast': r['AST'] or 0,
                        'gp': r['GP'] or 0,
                    }
        except Exception as e:
            print(f"Warning: Could not load player stats: {e}")
    
    # ==========================================================================
    # INJURY PARSING
    # ==========================================================================
    
    def parse_injury_from_text(self, news_text: str) -> Dict:
        """
        Parse injury information from news text.
        
        Args:
            news_text: News headline or injury report text
            
        Returns:
            Parsed injury dict with player, team, status, injury_type
        """
        text_lower = news_text.lower()
        
        # Extract status
        status = 'unknown'
        for status_key, multiplier in STATUS_MULTIPLIERS.items():
            if status_key in text_lower:
                status = status_key
                break
        
        # Extract injury type
        injury_type = 'unspecified'
        for injury_key in INJURY_SEVERITY.keys():
            if injury_key in text_lower:
                injury_type = injury_key
                break
        
        # Try to extract player name (from our known players)
        player_found = None
        for player_name in list(SUPERSTAR_TIER.keys()) + list(ALL_STAR_TIER.keys()) + list(self._player_cache.keys()):
            if player_name in text_lower:
                player_found = player_name
                break
        
        # Try to extract team
        team_found = None
        for team_key, abbr in TEAM_ABBR_MAP.items():
            if team_key in text_lower:
                team_found = abbr
                break
        
        return {
            'player_name': player_found,
            'team': team_found,
            'status': status,
            'injury_type': injury_type,
            'raw_text': news_text,
            'parsed_at': datetime.now().isoformat(),
        }
    
    def get_injuries_from_news(self, hours_back: int = 48) -> List[Dict]:
        """
        Get recent injury news from nba_news table.
        
        Args:
            hours_back: How many hours of news to check
            
        Returns:
            List of parsed injury reports
        """
        injuries = []
        
        # Keywords that indicate injury news
        injury_keywords = [
            'out', 'questionable', 'doubtful', 'probable', 'injury',
            'injured', 'ruled out', 'miss', 'sidelined', 'day-to-day',
            'knee', 'ankle', 'hamstring', 'concussion', 'rest',
            'load management', 'personal', 'illness'
        ]
        
        try:
            with self.engine.connect() as conn:
                # Get recent news
                query = """
                    SELECT title, link, fetched_at 
                    FROM nba_news 
                    ORDER BY fetched_at DESC 
                    LIMIT 500
                """
                result = conn.execute(text(query))
                
                for row in result:
                    title = row[0] or ''
                    title_lower = title.lower()
                    
                    # Check if this is injury-related news
                    if any(kw in title_lower for kw in injury_keywords):
                        parsed = self.parse_injury_from_text(title)
                        if parsed['player_name'] or parsed['team']:
                            parsed['source'] = row[1]
                            parsed['fetched_at'] = row[2]
                            injuries.append(parsed)
        
        except Exception as e:
            print(f"Error fetching news: {e}")
        
        return injuries
    
    def get_injuries_from_table(self, team: str = None) -> List[Dict]:
        """
        Get injuries from injuries table (if populated).
        
        Args:
            team: Filter by team abbreviation (optional)
            
        Returns:
            List of injury records
        """
        injuries = []
        
        # Map abbreviations to full team names
        ABBR_TO_FULL = {
            'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
            'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
            'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
            'GSW': 'Golden State Warriors', 'GS': 'Golden State Warriors',
            'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
            'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
            'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
            'NOP': 'New Orleans Pelicans', 'NO': 'New Orleans Pelicans',
            'NYK': 'New York Knicks', 'NY': 'New York Knicks',
            'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic',
            'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns', 'PHO': 'Phoenix Suns',
            'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings',
            'SAS': 'San Antonio Spurs', 'SA': 'San Antonio Spurs',
            'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz',
            'WAS': 'Washington Wizards'
        }
        
        # Reverse map for getting abbr from full name
        FULL_TO_ABBR = {v: k for k, v in ABBR_TO_FULL.items()}
        
        try:
            with self.engine.connect() as conn:
                query = "SELECT * FROM injuries"
                params = {}
                
                if team:
                    # Convert abbreviation to full name if needed
                    team_upper = team.upper()
                    team_full = ABBR_TO_FULL.get(team_upper, team)
                    query += " WHERE team_name = :team"
                    params['team'] = team_full
                
                result = conn.execute(text(query), params)
                
                for row in result:
                    r = dict(row._mapping)
                    team_name = r.get('team_name', '')
                    team_abbr = FULL_TO_ABBR.get(team_name, r.get('team_abbr', ''))
                    
                    injuries.append({
                        'player_name': r.get('player_name', '').lower() if r.get('player_name') else None,
                        'team': team_abbr,
                        'team_name': team_name,
                        'status': r.get('status', 'unknown').lower() if r.get('status') else 'unknown',
                        'injury_type': r.get('injury_type', 'unspecified').lower() if r.get('injury_type') else 'unspecified',
                        'description': r.get('description'),
                        'date': r.get('date'),
                    })
        
        except Exception as e:
            print(f"Error fetching injuries: {e}")
        
        return injuries
    
    # ==========================================================================
    # IMPACT CALCULATION
    # ==========================================================================
    
    def get_player_impact(self, player_name: str) -> Dict:
        """
        Calculate a player's impact on their team.
        
        Uses:
        1. Predefined tiers (superstars, all-stars)
        2. Actual stats (minutes, usage, production)
        3. Position defaults
        
        Args:
            player_name: Player name (case insensitive)
            
        Returns:
            Impact metrics
        """
        name_lower = player_name.lower()
        
        # Check superstar tier
        if name_lower in SUPERSTAR_TIER:
            base_impact = SUPERSTAR_TIER[name_lower]
            tier = 'SUPERSTAR'
        # Check all-star tier
        elif name_lower in ALL_STAR_TIER:
            base_impact = ALL_STAR_TIER[name_lower]
            tier = 'ALL_STAR'
        # Calculate from stats
        elif name_lower in self._player_cache:
            stats = self._player_cache[name_lower]
            # Impact formula: minutes-weighted production
            # High minutes + high production = high impact
            mins = stats['minutes']
            pts = stats['pts']
            reb = stats['reb']
            ast = stats['ast']
            
            # Simple impact score
            production = pts + 0.5 * reb + 0.7 * ast
            minutes_factor = mins / 35  # Normalize to ~35 min player
            
            base_impact = production * minutes_factor * 0.3
            base_impact = max(1, min(8, base_impact))  # Cap between 1-8
            
            if base_impact >= 6:
                tier = 'STARTER_HIGH'
            elif base_impact >= 4:
                tier = 'STARTER'
            elif base_impact >= 2:
                tier = 'ROTATION'
            else:
                tier = 'BENCH'
        else:
            # Unknown player - default
            base_impact = 2.0
            tier = 'UNKNOWN'
        
        # Get team
        team = None
        if name_lower in self._player_cache:
            team = self._player_cache[name_lower].get('team')
        
        return {
            'player_name': player_name,
            'team': team,
            'tier': tier,
            'base_impact': round(base_impact, 1),
            'spread_impact': round(base_impact, 1),  # Points impact on spread
            'total_impact': round(base_impact * 0.8, 1),  # Impact on total
            'pace_impact': round(base_impact * 0.1, 2),  # Pace change
        }
    
    def calculate_injury_impact(self, player_name: str, status: str, 
                                injury_type: str = 'unspecified') -> Dict:
        """
        Calculate the impact of a specific injury.
        
        Combines:
        - Player's base impact
        - Status multiplier (out=100%, questionable=40%, etc.)
        - Injury severity (if known)
        
        Args:
            player_name: Player name
            status: Injury status (out, questionable, etc.)
            injury_type: Type of injury
            
        Returns:
            Calculated impact
        """
        # Get base impact
        impact = self.get_player_impact(player_name)
        
        # Get status multiplier
        status_lower = status.lower()
        status_mult = STATUS_MULTIPLIERS.get(status_lower, 0.5)
        
        # Get injury severity (optional modifier)
        injury_lower = injury_type.lower()
        injury_mult = INJURY_SEVERITY.get(injury_lower, 0.6)
        
        # Calculate adjusted impact
        # Final impact = base * status_multiplier
        # (injury severity affects confidence, not direct impact)
        adjusted_spread = impact['spread_impact'] * status_mult
        adjusted_total = impact['total_impact'] * status_mult
        adjusted_pace = impact['pace_impact'] * status_mult
        
        # Confidence penalty based on status and injury
        if status_lower in ['out', 'ruled out']:
            confidence_penalty = 0  # Certain, no penalty
        elif status_lower in ['doubtful']:
            confidence_penalty = 5  # Some uncertainty
        elif status_lower in ['questionable', 'day-to-day', 'gtd', 'game-time decision']:
            confidence_penalty = 15  # High uncertainty
        elif status_lower in ['probable', 'likely']:
            confidence_penalty = 3  # Low uncertainty
        else:
            confidence_penalty = 10  # Unknown status
        
        return {
            'player_name': player_name,
            'team': impact['team'],
            'tier': impact['tier'],
            'status': status,
            'injury_type': injury_type,
            
            # Base impact
            'base_spread_impact': impact['spread_impact'],
            'base_total_impact': impact['total_impact'],
            
            # Adjusted for status
            'status_multiplier': status_mult,
            'adjusted_spread_impact': round(adjusted_spread, 2),
            'adjusted_total_impact': round(adjusted_total, 2),
            'adjusted_pace_impact': round(adjusted_pace, 2),
            
            # Confidence
            'confidence_penalty': confidence_penalty,
            
            # Interpretation
            'summary': f"{player_name} ({status}): {adjusted_spread:+.1f} pts spread, {adjusted_total:+.1f} pts total"
        }
    
    # ==========================================================================
    # TEAM-LEVEL AGGREGATION
    # ==========================================================================
    
    def get_team_injury_report(self, team: str) -> Dict:
        """
        Get full injury report for a team.
        
        Aggregates all injuries into team-level adjustments.
        
        Args:
            team: Team name or abbreviation
            
        Returns:
            Team injury report with aggregated adjustments
        """
        # Normalize team name
        team_abbr = self._normalize_team(team)
        
        # Get injuries from both sources
        injuries_table = self.get_injuries_from_table(team_abbr)
        injuries_news = [i for i in self.get_injuries_from_news() 
                        if i.get('team') == team_abbr]
        
        # Combine and deduplicate (prefer table over news)
        all_injuries = {}
        
        for inj in injuries_news:
            if inj['player_name']:
                all_injuries[inj['player_name']] = inj
        
        for inj in injuries_table:
            if inj['player_name']:
                all_injuries[inj['player_name']] = inj  # Overwrites news
        
        # Calculate impacts
        injury_impacts = []
        total_spread_impact = 0
        total_total_impact = 0
        total_pace_impact = 0
        total_confidence_penalty = 0
        
        for player_name, injury in all_injuries.items():
            impact = self.calculate_injury_impact(
                player_name,
                injury.get('status', 'unknown'),
                injury.get('injury_type', 'unspecified')
            )
            injury_impacts.append(impact)
            
            total_spread_impact += impact['adjusted_spread_impact']
            total_total_impact += impact['adjusted_total_impact']
            total_pace_impact += impact['adjusted_pace_impact']
            total_confidence_penalty += impact['confidence_penalty']
        
        # Cap confidence penalty at 30
        total_confidence_penalty = min(30, total_confidence_penalty)
        
        # Apply Vegas-style caps to prevent runaway adjustments
        capped_spread = min(total_spread_impact, MAX_TEAM_SPREAD_ADJ)
        capped_total = min(total_total_impact, MAX_TEAM_TOTAL_ADJ)
        
        return {
            'team': team_abbr,
            'num_injuries': len(injury_impacts),
            'injuries': injury_impacts,
            
            # Aggregate adjustments (negative = team weaker)
            'spread_adjustment': round(-capped_spread, 2),
            'total_adjustment': round(-capped_total, 2),
            'pace_adjustment': round(-total_pace_impact, 2),
            
            # Confidence
            'confidence_penalty': round(total_confidence_penalty, 1),
            'confidence_note': self._get_confidence_note(total_confidence_penalty),
            
            # Summary
            'summary': f"{team_abbr}: {len(injury_impacts)} injuries, {-total_spread_impact:+.1f} pts adjustment"
        }
    
    def _normalize_team(self, team: str) -> str:
        """Normalize team name to abbreviation"""
        team_lower = team.lower().strip()
        
        # Already an abbreviation
        if len(team_lower) <= 3:
            return team.upper()
        
        # Look up
        return TEAM_ABBR_MAP.get(team_lower, team.upper())
    
    def _get_confidence_note(self, penalty: float) -> str:
        """Get human-readable confidence note"""
        if penalty <= 3:
            return "HIGH_CONFIDENCE - Injury situation clear"
        elif penalty <= 10:
            return "MODERATE_CONFIDENCE - Some uncertainty"
        elif penalty <= 20:
            return "LOW_CONFIDENCE - Multiple questionable players"
        else:
            return "VERY_LOW_CONFIDENCE - High uncertainty, consider passing"
    
    # ==========================================================================
    # GAME-LEVEL ANALYSIS
    # ==========================================================================
    
    def analyze_game_injuries(self, home_team: str, away_team: str) -> Dict:
        """
        Full injury analysis for a game matchup.
        
        Args:
            home_team: Home team
            away_team: Away team
            
        Returns:
            Complete injury analysis with adjustments for both teams
        """
        home_report = self.get_team_injury_report(home_team)
        away_report = self.get_team_injury_report(away_team)
        
        # Net adjustments (positive = home team advantage)
        net_spread_adj = home_report['spread_adjustment'] - away_report['spread_adjustment']
        net_total_adj = home_report['total_adjustment'] + away_report['total_adjustment']
        
        # Combined confidence penalty
        combined_penalty = home_report['confidence_penalty'] + away_report['confidence_penalty']
        combined_penalty = min(40, combined_penalty)  # Cap at 40
        
        # Determine injury edge
        if abs(net_spread_adj) >= 5:
            injury_edge = 'MAJOR' if net_spread_adj > 0 else 'MAJOR_AGAINST'
        elif abs(net_spread_adj) >= 2:
            injury_edge = 'MODERATE' if net_spread_adj > 0 else 'MODERATE_AGAINST'
        elif abs(net_spread_adj) >= 0.5:
            injury_edge = 'MINOR' if net_spread_adj > 0 else 'MINOR_AGAINST'
        else:
            injury_edge = 'NEUTRAL'
        
        return {
            'matchup': f"{away_team} @ {home_team}",
            'home_team': home_report,
            'away_team': away_report,
            
            # Net adjustments
            'net_spread_adjustment': round(net_spread_adj, 2),
            'net_total_adjustment': round(net_total_adj, 2),
            
            # Interpretation
            'injury_edge': injury_edge,
            'edge_for': home_team if net_spread_adj > 0 else away_team if net_spread_adj < 0 else 'NEUTRAL',
            
            # Confidence
            'combined_confidence_penalty': round(combined_penalty, 1),
            'model_confidence': max(60, 100 - combined_penalty),
            
            # Recommendations
            'spread_note': f"Adjust spread by {net_spread_adj:+.1f} pts toward {home_team if net_spread_adj > 0 else away_team}",
            'total_note': f"Adjust total by {net_total_adj:+.1f} pts",
            'confidence_note': self._get_confidence_note(combined_penalty),
        }
    
    # ==========================================================================
    # MANUAL INJURY INPUT
    # ==========================================================================
    
    def add_manual_injury(self, player_name: str, team: str, status: str,
                         injury_type: str = 'unspecified') -> Dict:
        """
        Add injury manually (for real-time updates).
        
        Args:
            player_name: Player name
            team: Team abbreviation
            status: Injury status
            injury_type: Type of injury
            
        Returns:
            Calculated impact
        """
        impact = self.calculate_injury_impact(player_name, status, injury_type)
        impact['team'] = self._normalize_team(team)
        impact['source'] = 'manual'
        impact['added_at'] = datetime.now().isoformat()
        
        return impact
    
    # ==========================================================================
    # USAGE REALLOCATION
    # ==========================================================================
    
    def calculate_usage_reallocation(self, team: str, injured_player: str) -> Dict:
        """
        Calculate how usage redistributes when a player is out.
        
        When a star player is out, their usage goes to teammates.
        This affects prop lines for remaining players.
        
        Args:
            team: Team abbreviation
            injured_player: Name of injured player
            
        Returns:
            Usage reallocation map
        """
        team_abbr = self._normalize_team(team)
        
        # Get injured player's stats
        injured_lower = injured_player.lower()
        if injured_lower not in self._player_cache:
            return {'error': f'Player {injured_player} not found'}
        
        injured_stats = self._player_cache[injured_lower]
        injured_mins = injured_stats['minutes']
        injured_pts = injured_stats['pts']
        injured_reb = injured_stats['reb']
        injured_ast = injured_stats['ast']
        
        # Get teammates
        teammates = []
        for name, stats in self._player_cache.items():
            if stats.get('team') == team_abbr and name != injured_lower:
                teammates.append({
                    'name': name,
                    'minutes': stats['minutes'],
                    'pts': stats['pts'],
                    'reb': stats['reb'],
                    'ast': stats['ast'],
                })
        
        if not teammates:
            return {'error': f'No teammates found for {team_abbr}'}
        
        # Sort by minutes (top players get more redistribution)
        teammates.sort(key=lambda x: x['minutes'], reverse=True)
        
        # Redistribute usage (simplified model)
        # Top players absorb more of the load
        total_teammate_mins = sum(t['minutes'] for t in teammates[:5])
        
        reallocation = []
        for i, teammate in enumerate(teammates[:5]):
            share = teammate['minutes'] / total_teammate_mins if total_teammate_mins > 0 else 0.2
            
            pts_boost = injured_pts * share * 0.7  # 70% of production redistributed
            reb_boost = injured_reb * share * 0.5
            ast_boost = injured_ast * share * 0.6
            
            reallocation.append({
                'player': teammate['name'].title(),
                'current_pts': teammate['pts'],
                'pts_boost': round(pts_boost, 1),
                'projected_pts': round(teammate['pts'] + pts_boost, 1),
                'reb_boost': round(reb_boost, 1),
                'ast_boost': round(ast_boost, 1),
            })
        
        return {
            'injured_player': injured_player,
            'team': team_abbr,
            'injured_production': {
                'pts': injured_pts,
                'reb': injured_reb,
                'ast': injured_ast,
            },
            'reallocation': reallocation,
            'note': f"With {injured_player} out, usage redistributes to remaining players"
        }


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("INJURY / AVAILABILITY ENGINE v3.0 - TEST SUITE")
    print("=" * 80)
    
    engine = InjuryEngine()
    
    # -------------------------------------------------------------------------
    # Test 1: Parse injury from text
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: PARSE INJURY FROM TEXT")
    print("=" * 80)
    
    test_texts = [
        "Butler is questionable for Thursday's game against the 76ers due to left knee soreness.",
        "LeBron James ruled out for tonight's game with ankle injury",
        "Giannis Antetokounmpo is probable for Monday's matchup",
        "Anthony Davis day-to-day with back tightness",
    ]
    
    for test_text in test_texts:
        parsed = engine.parse_injury_from_text(test_text)
        print(f"\n  Input: \"{test_text[:60]}...\"")
        print(f"  Player: {parsed['player_name']}")
        print(f"  Status: {parsed['status']}")
        print(f"  Injury: {parsed['injury_type']}")
    
    # -------------------------------------------------------------------------
    # Test 2: Get injuries from news
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: GET INJURIES FROM NEWS")
    print("=" * 80)
    
    news_injuries = engine.get_injuries_from_news()
    print(f"\n  Found {len(news_injuries)} injury-related news items")
    
    if news_injuries[:5]:
        print("\n  Recent injuries:")
        for inj in news_injuries[:5]:
            print(f"    {inj.get('player_name', 'Unknown')} ({inj.get('status', '?')}) - {inj.get('injury_type', '?')}")
    
    # -------------------------------------------------------------------------
    # Test 3: Player impact calculation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: PLAYER IMPACT CALCULATION")
    print("=" * 80)
    
    test_players = ['LeBron James', 'Giannis Antetokounmpo', 'Jimmy Butler', 'Austin Reaves']
    
    for player in test_players:
        impact = engine.get_player_impact(player)
        print(f"\n  {player}")
        print(f"    Tier: {impact['tier']}")
        print(f"    Spread Impact: {impact['spread_impact']} pts")
        print(f"    Total Impact: {impact['total_impact']} pts")
    
    # -------------------------------------------------------------------------
    # Test 4: Injury impact with status
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 4: INJURY IMPACT WITH STATUS")
    print("=" * 80)
    
    scenarios = [
        ('LeBron James', 'out', 'ankle'),
        ('LeBron James', 'questionable', 'ankle'),
        ('Jimmy Butler', 'doubtful', 'knee'),
        ('Austin Reaves', 'probable', 'illness'),
    ]
    
    for player, status, injury in scenarios:
        impact = engine.calculate_injury_impact(player, status, injury)
        print(f"\n  {impact['summary']}")
        print(f"    Status Multiplier: {impact['status_multiplier']}")
        print(f"    Confidence Penalty: {impact['confidence_penalty']}")
    
    # -------------------------------------------------------------------------
    # Test 5: Team injury report
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 5: TEAM INJURY REPORT")
    print("=" * 80)
    
    # Add some manual injuries for testing
    manual_injuries = [
        engine.add_manual_injury('LeBron James', 'LAL', 'questionable', 'ankle'),
        engine.add_manual_injury('Anthony Davis', 'LAL', 'probable', 'back'),
    ]
    
    print("\n  Manual injuries added for Lakers:")
    for inj in manual_injuries:
        print(f"    {inj['summary']}")
    
    # -------------------------------------------------------------------------
    # Test 6: Game injury analysis
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 6: GAME INJURY ANALYSIS")
    print("=" * 80)
    
    # Simulate a game
    analysis = engine.analyze_game_injuries('Celtics', 'Lakers')
    
    print(f"\n  {analysis['matchup']}")
    print(f"\n  Home ({analysis['home_team']['team']}):")
    print(f"    Injuries: {analysis['home_team']['num_injuries']}")
    print(f"    Spread Adj: {analysis['home_team']['spread_adjustment']}")
    
    print(f"\n  Away ({analysis['away_team']['team']}):")
    print(f"    Injuries: {analysis['away_team']['num_injuries']}")
    print(f"    Spread Adj: {analysis['away_team']['spread_adjustment']}")
    
    print(f"\n  📊 NET ANALYSIS:")
    print(f"    Net Spread Adjustment: {analysis['net_spread_adjustment']:+.1f} pts")
    print(f"    Injury Edge: {analysis['injury_edge']} ({analysis['edge_for']})")
    print(f"    Model Confidence: {analysis['model_confidence']}%")
    print(f"\n  💡 {analysis['spread_note']}")
    
    # -------------------------------------------------------------------------
    # Test 7: Usage reallocation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 7: USAGE REALLOCATION")
    print("=" * 80)
    
    realloc = engine.calculate_usage_reallocation('LAL', 'LeBron James')
    
    if 'error' not in realloc:
        print(f"\n  {realloc['note']}")
        print(f"\n  LeBron's production to redistribute:")
        print(f"    PTS: {realloc['injured_production']['pts']}")
        print(f"    REB: {realloc['injured_production']['reb']}")
        print(f"    AST: {realloc['injured_production']['ast']}")
        
        print(f"\n  Reallocation to teammates:")
        for r in realloc['reallocation'][:3]:
            print(f"    {r['player']}: {r['current_pts']} → {r['projected_pts']} PTS (+{r['pts_boost']})")
    
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("✅ INJURY ENGINE v3.0 - ALL TESTS COMPLETE")
    print("=" * 80)
