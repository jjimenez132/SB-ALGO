#!/usr/bin/env python3
"""
NBA Games Manager - Add and Update Daily Games
With team name validation and proper data structure
"""

import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# ============================================
# OFFICIAL NBA TEAMS (2024-25 Season)
# ============================================
NBA_TEAMS = {
    # Eastern Conference - Atlantic
    "BOS": {"full": "Boston Celtics", "city": "Boston", "abbrev": "BOS"},
    "BKN": {"full": "Brooklyn Nets", "city": "Brooklyn", "abbrev": "BKN"},
    "NYK": {"full": "New York Knicks", "city": "New York", "abbrev": "NYK"},
    "PHI": {"full": "Philadelphia 76ers", "city": "Philadelphia", "abbrev": "PHI"},
    "TOR": {"full": "Toronto Raptors", "city": "Toronto", "abbrev": "TOR"},
    
    # Eastern Conference - Central
    "CHI": {"full": "Chicago Bulls", "city": "Chicago", "abbrev": "CHI"},
    "CLE": {"full": "Cleveland Cavaliers", "city": "Cleveland", "abbrev": "CLE"},
    "DET": {"full": "Detroit Pistons", "city": "Detroit", "abbrev": "DET"},
    "IND": {"full": "Indiana Pacers", "city": "Indiana", "abbrev": "IND"},
    "MIL": {"full": "Milwaukee Bucks", "city": "Milwaukee", "abbrev": "MIL"},
    
    # Eastern Conference - Southeast
    "ATL": {"full": "Atlanta Hawks", "city": "Atlanta", "abbrev": "ATL"},
    "CHA": {"full": "Charlotte Hornets", "city": "Charlotte", "abbrev": "CHA"},
    "MIA": {"full": "Miami Heat", "city": "Miami", "abbrev": "MIA"},
    "ORL": {"full": "Orlando Magic", "city": "Orlando", "abbrev": "ORL"},
    "WAS": {"full": "Washington Wizards", "city": "Washington", "abbrev": "WAS"},
    
    # Western Conference - Northwest
    "DEN": {"full": "Denver Nuggets", "city": "Denver", "abbrev": "DEN"},
    "MIN": {"full": "Minnesota Timberwolves", "city": "Minnesota", "abbrev": "MIN"},
    "OKC": {"full": "Oklahoma City Thunder", "city": "Oklahoma City", "abbrev": "OKC"},
    "POR": {"full": "Portland Trail Blazers", "city": "Portland", "abbrev": "POR"},
    "UTA": {"full": "Utah Jazz", "city": "Utah", "abbrev": "UTA"},
    
    # Western Conference - Pacific
    "GSW": {"full": "Golden State Warriors", "city": "Golden State", "abbrev": "GSW"},
    "LAC": {"full": "LA Clippers", "city": "Los Angeles", "abbrev": "LAC"},
    "LAL": {"full": "LA Lakers", "city": "Los Angeles", "abbrev": "LAL"},
    "PHX": {"full": "Phoenix Suns", "city": "Phoenix", "abbrev": "PHX"},
    "SAC": {"full": "Sacramento Kings", "city": "Sacramento", "abbrev": "SAC"},
    
    # Western Conference - Southwest
    "DAL": {"full": "Dallas Mavericks", "city": "Dallas", "abbrev": "DAL"},
    "HOU": {"full": "Houston Rockets", "city": "Houston", "abbrev": "HOU"},
    "MEM": {"full": "Memphis Grizzlies", "city": "Memphis", "abbrev": "MEM"},
    "NOP": {"full": "New Orleans Pelicans", "city": "New Orleans", "abbrev": "NOP"},
    "SAS": {"full": "San Antonio Spurs", "city": "San Antonio", "abbrev": "SAS"},
}

# Aliases for flexible input
TEAM_ALIASES = {
    # Full names
    "boston celtics": "BOS", "boston": "BOS", "celtics": "BOS",
    "brooklyn nets": "BKN", "brooklyn": "BKN", "nets": "BKN",
    "new york knicks": "NYK", "new york": "NYK", "knicks": "NYK", "ny": "NYK",
    "philadelphia 76ers": "PHI", "philadelphia": "PHI", "76ers": "PHI", "sixers": "PHI", "philly": "PHI",
    "toronto raptors": "TOR", "toronto": "TOR", "raptors": "TOR",
    
    "chicago bulls": "CHI", "chicago": "CHI", "bulls": "CHI",
    "cleveland cavaliers": "CLE", "cleveland": "CLE", "cavaliers": "CLE", "cavs": "CLE",
    "detroit pistons": "DET", "detroit": "DET", "pistons": "DET",
    "indiana pacers": "IND", "indiana": "IND", "pacers": "IND",
    "milwaukee bucks": "MIL", "milwaukee": "MIL", "bucks": "MIL",
    
    "atlanta hawks": "ATL", "atlanta": "ATL", "hawks": "ATL",
    "charlotte hornets": "CHA", "charlotte": "CHA", "hornets": "CHA",
    "miami heat": "MIA", "miami": "MIA", "heat": "MIA",
    "orlando magic": "ORL", "orlando": "ORL", "magic": "ORL",
    "washington wizards": "WAS", "washington": "WAS", "wizards": "WAS",
    
    "denver nuggets": "DEN", "denver": "DEN", "nuggets": "DEN",
    "minnesota timberwolves": "MIN", "minnesota": "MIN", "timberwolves": "MIN", "wolves": "MIN",
    "oklahoma city thunder": "OKC", "oklahoma city": "OKC", "thunder": "OKC", "okc": "OKC",
    "portland trail blazers": "POR", "portland": "POR", "trail blazers": "POR", "blazers": "POR",
    "utah jazz": "UTA", "utah": "UTA", "jazz": "UTA",
    
    "golden state warriors": "GSW", "golden state": "GSW", "warriors": "GSW",
    "la clippers": "LAC", "los angeles clippers": "LAC", "clippers": "LAC",
    "la lakers": "LAL", "los angeles lakers": "LAL", "lakers": "LAL",
    "phoenix suns": "PHX", "phoenix": "PHX", "suns": "PHX",
    "sacramento kings": "SAC", "sacramento": "SAC", "kings": "SAC",
    
    "dallas mavericks": "DAL", "dallas": "DAL", "mavericks": "DAL", "mavs": "DAL",
    "houston rockets": "HOU", "houston": "HOU", "rockets": "HOU",
    "memphis grizzlies": "MEM", "memphis": "MEM", "grizzlies": "MEM", "grizz": "MEM",
    "new orleans pelicans": "NOP", "new orleans": "NOP", "pelicans": "NOP", "nola": "NOP",
    "san antonio spurs": "SAS", "san antonio": "SAS", "spurs": "SAS",
}

# Add abbreviations to aliases
for abbrev in NBA_TEAMS.keys():
    TEAM_ALIASES[abbrev.lower()] = abbrev


def get_db_engine():
    """Connect to database"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require"
    return create_engine(database_url)


def normalize_team(team_input):
    """Convert any team input to standard 3-letter abbreviation"""
    team_lower = team_input.strip().lower()
    
    if team_lower in TEAM_ALIASES:
        return TEAM_ALIASES[team_lower]
    
    # Try partial match
    for alias, abbrev in TEAM_ALIASES.items():
        if alias in team_lower or team_lower in alias:
            return abbrev
    
    return None


def print_teams():
    """Print all available teams"""
    print("\n📋 AVAILABLE NBA TEAMS:")
    print("=" * 50)
    
    conferences = {
        "EASTERN - Atlantic": ["BOS", "BKN", "NYK", "PHI", "TOR"],
        "EASTERN - Central": ["CHI", "CLE", "DET", "IND", "MIL"],
        "EASTERN - Southeast": ["ATL", "CHA", "MIA", "ORL", "WAS"],
        "WESTERN - Northwest": ["DEN", "MIN", "OKC", "POR", "UTA"],
        "WESTERN - Pacific": ["GSW", "LAC", "LAL", "PHX", "SAC"],
        "WESTERN - Southwest": ["DAL", "HOU", "MEM", "NOP", "SAS"],
    }
    
    for conf, teams in conferences.items():
        print(f"\n{conf}:")
        for abbrev in teams:
            team = NBA_TEAMS[abbrev]
            print(f"  {abbrev} - {team['full']}")


def add_games_for_date(engine, game_date):
    """Add games for a specific date"""
    print(f"\n📅 ADDING GAMES FOR: {game_date}")
    print("=" * 60)
    print("\n🏀 ENTER GAMES")
    print("Format: Away @ Home (e.g., Lakers @ Celtics)")
    print("Type 'DONE' when finished, 'LIST' to see teams\n")
    
    games = []
    game_num = 1
    
    while True:
        user_input = input(f"Game {game_num}: ").strip()
        
        if user_input.upper() == 'DONE':
            break
        
        if user_input.upper() == 'LIST':
            print_teams()
            continue
        
        if '@' not in user_input:
            print("  ❌ Invalid format. Use: Away @ Home")
            continue
        
        parts = user_input.split('@')
        if len(parts) != 2:
            print("  ❌ Invalid format. Use: Away @ Home")
            continue
        
        away_input = parts[0].strip()
        home_input = parts[1].strip()
        
        away_abbrev = normalize_team(away_input)
        home_abbrev = normalize_team(home_input)
        
        if not away_abbrev:
            print(f"  ❌ Unknown team: '{away_input}'. Type 'LIST' to see teams.")
            continue
        
        if not home_abbrev:
            print(f"  ❌ Unknown team: '{home_input}'. Type 'LIST' to see teams.")
            continue
        
        if away_abbrev == home_abbrev:
            print("  ❌ A team can't play itself!")
            continue
        
        away_name = NBA_TEAMS[away_abbrev]['full']
        home_name = NBA_TEAMS[home_abbrev]['full']
        
        games.append({
            'date': game_date,
            'visitor_team': away_abbrev,
            'visitor_team_std': away_abbrev,
            'home_team': home_abbrev,
            'home_team_std': home_abbrev,
            'visitor_pts': None,  # Will be updated later
            'home_pts': None,
            'home_win': None,
            'total_points': None,
            'margin_home': None,
            'season': 2025,
            'start_time': None,
        })
        
        print(f"  ✅ Added: {away_name} @ {home_name}")
        game_num += 1
    
    if not games:
        print("\n⚠️ No games added.")
        return
    
    # Save to database
    print(f"\n💾 Saving {len(games)} games to database...")
    
    with engine.connect() as conn:
        for game in games:
            # Check if game already exists
            check_query = text("""
                SELECT COUNT(*) FROM games 
                WHERE date = :date 
                AND home_team = :home_team 
                AND visitor_team = :visitor_team
            """)
            result = conn.execute(check_query, {
                "date": game['date'],
                "home_team": game['home_team'],
                "visitor_team": game['visitor_team']
            }).fetchone()
            
            if result[0] > 0:
                print(f"  ⚠️ Game already exists: {game['visitor_team']} @ {game['home_team']}")
                continue
            
            insert_query = text("""
                INSERT INTO games (date, home_team, home_team_std, visitor_team, visitor_team_std, 
                                   home_pts, visitor_pts, home_win, total_points, margin_home, season)
                VALUES (:date, :home_team, :home_team_std, :visitor_team, :visitor_team_std,
                        :home_pts, :visitor_pts, :home_win, :total_points, :margin_home, :season)
            """)
            conn.execute(insert_query, game)
        
        conn.commit()
    
    print(f"\n✅ Successfully saved {len(games)} games for {game_date}")


def update_scores(engine, game_date):
    """Update scores for games on a specific date"""
    print(f"\n📊 UPDATING SCORES FOR: {game_date}")
    print("=" * 60)
    
    # Get games for that date
    with engine.connect() as conn:
        query = text("""
            SELECT home_team, visitor_team, home_pts, visitor_pts
            FROM games
            WHERE date = :date
            ORDER BY home_team
        """)
        result = conn.execute(query, {"date": game_date}).fetchall()
    
    if not result:
        print(f"❌ No games found for {game_date}")
        return
    
    print(f"\n📋 Found {len(result)} games:\n")
    
    games_to_update = []
    
    for row in result:
        home = row[0]
        visitor = row[1]
        current_home_pts = row[2]
        current_visitor_pts = row[3]
        
        home_name = NBA_TEAMS.get(home, {}).get('full', home)
        visitor_name = NBA_TEAMS.get(visitor, {}).get('full', visitor)
        
        if current_home_pts and current_home_pts > 0:
            print(f"  ✅ {visitor_name} @ {home_name}: {int(current_visitor_pts)}-{int(current_home_pts)} (already scored)")
            continue
        
        print(f"\n🏀 {visitor_name} @ {home_name}")
        
        while True:
            score_input = input(f"   Enter score (away-home, e.g., 105-112) or 'skip': ").strip()
            
            if score_input.lower() == 'skip':
                break
            
            if '-' not in score_input:
                print("   ❌ Invalid format. Use: 105-112")
                continue
            
            parts = score_input.split('-')
            if len(parts) != 2:
                print("   ❌ Invalid format. Use: 105-112")
                continue
            
            try:
                visitor_pts = int(parts[0].strip())
                home_pts = int(parts[1].strip())
            except ValueError:
                print("   ❌ Invalid numbers. Use: 105-112")
                continue
            
            if visitor_pts < 50 or visitor_pts > 200 or home_pts < 50 or home_pts > 200:
                confirm = input(f"   ⚠️ Unusual score ({visitor_pts}-{home_pts}). Confirm? (y/n): ")
                if confirm.lower() != 'y':
                    continue
            
            total_points = visitor_pts + home_pts
            margin_home = home_pts - visitor_pts
            home_win = 1 if home_pts > visitor_pts else 0
            
            games_to_update.append({
                'date': game_date,
                'home_team': home,
                'visitor_team': visitor,
                'home_pts': home_pts,
                'visitor_pts': visitor_pts,
                'total_points': total_points,
                'margin_home': margin_home,
                'home_win': home_win,
            })
            
            winner = home_name if home_win else visitor_name
            print(f"   ✅ {visitor_pts}-{home_pts} | Total: {total_points} | Winner: {winner}")
            break
    
    if not games_to_update:
        print("\n⚠️ No scores to update.")
        return
    
    # Update database
    print(f"\n💾 Updating {len(games_to_update)} games...")
    
    with engine.connect() as conn:
        for game in games_to_update:
            update_query = text("""
                UPDATE games 
                SET home_pts = :home_pts,
                    visitor_pts = :visitor_pts,
                    total_points = :total_points,
                    margin_home = :margin_home,
                    home_win = :home_win
                WHERE date = :date 
                AND home_team = :home_team 
                AND visitor_team = :visitor_team
            """)
            conn.execute(update_query, game)
        
        conn.commit()
    
    print(f"\n✅ Successfully updated {len(games_to_update)} games!")


def view_games(engine, game_date):
    """View games for a specific date"""
    print(f"\n📋 GAMES FOR: {game_date}")
    print("=" * 60)
    
    with engine.connect() as conn:
        query = text("""
            SELECT home_team, visitor_team, home_pts, visitor_pts, total_points, home_win
            FROM games
            WHERE date = :date
            ORDER BY home_team
        """)
        result = conn.execute(query, {"date": game_date}).fetchall()
    
    if not result:
        print(f"❌ No games found for {game_date}")
        return
    
    print(f"\n{'Away':<25} {'Home':<25} {'Score':<15} {'Total':<8} {'Winner':<15}")
    print("-" * 90)
    
    for row in result:
        home = row[0]
        visitor = row[1]
        home_pts = row[2]
        visitor_pts = row[3]
        total = row[4]
        home_win = row[5]
        
        home_name = NBA_TEAMS.get(home, {}).get('full', home)
        visitor_name = NBA_TEAMS.get(visitor, {}).get('full', visitor)
        
        if home_pts and home_pts > 0:
            score = f"{int(visitor_pts)}-{int(home_pts)}"
            total_str = str(int(total)) if total else "—"
            winner = home_name if home_win else visitor_name
        else:
            score = "Pending"
            total_str = "—"
            winner = "—"
        
        print(f"{visitor_name:<25} {home_name:<25} {score:<15} {total_str:<8} {winner:<15}")
    
    print(f"\nTotal: {len(result)} games")


def main():
    engine = get_db_engine()
    
    print("\n" + "=" * 60)
    print("🏀 NBA GAMES MANAGER")
    print("=" * 60)
    
    while True:
        print("\n📌 MENU:")
        print("  1. Add today's games")
        print("  2. Add games for specific date")
        print("  3. Update scores for today")
        print("  4. Update scores for specific date")
        print("  5. View games for date")
        print("  6. List all NBA teams")
        print("  0. Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '0':
            print("\n👋 Goodbye!")
            break
        
        elif choice == '1':
            today = datetime.now().strftime('%Y-%m-%d')
            add_games_for_date(engine, today)
        
        elif choice == '2':
            date_input = input("Enter date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(date_input, '%Y-%m-%d')
                add_games_for_date(engine, date_input)
            except ValueError:
                print("❌ Invalid date format. Use YYYY-MM-DD")
        
        elif choice == '3':
            today = datetime.now().strftime('%Y-%m-%d')
            update_scores(engine, today)
        
        elif choice == '4':
            date_input = input("Enter date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(date_input, '%Y-%m-%d')
                update_scores(engine, date_input)
            except ValueError:
                print("❌ Invalid date format. Use YYYY-MM-DD")
        
        elif choice == '5':
            date_input = input("Enter date (YYYY-MM-DD) or 'today': ").strip()
            if date_input.lower() == 'today':
                date_input = datetime.now().strftime('%Y-%m-%d')
            try:
                datetime.strptime(date_input, '%Y-%m-%d')
                view_games(engine, date_input)
            except ValueError:
                print("❌ Invalid date format. Use YYYY-MM-DD")
        
        elif choice == '6':
            print_teams()
        
        else:
            print("❌ Invalid option")


if __name__ == "__main__":
    main()
