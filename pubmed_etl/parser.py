"""Parse PubMed efetch XML into one dict per article.

Each field is read from inside its own <PubmedArticle> node, so a missing
field yields an empty value in that record instead of shifting later rows.
"""
import logging
import re

log = logging.getLogger(__name__)
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _text(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _year(article):
    for path in ("Journal/JournalIssue/PubDate/Year", "ArticleDate/Year"):
        el = article.find(path)
        if el is not None and el.text and el.text.strip().isdigit():
            return int(el.text.strip())
    medline = article.find("Journal/JournalIssue/PubDate/MedlineDate")
    match = _YEAR_RE.search(_text(medline))
    return int(match.group(0)) if match else None


def _authors(article):
    names = []
    for author in article.findall("AuthorList/Author"):
        collective = _text(author.find("CollectiveName"))
        if collective:
            names.append(collective)
            continue
        last = _text(author.find("LastName"))
        initials = _text(author.find("Initials")) or _text(author.find("ForeName"))
        name = f"{last} {initials}".strip()
        if name:
            names.append(name)
    return names


def _abstract(article):
    parts = []
    for node in article.findall("Abstract/AbstractText"):
        text = _text(node)
        label = node.get("Label")
        if text:
            parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts)


def parse_article(node):
    citation = node.find("MedlineCitation")
    if citation is None:
        return None
    pmid = _text(citation.find("PMID"))
    article = citation.find("Article")
    if not pmid or article is None:
        return None
    doi = next(
        (_text(i) for i in node.findall("PubmedData/ArticleIdList/ArticleId")
         if i.get("IdType") == "doi"),
        "",
    )
    return {
        "pmid": pmid,
        "title": _text(article.find("ArticleTitle")),
        "abstract": _abstract(article),
        "journal": _text(article.find("Journal/Title")),
        "year": _year(article),
        "doi": doi,
        "authors": _authors(article),
        "pub_types": [_text(t) for t in article.findall("PublicationTypeList/PublicationType")],
        "mesh_terms": [_text(d) for d in citation.findall("MeshHeadingList/MeshHeading/DescriptorName")],
    }


def parse_articles(root):
    records, skipped = [], 0
    for node in root.findall("PubmedArticle"):
        record = parse_article(node)
        if record is None:
            skipped += 1
        else:
            records.append(record)
    if skipped:
        log.warning("skipped %d malformed article nodes", skipped)
    return records
