#!/usr/bin/env python3
"""
Database Cleanup Script v3 - FAST BULK OPERATIONS
"""

import os
from sqlalchemy import create_engine, text

def get_db_engine():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require"
    return create_engine(database_url)


def fast_standardize_teams(engine):
    """Use bulk SQL updates - much faster"""
    print("\n🔧 FAST BULK STANDARDIZING TEAM NAMES...")
    print("=" * 60)
    
    # Map of old names to new abbreviations
    team_mappings = [
        ("Atlanta Hawks", "ATL"),
        ("Atlanta", "ATL"),
        ("Hawks", "ATL"),
        ("Boston Celtics", "BOS"),
        ("Boston", "BOS"),
        ("Celtics", "BOS"),
        ("Brooklyn Nets", "BKN"),
        ("Brooklyn", "BKN"),
        ("Nets", "BKN"),
        ("Charlotte Hornets", "CHA"),
        ("Charlotte", "CHA"),
        ("Hornets", "CHA"),
        ("Chicago Bulls", "CHI"),
        ("Chicago", "CHI"),
        ("Bulls", "CHI"),
        ("Cleveland Cavaliers", "CLE"),
        ("Cleveland", "CLE"),
        ("Cavaliers", "CLE"),
        ("Dallas Mavericks", "DAL"),
        ("Dallas", "DAL"),
        ("Mavericks", "DAL"),
        ("Denver Nuggets", "DEN"),
        ("Denver", "DEN"),
        ("Nuggets", "DEN"),
        ("Detroit Pistons", "DET"),
        ("Detroit", "DET"),
        ("Pistons", "DET"),
        ("Golden State Warriors", "GSW"),
        ("Golden State", "GSW"),
        ("Warriors", "GSW"),
        ("Houston Rockets", "HOU"),
        ("Houston", "HOU"),
        ("Rockets", "HOU"),
        ("Indiana Pacers", "IND"),
        ("Indiana", "IND"),
        ("Pacers", "IND"),
        ("LA Clippers", "LAC"),
        ("Los Angeles Clippers", "LAC"),
        ("Clippers", "LAC"),
        ("LA Lakers", "LAL"),
        ("Los Angeles Lakers", "LAL"),
        ("Lakers", "LAL"),
        ("Memphis Grizzlies", "MEM"),
        ("Memphis", "MEM"),
        ("Grizzlies", "MEM"),
        ("Miami Heat", "MIA"),
        ("Miami", "MIA"),
        ("Heat", "MIA"),
        ("Milwaukee Bucks", "MIL"),
        ("Milwaukee", "MIL"),
        ("Bucks", "MIL"),
        ("Minnesota Timberwolves", "MIN"),
        ("Minnesota", "MIN"),
        ("Timberwolves", "MIN"),
        ("New Orleans Pelicans", "NOP"),
        ("New Orleans", "NOP"),
        ("Pelicans", "NOP"),
        ("New York Knicks", "NYK"),
        ("New York", "NYK"),
        ("Knicks", "NYK"),
        ("Oklahoma City Thunder", "OKC"),
        ("Oklahoma City", "OKC"),
        ("Thunder", "OKC"),
        ("Orlando Magic", "ORL"),
        ("Orlando", "ORL"),
        ("Magic", "ORL"),
        ("Philadelphia 76ers", "PHI"),
        ("Philadelphia", "PHI"),
        ("76ers", "PHI"),
        ("Phoenix Suns", "PHX"),
        ("Phoenix", "PHX"),
        ("Suns", "PHX"),
        ("Portland Trail Blazers", "POR"),
        ("Portland", "POR"),
        ("Trail Blazers", "POR"),
        ("Sacramento Kings", "SAC"),
        ("Sacramento", "SAC"),
        ("Kings", "SAC"),
        ("San Antonio Spurs", "SAS"),
        ("San Antonio", "SAS"),
        ("Spurs", "SAS"),
        ("Toronto Raptors", "TOR"),
        ("Toronto", "TOR"),
        ("Raptors", "TOR"),
        ("Utah Jazz", "UTA"),
        ("Utah", "UTA"),
        ("Jazz", "UTA"),
        ("Washington Wizards", "WAS"),
        ("Washington", "WAS"),
        ("Wizards", "WAS"),
    ]
    
    with engine.connect() as conn:
        total_updated = 0
        
        for old_name, new_abbrev in team_mappings:
            if old_name == new_abbrev:
                continue
            
            # First, delete any games that would become duplicates
            delete_dups = text("""
                DELETE FROM games g1
                USING games g2
                WHERE g1.date = g2.date
                AND g1.home_team = :old_name
                AND g2.home_team = :new_abbrev
                AND (
                    (g1.visitor_team = g2.visitor_team) OR
                    (g1.visitor_team IN (SELECT unnest(ARRAY[:old_name, :new_abbrev])) AND g2.visitor_team IN (SELECT unnest(ARRAY[:old_name, :new_abbrev])))
                )
            """)
            
            # Update home_team
            update_home = text("""
                UPDATE games 
                SET home_team = :new_abbrev, home_team_std = :new_abbrev
                WHERE home_team = :old_name
            """)
            result1 = conn.execute(update_home, {"new_abbrev": new_abbrev, "old_name": old_name})
            
            # Update visitor_team  
            update_visitor = text("""
                UPDATE games 
                SET visitor_team = :new_abbrev, visitor_team_std = :new_abbrev
                WHERE visitor_team = :old_name
            """)
            result2 = conn.execute(update_visitor, {"new_abbrev": new_abbrev, "old_name": old_name})
            
            count = result1.rowcount + result2.rowcount
            if count > 0:
                print(f"   '{old_name}' → '{new_abbrev}': {count} updates")
                total_updated += count
        
        conn.commit()
        print(f"\n   ✅ Total updated: {total_updated}")


def recalculate_totals(engine):
    """Recalculate all totals in one query"""
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


def delete_corrupted_entries(engine):
    """Delete obviously corrupted entries"""
    print("\n🗑️  REMOVING CORRUPTED ENTRIES...")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Delete entries with numbers in team names
        delete_query = text("""
            DELETE FROM games 
            WHERE home_team ~ '[0-9]' 
            OR visitor_team ~ '[0-9]'
        """)
        result = conn.execute(delete_query)
        conn.commit()
        
        if result.rowcount > 0:
            print(f"   ✅ Deleted {result.rowcount} corrupted entries")
        else:
            print("   ✅ No corrupted entries found")


def verify_results(engine):
    """Check the results"""
    print("\n✅ VERIFICATION...")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Count unique team names in recent games
        query = text("""
            SELECT DISTINCT home_team 
            FROM games 
            WHERE date >= '2024-10-01'
            ORDER BY home_team
        """)
        teams = conn.execute(query).fetchall()
        
        print(f"\n   Teams in 2024-25 season games: {len(teams)}")
        
        standard_abbrevs = {'ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW',
                          'HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK',
                          'OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS'}
        
        non_standard = [t[0] for t in teams if t[0] not in standard_abbrevs]
        
        if non_standard:
            print(f"\n   ⚠️  Non-standard names remaining: {non_standard[:10]}")
        else:
            print("   ✅ All teams use standard 3-letter abbreviations!")
        
        # Count games with totals
        totals_query = text("""
            SELECT 
                COUNT(*) FILTER (WHERE total_points IS NOT NULL AND total_points > 0) as with_totals,
                COUNT(*) FILTER (WHERE total_points IS NULL OR total_points = 0) as without_totals
            FROM games
            WHERE home_pts > 0
        """)
        result = conn.execute(totals_query).fetchone()
        print(f"\n   Games with totals calculated: {result[0]}")
        print(f"   Games without totals: {result[1]}")


def main():
    engine = get_db_engine()
    
    print("\n" + "=" * 60)
    print("🚀 FAST DATABASE CLEANUP v3")
    print("=" * 60)
    
    print("\nThis will:")
    print("  1. Standardize all team names to 3-letter codes")
    print("  2. Remove corrupted entries (numbers in team names)")
    print("  3. Recalculate total_points, margin, home_win")
    
    confirm = input("\nProceed? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    print("\n" + "=" * 60)
    
    # Step 1: Delete corrupted entries first
    delete_corrupted_entries(engine)
    
    # Step 2: Standardize team names
    fast_standardize_teams(engine)
    
    # Step 3: Recalculate totals
    recalculate_totals(engine)
    
    # Step 4: Verify
    verify_results(engine)
    
    print("\n" + "=" * 60)
    print("✅ CLEANUP COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
