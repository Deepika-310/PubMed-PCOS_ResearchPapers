"""Extract -> Transform -> Load -> Analyse for one PubMed query."""
import logging
import re
from pathlib import Path

from . import analysis, parser, storage, transform
from .client import EutilsClient

log = logging.getLogger(__name__)


def slugify(query):
    return re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:60] or "query"


def run(query, max_results=200, sort=None, db_path="data/pubmed.db",
        out_dir="data", report_dir="reports", client=None, analyse=True):
    client = client or EutilsClient()
    slug = slugify(query)

    # Extract
    result = client.search(query, sort=sort)
    log.info("PubMed matched %d papers; PubMed interpreted the query as: %s",
             result.count, result.translation)
    records = []
    for root in client.iter_batches(result, max_results=max_results):
        records.extend(parser.parse_articles(root))

    # Transform
    df = transform.build_dataframe(records)
    quality = transform.quality_report(df)
    log.info("parsed %d records -> %d unique papers", len(records), len(df))

    # Load
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    conn = storage.connect(db_path)
    try:
        inserted, updated = storage.upsert_papers(conn, df, query)
        stored = storage.load_papers(conn, query)
    finally:
        conn.close()
    csv_path = Path(out_dir) / f"{slug}.csv"
    stored.to_csv(csv_path, index=False)
    log.info("db: %d inserted, %d updated; csv: %s", inserted, updated, csv_path)

    # Analyse
    report_path = None
    if analyse and not stored.empty:
        report_path = analysis.build_report(stored, report_dir, slug, query, quality)
    return {"total_matches": result.count, "fetched": len(records), "unique": len(df),
            "inserted": inserted, "updated": updated, "quality": quality,
            "csv": csv_path, "report": report_path}
