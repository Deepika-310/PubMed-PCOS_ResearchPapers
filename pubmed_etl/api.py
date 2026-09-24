"""Read-only REST API over the SQLite store (run: uvicorn pubmed_etl.api:app)."""
import os
import sqlite3

from fastapi import FastAPI, HTTPException, Query

DB_PATH = os.environ.get("PUBMED_DB", "data/pubmed.db")

app = FastAPI(title="PubMed ETL API", version="1.0")


def _query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    except sqlite3.OperationalError as exc:  # e.g. ETL has not been run yet
        raise HTTPException(503, f"database not ready: {exc}") from exc
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "ok", "papers": _query("SELECT COUNT(*) AS n FROM papers")[0]["n"]}


@app.get("/papers")
def list_papers(year: int | None = None, study_type: str | None = None,
                q: str | None = Query(None, description="substring of title"),
                limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    # Filters are bound parameters (never string-formatted) to prevent SQL injection.
    sql = ("SELECT pmid, title, journal, year, study_type, doi FROM papers "
           "WHERE (:year IS NULL OR year = :year) "
           "AND (:st IS NULL OR study_type = :st) "
           "AND (:q IS NULL OR title LIKE '%' || :q || '%') "
           "ORDER BY year DESC, pmid LIMIT :limit OFFSET :offset")
    return _query(sql, {"year": year, "st": study_type, "q": q, "limit": limit, "offset": offset})


@app.get("/papers/{pmid}")
def get_paper(pmid: str):
    rows = _query("SELECT * FROM papers WHERE pmid = ?", (pmid,))
    if not rows:
        raise HTTPException(404, "paper not found")
    rows[0]["authors"] = [r["name"] for r in _query(
        "SELECT name FROM authors WHERE pmid = ? ORDER BY position", (pmid,))]
    return rows[0]


@app.get("/stats/years")
def papers_per_year():
    return _query("SELECT year, COUNT(*) AS papers FROM papers "
                  "WHERE year IS NOT NULL GROUP BY year ORDER BY year")
