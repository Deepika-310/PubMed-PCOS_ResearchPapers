import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pubmed_etl import analysis, parser, storage, transform
from pubmed_etl.client import EutilsClient
from pubmed_etl.pipeline import slugify

FIXTURE = Path(__file__).parent / "fixtures" / "sample_efetch.xml"


@pytest.fixture
def records():
    return parser.parse_articles(ET.parse(FIXTURE).getroot())


# ---- parser: the misalignment bug from v1 ---------------------------------

def test_missing_fields_do_not_shift_other_rows(records):
    by_pmid = {r["pmid"]: r for r in records}
    assert set(by_pmid) == {"111", "222", "333"}          # book article skipped
    assert by_pmid["111"]["authors"] == ["Smith J", "Doe A"]
    assert by_pmid["222"]["abstract"] == ""                # missing abstract stays with 222
    assert by_pmid["222"]["authors"] == ["PCOS Consortium"]
    assert by_pmid["333"]["authors"] == []                 # missing authors stay with 333
    assert by_pmid["333"]["title"].startswith("A systematic review")


def test_field_parsing(records):
    r = {x["pmid"]: x for x in records}
    assert r["111"]["title"] == "Complete paper with italic title."
    assert r["111"]["abstract"] == "BACKGROUND: Background text. RESULTS: Results text."
    assert r["111"]["doi"] == "10.1/one"
    assert r["111"]["year"] == 2022
    assert r["222"]["year"] == 2019                        # MedlineDate fallback
    assert r["111"]["mesh_terms"] == ["Polycystic Ovary Syndrome", "Exercise"]


# ---- transform ------------------------------------------------------------

def test_dedupe_and_classification(records):
    df = transform.build_dataframe(records + [records[0]])
    assert len(df) == 3 and df["pmid"].is_unique
    types = dict(zip(df["pmid"], df["study_type"]))
    assert types == {"111": "Randomized Controlled Trial", "222": "Other", "333": "Systematic Review"}


def test_classify_falls_back_to_title():
    assert transform.classify_study_type(["Journal Article"], "A randomised trial of X") == \
        "Randomized Controlled Trial"


def test_quality_report(records):
    q = transform.quality_report(transform.build_dataframe(records))
    assert q["abstract"] == pytest.approx(33.3)
    assert q["authors"] == pytest.approx(33.3)


# ---- storage --------------------------------------------------------------

def test_upsert_is_idempotent_and_updates(records):
    conn = storage.connect(":memory:")
    df = transform.build_dataframe(records)
    assert storage.upsert_papers(conn, df, "q1") == (3, 0)
    assert storage.upsert_papers(conn, df, "q1") == (0, 3)
    assert conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM authors").fetchone()[0] == 3   # 2 + 1 + 0

    df.loc[df["pmid"] == "111", "title"] = "Edited"
    storage.upsert_papers(conn, df, "q2")
    assert conn.execute("SELECT title FROM papers WHERE pmid='111'").fetchone()[0] == "Edited"
    assert len(storage.load_papers(conn, "q2")) == 3


# ---- client: pagination derived from the server count ---------------------

class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self._payload, self.content = payload, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, count):
        self.count, self.calls = count, []

    def get(self, url, params, timeout):
        self.calls.append((url.rsplit("/", 1)[-1], params))
        if url.endswith("esearch.fcgi"):
            return FakeResponse({"esearchresult": {"count": str(self.count), "webenv": "W",
                                                   "querykey": "1", "querytranslation": "t"}})
        return FakeResponse(content=b"<PubmedArticleSet/>")


@pytest.mark.parametrize("count,cap,expected_starts", [
    (5, None, [0, 2, 4]),        # ceil(5/2) = 3 requests, last one has retmax=1
    (5, 3, [0, 2]),              # cap limits the pages
    (0, None, []),               # no results -> no efetch calls
])
def test_pagination_from_count(count, cap, expected_starts):
    session = FakeSession(count)
    client = EutilsClient(session=session, min_interval=0)
    result = client.search("x")
    assert result.count == count
    list(client.iter_batches(result, max_results=cap, batch_size=2))
    fetches = [p for name, p in session.calls if name == "efetch.fcgi"]
    assert [p["retstart"] for p in fetches] == expected_starts
    if count == 5 and cap is None:
        assert fetches[-1]["retmax"] == 1


# ---- analysis + misc ------------------------------------------------------

def test_report_generation(tmp_path, records):
    df = transform.build_dataframe(records)
    path = analysis.build_report(df, tmp_path, "demo", "demo query", transform.quality_report(df))
    assert path.exists() and "Papers per year" in path.read_text(encoding="utf-8")
    assert (tmp_path / "demo_years.png").exists()


def test_slugify():
    assert slugify("PCOS AND sedentary lifestyle") == "pcos_and_sedentary_lifestyle"
