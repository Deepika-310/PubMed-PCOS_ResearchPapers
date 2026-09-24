"""Thin, polite client for NCBI E-utilities (esearch + efetch)."""
import logging
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    count: int
    webenv: str
    query_key: str
    translation: str


def build_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


class EutilsClient:
    def __init__(self, api_key=None, email=None, tool="pubmed-etl",
                 session=None, min_interval=None, timeout=30):
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.email = email or os.environ.get("NCBI_EMAIL")
        self.tool = tool
        self.session = session or build_session()
        self.timeout = timeout
        # NCBI limit: 3 req/s without a key, 10 req/s with one.
        self.min_interval = (
            min_interval if min_interval is not None
            else (0.11 if self.api_key else 0.34)
        )
        self._last_call = 0.0

    def _get(self, endpoint, params):
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        params = {**params, "tool": self.tool}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email
        resp = self.session.get(BASE_URL + endpoint, params=params, timeout=self.timeout)
        self._last_call = time.monotonic()
        resp.raise_for_status()
        return resp

    def search(self, term, sort=None):
        """Run esearch with the history server; returns the TOTAL match count."""
        params = {"db": "pubmed", "term": term, "retmode": "json",
                  "retmax": 0, "usehistory": "y"}
        if sort:
            params["sort"] = sort
        data = self._get("esearch.fcgi", params).json()["esearchresult"]
        if "ERROR" in data:
            raise ValueError(f"esearch error: {data['ERROR']}")
        return SearchResult(
            count=int(data["count"]),
            webenv=data.get("webenv", ""),
            query_key=data.get("querykey", ""),
            translation=data.get("querytranslation", ""),
        )

    def fetch_batch(self, result, retstart, retmax):
        params = {"db": "pubmed", "query_key": result.query_key,
                  "WebEnv": result.webenv, "retstart": retstart,
                  "retmax": retmax, "retmode": "xml"}
        return ET.fromstring(self._get("efetch.fcgi", params).content)

    def iter_batches(self, result, max_results=None, batch_size=200):
        """Yield one XML root per batch until every matching record is fetched.

        Number of pages is derived from the server-reported count, not hardcoded:
        requests = ceil(min(count, max_results) / batch_size).
        """
        total = result.count if max_results is None else min(result.count, max_results)
        for retstart in range(0, total, batch_size):
            retmax = min(batch_size, total - retstart)
            log.info("efetch %d-%d of %d", retstart + 1, retstart + retmax, total)
            yield self.fetch_batch(result, retstart, retmax)
