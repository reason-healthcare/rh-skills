# hi-status Reference

## Lifecycle Stages

| Stage | Tracking Key | Meaning |
|-------|-------------|---------|
| `initialized` | No sources, no structured, no computable | Topic created; discovery planning not yet done |
| `l1-discovery` | ≥1 source in `sources[]` | Sources ingested (L1 raw artifacts present) |
| `l2-semi-structured` | ≥1 entry in `topic.structured[]` | Extraction complete (L2 structured artifacts present) |
| `l3-computable` | ≥1 entry in `topic.computable[]` | Formalization complete (L3 computable artifact present) |

## Completeness Percentages

| Completeness | Condition |
|---|---|
| 25% | initialized — no sources yet |
| 50% | l1-discovery — sources present, no structured artifacts |
| 75% | l2-semi-structured — structured artifacts present, no computable |
| 100% | l3-computable — all artifact levels present |

## Pipeline Stage Bar

`hi status progress` outputs the pipeline as a flow with the active stage in
brackets:

```
Discovery → [Ingest] → Extract → Formalize
```

The bracketed label is the **next recommended stage**, not the completed stage.

## Next-Step Recommendations

`hi status next-steps` applies this state machine:

| State | Recommended action | Command |
|-------|-------------------|---------|
| No sources | Discover and ingest raw source artifacts (L1) | `hi-ingest plan` |
| Sources, no structured | Extract structured (L2) artifacts | `hi-extract plan` |
| Structured, no computable | Formalize to computable (L3) artifact | `hi-formalize plan` |
| All levels present | Review and validate artifacts | `hi validate <topic> <artifact>` |

## Source Change Detection

`hi status check-changes` re-checksums every source registered in
`tracking.yaml` and compares against stored checksums.

- **OK**: checksum matches stored value — source is unchanged
- **CHANGED**: current checksum differs — source has been modified on disk
- **MISSING**: file path does not exist — source was deleted or moved

For each changed or missing source, the CLI lists structured artifacts whose
`derived_from[]` field references that source name. These L2 artifacts are
"potentially stale" and should be regenerated.

## Plan Schema

Not applicable — `hi-status` is read-only and produces no plan artifact.

## Output Artifact

Not applicable — `hi-status` is read-only and produces no output artifact.

## Glossary

| Term | Meaning |
|------|---------|
| L1 source | Raw ingested file (PDF, HTML, Word, etc.) in `sources/` |
| L2 structured | Extracted structured criteria file in `topics/<name>/structured/` |
| L3 computable | Formalized FHIR/CQL artifact in `topics/<name>/computable/` |
| Checksum drift | A source file on disk differs from its recorded SHA-256 checksum |
| Stale artifact | An L2 or L3 artifact whose upstream source has changed |
| tracking.yaml | Single authoritative lifecycle ledger at the repo root |
