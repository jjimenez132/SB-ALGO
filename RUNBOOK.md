# SB ALGO — Render Postgres Runbook

Seed and launch with the hosted Postgres URL that already includes `?sslmode=require`:

```bash
export DATABASE_URL="postgresql://...YOUR_RENDER_URL...?sslmode=require"
python etl/pg_load_from_duckdb.py
streamlit run app.py --server.port 8501
```
