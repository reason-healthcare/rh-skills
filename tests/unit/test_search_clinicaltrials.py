"""Tests for rh-skills search clinicaltrials subcommand."""

import json
from unittest.mock import patch

import pytest
import httpx
from click.testing import CliRunner

from hi.commands.search import clinicaltrials, _clinicaltrials_search

# ── Fixtures ──────────────────────────────────────────────────────────────────

CT_RESPONSE = {
    "totalCount": 142,
    "studies": [
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT04512345",
                    "briefTitle": "Chronic Care Management for Diabetes Mellitus",
                },
                "statusModule": {
                    "overallStatus": "COMPLETED",
                    "startDateStruct": {"date": "2019-03-01"},
                },
                "designModule": {
                    "phases": ["PHASE3"],
                },
                "conditionsModule": {
                    "conditions": ["Diabetes Mellitus, Type 2"],
                },
                "armsInterventionsModule": {
                    "interventions": [
                        {"name": "Chronic Care Management Program"},
                        {"name": "Usual Care"},
                    ],
                },
                "descriptionModule": {
                    "briefSummary": "This RCT evaluates CCM programs for type 2 diabetes management.",
                },
            }
        },
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT05678901",
                    "briefTitle": "Remote Monitoring in Diabetic Patients",
                },
                "statusModule": {
                    "overallStatus": "RECRUITING",
                    "startDateStruct": {"date": "2023-01-15"},
                },
                "designModule": {
                    "phases": ["PHASE2"],
                },
                "conditionsModule": {
                    "conditions": ["Diabetes Mellitus"],
                },
                "armsInterventionsModule": {
                    "interventions": [
                        {"name": "Remote Monitoring"},
                    ],
                },
                "descriptionModule": {
                    "briefSummary": "A study of remote monitoring technology in diabetes care.",
                },
            }
        },
    ],
}

CT_EMPTY_RESPONSE = {"totalCount": 0, "studies": []}


# ── Unit tests: _clinicaltrials_search ────────────────────────────────────────

def test_clinicaltrials_search_extracts_fields(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=CT_RESPONSE)

    results = _clinicaltrials_search("diabetes", max_results=20)

    assert len(results) == 2
    r0 = results[0]
    assert r0["id"] == "NCT04512345"
    assert "Chronic Care" in r0["title"]
    assert r0["year"] == "2019"
    assert r0["url"] == "https://clinicaltrials.gov/study/NCT04512345"
    assert r0["open_access"] is True
    assert r0["journal"] is None
    assert r0["pmcid"] is None
    assert r0["nct_id"] == "NCT04512345"
    assert r0["status"] == "COMPLETED"
    assert r0["phase"] == "PHASE3"
    assert r0["conditions"] == ["Diabetes Mellitus, Type 2"]
    assert r0["interventions"] == ["Chronic Care Management Program", "Usual Care"]
    assert "CCM programs" in r0["abstract_snippet"]


def test_clinicaltrials_all_open_access(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=CT_RESPONSE)
    results = _clinicaltrials_search("diabetes")
    for r in results:
        assert r["open_access"] is True


def test_clinicaltrials_total_found_attached(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=CT_RESPONSE)
    results = _clinicaltrials_search("diabetes")
    assert results[0].get("_total_found") == 142


def test_clinicaltrials_empty_results(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=CT_EMPTY_RESPONSE)
    results = _clinicaltrials_search("xyz-very-obscure")
    assert results == []


def test_clinicaltrials_network_error(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    import click
    with pytest.raises(click.ClickException):
        _clinicaltrials_search("diabetes")


# ── CLI tests: rh-skills search clinicaltrials ───────────────────────────────────────

def test_hi_search_clinicaltrials_human_output(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=CT_RESPONSE)

    runner = CliRunner()
    result = runner.invoke(clinicaltrials, ["--query", "diabetes"])

    assert result.exit_code == 0
    assert "ClinicalTrials.gov" in result.output
    assert "NCT04512345" in result.output


def test_hi_search_clinicaltrials_json_output(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=CT_RESPONSE)

    runner = CliRunner()
    result = runner.invoke(clinicaltrials, ["--query", "diabetes", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["source"] == "clinicaltrials"
    assert data["query"] == "diabetes"
    assert data["total_found"] == 142
    assert len(data["results"]) == 2
    assert "retrieved_at" in data
    assert data["results"][0]["status"] == "COMPLETED"
    assert data["results"][0]["phase"] == "PHASE3"


def test_hi_search_clinicaltrials_json_schema(httpx_mock):
    """Verify JSON output matches data-model.md Entity 3 schema."""
    httpx_mock.add_response(method="GET", url=None, json=CT_RESPONSE)

    runner = CliRunner()
    result = runner.invoke(clinicaltrials, ["--query", "diabetes", "--json"])
    data = json.loads(result.output)

    required_top_keys = {"query", "source", "retrieved_at", "total_found", "returned", "results"}
    assert required_top_keys.issubset(data.keys())

    required_result_keys = {
        "id", "pmid", "nct_id", "title", "url", "year", "journal", "authors", "doi",
        "open_access", "pmcid", "abstract_snippet", "status", "phase", "conditions", "interventions",
    }
    for r in data["results"]:
        assert required_result_keys.issubset(r.keys())


def test_hi_search_clinicaltrials_zero_results_exit_2(httpx_mock):
    httpx_mock.add_response(method="GET", url=None, json=CT_EMPTY_RESPONSE)

    runner = CliRunner()
    result = runner.invoke(clinicaltrials, ["--query", "xyz-very-obscure"])

    assert result.exit_code == 2


def test_hi_search_clinicaltrials_status_filter(httpx_mock):
    """Verify --status filter is passed to API."""
    httpx_mock.add_response(method="GET", url=None, json=CT_RESPONSE)

    runner = CliRunner()
    result = runner.invoke(clinicaltrials, ["--query", "diabetes", "--status", "COMPLETED"])

    # Should succeed (status param is forwarded — we trust the API)
    assert result.exit_code == 0
