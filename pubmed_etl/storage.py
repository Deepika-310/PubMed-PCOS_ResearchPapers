"""SQLite storage: idempotent upserts keyed on PMID, authors normalised."""
import sqlite3
from datetime import datetime, timezone

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    pmid TEXT PRIMARY KEY,
    title TEXT, abstract TEXT, journal TEXT, year INTEGER, doi TEXT,
    first_author TEXT, n_authors INTEGER, study_type TEXT,
    pub_types TEXT, mesh_terms TEXT, fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS authors (
    pmid TEXT NOT NULL REFERENCES papers(pmid) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (pmid, position)
);
CREATE TABLE IF NOT EXISTS paper_queries (
    pmid TEXT NOT NULL REFERENCES papers(pmid) ON DELETE CASCADE,
    query TEXT NOT NULL,
    PRIMARY KEY (pmid, query)
);
"""

_PAPER_COLS = ["pmid", "title", "abstract", "journal", "year", "doi", "first_author",
               "n_authors", "study_type", "pub_types", "mesh_terms"]


def connect(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_papers(conn, df, query):
    """Insert new PMIDs, update existing ones. Returns (inserted, updated)."""
    if df.empty:
        return 0, 0
    pmids = df["pmid"].tolist()
    marks = ",".join("?" * len(pmids))
    existing = {r[0] for r in conn.execute(
        f"SELECT pmid FROM papers WHERE pmid IN ({marks})", pmids)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    placeholders = ",".join("?" * (len(_PAPER_COLS) + 1))
    updates = ",".join(f"{c}=excluded.{c}" for c in _PAPER_COLS[1:] + ["fetched_at"])
    sql = (f"INSERT INTO papers ({','.join(_PAPER_COLS)},fetched_at) VALUES ({placeholders}) "
           f"ON CONFLICT(pmid) DO UPDATE SET {updates}")
    with conn:
        for row in df.to_dict("records"):
            year = None if pd.isna(row["year"]) else int(row["year"])
            values = [year if c == "year" else row[c] for c in _PAPER_COLS]
            conn.execute(sql, values + [now])
            conn.execute("DELETE FROM authors WHERE pmid = ?", (row["pmid"],))
            names = [n for n in row["authors"].split("; ") if n]
            conn.executemany("INSERT INTO authors VALUES (?,?,?)",
                             [(row["pmid"], i, n) for i, n in enumerate(names, 1)])
            conn.execute("INSERT OR IGNORE INTO paper_queries VALUES (?,?)",
                         (row["pmid"], query))
    return len(pmids) - len(existing), len(existing)


def load_papers(conn, query=None):
    if query is None:
        return pd.read_sql_query("SELECT * FROM papers", conn)
    return pd.read_sql_query(
        "SELECT p.* FROM papers p JOIN paper_queries q ON q.pmid = p.pmid WHERE q.query = ?",
        conn, params=(query,))
