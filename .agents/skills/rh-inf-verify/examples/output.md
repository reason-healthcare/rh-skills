# Example Unified Verification Output

```text
$ rh-inf-verify verify diabetes-ccm
Running: rh-skills status show diabetes-ccm
Launching verify subagents for: discovery, ingest, extract

Topic Summary
- Topic: diabetes-ccm
- Overall status: review-required

Stage Results
- discovery
  - skill: rh-inf-discovery
  - applicability: applicable
  - status: pass
  - summary: discovery plan is present and internally consistent
  - blocking findings: none
  - advisory findings: none
  - next action: none
- ingest
  - skill: rh-inf-ingest
  - applicability: applicable
  - status: pass
  - summary: registered sources and normalized outputs remain consistent
  - blocking findings: none
  - advisory findings: none
  - next action: none
- extract
  - skill: rh-inf-extract
  - applicability: applicable
  - status: warning-only
  - summary: structured artifacts are valid but one approved conflict note still needs review
  - blocking findings: none
  - advisory findings:
    - workflow-steps still carries an unresolved reviewer note
  - next action: review the extract warning before formalize planning
- formalize
  - skill: rh-inf-formalize
  - applicability: not-yet-ready
  - status: not-applicable
  - summary: no formalize plan or computable artifact exists yet
  - blocking findings: none
  - advisory findings:
    - formalize verify becomes applicable after formalize planning begins
  - next action: run rh-inf-formalize plan diabetes-ccm after extract review is complete

Overall Readiness
- No stage is blocked, but reviewer attention is still required before the topic can advance.

Recommended Next Action
- Review the extract warning, then begin formalize planning.
```
