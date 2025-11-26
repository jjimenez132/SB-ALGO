#!/usr/bin/env python3
from basketball_reference_scraper import client
from datetime import datetime, timedelta
import psycopg2
import pandas as pd

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'

# Fecha de ayer
yesterday = datetime.now() - timedelta(days=1)
month = yesterday.strftime('%B').upper()
day = yesterday.day
year = yesterday.year

print(f"🏀 Obteniendo boxscores del {day} de {month} {year}...")

try:
    # Obtener boxscores usando la función correcta
    boxscores = client.player_stats(day=day, month=month, year=year)
    
    if boxscores.empty:
        print("No se encontraron juegos")
    else:
        # Conectar a DB
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        saved = 0
        for _, player in boxscores.iterrows():
            try:
                cur.execute("""
                    INSERT INTO player_boxscores 
                    (game_date, player_name, team_abbreviation, pts, reb, ast)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    yesterday.strftime('%Y-%m-%d'),
                    player['PLAYER'],
                    player['TEAM'],
                    int(player.get('PTS', 0)),
                    int(player.get('TRB', 0)),
                    int(player.get('AST', 0))
                ))
                saved += 1
            except Exception as e:
                print(f"Error con jugador: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        print(f"✅ Guardados {saved} boxscores")
        
        # Mostrar top 5
        top_scorers = boxscores.nlargest(5, 'PTS')[['PLAYER', 'TEAM', 'PTS', 'TRB', 'AST']]
        print("\n🌟 TOP SCORERS:")
        for _, p in top_scorers.iterrows():
            print(f"  {p['PLAYER']} ({p['TEAM']}): {p['PTS']} pts, {p['TRB']} reb, {p['AST']} ast")
    
except Exception as e:
    print(f"Error: {e}")
    print("\nIntentando método alternativo...")
    
    # Método alternativo: obtener por equipo
    from basketball_reference_scraper import teams
    
    # Lista de equipos NBA
    nba_teams = ['LAL', 'GSW', 'BOS', 'MIA', 'CHI', 'DAL', 'PHI', 'DEN', 'MIL', 'PHX']
    
    for team in nba_teams[:3]:  # Probar con 3 equipos primero
        try:
            roster = teams.get_roster(team, year)
            print(f"  Roster de {team}: {len(roster)} jugadores")
        except:
            continue
