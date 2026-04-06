"""Tests for hi search pubmed and hi search pmc subcommands."""

import json
from unittest.mock import patch

import pytest
import httpx
from click.testing import CliRunner

from hi.commands.search import pubmed, pmc, _entrez_search_fetch, _parse_pubmed_xml, _http_get_with_retry

# ── Fixtures ──────────────────────────────────────────────────────────────────

ESEARCH_RESPONSE = {
    "esearchresult": {
        "count": "847",
        "idlist": ["12345678", "87654321"],
    }
}

EFETCH_XML = """\
<?xml version="1.0" ?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN"
  "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <Title>Journal of Clinical Informatics</Title>
          <JournalIssue>
            <PubDate><Year>2023</Year></PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Chronic Care Management in Diabetes: A Systematic Review</ArticleTitle>
        <Abstract>
          <AbstractText>Chronic care management interventions for type 2 diabetes reduce HbA1c.</AbstractText>
        </Abstract>
      </Article>
      <ArticleIdList>
        <ArticleId IdType="pmc">PMC9999001</ArticleId>
      </ArticleIdList>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>87654321</PMID>
      <Article>
        <Journal>
          <Title>NEJM</Title>
          <JournalIssue>
            <PubDate><Year>2022</Year></PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Empagliflozin versus Standard Care in Type 2 Diabetes</ArticleTitle>
        <Abstract>
          <AbstractText>A randomized trial of empagliflozin in type 2 diabetes patients.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

EFETCH_XML_NO_RESULTS = "<PubmedArticleSet></PubmedArticleSet>"


# ── Unit tests: _parse_pubmed_xml ─────────────────────────────────────────────

def test_parse_pubmed_xml_extracts_fields():
    results = _parse_pubmed_xml(EFETCH_XML)
    assert len(results) == 2

    r0 = results[0]
    assert r0["id"] == "12345678"
    assert "Chronic Care" in r0["title"]
    assert r0["year"] == "2023"
    assert r0["journal"] == "Journal of Clinical Informatics"
    assert r0["open_access"] is True  # has PMC ID
    assert r0["pmcid"] == "PMC9999001"
    assert r0["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert len(r0["abstract_snippet"]) <= 200


def test_parse_pubmed_xml_no_pmcid_open_access_false():
    results = _parse_pubmed_xml(EFETCH_XML)
    r1 = results[1]
    assert r1["id"] == "87654321"
    assert r1["pmcid"] is None or r1["pmcid"] == ""
    assert r1["open_access"] is False


def test_parse_pubmed_xml_pmc_db_always_open_access():
    results = _parse_pubmed_xml(EFETCH_XML, db="pmc")
    for r in results:
        assert r["open_access"] is True


def test_parse_pubmed_xml_empty_set():
    results = _parse_pubmed_xml(EFETCH_XML_NO_RESULTS)
    assert results == []


def test_parse_pubmed_xml_malformed():
    results = _parse_pubmed_xml("NOT XML AT ALL")
    assert results == []


# ── Integration tests: _entrez_search_fetch ───────────────────────────────────

def test_entrez_search_fetch_success(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=httpx.URL("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                      params={"db": "pubmed", "term": "(diabetes)", "retmax": 2, "retmode": "json"}),
        json=ESEARCH_RESPONSE,
    )
    httpx_mock.add_response(
        method="GET",
        url=None,  # any efetch URL
        text=EFETCH_XML,
    )

    with patch("time.sleep"):
        results = _entrez_search_fetch("diabetes", db="pubmed", max_results=2)

    assert len(results) == 2
    assert results[0]["id"] == "12345678"
    assert results[0].get("_total_found") == 847


def test_entrez_search_fetch_zero_results(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=None,
        json={"esearchresult": {"count": "0", "idlist": []}},
    )

    with patch("time.sleep"):
        results = _entrez_search_fetch("very-obscure-query-xyz", db="pubmed", max_results=20)

    assert results == []


def test_entrez_search_fetch_network_error(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

    import click
    with patch("time.sleep"), pytest.raises(click.ClickException):
        _entrez_search_fetch("diabetes", db="pubmed", max_results=5)


# ── Rate limit retry tests ────────────────────────────────────────────────────

def test_http_get_retries_on_429_then_succeeds(httpx_mock):
    """A 429 response triggers a retry; a subsequent 200 succeeds."""
    import click
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(status_code=200, json={"ok": True})

    with patch("time.sleep"):
        r = _http_get_with_retry("https://example.com", params={}, timeout=10)
    assert r.status_code == 200


def test_http_get_raises_after_all_retries_exhausted(httpx_mock):
    """Persistent 429s eventually raise a ClickException."""
    import click
    for _ in range(4):  # initial + 3 retries
        httpx_mock.add_response(status_code=429)

    with patch("time.sleep"), pytest.raises(click.ClickException, match="Rate limit"):
        _http_get_with_retry("https://example.com", params={}, timeout=10)


def test_http_get_prints_warning_on_retry(httpx_mock, capsys):
    """A retry emits a message to stderr."""
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(status_code=200, json={})

    with patch("time.sleep"):
        _http_get_with_retry("https://example.com", params={}, timeout=10)

    captured = capsys.readouterr()
    assert "Rate limit" in captured.err
    assert "retrying" in captured.err.lower()


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_entrez_search_fetch_recovers_from_429(httpx_mock):
    """_entrez_search_fetch succeeds when esearch 429 is followed by 200."""
    httpx_mock.add_response(status_code=429)       # first attempt → rate limited
    httpx_mock.add_response(json=ESEARCH_RESPONSE) # retry → ok
    httpx_mock.add_response(text=EFETCH_XML)       # efetch → ok

    with patch("time.sleep"):
        results = _entrez_search_fetch("diabetes", db="pubmed", max_results=5)
    assert len(results) >= 1


# ── CLI tests: hi search pubmed ───────────────────────────────────────────────

def test_hi_search_pubmed_human_output(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=ESEARCH_RESPONSE)
    httpx_mock.add_response(method="GET", url=None, text=EFETCH_XML)

    runner = CliRunner()
    with patch("time.sleep"):
        result = runner.invoke(pubmed, ["--query", "diabetes"])

    assert result.exit_code == 0
    assert "PubMed" in result.output
    assert "Chronic Care Management" in result.output


def test_hi_search_pubmed_json_output(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=ESEARCH_RESPONSE)
    httpx_mock.add_response(method="GET", url=None, text=EFETCH_XML)

    runner = CliRunner()
    with patch("time.sleep"):
        result = runner.invoke(pubmed, ["--query", "diabetes", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["source"] == "pubmed"
    assert data["query"] == "diabetes"
    assert len(data["results"]) == 2
    assert "total_found" in data
    assert "retrieved_at" in data


def test_hi_search_pubmed_zero_results_exit_2(httpx_mock):
    httpx_mock.add_response(method="GET", url=None,
                            json={"esearchresult": {"count": "0", "idlist": []}})

    runner = CliRunner()
    with patch("time.sleep"):
        result = runner.invoke(pubmed, ["--query", "xyz-obscure-query"])

    assert result.exit_code == 2


# ── CLI tests: hi search pmc ──────────────────────────────────────────────────

def test_hi_search_pmc_all_open_access(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=ESEARCH_RESPONSE)
    httpx_mock.add_response(method="GET", url=None, text=EFETCH_XML)

    runner = CliRunner()
    with patch("time.sleep"):
        result = runner.invoke(pmc, ["--query", "diabetes", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["source"] == "pmc"
    for r in data["results"]:
        assert r["open_access"] is True


def test_hi_search_pmc_zero_results_exit_2(httpx_mock):
    httpx_mock.add_response(method="GET", url=None,
                            json={"esearchresult": {"count": "0", "idlist": []}})

    runner = CliRunner()
    with patch("time.sleep"):
        result = runner.invoke(pmc, ["--query", "xyz-obscure"])

    assert result.exit_code == 2
