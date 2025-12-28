# NBA Data Pipeline

A complete data pipeline for pulling, processing, and analyzing NBA statistics for sports betting models.

## 🎯 What This Does

This pipeline pulls **ALL** the NBA nerd stats you need for a betting algorithm:

### Stats Coverage

| Category | Metrics | Source |
|----------|---------|--------|
| **Efficiency** | ORtg, DRtg, Net Rating, eFG%, TS% | NBA.com |
| **Pace** | Pace, Possessions, Time of Possession | NBA.com |
| **Four Factors** | eFG%, TOV%, OREB%, FTr | NBA.com |
| **Player Advanced** | USG%, AST%, REB%, On/Off splits | NBA.com |
| **Tracking** | Touches, Passes, Secondary Assists | NBA.com |
| **Shot Zones** | Rim, Paint, Mid-Range, Corner 3, ATB 3 | NBA.com |
| **Defense** | Deflections, Contested Shots, Rim Protection | NBA.com |
| **Hustle** | Box Outs, Loose Balls, Charges Drawn | NBA.com |
| **Clutch** | All stats in Last 5 min, within 5 pts | NBA.com |
| **Lineups** | 5-man combo stats with Net Rating | NBA.com |
| **BPM/VORP** | Box Plus Minus, Value Over Replacement | BBRef |
| **Odds** | Spreads, Totals, Moneylines from 9+ books | Odds API |

### Derived Stats (Calculated)

- Points per Touch / Shot / Possession
- AST/TO Ratio
- Usage Elasticity
- Minutes Volatility
- Role Stability Score
- Stat Correlations (PTS↔AST, PTS↔REB, etc.)
- Rest Days, B2B, 3-in-4, 4-in-6
- Travel Distance (Haversine)
- Timezone Changes
- Altitude Adjustments
- Implied Probability
- Vig-Free Probability
- Closing Line Value (CLV)
- Kelly Criterion Sizing

## 📁 Project Structure

```
nba_data_pipeline/
├── config.py              # All configuration and API endpoints
├── database.py            # SQLite database setup and queries
├── run_daily.py           # Main daily pull script (cron this at 4 AM)
├── run_odds.py            # Game-day odds pulls (every 15 min)
│
├── pullers/
│   ├── nba_stats.py       # NBA.com API puller
│   ├── bbref.py           # Basketball-Reference scraper
│   └── odds.py            # The-Odds-API puller
│
├── calculators/
│   ├── derived_stats.py   # Meta-stat calculations
│   ├── schedule_context.py # Rest, travel, B2B analysis
│   └── odds_math.py       # EV, Kelly, CLV calculations
│
├── exporters/
│   └── feature_store.py   # Export model-ready features
│
└── data/
    └── nba_stats.db       # SQLite database (created on first run)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install pandas numpy requests
```

### 2. Run Your First Pull

```bash
# Test mode (quick verification)
python run_daily.py --test

# Full daily pull
python run_daily.py

# Quick pull (essential stats only)
python run_daily.py --quick
```

### 3. Set Up Odds API (Optional but Recommended)

Get a free API key at https://the-odds-api.com/ (500 requests/month free).

```bash
export ODDS_API_KEY=your_key_here
# Or edit config.py directly
```

```bash
# Pull current odds
python run_odds.py

# Pull and analyze for edges
python run_odds.py --analyze
```

### 4. Export Features for Your Model

```python
from exporters.feature_store import FeatureExporter

exporter = FeatureExporter()

# Get all team features as DataFrame
team_features = exporter.get_team_features()

# Get all player features
player_features = exporter.get_player_features()

# Get matchup-specific features
matchup = exporter.get_matchup_features(
    home_team_id=1610612747,  # Lakers
    away_team_id=1610612738   # Celtics
)

# Export everything to CSV
exporter.export_all()
```

## ⏰ Recommended Schedule

Set up cron jobs:

```cron
# Daily full pull at 4 AM ET (when NBA.com traffic is lowest)
0 4 * * * cd /path/to/nba_data_pipeline && python run_daily.py >> logs/daily.log 2>&1

# Odds pull every 15 minutes on game days (adjust days as needed)
*/15 17-23 * * * cd /path/to/nba_data_pipeline && python run_odds.py >> logs/odds.log 2>&1
```

## 📊 Database Schema

All data is stored in SQLite (`data/nba_stats.db`). Key tables:

**Team Tables:**
- `team_base_stats` - Basic counting stats
- `team_advanced_stats` - ORtg, DRtg, Net Rating, Pace
- `team_four_factors` - Dean Oliver's Four Factors
- `team_scoring` - Shot distribution breakdown
- `team_opponent_stats` - Defensive stats
- `team_hustle` - Deflections, contests, etc.
- `team_clutch` - Close game performance

**Player Tables:**
- `player_base_stats` - Basic counting stats
- `player_advanced_stats` - Efficiency metrics
- `player_scoring` - Shot distribution
- `player_usage` - Usage percentages
- `player_tracking_possessions` - Touches, time of possession
- `player_tracking_passes` - Passing metrics
- `player_tracking_rebounding` - Rebound opportunities
- `player_hustle` - Deflections, contests
- `player_clutch` - Close game performance
- `player_shot_zones` - Shot location breakdown
- `player_bpm_vorp` - BPM/VORP from BBRef

**Other Tables:**
- `lineups` - 5-man lineup combinations
- `defense_dashboard` - Individual defensive metrics
- `schedule` - Game schedule with results
- `odds` - Historical odds data
- `derived_player_stats` - Calculated meta-stats
- `derived_team_stats` - Calculated team meta-stats

## 🧮 Using the Calculators

### Odds Math

```python
from calculators.odds_math import OddsMathCalculator

calc = OddsMathCalculator()

# Convert odds
prob = calc.american_to_implied_prob(-150)  # 0.6 (60%)

# Calculate EV
ev = calc.calculate_ev_percentage(true_prob=0.55, american_odds=-110)  # +5.0%

# Kelly sizing
kelly = calc.kelly_criterion(true_prob=0.55, american_odds=-110)  # ~5.5%
half_kelly = calc.fractional_kelly(0.55, -110, fraction=0.5)  # ~2.75%

# CLV
clv = calc.calculate_clv(bet_odds=-110, closing_odds=-105)  # +2.38 cents

# Remove vig
no_vig1, no_vig2 = calc.calculate_no_vig_prob(-110, -110)  # 0.5, 0.5
```

### Schedule Context

```python
from calculators.schedule_context import ScheduleContextCalculator

calc = ScheduleContextCalculator()

# Calculate travel distance
dist = calc.calculate_travel_distance('LAL', 'BOS')  # ~2600 miles

# Estimate fatigue
context = {
    'REST_DAYS': 0,
    'IS_B2B': True,
    'IS_3IN4': True,
    'TRAVEL_DISTANCE': 2500,
    'IS_HIGH_ALTITUDE': True,
}
fatigue = calc.calculate_fatigue_score(context)  # 0-10 scale

# Net rating adjustment
adj = calc.estimate_performance_adjustment(context)  # -5.0 points
```

### Derived Stats

```python
from calculators.derived_stats import DerivedStatsCalculator

calc = DerivedStatsCalculator()

# Efficiency metrics
pts_per_shot = calc.calculate_points_per_shot(pts=25, fga=15, fta=8)
ast_to_ratio = calc.calculate_ast_to_ratio(ast=8, tov=2)

# From game logs DataFrame
volatility = calc.calculate_player_volatility_metrics(game_logs_df)
correlations = calc.calculate_stat_correlations(game_logs_df)
```

## ⚠️ Rate Limiting

The pipeline is designed to avoid rate limits:

- **NBA.com**: 1-second delays between calls, ~50 calls total per daily run
- **Basketball-Reference**: 3-second delays, weekly pulls only
- **Odds API**: One call gets all games (conserves 500/month limit)

## 🔧 Configuration

Edit `config.py` to customize:

- `CURRENT_SEASON` - NBA season (e.g., "2024-25")
- `ODDS_API_KEY` - Your Odds API key
- `NBA_DELAY_SECONDS` - Delay between NBA.com calls
- `TEAM_LOCATIONS` - Arena coordinates for travel calculations

## 📝 License

MIT License - use freely for personal betting models.

## 🤝 Contributing

Pull requests welcome! Areas that need work:
- Referee data scraping
- Play-by-play parsing
- Live game data
- More advanced derived stats

---

Built for the SB ALGO NBA Edge Engine 🏀📊
