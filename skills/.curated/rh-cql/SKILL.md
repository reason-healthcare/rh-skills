---
name: "rh-cql"
description: "First-class CQL (Clinical Quality Language) authoring, review, debugging, and test-plan skill for the rh-skills informatics workflow."
compatibility: "Requires rh-skills project with topics/<topic>/computable/ structure and `rh` CLI on PATH"
metadata:
  author: "rh-skills"
  version: "1.0.0"
---

## User Input

```text
$ARGUMENTS
```

Read the user input and determine the operating mode (`author`, `review`, `debug`,
or `test-plan`). If no mode is stated, infer from context:
- Structured artifact YAML provided → `author`
- Existing `.cql` file + "review" / "check" / "audit" → `review`
- Error message or failing test provided → `debug`
- "test plan" / "fixtures" / "cases" requested → `test-plan`

If mode is still ambiguous, ask the user to confirm before proceeding.

**CONFLICTS**: Any decision that could produce incorrect or ambiguous output MUST
be confirmed by the human before proceeding. Do not resolve conflicts silently.

---

## Pre-Execution Checks

Before producing any output:

1. Confirm the `rh` CLI binary is reachable (via `RH_CLI_PATH`, `.rh-skills.toml [cql] rh_cli_path`, or `rh` on PATH). If absent, halt and show `cargo install rh` hint.
2. Confirm the topic directory `topics/<topic>/` exists. If it does not, halt and prompt the user to run `rh-skills init <topic>` or correct the topic name.
3. For **author** mode: confirm the structured artifact YAML exists at `topics/<topic>/structured/<artifact>.yaml`.
4. For **review**/**debug**/**test-plan** modes: confirm the `.cql` source file exists at `topics/<topic>/computable/<LibraryName>.cql`.

If any check fails, report the missing resource and halt. Do NOT proceed with a partial context.

---

## Guiding Principles

- **Deterministic work via CLI**: validation (`rh-skills cql validate`), compilation (`rh-skills cql translate`), and test execution (`rh-skills cql test`) are always delegated to the `rh-skills` CLI. The agent reasons about CQL but does not replace the CLI for deterministic operations.
- **Ownership boundary**: `rh-cql` owns `.cql` source files. `rh-inf-formalize` owns FHIR Library JSON wrappers. These boundaries are never crossed.
- **Human confirmation for conflicts**: any ambiguity, inconsistency, or multi-option decision MUST be surfaced to the human before the agent proceeds. Silent resolution is not permitted.
- **FHIRHelpers-agnostic runtime**: `rh cql compile` does not inject FHIRHelpers wrapper calls. Type coercion between FHIR and CQL system types is the runtime's responsibility, not the author's. Authors should still `include FHIRHelpers` for explicit conversions where needed.

---

## Mode: author

**Goal**: Produce a valid, well-formed CQL library from L2 structured artifacts.

### Inputs
- L2 structured artifact YAML from `topics/<topic>/structured/<artifact>.yaml`
- The topic name and library name (infer from artifact if not stated)
- Optionally: existing CQL libraries to include (pinned versions required)

### Workflow

1. **Read the structured artifact** — extract:
   - Measure/concept name → becomes the `library` identifier
   - FHIR R4 model version
   - Valuesets (name, OID/URL, version) — all must be pinned
   - Logic statements → map to CQL `define` names
   - Population criteria (if measure) → Initial Population, Denominator, Numerator

2. **Apply the CQL style guide** (see Style Guide section below) and the
   **authoring rubric** (see Authoring Rubric section below) before writing any code.

3. **Draft the CQL library** using this template:

   ```cql
   /**
    * Library: <LibraryName>
    * Version: 1.0.0
    * Description: <one-line description from artifact>
    * Author: rh-cql (generated from structured artifact)
    * Date: <today>
    */
   library <LibraryName> version '1.0.0'

   using FHIR version '4.0.1'

   include FHIRHelpers version '4.0.1' called FHIRHelpers

   codesystem "<SystemName>": '<system-url>'

   valueset "<ValuesetName>": '<valueset-url>'  // version '<pinned-version>'

   parameter "Measurement Period" Interval<DateTime>
     default Interval[@2024-01-01, @2024-12-31]

   context Patient

   define "Initial Population":
     <expression>

   define "Denominator":
     "Initial Population"

   define "Numerator":
     <expression>
   ```

4. **Check the library against the authoring rubric** (all 10 areas) — see
   Authoring Rubric section.

5. **Validate** by calling the deterministic CLI command:
   ```
   rh-skills cql validate <topic> <LibraryName>
   ```
   Do not declare the library complete until `rh-skills cql validate` exits 0.
   If it exits non-zero, read the error output and fix issues before retrying.

6. **Produce the FHIR Library wrapper** by calling:
   ```
   rh-skills formalize <topic> <artifact>
   ```
   This step is owned by `rh-inf-formalize`, not by `rh-cql`. Hand off after
   the `.cql` file is validated.

### Output contract
- `.cql` file at `topics/<topic>/computable/<LibraryName>.cql`
- Passes `rh-skills cql validate` with zero errors
- Follows all style guide and rubric requirements
- FHIR Library JSON wrapper produced by `rh-skills formalize`

---

## Mode: review

**Goal**: Produce a structured Markdown review report classifying findings as
`BLOCKING`, `ADVISORY`, or `INFO`.

### Inputs
- Path to an existing `.cql` file
- Optionally: context about the intended use (measure, CDS rule, etc.)

### Workflow

1. Read the CQL source fully before writing any finding.
2. Apply the **authoring rubric** (10 areas) — flag deficiencies.
3. Apply the **high-risk pattern catalog** (7 categories) — flag matches.
4. Apply the **packaging rubric** (4 concerns) — flag issues.
5. Write the review report.

### Report format

```markdown
# CQL Review Report: <LibraryName>
**Reviewed**: <date>
**File**: `topics/<topic>/computable/<LibraryName>.cql`
**Reviewer**: rh-cql (automated review)

## Summary
- BLOCKING: N
- ADVISORY: N
- INFO: N

## Findings

### BLOCKING: <Finding Category>
**Area**: <rubric area or high-risk pattern>
**Evidence**:
```cql
<quoted excerpt>
```
**Issue**: <description>
**Recommended fix**: <concrete fix>

### ADVISORY: ...
### INFO: ...

## Rubric Coverage
| Area | Status | Notes |
|------|--------|-------|
| Model declaration and version | ✓ PASS / ✗ FAIL | ... |
| ... (all 10 areas) |

## High-Risk Pattern Scan
| Pattern | Status | Notes |
|---------|--------|-------|
| Unpinned terminology | ✓ PASS / ✗ FOUND | ... |
| ... (all 7 patterns) |

## Packaging
| Concern | Status | Notes |
|---------|--------|-------|
| CQL source present | ✓ / ✗ | ... |
| ... |
```

### Output contract
- Review report at `topics/<topic>/process/reviews/<LibraryName>-review.md`
- All 10 rubric areas covered (no category omitted)
- All 7 high-risk patterns scanned
- Accepted by `rh-skills verify` as review evidence

---

## Mode: debug

**Goal**: Identify the root cause of a CQL error and propose a minimal corrective
change.

### Inputs (provide at least one)
- A `.cql` file path
- Translator error from `rh-skills cql validate`
- Failing fixture: `case-NNN/input/bundle.json` + `expected/expression-results.json`
  \+ actual output from `rh cql eval`
- Runtime error description

### Workflow

1. **Classify the error type** using the taxonomy below.
2. **Locate the responsible `define`** — trace from the error message or failing
   expression back to the source statement.
3. **Propose the minimal corrective change** — prefer one-line fixes over
   restructuring.

### Error taxonomy

| Category | Description | Fix domain |
|----------|-------------|------------|
| Temporal precision | Date/time comparison with mismatched precision | Authoring |
| Null propagation | Unexpected null from missing optional element | Authoring |
| Terminology mismatch | Code not in valueset, wrong system URL | Authoring |
| Retrieve scope | Too broad a retrieve, filtered after the fact | Authoring |
| Unit conversion | Quantity comparison without normalization | Authoring |
| Version drift | Library or valueset version changed | Authoring |
| Context misuse | `Patient` context used where wrong | Authoring |
| Missing binary | `rh` not on PATH or CQL_TRANSLATOR_PATH unset | Environment |
| Model mismatch | Wrong FHIR version, QI-Core vs base FHIR | Environment |
| Translator option mismatch | Options differ between compile and evaluate | Environment |

### Diagnosis report format

```markdown
# CQL Debug Report: <LibraryName>
**Error input**: <translator / test / runtime>

## Root Cause
**Category**: <from taxonomy>
**Responsible define**: `<define-name>` at line N
**Evidence**: <error message or diff>

## Explanation
<one paragraph>

## Minimal Corrective Change
```cql
// Before:
<old expression>

// After:
<new expression>
```

## Distinguishing authoring vs environment
<if authoring: fix by editing .cql>
<if environment: fix by correcting tooling setup / config>
```

---

## Mode: test-plan

**Goal**: Enumerate all `define` statements and produce a test plan Markdown plus
structurally valid fixture skeletons.

### Inputs
- Path to an existing `.cql` file
- Topic and library name

### Workflow

1. Parse all non-context `define` statements from the CQL source.
2. For each `define`, determine applicable test families from the matrix below.
3. Write the test plan Markdown.
4. Write fixture skeleton files for each case.

### Test family matrix

| Dimension | Case variants |
|-----------|--------------|
| Age | below threshold / at threshold / above threshold |
| Timing | before boundary / on boundary / after boundary |
| Terminology | code matches valueset / code not in valueset / code absent |
| Value | value present / value absent / value null |
| Events | single event / multiple events / conflicting events |

**Minimum cases per define**: 4×N rule — for N `define` statements, generate at
minimum 4N fixture cases: one positive, one negative, one null/absent, one boundary.

### Fixture directory structure

```
tests/cql/<LibraryName>/
├── case-001-<description>/
│   ├── input/
│   │   ├── patient.json        # FHIR R4 Patient resource
│   │   ├── bundle.json         # FHIR R4 Bundle (transaction or collection)
│   │   └── parameters.json     # (optional) FHIR Parameters for overrides
│   ├── expected/
│   │   └── expression-results.json   # { "<define>": <value>, ... }
│   └── notes.md                # What this case proves, placeholder explanations
├── case-002-<description>/
│   └── ...
```

`expression-results.json` format:
```json
{
  "Initial Population": true,
  "Denominator": true,
  "Numerator": false,
  "Patient Age": 45
}
```

### Test plan Markdown format

```markdown
# Test Plan: <LibraryName>

## Define Inventory
| Define | Purpose | Test families |
|--------|---------|--------------|
| <name> | <intent> | age, timing, terminology |
| ...    |          |              |

## Case Summary
| Case | Define(s) | Family | Expected outcome |
|------|-----------|--------|-----------------|
| case-001-... | ... | positive | IsAdult = true |
| ...           |     |          |                |

## Fixture Notes
<any special data requirements>
```

### Output contract
- Test plan at `topics/<topic>/process/test-plans/<LibraryName>-test-plan.md`
- Fixture directories at `tests/cql/<LibraryName>/case-NNN-<description>/`
- Every fixture has structurally valid JSON (not empty files)
- All `notes.md` files explain placeholder values

---

## Authoring Rubric (10 Areas)

Check every authored library against all 10 areas. Flag deficiencies in the
review report.

| # | Area | What to check |
|---|------|--------------|
| 1 | Model declaration and version | `using FHIR version '4.0.1'` present and pinned |
| 2 | Included libraries and versions | All `include` statements have explicit version strings |
| 3 | Terminology declarations and version pinning | All `valueset` and `codesystem` declarations have pinned versions or OIDs |
| 4 | Top-level documentation and intent | Library has a doc comment block with name, version, description, date |
| 5 | Separation of retrieval logic from derived logic | Retrieve (`[Condition]`, `[Observation]`, etc.) kept in dedicated `define`; derivations reference those defines |
| 6 | Reuse of helper functions | Repeated logic extracted into named helpers; no copy-paste expressions |
| 7 | Null/empty semantics | Null propagation is explicit; lists checked with `exists` before access |
| 8 | Interval boundary behavior | Interval operators (`during`, `starts`, `ends`, `overlaps`) include correct boundary (open/closed) |
| 9 | Date/time precision assumptions | Date truncation (`ToDate()`, `date from`) is explicit; no silent precision coercion |
| 10 | Output shape and expected result types | Each `define` has a clear expected type (Boolean, List, Interval, etc.) documented in a comment |

---

## High-Risk Pattern Catalog

Flag each pattern as BLOCKING (must fix before use) or ADVISORY (should fix).

| # | Pattern | Classification | What to look for |
|---|---------|---------------|-----------------|
| 1 | Unpinned terminology | BLOCKING | `valueset "X": 'urn:oid:...'` without version pinning where reproducibility matters |
| 2 | Hidden timezone/precision assumptions | ADVISORY | `Today()` or `Now()` without explicit context clock; date arithmetic without `ToDate()` |
| 3 | Quantity comparison without unit normalization | BLOCKING | `obs.value > 5 'mg'` where source unit may differ |
| 4 | Overly broad retrieves filtered ad hoc | ADVISORY | `[Observation]` without a `where` status filter; large retrieves narrowed by downstream defines |
| 5 | Duplicate logic instead of helper definitions | ADVISORY | Same expression repeated in 3+ defines without extraction |
| 6 | Ambiguous null handling | BLOCKING | `if X then Y` without `else null` where null branch matters; comparing null to a value without `~` |
| 7 | Dependence on implicit engine behavior | ADVISORY | Logic that relies on FHIRHelpers auto-injection, implicit conversions, or unspecified operator overloads |

---

## CQL Style Guide

### Library naming and versioning
- Library identifiers use PascalCase: `LipidManagementLogic`, `PHQ9AssessmentLogic`
- Version follows semantic versioning: `version '1.0.0'`
- Match the library filename: `LipidManagementLogic.cql` → `library LipidManagementLogic`

### Terminology declaration rules
- Always pin valueset versions in production libraries
- Prefer canonical VSAC/FHIR URLs over raw OIDs for new libraries
- One `codesystem` declaration per system; reuse across the library

### Retrieve patterns
- One `define` per resource type retrieve; name it `"<Resource> by <filter>"`
- Apply status filters in the retrieve define, not in derived defines
- Do not retrieve inside functions; retrieves belong at the library expression level

### Null and interval conventions
- Use `~` (equivalent) for concept comparisons, `=` for exact equality
- Use `exists ( ... )` before accessing list elements
- Prefer `Interval[start, end]` with explicit closed brackets over implicit

### Date/time precision rules
- Use `ToDate()` when comparing dates; use `ToDateTime()` for datetime comparisons
- Never rely on implicit precision coercion between `Date` and `DateTime`
- Use `FixedClock` / `"Measurement Period"` parameter for deterministic evaluation

### When to split into included libraries
- Extract reusable helpers (age, encounter, status) into a separate shared library
- A library over 200 lines with repeated patterns should be refactored

### Anti-pattern catalog
- ❌ `[Observation] O where O.status = 'final'` (literal string; use code)
- ❌ Nested function calls beyond 3 levels deep without intermediate defines
- ❌ `if X is not null then X else default` — prefer `Coalesce(X, default)`
- ❌ `First([Condition])` without an ordering expression
- ❌ Comparing dates with `=` instead of `same day as` or interval operators

---

## CLI Commands (Deterministic Boundary)

These are the **only** commands that perform file writes or validation. The agent
must call these — do not write files directly.

| Action | Command |
|--------|---------|
| Validate CQL syntax and semantics | `rh-skills cql validate <topic> <library>` |
| Compile CQL to ELM JSON | `rh-skills cql translate <topic> <library>` |
| Run fixture-based test cases | `rh-skills cql test <topic> <library>` |
| Write FHIR Library JSON wrapper | `rh-skills formalize <topic> <artifact>` |

`rh-skills cql validate` wraps `rh cql validate` (Rust-native CQL compiler in
`rh/crates/rh-cql`). For interactive debugging, `rh cql repl` and
`rh cql explain` are available directly.

---

## MCP Tools

| Tool | When to use |
|------|------------|
| `reasonhub-search_loinc` | Look up LOINC codes for observation concepts in the library |
| `reasonhub-search_snomed` | Look up SNOMED codes for condition/procedure concepts |
| `reasonhub-search_rxnorm` | Look up RxNorm codes for medication concepts |
| `reasonhub-codesystem_lookup` | Get UCUM units for a LOINC code |
| `reasonhub-search_valuesets` | Find existing ValueSets to reference |
| `reasonhub-search_spec_content` | Look up CQL specification sections for syntax/semantic questions |

---

## Human-in-the-Loop Rules

- **All conflicts must be confirmed by the human** before resolution. Never silently
  resolve ambiguity in clinical logic.
- If two valuesets could satisfy a concept, present both and ask the user to choose.
- If the rubric reveals a BLOCKING issue, halt and report — do not auto-fix.
- If `rh-skills cql validate` fails after two correction attempts, report the
  error and ask the user for guidance.
- Before writing more than one fixture case with placeholder data, confirm the
  fixture schema is acceptable.

---

## File Read/Write Table

| Operation | Path | Command |
|-----------|------|---------|
| Read structured artifact | `topics/<topic>/structured/<artifact>.yaml` | direct read |
| Write CQL source | `topics/<topic>/computable/<Library>.cql` | via `rh-skills formalize` (after author) |
| Write ELM JSON | `topics/<topic>/computable/<Library>.json` | via `rh-skills cql translate` |
| Write FHIR Library JSON | `topics/<topic>/computable/Library-<artifact>.json` | via `rh-skills formalize` |
| Write review report | `topics/<topic>/process/reviews/<Library>-review.md` | direct write |
| Write test plan | `topics/<topic>/process/test-plans/<Library>-test-plan.md` | direct write |
| Write fixture cases | `tests/cql/<LibraryName>/case-NNN-<desc>/` | direct write |

---

## Boundary with rh-inf-formalize

- `rh-cql` owns **CQL content** — the `.cql` source text and its logical correctness.
- `rh-inf-formalize` owns **FHIR Library JSON wrapper** — the `Library` resource that
  packages the CQL.
- `rh-cql` must not write Library JSON directly.
- `rh-inf-formalize` must not generate CQL content inline. For `measure`,
  `decision-table`, and `policy` artifact types, the `.cql` file must be authored by
  `rh-cql author` mode before `rh-skills formalize` is called.
- `rh-inf-formalize` does NOT invoke `rh-cql` for `terminology` and `assessment`
  artifact types (these do not produce CQL Libraries).
