from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "ttd" / "crs-surgical-management"
STRUCTURED_DIR = FIXTURE_ROOT / "structured"


def _load_yaml(path: Path):
    return YAML(typ="safe").load(path.read_text())


def test_crs_ttd_target_structure_exists_and_is_complete():
    target = _load_yaml(FIXTURE_ROOT / "target-structure.yaml")

    assert target["topic"] == "crs-surgical-management"
    assert target["model"]["pathway_plan"]["id"] == "crs-surgical-management-pathway"

    recommendation_ids = [
        entry["id"] for entry in target["model"]["recommendation_plans"]
    ]
    assert recommendation_ids == [
        "crs-rec-medical-therapy-guardrails",
        "crs-rec-offer-or-defer-sinus-surgery",
        "crs-rec-preoperative-management",
        "crs-rec-postoperative-management",
    ]

    assert len(target["model"]["activity_definitions"]) >= 12
    assert len(target["model"]["libraries"]) == 7
    assert set(target["source_coverage"]) == {
        "KAS-1A",
        "KAS-1B",
        "KAS-2",
        "KAS-3",
        "KAS-4",
        "KAS-5",
        "KAS-6",
        "KAS-7",
        "KAS-8",
        "KAS-9",
        "KAS-10",
        "KAS-11",
    }


def test_crs_ttd_structured_fixture_split_matches_target_model():
    structured_files = sorted(path.name for path in STRUCTURED_DIR.glob("*.yaml"))
    assert structured_files == [
        "crs-rec-medical-therapy-guardrails.yaml",
        "crs-rec-offer-or-defer-sinus-surgery.yaml",
        "crs-rec-postoperative-management.yaml",
        "crs-rec-preoperative-management.yaml",
        "crs-surgical-management-pathway.yaml",
    ]

    pathway = _load_yaml(STRUCTURED_DIR / "crs-surgical-management-pathway.yaml")
    assert pathway["artifact_type"] == "care-pathway"
    assert [step["id"] for step in pathway["sections"]["steps"]] == [
        "evaluate-and-confirm",
        "review-medical-therapy-guardrails",
        "decide-on-surgery",
        "continue-nonsurgical-management",
        "prepare-for-surgery",
        "manage-postoperative-course",
    ]

    offer_or_defer = _load_yaml(
        STRUCTURED_DIR / "crs-rec-offer-or-defer-sinus-surgery.yaml"
    )
    assert offer_or_defer["artifact_type"] == "decision-table"
    action_ids = [entry["id"] for entry in offer_or_defer["sections"]["actions"]]
    assert (
        "counsel-on-surgery-benefits-limits-and-long-term-management" in action_ids
    )
    offer_rule = next(
        rule
        for rule in offer_or_defer["sections"]["rules"]
        if rule["id"] == "offer-surgery-after-counseling"
    )
    assert offer_rule["when"]["expectations-reviewed"] == "yes"

    postop = _load_yaml(STRUCTURED_DIR / "crs-rec-postoperative-management.yaml")
    assert [event["id"] for event in postop["sections"]["events"]] == [
        "sinus-surgery-scheduled",
        "postoperative-followup-window-reached",
    ]
