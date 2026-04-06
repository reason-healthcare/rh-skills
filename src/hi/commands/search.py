"""hi search — Search biomedical databases for evidence-based sources."""

import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import click
import httpx

from hi.common import log_warn

# ── Constants ──────────────────────────────────────────────────────────────────

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CLINICALTRIALS_V2 = "https://clinicaltrials.gov/api/v2/studies"

MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/xml": ".xml",
    "text/xml": ".xml",
}

VALID_EVIDENCE_LEVELS = {"ia", "ib", "iia", "iib", "iii", "iv", "v", "expert-consensus"}
VALID_SOURCE_TYPES = {
    "clinical-guideline", "systematic-review", "rct", "cohort-study",
    "case-control", "cross-sectional", "case-report", "expert-opinion",
    "textbook", "government-program", "quality-measure", "terminology",
    "fhir-ig", "sdoh-assessment", "health-economics", "document",
}


# ── HTTP helper with rate-limit retry ─────────────────────────────────────────

_RETRY_DELAYS = (1.0, 3.0, 10.0)  # seconds between retries on 429


def _http_get_with_retry(url: str, params: dict, timeout: int) -> httpx.Response:
    """GET with automatic retry on HTTP 429 (rate limited).

    Prints a warning to stderr on each retry so the caller can see progress
    without the agent needing to improvise its own retry commentary.
    Raises click.ClickException after all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt, delay in enumerate((_RETRY_DELAYS[0] - 1,) + _RETRY_DELAYS, start=0):
        if attempt > 0:
            print(
                f"Rate limit hit — retrying in {int(delay)}s "
                f"(attempt {attempt}/{len(_RETRY_DELAYS)})",
                file=sys.stderr,
            )
            time.sleep(delay)
        try:
            r = httpx.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                last_exc = httpx.HTTPStatusError(
                    f"429 Too Many Requests", request=r.request, response=r
                )
                continue
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                last_exc = e
                continue
            raise click.ClickException(f"HTTP error: {e}") from e
        except httpx.HTTPError as e:
            raise click.ClickException(f"Network error: {e}") from e

    raise click.ClickException(
        f"Rate limit persists after {len(_RETRY_DELAYS)} retries. "
        "Try again in a few minutes or set NCBI_API_KEY for higher limits."
    )


# ── NCBI Entrez helper ─────────────────────────────────────────────────────────

def _entrez_search_fetch(
    query: str,
    db: str = "pubmed",
    max_results: int = 20,
    api_key: Optional[str] = None,
    filter_str: Optional[str] = None,
) -> list[dict]:
    """Two-step NCBI E-utilities: esearch → efetch.

    Returns list of result dicts with standardised keys.
    Rate limits: 3 req/s without api_key, 10 req/s with.
    """
    sleep_s = 0.11 if api_key else 0.34

    # Step 1: esearch — retrieve PMIDs
    search_term = f"({query}){f' AND {filter_str}' if filter_str else ''}"
    esearch_params: dict = {
        "db": db,
        "term": search_term,
        "retmax": max_results,
        "retmode": "json",
    }
    if api_key:
        esearch_params["api_key"] = api_key

    try:
        r = _http_get_with_retry(NCBI_ESEARCH, params=esearch_params, timeout=15)
    except click.ClickException as e:
        raise click.ClickException(f"NCBI esearch failed: {e.format_message()}") from e

    esearch_data = r.json()
    id_list = esearch_data.get("esearchresult", {}).get("idlist", [])
    total_found = int(esearch_data.get("esearchresult", {}).get("count", 0))

    if not id_list:
        return []

    time.sleep(sleep_s)

    # Step 2: efetch — retrieve full metadata as XML
    efetch_params: dict = {
        "db": db,
        "id": ",".join(id_list),
        "rettype": "xml",
        "retmode": "xml",
    }
    if api_key:
        efetch_params["api_key"] = api_key

    try:
        r2 = _http_get_with_retry(NCBI_EFETCH, params=efetch_params, timeout=30)
    except click.ClickException as e:
        raise click.ClickException(f"NCBI efetch failed: {e.format_message()}") from e

    results = _parse_pubmed_xml(r2.text, db=db)
    results = results[:max_results]

    # Attach total_found to first result for caller convenience
    if results:
        results[0]["_total_found"] = total_found

    return results


def _parse_pubmed_xml(xml_text: str, db: str = "pubmed") -> list[dict]:
    """Parse PubMed/PMC efetch XML into standardised result dicts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    results = []

    # PubMed returns PubmedArticleSet; PMC returns pmc-articleset
    articles = root.findall(".//PubmedArticle") or root.findall(".//article")

    for article in articles:
        medline = article.find(".//MedlineCitation")
        if medline is None:
            continue

        pmid_el = medline.find(".//PMID")
        pmid = pmid_el.text.strip() if pmid_el is not None else ""

        # Title
        title_el = medline.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        # Journal
        journal_el = medline.find(".//Journal/Title")
        if journal_el is None:
            journal_el = medline.find(".//MedlineJournalInfo/MedlineTA")
        journal = journal_el.text.strip() if journal_el is not None else ""

        # Year
        pub_year = ""
        for year_path in [
            ".//PubDate/Year",
            ".//PubDate/MedlineDate",
            ".//ArticleDate/Year",
        ]:
            el = medline.find(year_path)
            if el is not None and el.text:
                pub_year = el.text.strip()[:4]
                break

        # Abstract snippet (first 200 chars)
        abstract_el = medline.find(".//AbstractText")
        abstract = ""
        if abstract_el is not None:
            abstract = "".join(abstract_el.itertext()).strip()[:200]

        # PMC ID (open access flag)
        pmcid = ""
        for id_el in article.findall(".//ArticleId"):
            if id_el.get("IdType") == "pmc":
                pmcid = id_el.text.strip() if id_el.text else ""
                break
        open_access = bool(pmcid) or db == "pmc"

        # URL
        if db == "pmc" and pmcid:
            url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            url = ""

        results.append({
            "id": pmcid if (db == "pmc" and pmcid) else pmid,
            "title": title,
            "url": url,
            "year": pub_year,
            "journal": journal,
            "open_access": open_access,
            "pmcid": pmcid or None,
            "abstract_snippet": abstract,
        })

    return results


# ── ClinicalTrials.gov helper ──────────────────────────────────────────────────

def _clinicaltrials_search(
    query: str,
    max_results: int = 20,
    status_filter: str = "COMPLETED,RECRUITING",
) -> list[dict]:
    """Search ClinicalTrials.gov REST API v2.

    Returns list of standardised result dicts.
    All ClinicalTrials results have open_access: True.
    """
    params = {
        "query.cond": query,
        "filter.overallStatus": status_filter,
        "pageSize": min(max_results, 100),
        "format": "json",
    }

    try:
        r = _http_get_with_retry(CLINICALTRIALS_V2, params=params, timeout=15)
    except click.ClickException as e:
        raise click.ClickException(f"ClinicalTrials.gov API failed: {e.format_message()}") from e

    data = r.json()
    studies = data.get("studies", [])[:max_results]
    total_found = data.get("totalCount", len(studies))

    results = []
    for study in studies:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        desc_mod = proto.get("descriptionModule", {})

        nct_id = ident.get("nctId", "")
        title = ident.get("briefTitle", "")
        status = status_mod.get("overallStatus", "")
        start_date = status_mod.get("startDateStruct", {}).get("date", "")
        year = start_date[:4] if start_date else ""
        summary = desc_mod.get("briefSummary", "")[:200]

        url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else ""

        results.append({
            "id": nct_id,
            "title": title,
            "url": url,
            "year": year,
            "journal": None,
            "open_access": True,
            "pmcid": None,
            "abstract_snippet": summary,
        })

    if results:
        results[0]["_total_found"] = total_found

    return results


# ── Formatters ─────────────────────────────────────────────────────────────────

def _format_human(results: list[dict], source: str) -> None:
    """Print human-readable search results."""
    for i, r in enumerate(results, 1):
        oa_label = "open-access: yes" if r.get("open_access") else "open-access: no"
        journal = r.get("journal") or "ClinicalTrials.gov"
        year = r.get("year") or "n/d"
        click.echo(f"\n[{i}] {r['title']} ({year})")
        click.echo(f"    ID: {r['id']} | {journal} | {oa_label}")
        if r.get("url"):
            click.echo(f"    {r['url']}")
        if r.get("abstract_snippet"):
            click.echo(f"    {r['abstract_snippet']}...")


def _format_json(results: list[dict], query: str, source: str) -> None:
    """Print structured JSON output per data-model.md Entity 3."""
    total = results[0].pop("_total_found", len(results)) if results else 0
    # Clean internal keys from all results
    for r in results:
        r.pop("_total_found", None)

    output = {
        "query": query,
        "source": source,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_found": total,
        "returned": len(results),
        "results": results,
    }
    click.echo(json.dumps(output, indent=2))


# ── Click command group ────────────────────────────────────────────────────────

@click.group()
def search():
    """Search biomedical databases for evidence-based sources."""


# ── hi search pubmed ───────────────────────────────────────────────────────────

@search.command()
@click.option("--query", required=True, help="PubMed search query (supports MeSH, boolean, filters)")
@click.option("--max", "max_results", default=20, show_default=True, help="Maximum results to return")
@click.option("--filter", "filter_str", default=None, help='PubMed filter (e.g. "systematic review[pt]")')
@click.option("--api-key", default=None, envvar="NCBI_API_KEY", help="NCBI API key (env: NCBI_API_KEY)")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output structured JSON")
def pubmed(query, max_results, filter_str, api_key, as_json):
    """Search PubMed via NCBI E-utilities."""
    try:
        results = _entrez_search_fetch(
            query=query, db="pubmed", max_results=max_results,
            api_key=api_key, filter_str=filter_str,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if not results:
        log_warn(f"No results found for query: {query}")
        raise SystemExit(2)

    if as_json:
        _format_json(results, query, "pubmed")
    else:
        total = results[0].pop("_total_found", len(results))
        click.echo(f"PubMed: {len(results)} of {total} results for: {query}")
        _format_human(results, "pubmed")


# ── hi search pmc ─────────────────────────────────────────────────────────────

@search.command()
@click.option("--query", required=True, help="PMC search query")
@click.option("--max", "max_results", default=20, show_default=True, help="Maximum results to return")
@click.option("--filter", "filter_str", default=None, help="PMC filter string")
@click.option("--api-key", default=None, envvar="NCBI_API_KEY", help="NCBI API key (env: NCBI_API_KEY)")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output structured JSON")
def pmc(query, max_results, filter_str, api_key, as_json):
    """Search PubMed Central for open-access full-text articles."""
    try:
        results = _entrez_search_fetch(
            query=query, db="pmc", max_results=max_results,
            api_key=api_key, filter_str=filter_str,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e)) from e

    # All PMC results are open-access
    for r in results:
        r["open_access"] = True

    if not results:
        log_warn(f"No PMC results found for query: {query}")
        raise SystemExit(2)

    if as_json:
        _format_json(results, query, "pmc")
    else:
        total = results[0].pop("_total_found", len(results))
        click.echo(f"PMC: {len(results)} of {total} results for: {query}")
        _format_human(results, "pmc")


# ── hi search clinicaltrials ──────────────────────────────────────────────────

@search.command()
@click.option("--query", required=True, help="Condition or intervention search term")
@click.option("--max", "max_results", default=20, show_default=True, help="Maximum results to return")
@click.option("--status", "status_filter", default="COMPLETED,RECRUITING",
              show_default=True, help="Filter by trial status")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output structured JSON")
def clinicaltrials(query, max_results, status_filter, as_json):
    """Search ClinicalTrials.gov via REST API v2."""
    try:
        results = _clinicaltrials_search(
            query=query, max_results=max_results, status_filter=status_filter,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e)) from e

    if not results:
        log_warn(f"No ClinicalTrials.gov results found for query: {query}")
        raise SystemExit(2)

    if as_json:
        _format_json(results, query, "clinicaltrials")
    else:
        total = results[0].pop("_total_found", len(results))
        click.echo(f"ClinicalTrials.gov: {len(results)} of {total} results for: {query}")
        _format_human(results, "clinicaltrials")
