"""
================================================================================
SB-ALGO FINAL FILTERS v2.1 (CLEANED)
================================================================================
Backtest: Dec 1, 2025 - Jan 25, 2026 (56 days)

HEADLINE (T1 + Games): 108-27 (80.0%) | 2.41/day | 1.0 units
FULL VOLUME (T1 + T2 + Games): 128-34 (79.0%) | 2.89/day | Mixed

TIER 1 Props: 82-20 (80.4%) | 1.82/day | 1.0 units
TIER 2 Props: 20-7 (74.1%) | 0.48/day | 0.5 units (reb_under + ast_under ONLY)
Games: 26-7 (78.8%) | 0.59/day | 1.0 units
================================================================================
"""

# =============================================================================
# TIER 1: PREMIUM PICKS (80.4% win rate) - 1.0 unit stakes
# =============================================================================
TIER_1_FILTERS = {
    'pts_over': {
        'edge': 0.25,      # ≥25%
        'cv': 0.40,        # ≤0.40
        'proj': 22,        # ≥22
        'backtest': '13-3 (81.2%)'
    },
    'pts_under': {
        'edge': 0.18,      # ≥18%
        'cv': 0.40,        # ≤0.40
        'proj': 20,        # ≥20
        'backtest': '14-3 (82.4%)'
    },
    'reb_over': {
        'edge': 0.15,      # ≥15%
        'cv': 0.40,        # ≤0.40
        'proj': 11,        # ≥11
        'backtest': '10-3 (76.9%)'
    },
    'reb_under': {
        'edge': 0.15,      # ≥15%
        'cv': 0.45,        # ≤0.45
        'proj': 8,         # ≥8
        'backtest': '12-3 (80.0%)'
    },
    'ast_over': {
        'edge': 0.25,      # ≥25%
        'cv': 0.40,        # ≤0.40
        'proj': 8,         # ≥8
        'backtest': '11-2 (84.6%)'
    },
    'ast_under': {
        'edge': 0.15,      # ≥15%
        'cv': 0.45,        # ≤0.45
        'proj': 6,         # ≥6
        'backtest': '11-3 (78.6%)'
    },
    '3pm_under': {
        'edge': 0.22,      # ≥22%
        'cv': 0.45,        # ≤0.45
        'proj': 0,         # ≥0 (any)
        'backtest': '11-3 (78.6%)'
    },
}

# =============================================================================
# TIER 2: VOLUME PICKS (74.1% win rate) - 0.5 unit stakes
# Only 2 filters enabled (reb_under + ast_under) - others were <70%
# =============================================================================
TIER_2_FILTERS = {
    'reb_under': {
        'edge': 0.20,      # ≥20% (loosened from T1's 15%)
        'cv': 0.48,        # ≤0.48
        'proj': 7,         # ≥7 (loosened from T1's 8)
        'backtest': '5-2 (71.4%)',
        'enabled': True,
    },
    'ast_under': {
        'edge': 0.08,      # ≥8% (MAJOR LOOSEN from T1's 15%) - KEY VALUE
        'cv': 0.45,        # ≤0.45
        'proj': 6,         # ≥6
        'backtest': '15-5 (75.0%) 🔥',
        'enabled': True,
    },
    # DISABLED - Poor backtest results
    'pts_over': {'enabled': False, 'backtest': '1-2 (33.3%)'},
    'pts_under': {'enabled': False, 'backtest': '4-3 (57.1%)'},
    'reb_over': {'enabled': False, 'backtest': '1-1 (50.0%)'},
    'ast_over': {'enabled': False, 'backtest': '1-1 (50.0%)'},
    '3pm_under': {'enabled': False, 'backtest': '0-1 (0.0%)'},
}

# =============================================================================
# GAME FILTERS (Tier 1 only - 78.8% win rate) - 1.0 unit stakes
# =============================================================================
GAME_FILTERS = {
    'moneyline': {
        'net_rating': 5,           # Team net rating ≥5
        'opp_def_rating': 114,     # Opponent defensive rating ≥114
        'opp_off_rating': 112,     # Opponent offensive rating ≤112
        'backtest': '4-0 (100%)'
    },
    'under': {
        'combined_def': 226,       # Combined defensive rating ≤226
        'combined_pace': 198,      # Combined pace ≤198
        'book_total_min': 225,     # Book total ≥225
        'book_total_max': 232,     # Book total ≤232
        'backtest': '9-2 (81.8%)'
    },
    'home_dog': {
        'spread': 7,               # Home spread ≥7 (underdog by 7+)
        'opp_net': 5,              # Opponent net rating ≤5
        'backtest': '12-4 (75.0%)'
    },
}

# =============================================================================
# SUMMARY
# =============================================================================
SYSTEM_SUMMARY = """
╔══════════════════════════════════════════════════════════════════════╗
║                    SB-ALGO FINAL SYSTEM v2.1                        ║
╠══════════════════════════════════════════════════════════════════════╣
║  BACKTEST: Dec 1, 2025 - Jan 25, 2026 (56 days)                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  COMPONENT          │ RECORD    │ WIN%   │ PICKS/DAY │ STAKES      ║
╠══════════════════════════════════════════════════════════════════════╣
║  Tier 1 Props       │ 82-20     │ 80.4%  │ 1.82      │ 1.0 units   ║
║  Tier 2 Props       │ 20-7      │ 74.1%  │ 0.48      │ 0.5 units   ║
║  Games              │ 26-7      │ 78.8%  │ 0.59      │ 1.0 units   ║
╠══════════════════════════════════════════════════════════════════════╣
║  HEADLINE (T1+Games)│ 108-27    │ 80.0%  │ 2.41      │ Marketing   ║
║  FULL VOLUME        │ 128-34    │ 79.0%  │ 2.89      │ Subscribers ║
╚══════════════════════════════════════════════════════════════════════╝

TIER 2 ENABLED FILTERS (74.1%):
  ✅ reb_under: 5-2 (71.4%)
  ✅ ast_under: 15-5 (75.0%) 🔥

TIER 2 DISABLED FILTERS (<70%):
  ❌ pts_over: 1-2 (33.3%)
  ❌ pts_under: 4-3 (57.1%)
  ❌ reb_over: 1-1 (50.0%)
  ❌ ast_over: 1-1 (50.0%)
  ❌ 3pm_under: 0-1 (0.0%)
"""

if __name__ == "__main__":
    print(SYSTEM_SUMMARY)
