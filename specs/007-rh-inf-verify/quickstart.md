# Quickstart: `rh-inf-verify`

**A minimal worked example of unified, read-only topic verification.**

---

## Prerequisites

```bash
uv sync

rh-skills init diabetes-ccm
# complete one or more lifecycle stages first
```

The topic should already have some combination of:
- discovery, ingest, extract, or formalize lifecycle artifacts
- enough state for at least one stage-specific verify workflow to apply

---

## Step 1: Run unified verification

```bash
rh-inf-verify verify diabetes-ccm
```

Expected behavior:
- detects which lifecycle stages are applicable to the topic
- launches the applicable stage-specific verify workflows
- preserves stage-specific failures and warnings
- returns one consolidated topic verification report
- makes the first failing or warning stage and its next action visible near the top of the report
- performs no file writes and no tracking updates

---

## Step 2: Review stage-level outcomes

Expected report shape:

```text
Topic Summary
- Topic: diabetes-ccm
- Overall status: review-required
- First attention item: extract warning-only — review warnings before formalize begins

Stage Results
- discovery: applicability=applicable, status=pass
- ingest: applicability=applicable, status=pass
- extract: applicability=applicable, status=warning-only
- formalize: applicability=not-yet-ready, status=not-applicable

Overall Readiness
- Topic is not yet ready to advance without reviewer attention.

Recommended Next Action
- Review extract warnings before formalize begins.
```

---

## Step 3: Re-run after remediation

```bash
rh-inf-verify verify diabetes-ccm
```

Expected behavior:
- produces the same stage inventory for an unchanged topic
- updates the conclusions only when stage-specific verify outcomes change
- remains read-only and safe to repeat
