# Contract: Status Output Contract

**Phase 1 Design Artifact** | **Branch**: `008-rh-inf-status`

---

## Goal

Define the required user-facing contract for topic and portfolio status output.

## Canonical Surface

`rh-inf-status` must be backed by the canonical `rh-skills status` command
family rather than a separate status engine.

## Required Output Elements

Every status response must include:

1. current topic or portfolio context
2. lifecycle stage or equivalent status summary
3. enough artifact or readiness context to explain the current state
4. a `Next steps` section

For failure or empty-state responses, the output must still make the recovery
path explicit even if the normal status block cannot be rendered.

## Next-Step Presentation Rules

- The `Next steps` section must always be present.
- Next steps must be rendered as bullet items.
- Lettered choice menus (`A)`, `B)`, `C)`) are not allowed.
- Each actionable bullet should include the exact command when applicable.
- If no action is required, the section should say so explicitly.

## Consistency Rules

- Topic and portfolio outputs must use the same status vocabulary.
- Drift-reporting output must use the same next-step presentation contract.
- The status skill may add minimal explanatory context, but it must not invent
  recommendations beyond the deterministic CLI output.
- Missing-tracking, empty-portfolio, and unknown-topic responses must provide a
  clear recovery command such as `rh-skills init <topic>` or `rh-skills list`.
