from sb_algo_db import get_pg_engine
from sqlalchemy import text


def main() -> None:
    engine = get_pg_engine()

    with engine.connect() as conn:
        # 1) Span de la tabla games
        games_span = conn.execute(
            text("SELECT MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS total_games FROM games")
        ).mappings().one()

        print("📅 GAMES TABLE")
        print(f"  Min date : {games_span['min_date']}")
        print(f"  Max date : {games_span['max_date']}")
        print(f"  # games  : {games_span['total_games']}")
        print()

        # 2) Span de la tabla player_boxscores
        box_span = conn.execute(
            text(
                "SELECT MIN(game_date) AS min_date, "
                "       MAX(game_date) AS max_date, "
                "       COUNT(*)       AS total_rows "
                "FROM player_boxscores"
            )
        ).mappings().one()

        print("📊 PLAYER_BOXSCORES TABLE")
        print(f"  Min game_date : {box_span['min_date']}")
        print(f"  Max game_date : {box_span['max_date']}")
        print(f"  # rows        : {box_span['total_rows']}")
        print()

        # 3) Últimos 30 días con games + cobertura de boxscores
        rows = conn.execute(
            text(
                """
                WITH game_days AS (
                    SELECT date, COUNT(*) AS games
                    FROM games
                    GROUP BY date
                ),
                box_days AS (
                    SELECT game_date,
                           COUNT(*)      AS box_rows,
                           COALESCE(SUM(pts), 0) AS total_pts
                    FROM player_boxscores
                    GROUP BY game_date
                )
                SELECT g.date,
                       g.games,
                       COALESCE(b.box_rows, 0)  AS box_rows,
                       COALESCE(b.total_pts, 0) AS total_pts
                FROM game_days g
                LEFT JOIN box_days b
                  ON b.game_date = g.date
                ORDER BY g.date DESC
                LIMIT 30
                """
            )
        ).mappings().all()

        print("🧾 LAST 30 GAME DATES (coverage check)")
        print("date       | games | box_rows | total_pts | status")
        print("-----------+-------+----------+-----------+--------")
        for r in rows:
            status = "✅ ok" if r["box_rows"] > 0 else "⚠️  NO BOXSCORES"
            print(
                f"{r['date']} | "
                f"{r['games']:5d} | "
                f"{r['box_rows']:8d} | "
                f"{r['total_pts']:9d} | {status}"
            )


if __name__ == "__main__":
    main()
