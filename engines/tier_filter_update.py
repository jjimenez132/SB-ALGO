"""
This script updates meta_merge_engine_v4.py with the final tiered filters.
Run this to apply the changes.
"""

# The new VEGAS_FILTERS section to replace the old one
NEW_VEGAS_FILTERS = '''
# =============================================================================
# VEGAS FILTERS v3.0 - TIERED SYSTEM (Jan 2026)
# =============================================================================
# BACKTEST: Dec 1, 2025 - Jan 25, 2026 (56 days)
# HEADLINE (T1+Games): 108-27 (80.0%) | 2.41/day
# FULL VOLUME (All): 135-42 (76.3%) | 3.16/day
# =============================================================================

VEGAS_FILTERS = {
    # =========================================================================
    # TIER 1: PREMIUM PICKS (80.4% win rate) - 1.0 unit stakes
    # =========================================================================
    
    # PTS OVER T1: Edge>=25%, CV<=0.40, Proj>=22 → 13-3 (81.2%)
    'prop_pts_over_t1': {
        'edge_min': 25,
        'cv_max': 0.40,
        'min_proj': 22,
        'tier': 1,
        'enabled': True,
    },
    
    # PTS UNDER T1: Edge>=18%, CV<=0.40, Proj>=20 → 14-3 (82.4%)
    'prop_pts_under_t1': {
        'edge_max': -18,
        'cv_max': 0.40,
        'min_proj': 20,
        'tier': 1,
        'enabled': True,
    },
    
    # REB OVER T1: Edge>=15%, CV<=0.40, Proj>=11 → 10-3 (76.9%)
    'prop_reb_over_t1': {
        'edge_min': 15,
        'cv_max': 0.40,
        'min_proj': 11,
        'tier': 1,
        'enabled': True,
    },
    
    # REB UNDER T1: Edge>=15%, CV<=0.45, Proj>=8 → 12-3 (80.0%)
    'prop_reb_under_t1': {
        'edge_max': -15,
        'cv_max': 0.45,
        'min_proj': 8,
        'tier': 1,
        'enabled': True,
    },
    
    # AST OVER T1: Edge>=25%, CV<=0.40, Proj>=8 → 11-2 (84.6%)
    'prop_ast_over_t1': {
        'edge_min': 25,
        'cv_max': 0.40,
        'min_proj': 8,
        'tier': 1,
        'enabled': True,
    },
    
    # AST UNDER T1: Edge>=15%, CV<=0.45, Proj>=6 → 11-3 (78.6%)
    'prop_ast_under_t1': {
        'edge_max': -15,
        'cv_max': 0.45,
        'min_proj': 6,
        'tier': 1,
        'enabled': True,
    },
    
    # 3PM UNDER T1: Edge>=22%, CV<=0.45, Proj>=0 → 11-3 (78.6%)
    'prop_3pm_under_t1': {
        'edge_max': -22,
        'cv_max': 0.45,
        'min_proj': 0,
        'tier': 1,
        'enabled': True,
    },
    
    # =========================================================================
    # TIER 2: VOLUME PICKS (64.3% incremental) - 0.5 unit stakes
    # Only applies if pick does NOT qualify for Tier 1
    # =========================================================================
    
    # PTS OVER T2: Edge>=22%, CV<=0.40, Proj>=22 → incremental 1-2
    'prop_pts_over_t2': {
        'edge_min': 22,
        'cv_max': 0.40,
        'min_proj': 22,
        'tier': 2,
        'enabled': True,
    },
    
    # PTS UNDER T2: Edge>=16%, CV<=0.40, Proj>=20 → incremental 4-3
    'prop_pts_under_t2': {
        'edge_max': -16,
        'cv_max': 0.40,
        'min_proj': 20,
        'tier': 2,
        'enabled': True,
    },
    
    # REB OVER T2: Edge>=14%, CV<=0.50, Proj>=11 → incremental 1-1
    'prop_reb_over_t2': {
        'edge_min': 14,
        'cv_max': 0.50,
        'min_proj': 11,
        'tier': 2,
        'enabled': True,
    },
    
    # REB UNDER T2: Edge>=20%, CV<=0.48, Proj>=7 → incremental 5-2
    'prop_reb_under_t2': {
        'edge_max': -20,
        'cv_max': 0.48,
        'min_proj': 7,
        'tier': 2,
        'enabled': True,
    },
    
    # AST OVER T2: Edge>=25%, CV<=0.35, Proj>=7 → incremental 1-1
    'prop_ast_over_t2': {
        'edge_min': 25,
        'cv_max': 0.35,
        'min_proj': 7,
        'tier': 2,
        'enabled': True,
    },
    
    # AST UNDER T2: Edge>=8%, CV<=0.45, Proj>=6 → incremental 15-5 (75%) 🔥 KEY VALUE
    'prop_ast_under_t2': {
        'edge_max': -8,
        'cv_max': 0.45,
        'min_proj': 6,
        'tier': 2,
        'enabled': True,
    },
    
    # 3PM UNDER T2: Edge>=20%, CV<=0.45, Proj>=0 → incremental 0-1
    'prop_3pm_under_t2': {
        'edge_max': -20,
        'cv_max': 0.45,
        'min_proj': 0,
        'tier': 2,
        'enabled': True,
    },
    
    # =========================================================================
    # GAME FILTERS (Tier 1 only - 78.8% win rate)
    # =========================================================================
    'game_moneyline': {
        'net_diff_min': 5,
        'opp_def_rating_min': 114,
        'opp_off_rating_max': 112,
        'tier': 1,
        'enabled': True,
    },
    'game_under': {
        'combined_def_max': 226,
        'combined_pace_max': 198,
        'book_total_min': 225,
        'book_total_max': 232,
        'tier': 1,
        'enabled': True,
    },
    'game_home_dog': {
        'spread_min': 7,
        'opp_net_max': 5,
        'tier': 1,
        'enabled': True,
    },
    
    # =========================================================================
    # DISABLED FILTERS
    # =========================================================================
    'prop_pra': {
        'edge_min': 15,
        'cv_max': 0.25,
        'min_proj': 35,
        'tier': 0,
        'enabled': False,  # 44.4% backtest
    },
    'prop_ra': {
        'edge_min': 18,
        'cv_max': 0.38,
        'min_proj': 11,
        'tier': 0,
        'enabled': False,  # 56.2% backtest
    },
}

def get_prop_tier(stat, is_over, edge_pct, cv, proj):
    """
    Determine which tier a prop bet belongs to.
    Returns: (tier, filter_key) where tier is 1, 2, or 0 (no bet)
    
    IMPORTANT: Check Tier 1 FIRST. If it qualifies for T1, don't check T2.
    """
    direction = 'over' if is_over else 'under'
    
    # Map stat names
    stat_map = {'pts': 'pts', 'reb': 'reb', 'ast': 'ast', '3pm': '3pm', 'fg3m': '3pm'}
    stat_key = stat_map.get(stat, stat)
    
    # Build filter keys
    t1_key = f'prop_{stat_key}_{direction}_t1'
    t2_key = f'prop_{stat_key}_{direction}_t2'
    
    # Check Tier 1 first
    if t1_key in VEGAS_FILTERS:
        f = VEGAS_FILTERS[t1_key]
        if f.get('enabled', False):
            cv_ok = cv <= f.get('cv_max', 1.0)
            proj_ok = proj >= f.get('min_proj', 0)
            
            if is_over:
                edge_ok = edge_pct >= f.get('edge_min', 100)
            else:
                edge_ok = edge_pct <= f.get('edge_max', -100)
            
            if cv_ok and proj_ok and edge_ok:
                return 1, t1_key
    
    # Check Tier 2 only if NOT Tier 1
    if t2_key in VEGAS_FILTERS:
        f = VEGAS_FILTERS[t2_key]
        if f.get('enabled', False):
            cv_ok = cv <= f.get('cv_max', 1.0)
            proj_ok = proj >= f.get('min_proj', 0)
            
            if is_over:
                edge_ok = edge_pct >= f.get('edge_min', 100)
            else:
                edge_ok = edge_pct <= f.get('edge_max', -100)
            
            if cv_ok and proj_ok and edge_ok:
                return 2, t2_key
    
    return 0, None

def get_unit_size(tier):
    """Returns unit size based on tier"""
    if tier == 1:
        return 1.0
    elif tier == 2:
        return 0.5
    return 0
'''

print("=" * 70)
print("TIER FILTER UPDATE")
print("=" * 70)
print(NEW_VEGAS_FILTERS)
print("\n\nCopy the above into meta_merge_engine_v4.py")
print("Replace the existing VEGAS_FILTERS section (around lines 160-320)")
