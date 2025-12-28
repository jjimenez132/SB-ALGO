"""
Basketball Reference Scraper
Fetches BPM, VORP, and other advanced stats not available on NBA.com
"""

import pandas as pd
import requests
import time
from datetime import datetime
from typing import Optional, Dict, List
from io import StringIO
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BBREF_BASE_URL, BBREF_DELAY_SECONDS, CURRENT_SEASON_YEAR


class BBRefScraper:
    """Scrapes advanced stats from Basketball Reference"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.pull_date = datetime.now().strftime('%Y-%m-%d')
        
    def _get_page(self, url: str) -> Optional[str]:
        """Fetch a page with retry logic"""
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                print(f"  ⚠️  Attempt {attempt + 1}/3 failed: {str(e)[:50]}")
                if attempt < 2:
                    time.sleep(BBREF_DELAY_SECONDS * (attempt + 1))
        return None
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean DataFrame from BBRef scraping artifacts"""
        # Remove header rows that appear in data
        if 'Rk' in df.columns:
            df = df[df['Rk'] != 'Rk']
        
        # Remove any rows with all NaN
        df = df.dropna(how='all')
        
        # Convert numeric columns
        numeric_cols = ['Age', 'G', 'MP', 'PER', 'TS%', '3PAr', 'FTr', 'ORB%', 'DRB%', 
                       'TRB%', 'AST%', 'STL%', 'BLK%', 'TOV%', 'USG%', 'OWS', 'DWS', 
                       'WS', 'WS/48', 'OBPM', 'DBPM', 'BPM', 'VORP']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def pull_advanced_stats(self, year: int = CURRENT_SEASON_YEAR) -> Optional[pd.DataFrame]:
        """
        Pull advanced stats table including BPM, VORP, WS
        URL: https://www.basketball-reference.com/leagues/NBA_2025_advanced.html
        """
        url = f"{BBREF_BASE_URL}/leagues/NBA_{year}_advanced.html"
        print(f"  📡 Pulling BBRef advanced stats ({year})...", end=" ", flush=True)
        
        html = self._get_page(url)
        if html is None:
            print("❌ Failed")
            return None
        
        try:
            # Parse tables from HTML
            tables = pd.read_html(StringIO(html))
            
            # Advanced stats is typically the first main table
            if len(tables) > 0:
                df = tables[0]
                
                # Handle multi-level columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(-1)
                
                df = self._clean_dataframe(df)
                
                # Standardize column names
                column_mapping = {
                    'Player': 'PLAYER_NAME',
                    'Tm': 'TEAM',
                    'Age': 'AGE',
                    'G': 'GP',
                    'MP': 'MP',
                    'PER': 'PER',
                    'TS%': 'TS_PCT',
                    'USG%': 'USG_PCT',
                    'OWS': 'OWS',
                    'DWS': 'DWS',
                    'WS': 'WS',
                    'WS/48': 'WS_48',
                    'OBPM': 'OBPM',
                    'DBPM': 'DBPM',
                    'BPM': 'BPM',
                    'VORP': 'VORP',
                }
                
                df = df.rename(columns=column_mapping)
                
                # Keep only columns we need
                keep_cols = [c for c in column_mapping.values() if c in df.columns]
                df = df[keep_cols]
                
                print(f"✅ {len(df)} rows")
                return df
                
        except Exception as e:
            print(f"❌ Error parsing: {e}")
            
        return None
    
    def pull_per_game_stats(self, year: int = CURRENT_SEASON_YEAR) -> Optional[pd.DataFrame]:
        """
        Pull per-game stats for additional metrics
        URL: https://www.basketball-reference.com/leagues/NBA_2025_per_game.html
        """
        url = f"{BBREF_BASE_URL}/leagues/NBA_{year}_per_game.html"
        print(f"  📡 Pulling BBRef per-game stats ({year})...", end=" ", flush=True)
        
        html = self._get_page(url)
        if html is None:
            print("❌ Failed")
            return None
        
        try:
            tables = pd.read_html(StringIO(html))
            
            if len(tables) > 0:
                df = tables[0]
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(-1)
                
                df = self._clean_dataframe(df)
                print(f"✅ {len(df)} rows")
                return df
                
        except Exception as e:
            print(f"❌ Error parsing: {e}")
            
        return None
    
    def pull_per_100_poss_stats(self, year: int = CURRENT_SEASON_YEAR) -> Optional[pd.DataFrame]:
        """
        Pull per 100 possessions stats
        URL: https://www.basketball-reference.com/leagues/NBA_2025_per_poss.html
        """
        url = f"{BBREF_BASE_URL}/leagues/NBA_{year}_per_poss.html"
        print(f"  📡 Pulling BBRef per-100-poss stats ({year})...", end=" ", flush=True)
        
        html = self._get_page(url)
        if html is None:
            print("❌ Failed")
            return None
        
        try:
            tables = pd.read_html(StringIO(html))
            
            if len(tables) > 0:
                df = tables[0]
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(-1)
                
                df = self._clean_dataframe(df)
                print(f"✅ {len(df)} rows")
                return df
                
        except Exception as e:
            print(f"❌ Error parsing: {e}")
            
        return None
    
    def pull_team_ratings(self, year: int = CURRENT_SEASON_YEAR) -> Optional[pd.DataFrame]:
        """
        Pull team ratings (ORtg, DRtg, Net Rating, Pace)
        URL: https://www.basketball-reference.com/leagues/NBA_2025_ratings.html
        """
        url = f"{BBREF_BASE_URL}/leagues/NBA_{year}_ratings.html"
        print(f"  📡 Pulling BBRef team ratings ({year})...", end=" ", flush=True)
        
        html = self._get_page(url)
        if html is None:
            print("❌ Failed")
            return None
        
        try:
            tables = pd.read_html(StringIO(html))
            
            if len(tables) > 0:
                df = tables[0]
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(-1)
                
                # Clean up
                df = df.dropna(how='all')
                if 'Rk' in df.columns:
                    df = df[df['Rk'] != 'Rk']
                
                print(f"✅ {len(df)} rows")
                return df
                
        except Exception as e:
            print(f"❌ Error parsing: {e}")
            
        return None
    
    def pull_schedule(self, year: int = CURRENT_SEASON_YEAR, month: str = None) -> Optional[pd.DataFrame]:
        """
        Pull schedule for a specific month or full season
        URL: https://www.basketball-reference.com/leagues/NBA_2025_games-december.html
        """
        if month:
            url = f"{BBREF_BASE_URL}/leagues/NBA_{year}_games-{month.lower()}.html"
        else:
            url = f"{BBREF_BASE_URL}/leagues/NBA_{year}_games.html"
            
        print(f"  📡 Pulling BBRef schedule ({year}, {month or 'full'})...", end=" ", flush=True)
        
        html = self._get_page(url)
        if html is None:
            print("❌ Failed")
            return None
        
        try:
            tables = pd.read_html(StringIO(html))
            
            if len(tables) > 0:
                df = tables[0]
                df = df.dropna(how='all')
                print(f"✅ {len(df)} rows")
                return df
                
        except Exception as e:
            print(f"❌ Error parsing: {e}")
            
        return None
    
    def pull_all(self, year: int = CURRENT_SEASON_YEAR) -> Dict[str, pd.DataFrame]:
        """Pull all available stats from Basketball Reference"""
        print("\n" + "=" * 60)
        print("🏀 BASKETBALL REFERENCE PULL")
        print(f"📅 Date: {self.pull_date}")
        print(f"🏀 Season: {year}")
        print("=" * 60)
        
        results = {}
        
        # Advanced stats (BPM, VORP)
        advanced = self.pull_advanced_stats(year)
        if advanced is not None:
            results['bbref_advanced'] = advanced
        time.sleep(BBREF_DELAY_SECONDS)
        
        # Per game stats
        per_game = self.pull_per_game_stats(year)
        if per_game is not None:
            results['bbref_per_game'] = per_game
        time.sleep(BBREF_DELAY_SECONDS)
        
        # Per 100 possessions
        per_100 = self.pull_per_100_poss_stats(year)
        if per_100 is not None:
            results['bbref_per_100'] = per_100
        time.sleep(BBREF_DELAY_SECONDS)
        
        # Team ratings
        team_ratings = self.pull_team_ratings(year)
        if team_ratings is not None:
            results['bbref_team_ratings'] = team_ratings
        
        # Summary
        print("\n" + "-" * 40)
        print("📊 BBRef Pull Summary:")
        for key, df in results.items():
            print(f"  {key}: {len(df)} rows")
        print("-" * 40)
        
        return results


# Standalone function for quick BPM/VORP pull
def get_bpm_vorp(year: int = CURRENT_SEASON_YEAR) -> Optional[pd.DataFrame]:
    """Quick function to just get BPM/VORP data"""
    scraper = BBRefScraper()
    return scraper.pull_advanced_stats(year)


if __name__ == "__main__":
    scraper = BBRefScraper()
    results = scraper.pull_all()
    
    if 'bbref_advanced' in results:
        print("\nSample BPM/VORP data:")
        print(results['bbref_advanced'].head(10))
