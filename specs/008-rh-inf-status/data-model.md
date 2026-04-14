# Data Model: `rh-inf-status` Skill

**Phase 1 Design Artifact** | **Branch**: `008-rh-inf-status`

---

## Entity 1: Topic Status View

Represents the user-facing status summary for one topic.

**Fields**:
- `topic`: topic slug
- `title`: human-readable topic title
- `stage_key`: lifecycle key from tracking
- `stage_label`: user-facing lifecycle label
- `artifact_counts`: counts for sources, structured artifacts, and computable artifacts
- `last_event`: latest lifecycle event, if present
- `readiness`: topic-level interpretation such as ready, review-needed, or blocked
- `next_steps[]`: ordered list of `Next-Step Recommendation`

**Rules**:
- The view is read-only and derived from the canonical status CLI.
- `next_steps[]` must always be present, even when it contains a single “no
  immediate action required” recommendation.

---

## Entity 2: Portfolio Status View

Represents the user-facing summary across all topics in the repository.

**Fields**:
- `topics_count`: number of tracked topics
- `sources_count`: number of registered sources
- `topic_summaries[]`: ordered list of topic status summaries
- `empty_state_next_steps[]`: ordered list of recovery actions shown only when no
  topics exist yet

**Rules**:
- The portfolio view must use the same status vocabulary and recommendation style
  as the topic view.
- Topic summaries should remain individually scannable and each summary carries
  its own deterministic `next_steps[]` set.
- When one or more topics exist, the portfolio view does not add a second,
  aggregated portfolio-level next-step list beyond the per-topic summaries.
- When no topics exist, `empty_state_next_steps[]` provides initialization
  guidance such as `rh-skills init <topic>`.

---

## Entity 3: Next-Step Recommendation

Represents one deterministic follow-up action shown after a status readout.

**Fields**:
- `summary`: short action description
- `command`: exact command to run, when applicable
- `scope`: `topic | portfolio | informational`
- `priority`: stable display order within the next-step set

**Rules**:
- Recommendations are rendered as bullet items, not lettered choices.
- Recommendations come from deterministic lifecycle logic, not freeform agent
  invention.
- A “no immediate action required” recommendation is valid when nothing actionable
  is pending.

---

## Entity 4: Drift Finding

Represents a changed or missing source input and its downstream impact.

**Fields**:
- `source_name`: affected source identifier
- `drift_status`: `ok | changed | missing`
- `stored_checksum`: prior checksum when available
- `current_checksum`: newly observed checksum when available
- `affected_artifacts[]`: downstream structured or computable artifacts that may be stale
- `recommended_next_steps[]`: deterministic remediation actions

**Rules**:
- Drift findings are read-only observations.
- A changed or missing source should make downstream stale risk directly visible.

---

## Relationships

- One portfolio status view contains many topic status views.
- One topic status view contains many next-step recommendations.
- One drift report contains many drift findings.
- One drift finding can reference many affected artifacts and many recommended
  next steps.
