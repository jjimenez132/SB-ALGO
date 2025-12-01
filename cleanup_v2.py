#!/usr/bin/env python3
"""
Database Cleanup Script v2
Handles duplicates and standardizes team names safely
"""

import os
from sqlalchemy import create_engine, text

# Standard 3-letter abbreviations
TEAM_NAME_TO_ABBREV = {
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

def get_db_engine():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require"
    return create_engine(database_url)


def find_and_remove_duplicates(engine):
    """Find and remove duplicate games (keep the one with more data)"""
    print("\n🔍 FINDING DUPLICATE GAMES...")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Find duplicates where same game exists with different team name formats
        # For example: (2025-10-29, Brooklyn Nets, Atlanta Hawks) AND (2025-10-29, BKN, ATL)
        
        find_dups_query = text("""
            WITH game_keys AS (
                SELECT 
                    date,
                    home_team,
                    visitor_team,
                    home_pts,
                    CASE 
                        WHEN home_team IN ('ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW',
                                          'HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK',
                                          'OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS')
                        THEN 1 ELSE 0 
                    END as is_abbrev
                FROM games
                WHERE date >= '2024-10-01'
            )
            SELECT date, home_team, visitor_team, home_pts, is_abbrev
            FROM game_keys
            ORDER BY date DESC, home_team
        """)
        
        results = conn.execute(find_dups_query).fetchall()
        
        # Group by date to find potential duplicates
        from collections import defaultdict
        games_by_date = defaultdict(list)
        
        for row in results:
            games_by_date[row[0]].append({
                'home': row[1],
                'visitor': row[2],
                'pts': row[3],
                'is_abbrev': row[4]
            })
        
        duplicates_to_remove = []
        
        for date, games in games_by_date.items():
            # Check each pair for duplicates
            seen = {}
            for game in games:
                # Normalize team names for comparison
                home_norm = TEAM_NAME_TO_ABBREV.get(game['home'], game['home'])
                visitor_norm = TEAM_NAME_TO_ABBREV.get(game['visitor'], game['visitor'])
                key = (home_norm, visitor_norm)
                
                if key in seen:
                    # Found duplicate - keep the abbreviated one or the one with scores
                    existing = seen[key]
                    if game['is_abbrev'] and not existing['is_abbrev']:
                        # Current is abbrev, remove existing (full name)
                        duplicates_to_remove.append((date, existing['home'], existing['visitor']))
                    elif not game['is_abbrev'] and existing['is_abbrev']:
                        # Existing is abbrev, remove current (full name)
                        duplicates_to_remove.append((date, game['home'], game['visitor']))
                    elif game['pts'] and not existing['pts']:
                        # Current has scores, remove existing
                        duplicates_to_remove.append((date, existing['home'], existing['visitor']))
                    else:
                        # Remove current (keep first one found)
                        duplicates_to_remove.append((date, game['home'], game['visitor']))
                else:
                    seen[key] = game
        
        print(f"\n   Found {len(duplicates_to_remove)} duplicate games to remove")
        
        if duplicates_to_remove:
            print("\n   Duplicates to remove:")
            for date, home, visitor in duplicates_to_remove[:10]:
                print(f"      {date}: {visitor} @ {home}")
            if len(duplicates_to_remove) > 10:
                print(f"      ... and {len(duplicates_to_remove) - 10} more")
        
        return duplicates_to_remove


def remove_duplicates(engine, duplicates):
    """Actually remove the duplicate games"""
    if not duplicates:
        print("   No duplicates to remove")
        return
    
    print(f"\n🗑️  REMOVING {len(duplicates)} DUPLICATE GAMES...")
    
    with engine.connect() as conn:
        for date, home, visitor in duplicates:
            delete_query = text("""
                DELETE FROM games 
                WHERE date = :date AND home_team = :home AND visitor_team = :visitor
            """)
            conn.execute(delete_query, {"date": date, "home": home, "visitor": visitor})
        
        conn.commit()
    
    print(f"   ✅ Removed {len(duplicates)} duplicates")


def standardize_team_names_safe(engine):
    """Standardize team names, skipping if would create duplicate"""
    print("\n🔧 STANDARDIZING TEAM NAMES (SAFE MODE)...")
    print("=" * 60)
    
    updated = 0
    skipped = 0
    
    with engine.connect() as conn:
        for old_name, new_abbrev in TEAM_NAME_TO_ABBREV.items():
            if old_name == new_abbrev:
                continue
            
            # Find games that need updating
            find_query = text("""
                SELECT date, home_team, visitor_team 
                FROM games 
                WHERE home_team = :old_name OR visitor_team = :old_name
            """)
            games_to_update = conn.execute(find_query, {"old_name": old_name}).fetchall()
            
            for game in games_to_update:
                date = game[0]
                home = game[1]
                visitor = game[2]
                
                new_home = new_abbrev if home == old_name else home
                new_visitor = new_abbrev if visitor == old_name else visitor
                
                # Also normalize the other team
                new_home = TEAM_NAME_TO_ABBREV.get(new_home, new_home)
                new_visitor = TEAM_NAME_TO_ABBREV.get(new_visitor, new_visitor)
                
                # Check if this would create a duplicate
                check_query = text("""
                    SELECT COUNT(*) FROM games 
                    WHERE date = :date AND home_team = :new_home AND visitor_team = :new_visitor
                """)
                exists = conn.execute(check_query, {
                    "date": date, 
                    "new_home": new_home, 
                    "new_visitor": new_visitor
                }).fetchone()[0]
                
                if exists > 0:
                    # Would create duplicate - delete this one instead
                    delete_query = text("""
                        DELETE FROM games 
                        WHERE date = :date AND home_team = :home AND visitor_team = :visitor
                    """)
                    conn.execute(delete_query, {"date": date, "home": home, "visitor": visitor})
                    skipped += 1
                else:
                    # Safe to update
                    update_query = text("""
                        UPDATE games 
                        SET home_team = :new_home, 
                            home_team_std = :new_home,
                            visitor_team = :new_visitor,
                            visitor_team_std = :new_visitor
                        WHERE date = :date AND home_team = :home AND visitor_team = :visitor
                    """)
                    conn.execute(update_query, {
                        "date": date,
                        "home": home,
                        "visitor": visitor,
                        "new_home": new_home,
                        "new_visitor": new_visitor
                    })
                    updated += 1
        
        conn.commit()
    
    print(f"   ✅ Updated: {updated} games")
    print(f"   🗑️  Removed duplicates: {skipped} games")


def recalculate_all_totals(engine):
    """Recalculate total_points, margin, home_win for all games"""
    print("\n🔢 RECALCULATING TOTALS...")
    print("=" * 60)
    
    with engine.connect() as conn:
        update_query = text("""
            UPDATE games 
            SET total_points = home_pts + visitor_pts,
                margin_home = home_pts - visitor_pts,
                home_win = CASE WHEN home_pts > visitor_pts THEN 1 ELSE 0 END
            WHERE home_pts IS NOT NULL 
            AND home_pts > 0
            AND visitor_pts IS NOT NULL
            AND visitor_pts > 0
        """)
        result = conn.execute(update_query)
        conn.commit()
        
        print(f"   ✅ Recalculated {result.rowcount} games")


def verify_cleanup(engine):
    """Verify the cleanup worked"""
    print("\n✅ VERIFICATION...")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Count games by team name type
        count_query = text("""
            SELECT 
                CASE 
                    WHEN home_team IN ('ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW',
                                      'HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK',
                                      'OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS')
                    THEN 'Standard (3-letter)'
                    ELSE 'Other'
                END as team_type,
                COUNT(*) as count
            FROM games
            WHERE date >= '2024-10-01'
            GROUP BY team_type
        """)
        results = conn.execute(count_query).fetchall()
        
        for row in results:
            print(f"   {row[0]}: {row[1]} games")
        
        # Check for any remaining non-standard names
        remaining_query = text("""
            SELECT DISTINCT home_team 
            FROM games 
            WHERE date >= '2024-10-01'
            AND home_team NOT IN ('ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW',
                                  'HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK',
                                  'OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS')
            LIMIT 20
        """)
        remaining = conn.execute(remaining_query).fetchall()
        
        if remaining:
            print(f"\n   ⚠️  Non-standard team names still remaining:")
            for row in remaining:
                print(f"      - {row[0]}")
        else:
            print(f"\n   ✅ All team names standardized!")


def main():
    engine = get_db_engine()
    
    print("\n" + "=" * 60)
    print("🧹 DATABASE CLEANUP v2 - DUPLICATE SAFE")
    print("=" * 60)
    
    while True:
        print("\n📌 OPTIONS:")
        print("  1. Find duplicates (scan only)")
        print("  2. Remove duplicates")
        print("  3. Standardize team names (safe mode)")
        print("  4. Recalculate totals")
        print("  5. Verify cleanup")
        print("  6. RUN FULL CLEANUP (recommended)")
        print("  0. Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            find_and_remove_duplicates(engine)
        elif choice == '2':
            dups = find_and_remove_duplicates(engine)
            if dups:
                confirm = input(f"   Remove {len(dups)} duplicates? (yes/no): ")
                if confirm.lower() == 'yes':
                    remove_duplicates(engine, dups)
        elif choice == '3':
            standardize_team_names_safe(engine)
        elif choice == '4':
            recalculate_all_totals(engine)
        elif choice == '5':
            verify_cleanup(engine)
        elif choice == '6':
            print("\n🚀 RUNNING FULL CLEANUP...")
            dups = find_and_remove_duplicates(engine)
            if dups:
                remove_duplicates(engine, dups)
            standardize_team_names_safe(engine)
            recalculate_all_totals(engine)
            verify_cleanup(engine)
            print("\n✅ FULL CLEANUP COMPLETE!")
        else:
            print("Invalid option")
    
    print("\n👋 Done!")


if __name__ == "__main__":
    main()
