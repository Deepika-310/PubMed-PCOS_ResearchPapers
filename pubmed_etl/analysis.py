"""Descriptive analysis of the collected papers: tables, charts, markdown report."""
import re
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

_WORD = re.compile(r"[a-z][a-z\-]{3,}")
STOPWORDS = set("""
that this with from were have been which their these than also into other such more most
between among about after before during within without using used use while when where
both each however however study studies results result conclusions conclusion background
objective objectives methods method purpose aims aim findings review analysis data
associated association women woman patients patient group groups compared including
included based showed shown found significant significantly higher lower increased
""".split())


def papers_per_year(df):
    years = df["year"].dropna().astype(int)
    return years.value_counts().sort_index().rename_axis("year").reset_index(name="papers")


def top_counts(series, n=10):
    counts = series[series != ""].value_counts().head(n)
    return counts.rename_axis(series.name).reset_index(name="papers")


def top_mesh_terms(df, n=15):
    counter = Counter(t for cell in df["mesh_terms"] for t in cell.split("; ") if t)
    return pd.DataFrame(counter.most_common(n), columns=["mesh_term", "papers"])


def top_abstract_words(df, n=15):
    counter = Counter()
    for text in (df["title"] + " " + df["abstract"]).str.lower():
        counter.update(w for w in set(_WORD.findall(text)) if w not in STOPWORDS)
    return pd.DataFrame(counter.most_common(n), columns=["word", "papers"])


def _barh(data, label_col, title, path):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    view = data.iloc[::-1]
    ax.barh(view[label_col].astype(str).str.slice(0, 45), view["papers"], color="#3b6ea5")
    ax.set_title(title)
    ax.set_xlabel("Number of papers")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _bar_years(data, title, path):
    full = data.set_index("year")["papers"].reindex(
        range(int(data["year"].min()), int(data["year"].max()) + 1), fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(full.index, full.values, color="#3b6ea5")
    ax.set_title(title)
    ax.set_ylabel("Number of papers")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _md_table(df):
    header = "| " + " | ".join(df.columns) + " |"
    rule = "|" + "---|" * len(df.columns)
    rows = ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([header, rule, *rows])


def build_report(df, out_dir, slug, query, quality=None):
    """Write charts and a markdown report; returns the report path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    per_year = papers_per_year(df)
    journals = top_counts(df["journal"], 10)
    types = top_counts(df["study_type"], 10)
    mesh = top_mesh_terms(df)
    words = top_abstract_words(df)

    if not per_year.empty:
        _bar_years(per_year, "Papers per publication year", out / f"{slug}_years.png")
    if not journals.empty:
        _barh(journals, "journal", "Top journals", out / f"{slug}_journals.png")
    if not types.empty:
        _barh(types, "study_type", "Study types", out / f"{slug}_study_types.png")
    if not mesh.empty:
        _barh(mesh, "mesh_term", "Top MeSH terms", out / f"{slug}_mesh.png")

    span = f"{int(per_year['year'].min())}-{int(per_year['year'].max())}" if not per_year.empty else "n/a"
    lines = [f"# PubMed report: {query}", "",
             f"- Papers analysed: **{len(df)}**", f"- Publication years: **{span}**", ""]
    if quality:
        lines += ["## Data quality (% of records missing the field)", "",
                  _md_table(pd.DataFrame(quality.items(), columns=["field", "missing_%"])), ""]
    lines += ["## Papers per year", "", _md_table(per_year), "",
              "## Top journals", "", _md_table(journals), "",
              "## Study types", "", _md_table(types), "",
              "## Top MeSH terms", "", _md_table(mesh), "",
              "## Most common words in titles and abstracts", "", _md_table(words), ""]
    report = out / f"{slug}_report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report
