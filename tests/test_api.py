import pandas as pd
import pytest
from fastapi.testclient import TestClient

from pubmed_etl import api, storage


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    conn = storage.connect(db)
    df = pd.DataFrame([
        dict(pmid="1", title="Exercise in PCOS", abstract="a", journal="J1", year=2022, doi="d1",
             first_author="A", n_authors=2, study_type="RCT", pub_types="", mesh_terms="",
             authors="A; B"),
        dict(pmid="2", title="Sitting and PCOS", abstract="b", journal="J2", year=2023, doi="d2",
             first_author="C", n_authors=1, study_type="Review", pub_types="", mesh_terms="",
             authors="C"),
    ])
    storage.upsert_papers(conn, df, "q")
    conn.close()
    monkeypatch.setattr(api, "DB_PATH", str(db))
    return TestClient(api.app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "papers": 2}


def test_filters_and_pagination(client):
    assert [p["pmid"] for p in client.get("/papers").json()] == ["2", "1"]   # newest first
    assert len(client.get("/papers?study_type=RCT").json()) == 1
    assert len(client.get("/papers?q=sitting").json()) == 1
    assert len(client.get("/papers?limit=1&offset=1").json()) == 1
    assert client.get("/papers?limit=0").status_code == 422


def test_sql_injection_is_inert(client):
    assert client.get("/papers", params={"q": "'; DROP TABLE papers; --"}).json() == []
    assert client.get("/health").json()["papers"] == 2


def test_paper_detail_and_404(client):
    assert client.get("/papers/1").json()["authors"] == ["A", "B"]
    assert client.get("/papers/999").status_code == 404


def test_stats(client):
    assert client.get("/stats/years").json() == [{"year": 2022, "papers": 1}, {"year": 2023, "papers": 1}]
