# Quickstart: `rh-inf-status`

**A minimal worked example of consistent, deterministic RH status reporting.**

---

## Prerequisites

```bash
uv sync

rh-skills init diabetes-ccm
# complete zero or more lifecycle steps first
```

The repository may contain one topic or many topics.

---

## Step 1: Check one topic

```bash
rh-inf-status diabetes-ccm
```

Expected behavior:
- uses the canonical RH status surface
- shows the topic's current lifecycle state
- includes a `Next steps` section every time
- renders next steps as bullet items, not A/B/C-style choices
- performs no file writes and no tracking updates

Example shape:

```text
Topic: diabetes-ccm
Stage: Ingest

Artifacts:
- sources: 9
- structured: 0
- computable: 0

Next steps:
- Extract structured criteria from ingested sources: `rh-inf-extract plan diabetes-ccm`
- Check whether any source files have changed since ingest: `rh-skills status check-changes diabetes-ccm`
```

---

## Step 2: Check the portfolio

```bash
rh-inf-status
```

Expected behavior:
- shows a portfolio summary
- uses the same status vocabulary as the topic view
- presents recommended follow-up work as bullet items

If no topics exist yet, the command should explain that the portfolio is empty
and recommend `rh-skills init <topic>`.

---

## Step 3: Check for source drift

```bash
rh-skills status check-changes diabetes-ccm
```

Expected behavior:
- reports changed or missing sources explicitly
- shows which downstream structured and computable artifacts may now be stale
- includes deterministic bullet next steps for remediation or review

---

## Step 4: Error and recovery guidance

```bash
rh-inf-status missing-topic
```

Expected behavior:
- fails clearly when the requested topic does not exist
- recommends a recovery command such as `rh-skills list` or `rh-skills init missing-topic`
