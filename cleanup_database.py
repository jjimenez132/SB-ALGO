#!/usr/bin/env python3
"""
Database Cleanup Script
Fixes corrupted team names and standardizes data
"""

import os
from sqlalchemy import create_engine, text

# Standard 3-letter abbreviations for all 30 NBA teams
NBA_TEAM_MAPPING = {
    # Full names to abbreviations
    "Atlanta Hawks": "ATL", "Atlanta": "ATL", "Hawks": "ATL",
    "Boston Celtics": "BOS", "Boston": "BOS", "Celtics": "BOS",
    "Brooklyn Nets": "BKN", "Brooklyn": "BKN", "Nets": "BKN",
    "Charlotte Hornets": "CHA", "Charlotte": "CHA", "Hornets": "CHA",
    "Chicago Bulls": "CHI", "Chicago": "CHI", "Bulls": "CHI",
    "Cleveland Cavaliers": "CLE", "Cleveland": "CLE", "Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Dallas": "DAL", "Mavericks": "DAL",
    "Denver Nuggets": "DEN", "Denver": "DEN", "Nuggets": "DEN",
    "Detroit Pistons": "DET", "Detroit": "DET", "Pistons": "DET",
    "Golden State Warriors": "GSW", "Golden State": "GSW", "Warriors": "GSW",
    "Houston Rockets": "HOU", "Houston": "HOU", "Rockets": "HOU",
    "Indiana Pacers": "IND", "Indiana": "IND", "Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Clippers": "LAC",
    "LA Lakers": "LAL", "Los Angeles Lakers": "LAL", "Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Memphis": "MEM", "Grizzlies": "MEM",
    "Miami Heat": "MIA", "Miami": "MIA", "Heat": "MIA",
    "Milwaukee Bucks": "MIL", "Milwaukee": "MIL", "Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "Minnesota": "MIN", "Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New Orleans": "NOP", "Pelicans": "NOP",
    "New York Knicks": "NYK", "New York": "NYK", "Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Oklahoma City": "OKC", "Thunder": "OKC",
    "Orlando Magic": "ORL", "Orlando": "ORL", "Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Philadelphia": "PHI", "76ers": "PHI",
    "Phoenix Suns": "PHX", "Phoenix": "PHX", "Suns": "PHX",
    "Portland Trail Blazers": "POR", "Portland": "POR", "Trail Blazers": "POR",
    "Sacramento Kings": "SAC", "Sacramento": "SAC", "Kings": "SAC",
    "San Antonio Spurs": "SAS", "San Antonio": "SAS", "Spurs": "SAS",
    "Toronto Raptors": "TOR", "Toronto": "TOR", "Raptors": "TOR",
    "Utah Jazz": "UTA", "Utah": "UTA", "Jazz": "UTA",
    "Washington Wizards": "WAS", "Washington": "WAS", "Wizards": "WAS",
}

# Also include abbreviations themselves
for abbrev in ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", 
               "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN",
               "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", 
               "TOR", "UTA", "WAS"]:
    NBA_TEAM_MAPPING[abbrev] = abbrev


def get_db_engine():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require"
    return create_engine(database_url)


def find_corrupted_teams(engine):
    """Find all team names that don't match standard format"""
    print("\n🔍 SCANNING FOR CORRUPTED TEAM NAMES...")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Get all unique team names from recent games
        query = text("""
            SELECT DISTINCT home_team FROM games WHERE date >= '2024-10-01'
            UNION
            SELECT DISTINCT visitor_team FROM games WHERE date >= '2024-10-01'
            ORDER BY 1
        """)
        result = conn.execute(query).fetchall()
    
    valid_abbrevs = set(["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", 
                         "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN",
                         "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", 
                         "TOR", "UTA", "WAS"])
    
    corrupted = []
    mappable = []
    
    for row in result:
        team = row[0]
        if team in valid_abbrevs:
            continue
        elif team in NBA_TEAM_MAPPING:
            mappable.append((team, NBA_TEAM_MAPPING[team]))
        else:
            corrupted.append(team)
    
    if mappable:
        print(f"\n✅ Found {len(mappable)} teams that can be standardized:")
        for old, new in mappable[:20]:
            print(f"   '{old}' → '{new}'")
        if len(mappable) > 20:
            print(f"   ... and {len(mappable) - 20} more")
    
    if corrupted:
        print(f"\n❌ Found {len(corrupted)} CORRUPTED team names that need manual review:")
        for team in corrupted[:20]:
            print(f"   '{team}'")
        if len(corrupted) > 20:
            print(f"   ... and {len(corrupted) - 20} more")
    
    return mappable, corrupted


def standardize_team_names(engine, dry_run=True):
    """Convert all team names to standard 3-letter abbreviations"""
    print("\n🔧 STANDARDIZING TEAM NAMES...")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made")
    
    updates_made = 0
    
    with engine.connect() as conn:
        for old_name, new_abbrev in NBA_TEAM_MAPPING.items():
            if old_name == new_abbrev:
                continue
            
            # Count affected rows
            count_query = text("""
                SELECT COUNT(*) FROM games 
                WHERE home_team = :old_name OR visitor_team = :old_name
            """)
            count = conn.execute(count_query, {"old_name": old_name}).fetchone()[0]
            
            if count > 0:
                print(f"   '{old_name}' → '{new_abbrev}': {count} games")
                updates_made += count
                
                if not dry_run:
                    # Update home_team
                    update_home = text("""
                        UPDATE games 
                        SET home_team = :new_abbrev, home_team_std = :new_abbrev
                        WHERE home_team = :old_name
                    """)
                    conn.execute(update_home, {"new_abbrev": new_abbrev, "old_name": old_name})
                    
                    # Update visitor_team
                    update_visitor = text("""
                        UPDATE games 
                        SET visitor_team = :new_abbrev, visitor_team_std = :new_abbrev
                        WHERE visitor_team = :old_name
                    """)
                    conn.execute(update_visitor, {"new_abbrev": new_abbrev, "old_name": old_name})
        
        if not dry_run:
            conn.commit()
    
    print(f"\n{'Would update' if dry_run else 'Updated'}: {updates_made} total records")
    return updates_made


def delete_corrupted_games(engine, dry_run=True):
    """Delete games with obviously corrupted data"""
    print("\n🗑️  CLEANING CORRUPTED GAMES...")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made")
    
    with engine.connect() as conn:
        # Find games with corrupted team names (like "Memphis 25 28 39 30")
        find_query = text("""
            SELECT date, home_team, visitor_team, home_pts, visitor_pts
            FROM games
            WHERE home_team ~ '[0-9]' OR visitor_team ~ '[0-9]'
            ORDER BY date DESC
        """)
        corrupted = conn.execute(find_query).fetchall()
        
        if corrupted:
            print(f"\n❌ Found {len(corrupted)} games with numbers in team names:")
            for row in corrupted:
                print(f"   {row[0]}: {row[2]} @ {row[1]} ({row[4]}-{row[3]})")
            
            if not dry_run:
                delete_query = text("""
                    DELETE FROM games
                    WHERE home_team ~ '[0-9]' OR visitor_team ~ '[0-9]'
                """)
                result = conn.execute(delete_query)
                conn.commit()
                print(f"\n✅ Deleted {result.rowcount} corrupted games")
        else:
            print("✅ No corrupted games found")
        
        # Find games with 0-0 scores that are old (should have scores by now)
        zero_query = text("""
            SELECT date, COUNT(*) 
            FROM games 
            WHERE home_pts = 0 AND visitor_pts = 0 
            AND date < CURRENT_DATE
            GROUP BY date
            ORDER BY date DESC
            LIMIT 10
        """)
        zero_games = conn.execute(zero_query).fetchall()
        
        if zero_games:
            print(f"\n⚠️  Games with 0-0 scores (need score updates):")
            for row in zero_games:
                print(f"   {row[0]}: {row[1]} games")


def recalculate_totals(engine, dry_run=True):
    """Recalculate total_points and margin for all games"""
    print("\n🔢 RECALCULATING TOTALS...")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made")
    
    with engine.connect() as conn:
        # Count games needing recalculation
        count_query = text("""
            SELECT COUNT(*) FROM games 
            WHERE home_pts IS NOT NULL AND home_pts > 0
            AND (total_points IS NULL OR total_points != home_pts + visitor_pts)
        """)
        count = conn.execute(count_query).fetchone()[0]
        
        print(f"   Found {count} games needing total recalculation")
        
        if not dry_run and count > 0:
            update_query = text("""
                UPDATE games 
                SET total_points = home_pts + visitor_pts,
                    margin_home = home_pts - visitor_pts,
                    home_win = CASE WHEN home_pts > visitor_pts THEN 1 ELSE 0 END
                WHERE home_pts IS NOT NULL AND home_pts > 0
            """)
            result = conn.execute(update_query)
            conn.commit()
            print(f"   ✅ Updated {result.rowcount} games")


def main():
    engine = get_db_engine()
    
    print("\n" + "=" * 60)
    print("🧹 DATABASE CLEANUP TOOL")
    print("=" * 60)
    
    while True:
        print("\n📌 OPTIONS:")
        print("  1. Scan for corrupted team names")
        print("  2. Standardize team names (DRY RUN)")
        print("  3. Standardize team names (APPLY)")
        print("  4. Find/delete corrupted games (DRY RUN)")
        print("  5. Find/delete corrupted games (APPLY)")
        print("  6. Recalculate totals (DRY RUN)")
        print("  7. Recalculate totals (APPLY)")
        print("  8. Run full cleanup (DRY RUN)")
        print("  9. Run full cleanup (APPLY)")
        print("  0. Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            find_corrupted_teams(engine)
        elif choice == '2':
            standardize_team_names(engine, dry_run=True)
        elif choice == '3':
            confirm = input("⚠️  This will modify the database. Continue? (yes/no): ")
            if confirm.lower() == 'yes':
                standardize_team_names(engine, dry_run=False)
        elif choice == '4':
            delete_corrupted_games(engine, dry_run=True)
        elif choice == '5':
            confirm = input("⚠️  This will DELETE data. Continue? (yes/no): ")
            if confirm.lower() == 'yes':
                delete_corrupted_games(engine, dry_run=False)
        elif choice == '6':
            recalculate_totals(engine, dry_run=True)
        elif choice == '7':
            confirm = input("⚠️  This will modify the database. Continue? (yes/no): ")
            if confirm.lower() == 'yes':
                recalculate_totals(engine, dry_run=False)
        elif choice == '8':
            print("\n🔄 FULL CLEANUP (DRY RUN)")
            find_corrupted_teams(engine)
            standardize_team_names(engine, dry_run=True)
            delete_corrupted_games(engine, dry_run=True)
            recalculate_totals(engine, dry_run=True)
        elif choice == '9':
            confirm = input("⚠️  This will modify AND delete data. Type 'YES I UNDERSTAND': ")
            if confirm == 'YES I UNDERSTAND':
                print("\n🔄 RUNNING FULL CLEANUP...")
                standardize_team_names(engine, dry_run=False)
                delete_corrupted_games(engine, dry_run=False)
                recalculate_totals(engine, dry_run=False)
                print("\n✅ CLEANUP COMPLETE!")
    
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
