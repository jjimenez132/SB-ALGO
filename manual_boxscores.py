#!/usr/bin/env python3
"""
CARGADOR MANUAL DE BOXSCORES
Uso: Copia los stats de ESPN/NBA.com y pégalos aquí
"""

import psycopg2
from datetime import datetime, timedelta

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'

def cargar_boxscores_manual():
    """
    INSTRUCCIONES:
    1. Ve a ESPN.com o NBA.com
    2. Busca los boxscores de ayer
    3. Copia las estadísticas aquí abajo
    """
    
    # CAMBIA ESTA FECHA AL DÍA QUE QUIERAS CARGAR
    fecha = '2025-11-17'
    
    # PEGA LOS BOXSCORES AQUÍ (formato: jugador, equipo, puntos, rebotes, asistencias)
    boxscores = [
        # Ejemplo: ('LeBron James', 'LAL', 28, 8, 6),
        # PEGA TUS LÍNEAS AQUÍ ABAJO:
        
    ]
    
    if not boxscores:
        print("❌ No hay boxscores para cargar. Edita el archivo y agrega los stats.")
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    for player, team, pts, reb, ast in boxscores:
        cur.execute("""
            INSERT INTO player_boxscores 
            (game_date, player_name, team_abbreviation, pts, reb, ast)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (fecha, player, team, pts, reb, ast))
    
    conn.commit()
    print(f"✅ Cargados {len(boxscores)} boxscores para {fecha}")
    
    # Mostrar top 5
    cur.execute("""
        SELECT player_name, team_abbreviation, pts 
        FROM player_boxscores 
        WHERE game_date = %s
        ORDER BY pts DESC LIMIT 5
    """, (fecha,))
    
    print("\n🌟 TOP SCORERS:")
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]}): {row[2]} pts")
    
    conn.close()

if __name__ == "__main__":
    cargar_boxscores_manual()
