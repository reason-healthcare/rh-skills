# Research: rh-cql — First-Class CQL Authoring Skill

**Branch**: `014-rh-cql-skill` | **Phase**: 0

## Decision 1 — CQL output path: `computable/` vs `output/`

**Decision**: CQL `.cql` files and ELM JSON are written to `topics/<topic>/computable/`
alongside the FHIR Library JSON — not to a separate `output/` directory.

**Rationale**: The spec proposes `topics/<topic>/output/` but the existing codebase
writes all L3 artifacts to `computable/` (see `formalize.py:316`,
`package.py` collecting from `computable/`). A separate `output/` directory
would break `rh-skills package` and require tracking schema changes. Consistency
wins.

**Alternatives considered**: A separate `output/` directory was spec'd to distinguish
intermediate CQL from packaged artifacts, but the `computable/` convention is
already the "ready to package" boundary in this project. Moving to `output/`
would require updating `package.py`, `verify.py`, and tracking schema — out of
scope.

---

## Decision 2 — CQL toolchain: use `rh` CLI (native Rust, in-house)

**Decision**: All CQL operations delegate to the `rh` CLI binary from
`rh/apps/rh-cli`, which wraps the `rh-cql` Rust crate. No external Java JAR or
Node.js framework is needed.

| `rh-skills cql` sub-command | `rh` invocation |
|---|---|
| `validate <topic> <library>` | `rh cql validate <file.cql>` |
| `translate <topic> <library>` | `rh cql compile <file.cql> --output <dir>` |
| `test <topic> <library>` | `rh cql eval <file.cql> --expr <name> --data <bundle.json>` per fixture |

The `rh` binary path is resolved from:
1. `RH_CLI_PATH` env var
2. `.rh-skills.toml` `[cql] rh_cli_path`
3. `rh` on `$PATH` (default — works after `cargo install --path apps/rh-cli`)

If absent, commands emit a clear install message and exit non-zero.

**Rationale**: `rh-cql` is a first-party pure-Rust CQL compiler + evaluator with
no Java or Node.js dependencies. It provides exactly the operations needed:
`validate`, `compile` (→ ELM JSON), `eval` (→ expression value with data), `explain`,
and `repl`. The `rh cql eval` command accepts a FHIR bundle JSON directly as
`--data`, which maps cleanly onto the fixture test format.

**Alternatives eliminated**: CQFramework Java JAR and AHRQ Node.js testing
framework are no longer needed.

---

## Decision 3 — Test execution: `rh cql eval` per fixture case

**Decision**: `rh-skills cql test <topic> <library>` iterates over
`tests/cql/<library-name>/case-*/` directories, running:

```bash
rh cql eval topics/<topic>/computable/<library>.cql \
    --expr <expression-name> \
    --data tests/cql/<library>/case-NNN/input/bundle.json
```

for each key in `expected/expression-results.json`. Results are compared
against expected values; mismatches are reported per case. Exit code is
non-zero if any case fails.

**Rationale**: `rh cql eval` directly evaluates named CQL expressions against
FHIR bundle data — this is precisely the fixture-based test pattern needed.
No separate testing framework required.

**Fixture format**: `input/bundle.json` is a FHIR R4 Bundle; `expected/expression-results.json`
is a flat map of `{ "<define-name>": <expected-value> }`. This is simpler than the
AHRQ YAML format and easier for an agent to generate.

---

## Decision 4 — rh-cql author mode and CQL file ownership

**Decision**: In agent mode, `rh-cql author` generates the full CQL source and
writes it to disk via `RH_STUB_RESPONSE` + `rh-skills formalize <topic> <artifact>`
(which calls the existing formalize command). In CLI mode with `LLM_PROVIDER` set,
`_invoke_llm` is called with a CQL-specific system prompt from SKILL.md.

**Rationale**: This is the same pattern used by `rh-inf-formalize` for all L3
artifacts. No new write path is needed. `rh-skills formalize` already handles
writing `.cql` and Library JSON when the LLM produces the combined output.

**Alternatives considered**: A dedicated `rh-skills cql author` command was
considered but would duplicate the `rh-skills formalize` write path. The boundary
is: `rh-cql` owns the CQL *content* (the reasoning); `rh-skills formalize` owns
the *file write*.

---

## Decision 5 — formalize.py CQL stub removal

**Decision**: Remove lines 355–376 in `formalize.py` that generate a hard-coded
CQL stub (`library <Name> version '1.0.0'\n...`). Replace with a comment block:
`# CQL content is authored by rh-cql skill — see skills/.curated/rh-cql/SKILL.md`.
The FHIR Library JSON wrapper generation remains in formalize.

**Rationale**: The existing stub is a minimal placeholder that produces invalid CQL
(no FHIR model, no terminology). It was always intended to be replaced by real CQL
content from the agent. Removing it makes the delegation boundary explicit.

**Impact**: Existing tests that assert a `.cql` file is created by `formalize` will
need to be updated to either mock the CQL content or assert the delegation comment.
This is a small, well-scoped change.

---

## Decision 6 — Review report and test plan file locations

**Decision**:
- Review reports: `topics/<topic>/process/reviews/<library-name>-review.md`
- Test plans: `topics/<topic>/process/test-plans/<library-name>-test-plan.md`
- Test fixtures: `tests/cql/<library-name>/case-NNN-<description>/`

**Rationale**: `process/` subdirectories are the established pattern for all
human-reviewable artifacts (plans, concept files). `tests/cql/` mirrors the
directory layout proposed in the research and keeps test fixtures at the repo
root separate from topic-specific data.

---

## Decision 7 — Skill audit test coverage for rh-cql

**Decision**: Extend `tests/skills/test_skill_audit.py` with an `rh-cql`-specific
contract test class (`TestRhCqlSkillContract`) checking:
- SKILL.md defines all four modes by name
- SKILL.md references `rh-skills cql validate` deterministically
- `reference.md` contains URLs for all four corpus layers
- `examples/` directory has at least two worked examples

**Rationale**: Every existing skill has audit tests. `rh-cql` must pass the same
framework contract suite automatically (skill schema, security, companion files).

---

## `rh cql` invocation reference (confirmed from rh-cli source)

```bash
# Build / install
cargo install --path /path/to/rh/apps/rh-cli

# Validate (exits non-zero on errors, structured stderr)
rh cql validate library.cql

# Compile to ELM JSON
rh cql compile library.cql --output topics/topic/computable/

# Evaluate a named expression against FHIR data
rh cql eval library.cql --expr "IsAdult" --data bundle.json

# Evaluate with trace
rh cql eval library.cql --expr "IsAdult" --data bundle.json --trace

# Explain parse tree / semantic analysis
rh cql explain parse library.cql
rh cql explain compile library.cql

# Interactive REPL
rh cql repl
```

`rh cql validate` supports glob patterns and multiple inputs:
```bash
rh cql validate "topics/*/computable/*.cql"
```

For fixture testing, `rh-skills cql test` calls `rh cql eval` per expression,
captures stdout, and diffs against `expected/expression-results.json`.
