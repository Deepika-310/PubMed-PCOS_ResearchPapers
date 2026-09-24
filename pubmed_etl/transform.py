"""Clean, classify and deduplicate parsed records."""
import re

import pandas as pd

_WS = re.compile(r"\s+")

# Checked in order; first hit wins.
_TYPE_RULES = [
    ("Meta-Analysis", ("meta-analysis",)),
    ("Systematic Review", ("systematic review",)),
    ("Randomized Controlled Trial", ("randomized controlled trial",)),
    ("Clinical Trial", ("clinical trial",)),
    ("Review", ("review",)),
    ("Case Report", ("case reports",)),
    ("Observational Study", ("observational study", "cohort", "cross-sectional")),
]
_TITLE_RULES = [
    ("Meta-Analysis", re.compile(r"meta-analy", re.I)),
    ("Systematic Review", re.compile(r"systematic review", re.I)),
    ("Randomized Controlled Trial", re.compile(r"randomi[sz]ed", re.I)),
    ("Review", re.compile(r"\breview\b", re.I)),
    ("Observational Study", re.compile(r"cohort|cross-sectional|case-control", re.I)),
    ("Case Report", re.compile(r"case (study|report)", re.I)),
]


def clean_text(value):
    return _WS.sub(" ", value).strip() if isinstance(value, str) else ""


def classify_study_type(pub_types, title=""):
    lowered = [p.lower() for p in pub_types]
    for label, keys in _TYPE_RULES:
        if any(k in p for k in keys for p in lowered):
            return label
    for label, pattern in _TITLE_RULES:
        if pattern.search(title):
            return label
    return "Other"


def build_dataframe(records):
    """Records -> DataFrame, one row per unique PMID (last occurrence wins)."""
    rows = []
    for r in records:
        title = clean_text(r["title"])
        rows.append({
            "pmid": r["pmid"],
            "title": title,
            "abstract": clean_text(r["abstract"]),
            "journal": clean_text(r["journal"]),
            "year": r["year"],
            "doi": r["doi"],
            "first_author": r["authors"][0] if r["authors"] else "",
            "n_authors": len(r["authors"]),
            "authors": "; ".join(r["authors"]),
            "study_type": classify_study_type(r["pub_types"], title),
            "pub_types": "; ".join(r["pub_types"]),
            "mesh_terms": "; ".join(r["mesh_terms"]),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    return df.drop_duplicates(subset="pmid", keep="last").reset_index(drop=True)


def quality_report(df):
    """Share of rows missing each key field, for a quick data-quality check."""
    if df.empty:
        return {}
    checks = {
        "abstract": df["abstract"].eq(""),
        "authors": df["authors"].eq(""),
        "year": df["year"].isna(),
        "doi": df["doi"].eq(""),
        "mesh_terms": df["mesh_terms"].eq(""),
    }
    return {k: round(float(v.mean()) * 100, 1) for k, v in checks.items()}
