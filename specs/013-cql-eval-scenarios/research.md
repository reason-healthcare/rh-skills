# Research: CQL Eval Scenarios — Full Measure Pipeline

**Branch**: `013-cql-eval-scenarios` | **Phase**: 0

## Decision 1 — Scenario YAML schema

**Decision**: Use the schema defined in `eval/scenarios/README.md` exactly as-is.

**Rationale**: The existing schema supports all required checks (`exists`,
`contains`, `contains_any_file_with`, `event`) and has a `files[].content`
literal-block-scalar pattern that can embed multiline CQL without escaping.

**Alternatives considered**: Adding a new `contains_cql_pattern:` check type
was considered but rejected — it would require harness code changes and is
out of scope. The string `contains:` checks on specific CQL keywords are
sufficient for the quality_focus evaluation goals.

---

## Decision 2 — Shared normalized source content

**Decision**: Embed `acc-aha-cholesterol-2023.md` inline in the extract
scenario's workspace fixture. The formalize scenarios re-embed the same
content (trimmed) since they only need the L2 artifact fixture, not the
full source.

**Rationale**: FR-004 requires all fixtures to be self-contained. Cross-
referencing a shared fixture file would require harness support for fixture
inheritance, which does not exist.

**Alternatives considered**: A `fixture:` file reference to
`eval/fixtures/acc-aha-cholesterol-2023.md` would reduce duplication but
requires the harness to support path-relative fixture loading — confirmed
supported by the schema, but the inline approach keeps each scenario fully
readable in isolation.

---

## Decision 3 — CQL content format in workspace fixtures

**Decision**: Use YAML literal block scalars (`|`) for all CQL content in
`workspace.files[].content`. Do not base64-encode. The eval harness writes
the content directly to disk.

**Rationale**: Confirmed in spec Assumptions section: "Inline CQL code samples
... use YAML literal block scalars (`|`) to preserve line breaks and special
characters." The YAML parser handles `"`, `|` inside literal blocks without
escaping.

**Alternatives considered**: Base64-encoding CQL was considered to avoid YAML
parsing ambiguity but adds unnecessary complexity and reduces readability during
scenario review.

---

## Decision 4 — Valueset URLs

**Decision**: Use real NLM VSAC canonical URLs from the existing
`cvd-risk-management` extract scenario as representative fixtures. They do not
need to resolve at test time.

- Hyperlipidemia: `http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.9`
- Statin medications: `http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1047.97`
- Liver disease: `http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.14`
- Pregnancy: `http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1032.80`
- ESRD: `http://cts.nlm.nih.gov/fhir/ValueSet/2.16.840.1.113762.1.4.1116.65`

**Rationale**: Realistic URLs give agents accurate MCP-resolvable fixtures.
Using placeholder URLs (e.g., `http://example.org/...`) would fail ReasonHub
MCP lookups and undermine efficiency_focus testing.

---

## Decision 5 — CQL population define-statement chaining

**Decision**: The canonical CQL structure for the formalize scenarios follows
the FHIR CQF-Measures IG pattern:

```cql
define "Initial Population": <age + diagnosis criteria>
define "Denominator": "Initial Population"
define "Numerator": <medication criteria during "Measurement Period">
define "Denominator Exclusion": <exclusion logic>
```

**Rationale**: This matches the existing `measure.yaml` scenario for
`diabetes-quality` and the FHIR US Core measure profiles. It provides concrete
`contains:` check targets (define statement names) that are specific and
machine-verifiable.

---

## Decision 6 — Tracking event names

**Decision**: Use the following existing tracking event names (no new events):

| Stage | Event |
|-------|-------|
| Ingest complete | `ingest_complete` |
| Extract planned | `extract_planned` |
| Structured artifact derived | `structured_derived` |
| Formalize planned | `formalize_planned` |
| Computable resources converged | `computable_converged` |

**Rationale**: All events are confirmed in existing scenarios (`measure.yaml`,
`single-source.yaml`). Introducing new event names would require CLI code
changes, which is out of scope.
