"""rh-skills search — Search biomedical databases for evidence-based sources."""

import io
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import httpx
from ruamel.yaml import YAML

from rh_skills.common import log_info, log_warn

# ── Constants ──────────────────────────────────────────────────────────────────

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CLINICALTRIALS_V2 = "https://clinicaltrials.gov/api/v2/studies"

# ── Offline fallback guidance ──────────────────────────────────────────────────
# Structured reference sources returned when network is unavailable.
# Keyed by source type; each entry has the same fields as a live result.
_OFFLINE_PUBMED: list[dict] = [
    {
        "title": "PubMed — MEDLINE literature database (NLM)",
        "url":   "https://pubmed.ncbi.nlm.nih.gov/",
        "year":  "",
        "authors": ["National Library of Medicine"],
        "abstract_snippet": (
            "Search PubMed for peer-reviewed biomedical literature including "
            "systematic reviews, RCTs, and clinical guidelines."
        ),
        "open_access": True,
    },
    {
        "title": "PubMed Central (PMC) — Open Access full-text archive",
        "url":   "https://pmc.ncbi.nlm.nih.gov/",
        "year":  "",
        "authors": ["National Library of Medicine"],
        "abstract_snippet": (
            "Free full-text archive of biomedical and life sciences journal articles "
            "at the National Institutes of Health."
        ),
        "open_access": True,
    },
]

_OFFLINE_CLINICALTRIALS: list[dict] = [
    {
        "title": "ClinicalTrials.gov — Registry of clinical studies",
        "url":   "https://clinicaltrials.gov/",
        "year":  "",
        "authors": ["U.S. National Library of Medicine"],
        "abstract_snippet": (
            "Registry and results database of publicly and privately supported "
            "clinical studies conducted around the world."
        ),
        "open_access": True,
    },
]

_OFFLINE_NOTICE = (
    "\nNetwork access unavailable — returning offline reference links.\n"
    "Re-run this command in a network-enabled environment to retrieve live results.\n"
    "Attempted query recorded; use it manually at the URL above.\n"
)

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

VALID_EVIDENCE_LEVELS = {
    # Oxford / traditional hierarchy
    "ia", "ib", "iia", "iib", "iii", "iv", "v", "expert-consensus",
    # GRADE certainty
    "grade-a", "grade-b", "grade-c", "grade-d",
    # USPSTF grades
    "uspstf-a", "uspstf-b", "uspstf-c", "uspstf-d", "uspstf-i",
    # Reference and non-study sources
    "reference-standard", "n/a",
}
VALID_SOURCE_TYPES = {
    # Guidelines
    "guideline", "clinical-guideline",          # clinical-guideline is alias for guideline
    # Study designs
    "systematic-review", "rct", "cohort-study", "case-control",
    "cross-sectional", "case-report", "expert-opinion",
    # Terminology and value sets
    "terminology", "value-set",
    # Measures and libraries
    "measure-library", "quality-measure",        # quality-measure is alias for measure-library
    "cds-library",
    # FHIR and implementation
    "fhir-ig",
    # Programmatic / real-world data
    "sdoh-assessment", "health-economics", "government-program", "registry",
    # Literature
    "pubmed-article", "textbook",
    # Catch-all
    "document", "other",
}


# ── HTTP helper with rate-limit retry ─────────────────────────────────────────

_RETRY_DELAYS = (1.0, 3.0, 10.0)  # seconds between retries on 429


def _http_get_with_retry(
    url: str,
    params: dict,
    timeout: int,
    subcmd: str = "pubmed",
) -> httpx.Response:
    """GET with automatic retry on HTTP 429 (rate limited).

    Prints a warning to stderr on each retry so the caller can see progress
    without the agent needing to improvise its own retry commentary.
    Raises click.ClickException after all retries are exhausted.

    ``subcmd`` is the search sub-command name (pubmed/pmc/clinicaltrials) used
    to generate a correct ``--offline`` hint in network-error messages.
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
            raise click.ClickException(
                f"Network error: {e}\n\n"
                "Network access may be restricted in this environment.\n"
                "Re-run with --offline to get reference links and record the query:\n"
                f"  rh-skills search {subcmd} --offline --query \"...\"\n\n"
                "Or build a discovery plan manually:\n"
                "  1. Gather source URLs from your browser or a web search tool\n"
                "  2. Use: rh-skills source add --type <type> --url <url> ...\n"
                "  3. Validate with: rh-skills validate --plan <file>"
            ) from e

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
        r = _http_get_with_retry(NCBI_ESEARCH, params=esearch_params, timeout=15, subcmd=db)
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
        r2 = _http_get_with_retry(NCBI_EFETCH, params=efetch_params, timeout=30, subcmd=db)
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

        # Authors
        authors = []
        for author_el in medline.findall(".//AuthorList/Author"):
            collective = author_el.findtext("CollectiveName")
            if collective:
                authors.append(collective.strip())
                continue
            last_name = (author_el.findtext("LastName") or "").strip()
            initials = (author_el.findtext("Initials") or "").strip()
            fore_name = (author_el.findtext("ForeName") or "").strip()
            if last_name and initials:
                authors.append(f"{last_name} {initials}")
            elif last_name and fore_name:
                authors.append(f"{last_name}, {fore_name}")
            elif last_name:
                authors.append(last_name)
            elif fore_name:
                authors.append(fore_name)

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
        doi = None
        for id_el in article.findall(".//ArticleId"):
            if id_el.get("IdType") == "pmc":
                pmcid = id_el.text.strip() if id_el.text else ""
            elif id_el.get("IdType") == "doi":
                doi = id_el.text.strip() if id_el.text else None
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
            "pmid": pmid or None,
            "nct_id": None,
            "title": title,
            "url": url,
            "year": pub_year,
            "journal": journal,
            "authors": authors,
            "doi": doi,
            "open_access": open_access,
            "pmcid": pmcid or None,
            "abstract_snippet": abstract,
            "status": None,
            "phase": None,
            "conditions": [],
            "interventions": [],
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
        r = _http_get_with_retry(CLINICALTRIALS_V2, params=params, timeout=15, subcmd="clinicaltrials")
    except click.ClickException as e:
        raise click.ClickException(
            f"ClinicalTrials.gov API failed: {e.format_message()}\n\n"
            "Network access may be restricted in this environment.\n"
            "Re-run with --offline to get reference links and record the query:\n"
            "  rh-skills search clinicaltrials --offline --query \"...\"\n\n"
            "Or build a discovery plan manually:\n"
            "  1. Gather source URLs from your browser or a web search tool\n"
            "  2. Use: rh-skills source add --type registry --url <url> ...\n"
            "  3. Validate with: rh-skills validate --plan <file>"
        ) from e

    data = r.json()
    studies = data.get("studies", [])[:max_results]
    total_found = data.get("totalCount", len(studies))

    results = []
    for study in studies:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        desc_mod = proto.get("descriptionModule", {})
        design_mod = proto.get("designModule", {})
        conditions_mod = proto.get("conditionsModule", {})
        interventions_mod = proto.get("armsInterventionsModule", {})

        nct_id = ident.get("nctId", "")
        title = ident.get("briefTitle", "")
        status = status_mod.get("overallStatus", "")
        start_date = status_mod.get("startDateStruct", {}).get("date", "")
        year = start_date[:4] if start_date else ""
        summary = desc_mod.get("briefSummary", "")[:200]
        phases = design_mod.get("phases", []) or []
        conditions = conditions_mod.get("conditions", []) or []
        interventions = [
            intervention.get("name", "")
            for intervention in interventions_mod.get("interventions", []) or []
            if intervention.get("name")
        ]

        url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else ""

        results.append({
            "id": nct_id,
            "pmid": None,
            "nct_id": nct_id or None,
            "title": title,
            "url": url,
            "year": year,
            "journal": None,
            "authors": [],
            "doi": None,
            "open_access": True,
            "pmcid": None,
            "abstract_snippet": summary,
            "status": status or None,
            "phase": ", ".join(phases) if phases else None,
            "conditions": conditions,
            "interventions": interventions,
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
        if source in {"pubmed", "pmc"} and r.get("authors"):
            click.echo(f"    Authors: {', '.join(r['authors'][:5])}")
        if source in {"pubmed", "pmc"} and r.get("doi"):
            click.echo(f"    DOI: {r['doi']}")
        if source == "clinicaltrials":
            status = r.get("status") or "n/d"
            phase = r.get("phase") or "n/d"
            click.echo(f"    Status: {status} | Phase: {phase}")
            if r.get("conditions"):
                click.echo(f"    Conditions: {', '.join(r['conditions'][:3])}")
            if r.get("interventions"):
                click.echo(f"    Interventions: {', '.join(r['interventions'][:3])}")
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


# ── Plan append helper ─────────────────────────────────────────────────────────

def _append_results_to_plan(results: list[dict], topic: str, source_type: str, query: str) -> None:
    """Append search results as stub source entries to a topic's discovery-plan.yaml."""
    from rh_skills.commands.validate import VALID_SOURCE_TYPES
    from rh_skills.common import topic_dir

    plan_path = topic_dir(topic) / "process" / "plans" / "discovery-plan.yaml"
    if not plan_path.exists():
        raise click.ClickException(
            f"No discovery plan found at {plan_path}\n"
            "Create one first with: rh-skills validate --plan <file>"
        )

    y_safe = YAML(typ="safe")
    with plan_path.open() as f:
        plan = y_safe.load(f) or {}

    existing_urls = {s.get("url") for s in plan.get("sources", []) if isinstance(s, dict)}
    existing_names = {s.get("name") for s in plan.get("sources", []) if isinstance(s, dict)}

    import re
    added = []
    for r in results:
        url = r.get("url", "")
        if url and url in existing_urls:
            continue  # skip duplicates by URL

        title = r.get("title", "Untitled")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
        # ensure uniqueness
        base, i = slug, 1
        while slug in existing_names:
            slug = f"{base}-{i}"
            i += 1

        entry = {
            "name": slug,
            "type": source_type,
            "title": title,
            "rationale": f"Retrieved via rh-skills search ({source_type}) for query: {query!r}",
            "search_terms": [query],
            "evidence_level": "n/a",
            "access": "open" if r.get("open_access") else "authenticated",
        }
        if url:
            entry["url"] = url
        if r.get("year"):
            entry["year"] = r["year"]
        if r.get("authors"):
            entry["authors"] = ", ".join(r["authors"][:5])

        plan.setdefault("sources", []).append(entry)
        existing_urls.add(url)
        existing_names.add(slug)
        added.append(slug)

    if not added:
        log_warn("No new sources to append (all results already in plan).")
        return

    y_rt = YAML()
    y_rt.default_flow_style = False
    y_rt.width = 120
    with plan_path.open("w") as f:
        y_rt.dump(plan, f)

    log_info(f"Appended {len(added)} source(s) to {plan_path}")
    for name in added:
        click.echo(f"  + {name}")


# ── Click command group ────────────────────────────────────────────────────────

@click.group()
def search():
    """Search biomedical databases for evidence-based sources."""


# ── rh-skills search pubmed ───────────────────────────────────────────────────────────

@search.command()
@click.option("--query", required=True, help="PubMed search query (supports MeSH, boolean, filters)")
@click.option("--max", "max_results", default=20, show_default=True, help="Maximum results to return")
@click.option("--filter", "filter_str", default=None, help='PubMed filter (e.g. "systematic review[pt]")')
@click.option("--api-key", default=None, envvar="NCBI_API_KEY", help="NCBI API key (env: NCBI_API_KEY)")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output structured JSON")
@click.option("--offline", is_flag=True, default=False,
              help="Skip network call; return offline reference links with the attempted query.")
@click.option("--append-to-plan", "append_to", default=None, metavar="TOPIC",
              help="Append results as stub source entries to this topic's discovery-plan.yaml.")
def pubmed(query, max_results, filter_str, api_key, as_json, offline, append_to):
    """Search PubMed via NCBI E-utilities."""
    if offline:
        click.echo(_OFFLINE_NOTICE, err=True)
        results = [
            {**r, "id": "", "pmid": None, "nct_id": None, "doi": None,
             "journal": "PubMed", "pmcid": None, "abstract_snippet": r["abstract_snippet"],
             "status": None, "phase": None, "conditions": [], "interventions": [],
             "_total_found": len(_OFFLINE_PUBMED)}
            for r in _OFFLINE_PUBMED
        ]
        click.echo(f"Offline: query recorded → {query!r}")
    else:
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

    if append_to:
        _append_results_to_plan(results, append_to, "pubmed-article", query)
    elif as_json:
        _format_json(results, query, "pubmed")
    else:
        total = results[0].pop("_total_found", len(results))
        click.echo(f"PubMed: {len(results)} of {total} results for: {query}")
        _format_human(results, "pubmed")


# ── rh-skills search pmc ─────────────────────────────────────────────────────────────

@search.command()
@click.option("--query", required=True, help="PMC search query")
@click.option("--max", "max_results", default=20, show_default=True, help="Maximum results to return")
@click.option("--filter", "filter_str", default=None, help="PMC filter string")
@click.option("--api-key", default=None, envvar="NCBI_API_KEY", help="NCBI API key (env: NCBI_API_KEY)")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output structured JSON")
@click.option("--offline", is_flag=True, default=False,
              help="Skip network call; return offline reference links with the attempted query.")
@click.option("--append-to-plan", "append_to", default=None, metavar="TOPIC",
              help="Append results as stub source entries to this topic's discovery-plan.yaml.")
def pmc(query, max_results, filter_str, api_key, as_json, offline, append_to):
    """Search PubMed Central for open-access full-text articles."""
    if offline:
        click.echo(_OFFLINE_NOTICE, err=True)
        results = [
            {**r, "id": "", "pmid": None, "nct_id": None, "doi": None,
             "journal": "PMC", "pmcid": None,
             "status": None, "phase": None, "conditions": [], "interventions": [],
             "_total_found": len(_OFFLINE_PUBMED)}
            for r in _OFFLINE_PUBMED
        ]
        click.echo(f"Offline: query recorded → {query!r}")
    else:
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

    if append_to:
        _append_results_to_plan(results, append_to, "pubmed-article", query)
    elif as_json:
        _format_json(results, query, "pmc")
    else:
        total = results[0].pop("_total_found", len(results))
        click.echo(f"PMC: {len(results)} of {total} results for: {query}")
        _format_human(results, "pmc")


# ── rh-skills search clinicaltrials ──────────────────────────────────────────────────

@search.command()
@click.option("--query", required=True, help="Condition or intervention search term")
@click.option("--max", "max_results", default=20, show_default=True, help="Maximum results to return")
@click.option("--status", "status_filter", default="COMPLETED,RECRUITING",
              show_default=True, help="Filter by trial status")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output structured JSON")
@click.option("--offline", is_flag=True, default=False,
              help="Skip network call; return offline reference links with the attempted query.")
@click.option("--append-to-plan", "append_to", default=None, metavar="TOPIC",
              help="Append results as stub source entries to this topic's discovery-plan.yaml.")
def clinicaltrials(query, max_results, status_filter, as_json, offline, append_to):
    """Search ClinicalTrials.gov via REST API v2."""
    if offline:
        click.echo(_OFFLINE_NOTICE, err=True)
        results = [
            {**r, "id": "", "pmid": None, "nct_id": None, "doi": None,
             "journal": None, "pmcid": None,
             "status": None, "phase": None, "conditions": [], "interventions": [],
             "_total_found": len(_OFFLINE_CLINICALTRIALS)}
            for r in _OFFLINE_CLINICALTRIALS
        ]
        click.echo(f"Offline: query recorded → {query!r}")
    else:
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

    if append_to:
        _append_results_to_plan(results, append_to, "registry", query)
    elif as_json:
        _format_json(results, query, "clinicaltrials")
    else:
        total = results[0].pop("_total_found", len(results))
        click.echo(f"ClinicalTrials.gov: {len(results)} of {total} results for: {query}")
        _format_human(results, "clinicaltrials")
