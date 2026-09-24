import argparse
import logging

from .pipeline import run


def main():
    ap = argparse.ArgumentParser(
        prog="pubmed_etl",
        description="Fetch PubMed papers for any query, store them in SQLite/CSV and report on them.")
    ap.add_argument("query", nargs="?", default="pcos AND sedentary lifestyle",
                    help='PubMed query, e.g. "diabetes AND exercise"')
    ap.add_argument("--max-results", type=int, default=200,
                    help="cap on papers to fetch (default 200)")
    ap.add_argument("--sort", choices=["relevance", "pub_date"], default=None)
    ap.add_argument("--db", default="data/pubmed.db")
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--report-dir", default="reports")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    summary = run(args.query, max_results=args.max_results, sort=args.sort,
                  db_path=args.db, out_dir=args.out_dir, report_dir=args.report_dir,
                  analyse=not args.no_report)
    print(f"\nMatched {summary['total_matches']} | fetched {summary['fetched']} | "
          f"unique {summary['unique']} | new {summary['inserted']} | updated {summary['updated']}")
    print(f"Missing-field % : {summary['quality']}")
    print(f"CSV   : {summary['csv']}")
    print(f"Report: {summary['report']}")


if __name__ == "__main__":
    main()
