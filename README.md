# PubMed ETL: research-literature pipeline

A small, tested Python ETL pipeline that pulls research papers from PubMed for **any query**, cleans and deduplicates them, stores them in SQLite/CSV, and generates a descriptive report with charts.

Sample topic: `pcos AND sedentary lifestyle` (Polycystic Ovary Syndrome and sedentary behaviour).

```
NCBI E-utilities  ->  XML parse  ->  clean + dedupe  ->  SQLite + CSV  ->  report + charts
 (esearch/efetch)    (per record)    (key: PMID)         (idempotent)      (pandas/matplotlib)
```

## Quick start

```bash
python run.py                          # installs, runs the ETL, lints, tests, then serves the API
python run.py "diabetes AND exercise"  # same, for another topic
python run.py --no-serve               # stop after the tests
```

Individual steps:

```bash
pip install -r requirements.txt
python -m pubmed_etl "pcos AND sedentary lifestyle" --max-results 500
python -m pytest
ruff check .
uvicorn pubmed_etl.api:app             # http://localhost:8000/docs
sqlite3 data/pubmed.db < sql/analytics.sql
docker build -t pubmed-etl . && docker run -p 8000:8000 -v pubmed:/app/data pubmed-etl
```

Outputs: `data/<query>.csv`, `data/pubmed.db`, `reports/<query>_report.md` plus PNG charts.
Optional: set `NCBI_API_KEY` (10 requests/s instead of 3) and `NCBI_EMAIL` as environment variables.

## What the sample run found (54 papers, 2002-2026)

- Output grows strongly after 2020 (peak of 7 papers in both 2023 and 2025).
- Study types: 8 randomized controlled trials, 12 reviews, 6 observational studies.
- Most frequent MeSH terms: Polycystic Ovary Syndrome (38), Sedentary Behavior (19), Exercise (18), Insulin Resistance (9).
- Data quality: 0% missing abstracts/authors/years, 1.9% missing DOI, 22.2% missing MeSH terms (recent papers are not yet indexed).

See [reports/pcos_and_sedentary_lifestyle_report.md](reports/pcos_and_sedentary_lifestyle_report.md).

## REST API

`GET /health`, `/papers?year=&study_type=&q=&limit=&offset=`, `/papers/{pmid}`, `/stats/years`. Interactive docs at `/docs`.

## Project layout

```
pubmed_etl/
  client.py     E-utilities client: throttling, retries, history-server pagination
  parser.py     XML -> one dict per article (robust to missing fields)
  transform.py  text cleaning, study-type classification, PMID dedupe, quality report
  storage.py    SQLite schema (papers, authors, paper_queries) and idempotent upsert
  analysis.py   tables, charts, markdown report
  pipeline.py   orchestrates extract -> transform -> load -> analyse
  api.py        FastAPI read-only REST API
  __main__.py   CLI
run.py          one-command runner
sql/            analytics queries
Dockerfile, .github/workflows/ci.yml   container and CI
tests/          pytest suite with an XML fixture of edge cases
```

## Limitations

- Study type comes from PubMed publication-type tags, with a title-keyword fallback; it is a heuristic.
- Word frequencies are simple counts (no stemming or phrase detection).
- Only abstracts, not full text, are collected.
