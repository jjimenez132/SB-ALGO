"""
Database Module
SQLite setup, schema definitions, and query utilities
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
from config import DB_PATH, DATA_DIR


def get_connection():
    """Get database connection with row factory for dict-like access"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize all database tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # =========================================================================
    # METADATA TABLE (Track pull times)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pull_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_type TEXT NOT NULL,
            pull_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            records_pulled INTEGER,
            status TEXT,
            error_message TEXT
        )
    ''')
    
    # =========================================================================
    # TEAM TABLES
    # =========================================================================
    
    # Team Base Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_base_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_NAME TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            FGM REAL,
            FGA REAL,
            FG_PCT REAL,
            FG3M REAL,
            FG3A REAL,
            FG3_PCT REAL,
            FTM REAL,
            FTA REAL,
            FT_PCT REAL,
            OREB REAL,
            DREB REAL,
            REB REAL,
            AST REAL,
            TOV REAL,
            STL REAL,
            BLK REAL,
            BLKA REAL,
            PF REAL,
            PFD REAL,
            PTS REAL,
            PLUS_MINUS REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # Team Advanced Stats (ORtg, DRtg, Net Rating, Pace, etc.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_advanced_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_NAME TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            E_OFF_RATING REAL,
            OFF_RATING REAL,
            E_DEF_RATING REAL,
            DEF_RATING REAL,
            E_NET_RATING REAL,
            NET_RATING REAL,
            AST_PCT REAL,
            AST_TO REAL,
            AST_RATIO REAL,
            OREB_PCT REAL,
            DREB_PCT REAL,
            REB_PCT REAL,
            E_TM_TOV_PCT REAL,
            TM_TOV_PCT REAL,
            EFG_PCT REAL,
            TS_PCT REAL,
            USG_PCT REAL,
            E_USG_PCT REAL,
            E_PACE REAL,
            PACE REAL,
            PACE_PER40 REAL,
            POSS REAL,
            PIE REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # Team Four Factors
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_four_factors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_NAME TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            EFG_PCT REAL,
            FTA_RATE REAL,
            TM_TOV_PCT REAL,
            OREB_PCT REAL,
            OPP_EFG_PCT REAL,
            OPP_FTA_RATE REAL,
            OPP_TOV_PCT REAL,
            OPP_OREB_PCT REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # Team Scoring Breakdown
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_scoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_NAME TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            PCT_FGA_2PT REAL,
            PCT_FGA_3PT REAL,
            PCT_PTS_2PT REAL,
            PCT_PTS_2PT_MR REAL,
            PCT_PTS_3PT REAL,
            PCT_PTS_FB REAL,
            PCT_PTS_FT REAL,
            PCT_PTS_OFF_TOV REAL,
            PCT_PTS_PAINT REAL,
            PCT_AST_2PM REAL,
            PCT_UAST_2PM REAL,
            PCT_AST_3PM REAL,
            PCT_UAST_3PM REAL,
            PCT_AST_FGM REAL,
            PCT_UAST_FGM REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # Team Opponent Stats (Defense)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_opponent_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_NAME TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            OPP_FGM REAL,
            OPP_FGA REAL,
            OPP_FG_PCT REAL,
            OPP_FG3M REAL,
            OPP_FG3A REAL,
            OPP_FG3_PCT REAL,
            OPP_FTM REAL,
            OPP_FTA REAL,
            OPP_FT_PCT REAL,
            OPP_OREB REAL,
            OPP_DREB REAL,
            OPP_REB REAL,
            OPP_AST REAL,
            OPP_TOV REAL,
            OPP_STL REAL,
            OPP_BLK REAL,
            OPP_BLKA REAL,
            OPP_PF REAL,
            OPP_PFD REAL,
            OPP_PTS REAL,
            PLUS_MINUS REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # Team Hustle Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_hustle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_NAME TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            MIN REAL,
            CONTESTED_SHOTS REAL,
            CONTESTED_SHOTS_2PT REAL,
            CONTESTED_SHOTS_3PT REAL,
            DEFLECTIONS REAL,
            CHARGES_DRAWN REAL,
            SCREEN_ASSISTS REAL,
            SCREEN_AST_PTS REAL,
            OFF_LOOSE_BALLS_RECOVERED REAL,
            DEF_LOOSE_BALLS_RECOVERED REAL,
            LOOSE_BALLS_RECOVERED REAL,
            OFF_BOXOUTS REAL,
            DEF_BOXOUTS REAL,
            BOX_OUTS REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # Team Clutch Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_clutch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_NAME TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            FGM REAL,
            FGA REAL,
            FG_PCT REAL,
            FG3M REAL,
            FG3A REAL,
            FG3_PCT REAL,
            FTM REAL,
            FTA REAL,
            FT_PCT REAL,
            OREB REAL,
            DREB REAL,
            REB REAL,
            AST REAL,
            TOV REAL,
            STL REAL,
            BLK REAL,
            PF REAL,
            PTS REAL,
            PLUS_MINUS REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # =========================================================================
    # PLAYER TABLES
    # =========================================================================
    
    # Player Base Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_base_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            FGM REAL,
            FGA REAL,
            FG_PCT REAL,
            FG3M REAL,
            FG3A REAL,
            FG3_PCT REAL,
            FTM REAL,
            FTA REAL,
            FT_PCT REAL,
            OREB REAL,
            DREB REAL,
            REB REAL,
            AST REAL,
            TOV REAL,
            STL REAL,
            BLK REAL,
            BLKA REAL,
            PF REAL,
            PFD REAL,
            PTS REAL,
            PLUS_MINUS REAL,
            NBA_FANTASY_PTS REAL,
            DD2 INTEGER,
            TD3 INTEGER,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Advanced Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_advanced_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            E_OFF_RATING REAL,
            OFF_RATING REAL,
            E_DEF_RATING REAL,
            DEF_RATING REAL,
            E_NET_RATING REAL,
            NET_RATING REAL,
            AST_PCT REAL,
            AST_TO REAL,
            AST_RATIO REAL,
            OREB_PCT REAL,
            DREB_PCT REAL,
            REB_PCT REAL,
            E_TM_TOV_PCT REAL,
            TM_TOV_PCT REAL,
            EFG_PCT REAL,
            TS_PCT REAL,
            USG_PCT REAL,
            E_USG_PCT REAL,
            E_PACE REAL,
            PACE REAL,
            PACE_PER40 REAL,
            POSS REAL,
            PIE REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Scoring Breakdown
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_scoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            PCT_FGA_2PT REAL,
            PCT_FGA_3PT REAL,
            PCT_PTS_2PT REAL,
            PCT_PTS_2PT_MR REAL,
            PCT_PTS_3PT REAL,
            PCT_PTS_FB REAL,
            PCT_PTS_FT REAL,
            PCT_PTS_OFF_TOV REAL,
            PCT_PTS_PAINT REAL,
            PCT_AST_2PM REAL,
            PCT_UAST_2PM REAL,
            PCT_AST_3PM REAL,
            PCT_UAST_3PM REAL,
            PCT_AST_FGM REAL,
            PCT_UAST_FGM REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Usage Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            USG_PCT REAL,
            PCT_FGM REAL,
            PCT_FGA REAL,
            PCT_FG3M REAL,
            PCT_FG3A REAL,
            PCT_FTM REAL,
            PCT_FTA REAL,
            PCT_OREB REAL,
            PCT_DREB REAL,
            PCT_REB REAL,
            PCT_AST REAL,
            PCT_TOV REAL,
            PCT_STL REAL,
            PCT_BLK REAL,
            PCT_BLKA REAL,
            PCT_PF REAL,
            PCT_PFD REAL,
            PCT_PTS REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Tracking - Possessions/Touches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_tracking_possessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            MIN REAL,
            TOUCHES REAL,
            FRONT_CT_TOUCHES REAL,
            TIME_OF_POSS REAL,
            AVG_SEC_PER_TOUCH REAL,
            AVG_DRIB_PER_TOUCH REAL,
            PTS_PER_TOUCH REAL,
            ELBOW_TOUCHES REAL,
            POST_TOUCHES REAL,
            PAINT_TOUCHES REAL,
            PTS_PER_ELBOW_TOUCH REAL,
            PTS_PER_POST_TOUCH REAL,
            PTS_PER_PAINT_TOUCH REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Tracking - Passing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_tracking_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            MIN REAL,
            PASSES_MADE REAL,
            PASSES_RECEIVED REAL,
            AST REAL,
            SECONDARY_AST REAL,
            POTENTIAL_AST REAL,
            AST_PTS_CREATED REAL,
            AST_ADJ REAL,
            AST_TO_PASS_PCT REAL,
            AST_TO_PASS_PCT_ADJ REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Tracking - Rebounding
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_tracking_rebounding (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            MIN REAL,
            OREB REAL,
            OREB_CONTEST REAL,
            OREB_UNCONTEST REAL,
            OREB_CONTEST_PCT REAL,
            OREB_CHANCES REAL,
            OREB_CHANCE_PCT REAL,
            OREB_CHANCE_DEFER REAL,
            OREB_CHANCE_PCT_ADJ REAL,
            AVG_OREB_DIST REAL,
            DREB REAL,
            DREB_CONTEST REAL,
            DREB_UNCONTEST REAL,
            DREB_CONTEST_PCT REAL,
            DREB_CHANCES REAL,
            DREB_CHANCE_PCT REAL,
            DREB_CHANCE_DEFER REAL,
            DREB_CHANCE_PCT_ADJ REAL,
            AVG_DREB_DIST REAL,
            REB REAL,
            REB_CONTEST REAL,
            REB_UNCONTEST REAL,
            REB_CONTEST_PCT REAL,
            REB_CHANCES REAL,
            REB_CHANCE_PCT REAL,
            REB_CHANCE_DEFER REAL,
            REB_CHANCE_PCT_ADJ REAL,
            AVG_REB_DIST REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Hustle Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_hustle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            MIN REAL,
            CONTESTED_SHOTS REAL,
            CONTESTED_SHOTS_2PT REAL,
            CONTESTED_SHOTS_3PT REAL,
            DEFLECTIONS REAL,
            CHARGES_DRAWN REAL,
            SCREEN_ASSISTS REAL,
            SCREEN_AST_PTS REAL,
            OFF_LOOSE_BALLS_RECOVERED REAL,
            DEF_LOOSE_BALLS_RECOVERED REAL,
            LOOSE_BALLS_RECOVERED REAL,
            OFF_BOXOUTS REAL,
            DEF_BOXOUTS REAL,
            BOX_OUTS REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player Clutch Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_clutch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            FGM REAL,
            FGA REAL,
            FG_PCT REAL,
            FG3M REAL,
            FG3A REAL,
            FG3_PCT REAL,
            FTM REAL,
            FTA REAL,
            FT_PCT REAL,
            OREB REAL,
            DREB REAL,
            REB REAL,
            AST REAL,
            TOV REAL,
            STL REAL,
            BLK REAL,
            PF REAL,
            PTS REAL,
            PLUS_MINUS REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # Player On/Off Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_on_off (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            GP INTEGER,
            MIN REAL,
            PLUS_MINUS REAL,
            OFF_RATING REAL,
            DEF_RATING REAL,
            NET_RATING REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # =========================================================================
    # SHOT ZONES TABLE
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_shot_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            -- Restricted Area
            RA_FGM REAL,
            RA_FGA REAL,
            RA_FG_PCT REAL,
            -- Paint (Non-RA)
            PAINT_FGM REAL,
            PAINT_FGA REAL,
            PAINT_FG_PCT REAL,
            -- Mid-Range
            MR_FGM REAL,
            MR_FGA REAL,
            MR_FG_PCT REAL,
            -- Left Corner 3
            LC3_FGM REAL,
            LC3_FGA REAL,
            LC3_FG_PCT REAL,
            -- Right Corner 3
            RC3_FGM REAL,
            RC3_FGA REAL,
            RC3_FG_PCT REAL,
            -- Above Break 3
            AB3_FGM REAL,
            AB3_FGA REAL,
            AB3_FG_PCT REAL,
            -- Backcourt
            BC_FGM REAL,
            BC_FGA REAL,
            BC_FG_PCT REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # =========================================================================
    # LINEUP STATS TABLE
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            GROUP_SET TEXT,
            GROUP_ID TEXT,
            GROUP_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            GP INTEGER,
            W INTEGER,
            L INTEGER,
            W_PCT REAL,
            MIN REAL,
            E_OFF_RATING REAL,
            OFF_RATING REAL,
            E_DEF_RATING REAL,
            DEF_RATING REAL,
            E_NET_RATING REAL,
            NET_RATING REAL,
            AST_PCT REAL,
            AST_TO REAL,
            AST_RATIO REAL,
            OREB_PCT REAL,
            DREB_PCT REAL,
            REB_PCT REAL,
            TM_TOV_PCT REAL,
            EFG_PCT REAL,
            TS_PCT REAL,
            E_PACE REAL,
            PACE REAL,
            PACE_PER40 REAL,
            POSS REAL,
            PIE REAL,
            UNIQUE(pull_date, GROUP_ID)
        )
    ''')
    
    # =========================================================================
    # DEFENSE DASHBOARD
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS defense_dashboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            AGE REAL,
            GP INTEGER,
            G INTEGER,
            FREQ REAL,
            D_FGM REAL,
            D_FGA REAL,
            D_FG_PCT REAL,
            NORMAL_FG_PCT REAL,
            PCT_PLUSMINUS REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    # =========================================================================
    # SCHEDULE TABLE
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            SEASON_ID TEXT,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            TEAM_NAME TEXT,
            GAME_ID TEXT,
            GAME_DATE DATE,
            MATCHUP TEXT,
            WL TEXT,
            MIN INTEGER,
            PTS INTEGER,
            FGM INTEGER,
            FGA INTEGER,
            FG_PCT REAL,
            FG3M INTEGER,
            FG3A INTEGER,
            FG3_PCT REAL,
            FTM INTEGER,
            FTA INTEGER,
            FT_PCT REAL,
            OREB INTEGER,
            DREB INTEGER,
            REB INTEGER,
            AST INTEGER,
            STL INTEGER,
            BLK INTEGER,
            TOV INTEGER,
            PF INTEGER,
            PLUS_MINUS INTEGER,
            UNIQUE(GAME_ID, TEAM_ID)
        )
    ''')
    
    # =========================================================================
    # ODDS TABLE
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            game_id TEXT,
            sport_key TEXT,
            sport_title TEXT,
            commence_time TIMESTAMP,
            home_team TEXT,
            away_team TEXT,
            bookmaker TEXT,
            market TEXT,
            outcome_name TEXT,
            outcome_price REAL,
            outcome_point REAL,
            UNIQUE(pull_timestamp, game_id, bookmaker, market, outcome_name)
        )
    ''')
    
    # =========================================================================
    # BPM/VORP TABLE (From Basketball Reference)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_bpm_vorp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_NAME TEXT,
            TEAM TEXT,
            AGE REAL,
            GP INTEGER,
            MP REAL,
            PER REAL,
            TS_PCT REAL,
            USG_PCT REAL,
            OWS REAL,
            DWS REAL,
            WS REAL,
            WS_48 REAL,
            OBPM REAL,
            DBPM REAL,
            BPM REAL,
            VORP REAL,
            UNIQUE(pull_date, PLAYER_NAME, TEAM)
        )
    ''')
    
    # =========================================================================
    # DERIVED STATS TABLE (Computed metrics)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS derived_player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            PLAYER_ID INTEGER,
            PLAYER_NAME TEXT,
            TEAM_ID INTEGER,
            -- Derived efficiency metrics
            PTS_PER_SHOT REAL,
            PTS_PER_TOUCH REAL,
            PTS_PER_POSS REAL,
            AST_TO_RATIO REAL,
            -- Volatility/Stability metrics
            USG_VOLATILITY REAL,
            MIN_VOLATILITY REAL,
            PTS_VOLATILITY REAL,
            ROLE_STABILITY REAL,
            -- Correlation coefficients
            PTS_AST_CORR REAL,
            PTS_REB_CORR REAL,
            AST_REB_CORR REAL,
            UNIQUE(pull_date, PLAYER_ID)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS derived_team_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_date DATE NOT NULL,
            TEAM_ID INTEGER,
            TEAM_ABBREVIATION TEXT,
            -- Schedule context
            REST_DAYS INTEGER,
            IS_B2B INTEGER,
            IS_3IN4 INTEGER,
            TRAVEL_DISTANCE REAL,
            TIMEZONE_CHANGE INTEGER,
            ALTITUDE_CHANGE REAL,
            -- Derived metrics
            BLOWOUT_RISK_INDEX REAL,
            PACE_VOLATILITY REAL,
            UNIQUE(pull_date, TEAM_ID)
        )
    ''')
    
    # =========================================================================
    # CREATE INDEXES
    # =========================================================================
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_team_base_date ON team_base_stats(pull_date)",
        "CREATE INDEX IF NOT EXISTS idx_team_base_team ON team_base_stats(TEAM_ID)",
        "CREATE INDEX IF NOT EXISTS idx_player_base_date ON player_base_stats(pull_date)",
        "CREATE INDEX IF NOT EXISTS idx_player_base_player ON player_base_stats(PLAYER_ID)",
        "CREATE INDEX IF NOT EXISTS idx_player_base_team ON player_base_stats(TEAM_ID)",
        "CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(GAME_DATE)",
        "CREATE INDEX IF NOT EXISTS idx_schedule_team ON schedule(TEAM_ID)",
        "CREATE INDEX IF NOT EXISTS idx_odds_time ON odds(pull_timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_id)",
    ]
    
    for stmt in index_statements:
        cursor.execute(stmt)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


def store_dataframe(df: pd.DataFrame, table_name: str, pull_date: str = None):
    """Store a DataFrame to a database table"""
    if pull_date is None:
        pull_date = datetime.now().strftime('%Y-%m-%d')
    
    df = df.copy()
    df['pull_date'] = pull_date
    
    conn = get_connection()
    
    # Get existing columns in table
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    # Filter DataFrame to only include columns that exist in the table
    df_cols = set(df.columns)
    valid_cols = list(df_cols.intersection(existing_cols))
    df_filtered = df[valid_cols]
    
    # Use INSERT OR REPLACE to handle duplicates
    df_filtered.to_sql(table_name, conn, if_exists='append', index=False, 
                       method='multi', chunksize=100)
    
    conn.commit()
    conn.close()
    
    return len(df_filtered)


def get_latest_data(table_name: str, pull_date: str = None) -> pd.DataFrame:
    """Get the latest data from a table"""
    conn = get_connection()
    
    if pull_date is None:
        query = f"""
            SELECT * FROM {table_name} 
            WHERE pull_date = (SELECT MAX(pull_date) FROM {table_name})
        """
    else:
        query = f"SELECT * FROM {table_name} WHERE pull_date = ?"
        
    df = pd.read_sql_query(query, conn, params=(pull_date,) if pull_date else None)
    conn.close()
    return df


def log_pull(pull_type: str, records: int, status: str, error: str = None):
    """Log a data pull to metadata table"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pull_metadata (pull_type, records_pulled, status, error_message)
        VALUES (?, ?, ?, ?)
    ''', (pull_type, records, status, error))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_database()
