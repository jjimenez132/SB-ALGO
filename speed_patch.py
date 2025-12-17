#!/usr/bin/env python3
"""
SPEED PATCH FOR premium_dashboard.py
=====================================
This script shows you exactly what to change.

Run from your SB-ALGO directory:
    python3 speed_patch.py
"""

INSTRUCTIONS = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SB-ALGO SPEED OPTIMIZATION PATCH                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  STEP 1: Copy fast_loader.py to your SB-ALGO folder                        ║
║                                                                              ║
║  STEP 2: Add this import near the TOP of premium_dashboard.py (after        ║
║          other imports, around line 15):                                    ║
║                                                                              ║
║      import fast_loader                                                      ║
║                                                                              ║
║  STEP 3: Replace the database functions with fast_loader calls.             ║
║          See the specific replacements below.                               ║
║                                                                              ║
║  STEP 4: Add session_state caching for edges (see code below)              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ============================================================
# CODE TO ADD NEAR TOP OF premium_dashboard.py (after imports)
# ============================================================

TOP_CODE = '''
# ========== SPEED LAYER IMPORT ==========
import fast_loader

# ========== LOAD EDGES ONCE AT STARTUP ==========
# This runs the algo ONCE and caches in session_state
if "edges_loaded" not in st.session_state:
    with st.spinner("🧠 Loading algorithm..."):
        st.session_state.game_edges, st.session_state.prop_edges = fast_loader.get_all_edges()
        st.session_state.edges_loaded = True

# Global references for use throughout the app
game_edges = st.session_state.game_edges
prop_edges = st.session_state.prop_edges
# ==========================================
'''

# ============================================================
# FUNCTION REPLACEMENTS
# ============================================================

REPLACEMENTS = '''
╔══════════════════════════════════════════════════════════════════════════════╗
║                         FUNCTION REPLACEMENTS                                ║
╠══════════════════════════════════════════════════════════════════════════════╣

1. REPLACE get_dashboard_metrics(engine) calls with:
   ─────────────────────────────────────────────────
   OLD: dashboard_data = get_dashboard_metrics(engine)
   NEW: dashboard_data = fast_loader.load_dashboard_metrics()

2. REPLACE get_todays_games(engine) calls with:
   ─────────────────────────────────────────────────
   OLD: todays_games = get_todays_games(engine)
   NEW: todays_games = fast_loader.load_todays_games()

3. REPLACE get_recent_team_record(engine, team) calls with:
   ─────────────────────────────────────────────────
   OLD: home_record = get_recent_team_record(engine, home)
   NEW: home_record = fast_loader.get_team_record(home)

4. REPLACE get_hot_teams(engine) calls with:
   ─────────────────────────────────────────────────
   OLD: hot_teams_df = get_hot_teams(engine, 5)
   NEW: hot_teams_df = fast_loader.get_hot_teams(5)

5. REPLACE get_cold_teams(engine) calls with:
   ─────────────────────────────────────────────────
   OLD: cold_teams_df = get_cold_teams(engine, 5)
   NEW: cold_teams_df = fast_loader.get_cold_teams(5)

6. DELETE all repeated analyze_games() / analyze_props() calls:
   ─────────────────────────────────────────────────
   OLD: 
       g_edges = analyze_games()
       p_edges = analyze_props()
   
   NEW: 
       # Already loaded at startup - just use the global variables
       # game_edges and prop_edges are available everywhere

7. WRAP AI/HEAVY SECTIONS in lazy-load blocks:
   ─────────────────────────────────────────────────
   OLD:
       ai_analysis = algo_ai.analyze_game(game_data)
       st.markdown(ai_analysis)
   
   NEW:
       if st.button("🧠 Generate AI Analysis", key=f"ai_{game_id}"):
           with st.spinner("Analyzing..."):
               ai_analysis = algo_ai.analyze_game(game_data)
               st.markdown(ai_analysis)

╚══════════════════════════════════════════════════════════════════════════════╝
'''

# ============================================================
# SED COMMANDS FOR AUTOMATIC PATCHING
# ============================================================

SED_COMMANDS = '''
# Run these commands in your terminal to auto-patch:

cd ~/Desktop/SB-ALGO

# 1. Add fast_loader import after the other imports
sed -i '' '/^from algo_ai import get_algo_ai/a\\
import fast_loader
' premium_dashboard.py

# 2. Replace get_dashboard_metrics calls
sed -i '' 's/get_dashboard_metrics(engine)/fast_loader.load_dashboard_metrics()/g' premium_dashboard.py

# 3. Replace get_todays_games calls  
sed -i '' 's/get_todays_games(engine)/fast_loader.load_todays_games()/g' premium_dashboard.py

# 4. Replace get_hot_teams calls
sed -i '' 's/get_hot_teams(engine, /fast_loader.get_hot_teams(/g' premium_dashboard.py
sed -i '' 's/get_hot_teams(engine)/fast_loader.get_hot_teams(5)/g' premium_dashboard.py

# 5. Replace get_cold_teams calls
sed -i '' 's/get_cold_teams(engine, /fast_loader.get_cold_teams(/g' premium_dashboard.py
sed -i '' 's/get_cold_teams(engine)/fast_loader.get_cold_teams(5)/g' premium_dashboard.py

# 6. Replace get_recent_team_record calls
sed -i '' 's/get_recent_team_record(engine, /fast_loader.get_team_record(/g' premium_dashboard.py
'''

# ============================================================
# SESSION STATE CODE BLOCK
# ============================================================

SESSION_STATE_CODE = '''
# ============================================================
# ADD THIS BLOCK AFTER THE IMPORTS AND BEFORE THE TABS
# (Around line 350, after "engine = get_db_engine()")
# ============================================================

# ========== SPEED OPTIMIZATION: Load algo data ONCE ==========
if "edges_loaded" not in st.session_state:
    try:
        game_edges, prop_edges = fast_loader.get_all_edges()
        st.session_state.game_edges = game_edges
        st.session_state.prop_edges = prop_edges
        st.session_state.edges_loaded = True
    except Exception as e:
        st.session_state.game_edges = []
        st.session_state.prop_edges = []
        st.session_state.edges_loaded = True
        print(f"Edge loading error: {e}")

# Use these throughout the app instead of calling analyze_games()/analyze_props()
game_edges = st.session_state.game_edges
prop_edges = st.session_state.prop_edges
# ===============================================================
'''

def main():
    print(INSTRUCTIONS)
    print("\n" + "="*80)
    print("CODE TO ADD NEAR TOP (after imports):")
    print("="*80)
    print(TOP_CODE)
    
    print("\n" + "="*80)
    print("SESSION STATE BLOCK (after engine = get_db_engine()):")
    print("="*80)
    print(SESSION_STATE_CODE)
    
    print(REPLACEMENTS)
    
    print("\n" + "="*80)
    print("AUTOMATIC SED COMMANDS (optional):")
    print("="*80)
    print(SED_COMMANDS)
    
    print("\n" + "="*80)
    print("EXPECTED RESULTS:")
    print("="*80)
    print("""
    BEFORE: 3-5 second page loads, multiple DB queries per interaction
    AFTER:  <100ms page loads, data cached in RAM
    
    The key insight: 
    - lru_cache in a separate module = data stays in RAM
    - Streamlit reruns the script, but fast_loader's cache persists
    - First load: ~1-2 seconds (cold cache)
    - Subsequent loads: ~50-100ms (hot cache)
    """)

if __name__ == "__main__":
    main()
