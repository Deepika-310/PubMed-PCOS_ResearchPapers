"""One-command runner:  python run.py

Installs dependencies, runs the ETL for a query, runs the tests, then starts the API
and opens its docs page. Use --no-serve to stop after the tests.
"""
import argparse
import subprocess
import sys
import webbrowser

PY = sys.executable


def step(title, *cmd):
    print(f"\n=== {title} ===", flush=True)
    if subprocess.call([PY, "-m", *cmd]) != 0:
        sys.exit(f"Step failed: {title}")


def main():
    ap = argparse.ArgumentParser(description="Install, run the pipeline, test, and serve the API.")
    ap.add_argument("query", nargs="?", default="pcos AND sedentary lifestyle")
    ap.add_argument("--max-results", default="100")
    ap.add_argument("--no-serve", action="store_true", help="skip starting the API")
    args = ap.parse_args()

    step("Install dependencies", "pip", "install", "-q", "-r", "requirements.txt")
    step("Run ETL pipeline", "pubmed_etl", args.query, "--max-results", args.max_results)
    step("Lint", "ruff", "check", ".")
    step("Run tests", "pytest", "-q")
    if args.no_serve:
        return
    print("\n=== API running at http://localhost:8000/docs  (Ctrl+C to stop) ===", flush=True)
    webbrowser.open("http://localhost:8000/docs")
    subprocess.call([PY, "-m", "uvicorn", "pubmed_etl.api:app", "--port", "8000"])


if __name__ == "__main__":
    main()
