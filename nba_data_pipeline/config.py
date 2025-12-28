"""
NBA Data Pipeline Configuration
All settings, API endpoints, and constants
"""

import os
from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "nba_stats.db"

# =============================================================================
# API CONFIGURATION
# =============================================================================

# NBA.com Stats API
NBA_STATS_BASE_URL = "https://stats.nba.com/stats"
NBA_STATS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

# Basketball Reference
BBREF_BASE_URL = "https://www.basketball-reference.com"

# =============================================================================
# CURRENT SEASON
# =============================================================================
CURRENT_SEASON = "2024-25"
CURRENT_SEASON_YEAR = 2025  # For BBRef URLs

# =============================================================================
# RATE LIMITING
# =============================================================================
NBA_DELAY_SECONDS = 1.0  # Delay between NBA.com calls
BBREF_DELAY_SECONDS = 3.0  # Delay between BBRef pages

# =============================================================================
# NBA.COM API ENDPOINTS AND PARAMETERS
# =============================================================================

# Common parameters used across endpoints
COMMON_PARAMS = {
    'LeagueID': '00',
    'Season': CURRENT_SEASON,
    'SeasonType': 'Regular Season',
}

# Endpoint configurations - what we pull and how
NBA_ENDPOINTS = {
    # =========================================================================
    # TEAM STATS
    # =========================================================================
    'team_base': {
        'endpoint': 'leaguedashteamstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Base',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'team_base_stats'
    },
    'team_advanced': {
        'endpoint': 'leaguedashteamstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Advanced',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'team_advanced_stats'
    },
    'team_four_factors': {
        'endpoint': 'leaguedashteamstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Four Factors',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'team_four_factors'
    },
    'team_scoring': {
        'endpoint': 'leaguedashteamstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Scoring',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'team_scoring'
    },
    'team_opponent': {
        'endpoint': 'leaguedashteamstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Opponent',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'team_opponent_stats'
    },
    'team_defense': {
        'endpoint': 'leaguedashteamstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Defense',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'team_defense'
    },
    
    # =========================================================================
    # PLAYER STATS
    # =========================================================================
    'player_base': {
        'endpoint': 'leaguedashplayerstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Base',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_base_stats'
    },
    'player_advanced': {
        'endpoint': 'leaguedashplayerstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Advanced',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_advanced_stats'
    },
    'player_scoring': {
        'endpoint': 'leaguedashplayerstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Scoring',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_scoring'
    },
    'player_usage': {
        'endpoint': 'leaguedashplayerstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Usage',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_usage'
    },
    
    # =========================================================================
    # PLAYER TRACKING STATS (Touches, Possessions, Speed)
    # =========================================================================
    'player_tracking_touches': {
        'endpoint': 'leaguedashptstats',
        'params': {
            **COMMON_PARAMS,
            'PlayerOrTeam': 'Player',
            'PtMeasureType': 'Possessions',
            'PerMode': 'PerGame',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_tracking_possessions'
    },
    'player_tracking_passes': {
        'endpoint': 'leaguedashptstats',
        'params': {
            **COMMON_PARAMS,
            'PlayerOrTeam': 'Player',
            'PtMeasureType': 'Passing',
            'PerMode': 'PerGame',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_tracking_passes'
    },
    'player_tracking_rebounding': {
        'endpoint': 'leaguedashptstats',
        'params': {
            **COMMON_PARAMS,
            'PlayerOrTeam': 'Player',
            'PtMeasureType': 'Rebounding',
            'PerMode': 'PerGame',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_tracking_rebounding'
    },
    
    # =========================================================================
    # SHOT DASHBOARD (Zone breakdowns)
    # =========================================================================
    'player_shots_general': {
        'endpoint': 'leaguedashplayershotlocations',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Base',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'DistanceRange': 'By Zone',
            'TwoWay': '0',
        },
        'table': 'player_shot_zones'
    },
    
    # =========================================================================
    # HUSTLE STATS (Deflections, Contested Shots, Box Outs)
    # =========================================================================
    'player_hustle': {
        'endpoint': 'leaguehustlestatsplayer',
        'params': {
            **COMMON_PARAMS,
            'PerMode': 'PerGame',
            'PlayerPosition': '',
        },
        'table': 'player_hustle'
    },
    'team_hustle': {
        'endpoint': 'leaguehustlestatsteam',
        'params': {
            **COMMON_PARAMS,
            'PerMode': 'PerGame',
        },
        'table': 'team_hustle'
    },
    
    # =========================================================================
    # CLUTCH STATS
    # =========================================================================
    'player_clutch': {
        'endpoint': 'leaguedashplayerclutch',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Base',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'ClutchTime': 'Last 5 Minutes',
            'AheadBehind': 'Ahead or Behind',
            'PointDiff': '5',
            'TwoWay': '0',
        },
        'table': 'player_clutch'
    },
    'team_clutch': {
        'endpoint': 'leaguedashteamclutch',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Base',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'ClutchTime': 'Last 5 Minutes',
            'AheadBehind': 'Ahead or Behind',
            'PointDiff': '5',
            'TwoWay': '0',
        },
        'table': 'team_clutch'
    },
    
    # =========================================================================
    # ON/OFF STATS
    # =========================================================================
    'player_on_off': {
        'endpoint': 'leaguedashplayerstats',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Advanced',
            'PerMode': 'Totals',
            'PlusMinus': 'Y',  # This gives on/off
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'player_on_off'
    },
    
    # =========================================================================
    # LINEUP STATS
    # =========================================================================
    'lineups': {
        'endpoint': 'leaguedashlineups',
        'params': {
            **COMMON_PARAMS,
            'MeasureType': 'Advanced',
            'PerMode': 'PerGame',
            'PlusMinus': 'N',
            'PaceAdjust': 'N',
            'Rank': 'N',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GroupQuantity': '5',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'lineups'
    },
    
    # =========================================================================
    # DEFENSE DASHBOARD
    # =========================================================================
    'defense_dashboard': {
        'endpoint': 'leaguedashptdefend',
        'params': {
            **COMMON_PARAMS,
            'DefenseCategory': 'Overall',
            'PerMode': 'PerGame',
            'Outcome': '',
            'Location': '',
            'Month': '0',
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'GameSegment': '',
            'Period': '0',
            'ShotClockRange': '',
            'LastNGames': '0',
            'GameScope': '',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'StarterBench': '',
            'TwoWay': '0',
        },
        'table': 'defense_dashboard'
    },
    
    # =========================================================================
    # SCHEDULE (For rest/travel calculations)
    # =========================================================================
    'schedule': {
        'endpoint': 'leaguegamefinder',
        'params': {
            'LeagueID': '00',
            'Season': CURRENT_SEASON,
            'SeasonType': 'Regular Season',
            'PlayerOrTeam': 'T',
        },
        'table': 'schedule'
    },
}

# =============================================================================
# TEAM MAPPINGS (For geo calculations)
# =============================================================================
TEAM_LOCATIONS = {
    'ATL': {'city': 'Atlanta', 'lat': 33.7573, 'lon': -84.3963, 'timezone': 'America/New_York', 'altitude': 1050},
    'BOS': {'city': 'Boston', 'lat': 42.3662, 'lon': -71.0621, 'timezone': 'America/New_York', 'altitude': 20},
    'BKN': {'city': 'Brooklyn', 'lat': 40.6826, 'lon': -73.9754, 'timezone': 'America/New_York', 'altitude': 30},
    'CHA': {'city': 'Charlotte', 'lat': 35.2251, 'lon': -80.8392, 'timezone': 'America/New_York', 'altitude': 751},
    'CHI': {'city': 'Chicago', 'lat': 41.8807, 'lon': -87.6742, 'timezone': 'America/Chicago', 'altitude': 594},
    'CLE': {'city': 'Cleveland', 'lat': 41.4965, 'lon': -81.6882, 'timezone': 'America/New_York', 'altitude': 653},
    'DAL': {'city': 'Dallas', 'lat': 32.7905, 'lon': -96.8103, 'timezone': 'America/Chicago', 'altitude': 430},
    'DEN': {'city': 'Denver', 'lat': 39.7487, 'lon': -105.0077, 'timezone': 'America/Denver', 'altitude': 5280},
    'DET': {'city': 'Detroit', 'lat': 42.3411, 'lon': -83.0552, 'timezone': 'America/Detroit', 'altitude': 600},
    'GSW': {'city': 'San Francisco', 'lat': 37.7680, 'lon': -122.3879, 'timezone': 'America/Los_Angeles', 'altitude': 52},
    'HOU': {'city': 'Houston', 'lat': 29.7508, 'lon': -95.3621, 'timezone': 'America/Chicago', 'altitude': 80},
    'IND': {'city': 'Indianapolis', 'lat': 39.7640, 'lon': -86.1555, 'timezone': 'America/Indiana/Indianapolis', 'altitude': 715},
    'LAC': {'city': 'Los Angeles', 'lat': 33.9425, 'lon': -118.2673, 'timezone': 'America/Los_Angeles', 'altitude': 233},
    'LAL': {'city': 'Los Angeles', 'lat': 34.0430, 'lon': -118.2673, 'timezone': 'America/Los_Angeles', 'altitude': 233},
    'MEM': {'city': 'Memphis', 'lat': 35.1382, 'lon': -90.0505, 'timezone': 'America/Chicago', 'altitude': 337},
    'MIA': {'city': 'Miami', 'lat': 25.7814, 'lon': -80.1870, 'timezone': 'America/New_York', 'altitude': 6},
    'MIL': {'city': 'Milwaukee', 'lat': 43.0436, 'lon': -87.9169, 'timezone': 'America/Chicago', 'altitude': 634},
    'MIN': {'city': 'Minneapolis', 'lat': 44.9795, 'lon': -93.2761, 'timezone': 'America/Chicago', 'altitude': 830},
    'NOP': {'city': 'New Orleans', 'lat': 29.9490, 'lon': -90.0821, 'timezone': 'America/Chicago', 'altitude': 3},
    'NYK': {'city': 'New York', 'lat': 40.7505, 'lon': -73.9934, 'timezone': 'America/New_York', 'altitude': 33},
    'OKC': {'city': 'Oklahoma City', 'lat': 35.4634, 'lon': -97.5151, 'timezone': 'America/Chicago', 'altitude': 1201},
    'ORL': {'city': 'Orlando', 'lat': 28.5392, 'lon': -81.3839, 'timezone': 'America/New_York', 'altitude': 82},
    'PHI': {'city': 'Philadelphia', 'lat': 39.9012, 'lon': -75.1720, 'timezone': 'America/New_York', 'altitude': 39},
    'PHX': {'city': 'Phoenix', 'lat': 33.4457, 'lon': -112.0712, 'timezone': 'America/Phoenix', 'altitude': 1086},
    'POR': {'city': 'Portland', 'lat': 45.5316, 'lon': -122.6668, 'timezone': 'America/Los_Angeles', 'altitude': 50},
    'SAC': {'city': 'Sacramento', 'lat': 38.5802, 'lon': -121.4997, 'timezone': 'America/Los_Angeles', 'altitude': 30},
    'SAS': {'city': 'San Antonio', 'lat': 29.4270, 'lon': -98.4375, 'timezone': 'America/Chicago', 'altitude': 650},
    'TOR': {'city': 'Toronto', 'lat': 43.6435, 'lon': -79.3791, 'timezone': 'America/Toronto', 'altitude': 249},
    'UTA': {'city': 'Salt Lake City', 'lat': 40.7683, 'lon': -111.9011, 'timezone': 'America/Denver', 'altitude': 4226},
    'WAS': {'city': 'Washington', 'lat': 38.8981, 'lon': -77.0209, 'timezone': 'America/New_York', 'altitude': 409},
}

# Team ID to abbreviation mapping
TEAM_ID_TO_ABBREV = {
    1610612737: 'ATL', 1610612738: 'BOS', 1610612751: 'BKN', 1610612766: 'CHA',
    1610612741: 'CHI', 1610612739: 'CLE', 1610612742: 'DAL', 1610612743: 'DEN',
    1610612765: 'DET', 1610612744: 'GSW', 1610612745: 'HOU', 1610612754: 'IND',
    1610612746: 'LAC', 1610612747: 'LAL', 1610612763: 'MEM', 1610612748: 'MIA',
    1610612749: 'MIL', 1610612750: 'MIN', 1610612740: 'NOP', 1610612752: 'NYK',
    1610612760: 'OKC', 1610612753: 'ORL', 1610612755: 'PHI', 1610612756: 'PHX',
    1610612757: 'POR', 1610612758: 'SAC', 1610612759: 'SAS', 1610612761: 'TOR',
    1610612762: 'UTA', 1610612764: 'WAS',
}

ABBREV_TO_TEAM_ID = {v: k for k, v in TEAM_ID_TO_ABBREV.items()}
