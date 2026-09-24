# PubMed ETL: research-literature pipeline

A small, tested Python ETL pipeline that pulls research papers from PubMed for **any query**, cleans and deduplicates them, stores them in SQLite/CSV, and generates a descriptive report with charts.

Sample topic: `pcos AND sedentary lifestyle` (Polycystic Ovary Syndrome and sedentary behaviour).

```
NCBI E-utilities  ->  XML parse  ->  clean + dedupe  ->  SQLite + CSV  ->  report + charts
 (esearch/efetch)    (per record)    (key: PMID)         (idempotent)      (pandas/matplotlib)
```

## Quick start

```bash
pip install -r requirements.txt
python -m pubmed_etl "pcos AND sedentary lifestyle" --max-results 500
python -m pubmed_etl "diabetes AND exercise" --max-results 100 --sort pub_date
python -m pytest
```

Outputs: `data/<query>.csv`, `data/pubmed.db`, `reports/<query>_report.md` plus PNG charts.
Optional: set `NCBI_API_KEY` (10 requests/s instead of 3) and `NCBI_EMAIL` as environment variables.

## What the sample run found (54 papers, 2002-2026)

- Output grows strongly after 2020 (peak of 7 papers in both 2023 and 2025).
- Study types: 8 randomized controlled trials, 12 reviews, 6 observational studies.
- Most frequent MeSH terms: Polycystic Ovary Syndrome (38), Sedentary Behavior (19), Exercise (18), Insulin Resistance (9).
- Data quality: 0% missing abstracts/authors/years, 1.9% missing DOI, 22.2% missing MeSH terms (recent papers are not yet indexed).

See [reports/pcos_and_sedentary_lifestyle_report.md](reports/pcos_and_sedentary_lifestyle_report.md).

## From v1 to v2: what changed and why

**v1** (`pubmed.ipynb`) was a notebook that scraped PubMed's search-results HTML with `requests` + `BeautifulSoup`, looped over a fixed 5 pages, and wrote a CSV of 50 papers. It worked as a first prototype, but review showed correctness, robustness and reuse problems, and PubMed has since started serving an anti-bot challenge page to plain HTTP clients, so HTML scraping no longer returns results. v2 rebuilds it as a proper ETL pipeline.

| # | v1 behaviour | Why it was a problem | v2 change |
|---|---|---|---|
| 1 | Scraped HTML by CSS class name | Breaks silently when the site changes; now blocked by PubMed's bot challenge; not the sanctioned access route | Official NCBI **E-utilities API** (`esearch` + `efetch`, XML). Stable schema and documented rate limits. HTML scraping was not bypassed |
| 2 | Hardcoded `range(1, 6)` | Empty/duplicate pages for small topics; silently truncated data for large ones | Total matches come from the API; requests = `ceil(min(count, cap) / batch)`; `--max-results` sets the cap |
| 3 | Five parallel lists joined by position | If one paper lacked a field, every later row shifted with no error (wrong author on wrong title) | Each field is read **inside its own `<PubmedArticle>` node**; a missing field stays empty in that row. Regression-tested with an edge-case XML fixture |
| 4 | No timeout, status check, retry or delay | One transient error killed the run; risked hammering the server | Timeout, `raise_for_status()`, retries with exponential backoff on 429/5xx, request throttle (3/s, or 10/s with `NCBI_API_KEY`) |
| 5 | "Description" was a truncated snippet; "Ref. and Year" was one string | Could not be analysed (no numeric year, no full abstract) | Full abstract, DOI, journal, integer year, MeSH terms, publication types, derived study type |
| 6 | Duplicates possible | Same paper could appear twice | Deduplicated on PMID (unique per paper) |
| 7 | CSV overwritten each run, with a junk index column | No history, no queries, unclear schema | SQLite (`papers`, `authors`, `paper_queries`) with idempotent upserts keyed on PMID; clean CSV export with `index=False` |
| 8 | Stopped after collection | Nothing learned from the data | Report and charts: papers per year, top journals, study types, MeSH terms, common words, data-quality table |
| 9 | Topic hardcoded in URL and filenames | One-off script | CLI takes any PubMed query (`python -m pubmed_etl "..."`) |
| 10 | No tests | Changes could break it unnoticed | 11 pytest tests (parsing edge cases, dedupe, upsert, pagination maths, report) |
| 11 | Single notebook | Hard to read, reuse or run outside Jupyter | Modular package, `requirements.txt`, `.gitignore`, this README |
| 12 | Query typo "sedantary" | No MeSH mapping, so PubMed matched the misspelt word literally | Corrected to "sedentary"; the log prints how PubMed interpreted the query |

Libraries: `requests` and `pandas` remain. `BeautifulSoup`/`lxml` were dropped because the API returns XML, which Python's built-in `xml.etree` parses. Regex whitespace cleaning is kept for text fields.

## Project layout

```
pubmed_etl/
  client.py     E-utilities client: throttling, retries, history-server pagination
  parser.py     XML -> one dict per article (robust to missing fields)
  transform.py  text cleaning, study-type classification, PMID dedupe, quality report
  storage.py    SQLite schema (papers, authors, paper_queries) and idempotent upsert
  analysis.py   tables, charts, markdown report
  pipeline.py   orchestrates extract -> transform -> load -> analyse
  __main__.py   CLI
tests/          pytest suite with an XML fixture of edge cases
pubmed.ipynb    v1 exploratory scraper (requests + BeautifulSoup), kept for history
```

## Limitations

- Study type comes from PubMed publication-type tags, with a title-keyword fallback; it is a heuristic.
- Word frequencies are simple counts (no stemming or phrase detection).
- Only abstracts, not full text, are collected.
