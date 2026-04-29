# rh-inf-status Reference

## CLI Commands

| Command | Purpose |
|---------|---------|
| `rh-skills status` | Portfolio summary — all topics with deterministic bullet next steps |
| `rh-skills status show <topic>` | Single-topic detail — stage, artifact counts, last event, and bullet next steps |
| `rh-skills status check-changes <topic>` | Drift detection — re-checksum all registered sources and emit remediation bullets |
| `rh-skills status progress <topic>` | Detailed pipeline bar with completeness % and bullet next steps |
| `rh-skills status next-steps <topic>` | Ranked deterministic bullet recommendations (power-user) |

The skill uses `rh-skills status` (portfolio) and `rh-skills status check-changes <topic>`
as its two main commands. The `show`, `progress`, and `next-steps` sub-commands
are available for power users.

## Lifecycle Stages

| Tracking Key | Display Label | Condition | Meaning |
|---|---|---|---|
| `initialized` | Discovery | No sources, no structured, no computable | Topic created; no sources yet |
| `l1-discovery` | Ingest | ≥1 source in `sources[]` | Raw sources ingested |
| `l2-semi-structured` | Extract | ≥1 entry in `topic.structured[]` | Structured criteria extracted |
| `l3-computable` | Formalize | ≥1 entry in `topic.computable[]` | Computable artifact present |

The display label is shown in `rh-skills status` portfolio output and `rh-skills status progress`.
The tracking key is stored in `tracking.yaml` and returned by `rh-skills status show --json`.

## Portfolio Output Format

`rh-skills status` (no arguments) prints a project-level header followed by a
block per topic:

```
Research Portfolio
  Topics:   <N>
  Sources:  <N shared sources>

<topic-name> — <Title>
  Stage:  <Display Label> [· discovery plan ✓]
  Sources:     <N>          ← shown only when N > 0
  Structured:  <N>          ← shown only when N > 0
  Computable:  <N>          ← shown only when N > 0
  Next steps:
    - <deterministic action>
    - <deterministic action>
```

Sources are **shared** across all topics; the count is global.

## Next-Step State Machine

The portfolio and sub-commands apply this logic per topic:

| State | Primary recommendation |
|-------|----------------------|
| No sources, no discovery plan | `rh-inf-discovery plan <topic>` or place files in `sources/` and run `rh-inf-ingest implement` |
| No sources, discovery plan present | `rh-inf-ingest plan <topic>` |
| Sources present, no structured | `rh-inf-extract plan <topic>` |
| Structured present, no computable | `rh-inf-formalize plan <topic>` |
| All levels present | `rh-inf-verify verify <topic>` plus an explicit “no immediate action required” note |

A discovery plan is detected by the presence of `topics/<topic>/process/plans/discovery-plan.yaml`.

## Source Change Detection

`rh-skills status check-changes <topic>` re-checksums every source registered in
`tracking.yaml` and compares against stored SHA-256 checksums.

- **OK**: checksum matches stored value — source is unchanged
- **CHANGED**: current checksum differs — source has been modified on disk
- **MISSING**: file path does not exist — source was deleted or moved

For each changed or missing source, the CLI lists structured artifacts whose
`derived_from[]` field references that source and computable artifacts whose
`converged_from[]` fields depend on those structured artifacts. These L2/L3
artifacts are "potentially stale" and should be regenerated or re-reviewed
after refresh.

## Next-Step Presentation

- All next steps are rendered as bullet items.
- Lettered menus (`A)`, `B)`, `C)`) are not part of the canonical status
  contract.
- If nothing urgent is pending, the CLI still emits a bullet explicitly stating
  that no immediate action is required.

## Error and Empty-State Behavior

- If `tracking.yaml` is missing, status commands tell the user to run
  `rh-skills init <topic>`.
- If the portfolio is empty, `rh-skills status` explains that no topics exist
  yet and recommends initialization.
- If a requested topic is missing, status commands tell the user to run
  `rh-skills list` to inspect available topics or `rh-skills init <topic>` to
  start the requested one.

Exit code 0 = all sources unchanged. Exit code 1 = at least one change found.

## Plan Schema

Not applicable — `rh-inf-status` is read-only and produces no plan artifact.

## Output Artifact

Not applicable — `rh-inf-status` is read-only and produces no output artifact.

## Glossary

| Term | Meaning |
|------|---------|
| L1 source | Raw ingested file (PDF, HTML, Word, etc.) in `sources/` |
| L2 structured | Extracted structured criteria file in `topics/<name>/structured/` |
| L3 computable | Formalized FHIR/CQL artifact in `topics/<name>/computable/` |
| Checksum drift | A source file on disk differs from its recorded SHA-256 checksum |
| Stale artifact | An L2 or L3 artifact whose upstream source has changed |
| tracking.yaml | Single authoritative lifecycle ledger at the repo root |
| Discovery plan | `topics/<topic>/process/plans/discovery-plan.yaml` — output of rh-inf-discovery |
