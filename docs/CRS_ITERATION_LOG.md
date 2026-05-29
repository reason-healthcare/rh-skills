# CRS Iteration Log

## Iteration 001 - Decision Table Extract Rerun

Date: 2026-06-01

Hypothesis:
Rerunning the approved `decision-table` extract in the external CRS project will
show whether the current extract CLI and prompt can regenerate a structurally
valid L2 artifact for a narrative surgical guideline without hand-editing.

Framework surfaces exercised:

- CLI: `src/rh_skills/commands/promote.py`
- Docs/process: [AI iteration guide](./AI_ITERATION_GUIDE.md)
- External test project:
  `/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs`

Commands run:

```bash
LLM_PROVIDER=openai RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills promote derive crs-surgical-management decision-table --force \
  --source CPG_SurgCRS_FAQ_V6_pdf \
  --source GLIA_Summary_Report-CPGSurgCRS-Final_pdf \
  --source Otolaryngol_head_neck_surg_2025_Shin_Clinical_Practice_Guideline_Surgical_Management_of_Chronic_Rhinosinusitis_pdf \
  --source crs_scope_pdf \
  --source crs_stage_1_search_narrative_pdf \
  --artifact-type decision-table \
  --clinical-question "What recommendation-scoped triggers, local conditions, and actions form the decision logic?" \
  --required-section summary \
  --required-section events \
  --required-section conditions \
  --required-section actions \
  --required-section rules \
  --required-section evidence_traceability
```

Observed execution issues:

- OpenAI with configured model returned `404 Not Found`.
- OpenAI with `OPENAI_MODEL=gpt-4o-mini` reached the API but returned
  `429 Too Many Requests`.
- Ollama fallback succeeded with `LLM_PROVIDER=ollama` and
  `OLLAMA_MODEL=gemma4:31b-cloud`.

Successful rerun command:

```bash
LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:31b-cloud \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills promote derive crs-surgical-management decision-table --force \
  --source CPG_SurgCRS_FAQ_V6_pdf \
  --source GLIA_Summary_Report-CPGSurgCRS-Final_pdf \
  --source Otolaryngol_head_neck_surg_2025_Shin_Clinical_Practice_Guideline_Surgical_Management_of_Chronic_Rhinosinusitis_pdf \
  --source crs_scope_pdf \
  --source crs_stage_1_search_narrative_pdf \
  --artifact-type decision-table \
  --clinical-question "What recommendation-scoped triggers, local conditions, and actions form the decision logic?" \
  --required-section summary \
  --required-section events \
  --required-section conditions \
  --required-section actions \
  --required-section rules \
  --required-section evidence_traceability
```

Validation result:

```bash
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills validate crs-surgical-management structured decision-table
```

Result:

- Validation failed.
- Missing required fields:
  - `artifact_type`
  - `clinical_question`
  - `sections`

Observed artifact delta:

- Previous artifact was a complete L2 decision-table with `sections.events`,
  `sections.conditions`, `sections.actions`, `sections.rules`, and
  `evidence_traceability`.
- Regenerated artifact only contained top-level metadata fields and
  `derived_from`.
- This means the CLI accepted and wrote model output that was structurally
  incomplete for L2.

Primary finding:

- `promote derive` currently trusts raw LLM YAML too much.
- The extract system prompt only requires generic metadata fields and does not
  force `artifact_type`, `clinical_question`, or `sections`.
- The CLI writes the LLM output before validating required L2 structure, so an
  invalid extract artifact can replace a previously valid one.

Generalizability assessment:

- This is a framework issue, not a CRS-only issue.
- Any narrative guideline artifact generated through `promote derive` could
  lose required L2 structure the same way.

Plan adjustment:

- Subsequent iterations should use `LLM_PROVIDER=stub` by default.
- Live-model execution introduced avoidable noise here:
  - configured OpenAI model returned `404`
  - fallback OpenAI model returned `429`
- Stub mode is the better default for validating framework mechanics before
  doing any content-quality pass.

Next change to try:

1. Strengthen the extract prompt so it explicitly requires:
   - `artifact_type`
   - `clinical_question`
   - `sections`
   - all requested `required_sections`
2. Add post-generation validation before overwriting the structured artifact.
3. Fail the command if the generated YAML is missing required L2 fields.
4. Add a regression test proving `derive --force` cannot replace a valid
   artifact with structurally invalid LLM output.

## Iteration 002 - Decision Table Extract Rerun in Stub Mode

Date: 2026-06-01

Hypothesis:
Running the same extract step with `LLM_PROVIDER=stub` will remove live-model
noise and show whether the framework's built-in scaffold path is a reliable
mechanical baseline.

Mode:

- `LLM_PROVIDER=stub`

Commands run:

```bash
LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills promote derive crs-surgical-management decision-table --force \
  --source CPG_SurgCRS_FAQ_V6_pdf \
  --source GLIA_Summary_Report-CPGSurgCRS-Final_pdf \
  --source Otolaryngol_head_neck_surg_2025_Shin_Clinical_Practice_Guideline_Surgical_Management_of_Chronic_Rhinosinusitis_pdf \
  --source crs_scope_pdf \
  --source crs_stage_1_search_narrative_pdf \
  --artifact-type decision-table \
  --clinical-question "What recommendation-scoped triggers, local conditions, and actions form the decision logic?" \
  --required-section summary \
  --required-section events \
  --required-section conditions \
  --required-section actions \
  --required-section rules \
  --required-section evidence_traceability

LLM_PROVIDER=stub \
RH_REPO_ROOT=/Users/taylorkingston/rh-skills-projects/aao_vermonster_crs \
uv run rh-skills validate crs-surgical-management structured decision-table
```

Result:

- Stub-mode derive completed and overwrote the external `decision-table.yaml`.
- Validation still failed, but for a different reason than Iteration 001.

Primary finding:

- The built-in `decision-table` stub scaffold is itself incompatible with the
  current validation contract.
- The generated artifact now includes the required top-level L2 fields, but the
  section content fails validation because the scaffold still uses old or
  placeholder semantics.

Concrete mismatches surfaced by validation:

- `sections.events[0]` is missing `trigger_type`
- `sections.conditions[0].values` uses `Yes`/`No` instead of booleans
- `sections.actions[*].kind` uses the legacy field name; validator expects
  `type`
- `sections.evidence_traceability` is empty
- multiple placeholder values remain unresolved and are treated as invalid

Interpretation:

- Iteration 001 showed the live-model path can write malformed L2 output.
- Iteration 002 shows the offline/stub path is also stale for
  `decision-table`.
- This confirms the issue is broader than prompt quality. The CLI's own stub
  generation logic is out of sync with the active validator and current L2
  schema expectations.

Framework surfaces implicated:

- `src/rh_skills/commands/promote.py`
  - `_build_stub_l2_artifact`
  - `_stub_section_value`
- `src/rh_skills/commands/validate.py`
- `src/rh_skills/validators/decision_table.py`
- tests covering extract stubs and decision-table validation

Next change to try:

1. Update the `decision-table` stub generator so it emits:
   - `trigger_type` on events
   - boolean condition values
   - `type` instead of legacy `kind`
   - minimally valid evidence traceability scaffolding
2. Make `promote derive` validate generated L2 output before overwriting the
   target artifact.
3. Add tests proving the stub path stays aligned with current
   `decision-table` validation rules.

### Retry After Refresh Steps

Date: 2026-06-01

Refresh actions completed before rerun:

```bash
cd /Users/taylorkingston/projects/rh-skills
make install

cd /Users/taylorkingston/rh-skills-projects/aao_vermonster_crs
rh-skills skills init --from /Users/taylorkingston/projects/rh-skills/skills/.curated --force
```

Observed result:

- The refreshed install state did not change the stub-mode validation outcome.
- The same `decision-table` scaffold defects remain:
  - missing `trigger_type`
  - `Yes`/`No` condition enums instead of booleans
  - legacy `kind` field instead of `type`
  - empty evidence traceability
  - unresolved placeholder values

Conclusion:

- This is not an artifact of stale installed CLI or stale installed skills.
- The source framework behavior itself needs to change before the external
  rerun can progress to formalize.
