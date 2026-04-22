# rh-inf-resolve Example Output

## Scenario: Extract plan with one open conflict

**Topic:** `diabetes-ccm`

---

### Step 1 — List open conflicts

```sh
$ rh-skills promote conflicts diabetes-ccm
Open conflicts for topic 'diabetes-ccm':

  plan=extract  artifact=screening-decisions  index=0
    Conflict  : ADA interval language is more explicit than USPSTF interval framing.
    Resolution: _pending_

Total: 1 open conflict(s). Use 'rh-skills promote resolve-conflict' to record resolutions.
```

---

### Step 2 — Present to reviewer

```
──────────────────────────────────────────────────────────────────────
Conflict [1 of 1]
  Plan     : extract-plan.yaml
  Artifact : screening-decisions
  Index    : 0
  Issue    : ADA interval language is more explicit than USPSTF interval framing.
──────────────────────────────────────────────────────────────────────

How should this conflict be resolved?
Please describe the preferred interpretation and rationale.
```

**Reviewer response:**

> ADA 2024 is the primary guideline for this population. The USPSTF framing
> is supplementary context only. Use ADA interval language (every 3 years
> for low-risk; annually for high-risk) as the authoritative specification.

---

### Step 3 — Record resolution

```sh
$ rh-skills promote resolve-conflict diabetes-ccm \
    --plan extract \
    --artifact screening-decisions \
    --index 0 \
    --resolution "ADA 2024 is the primary guideline; use ADA interval language \
(every 3 years low-risk, annually high-risk). USPSTF framing is supplementary context only."
Resolved conflict 0 on 'screening-decisions' in extract-plan.yaml.
No open conflicts remain in extract-plan.yaml.
```

---

### Step 4 — Final confirmation

```sh
$ rh-skills promote conflicts diabetes-ccm
No open conflicts for topic 'diabetes-ccm'.
```

**Skill output:**

```
✓ All conflicts resolved for topic 'diabetes-ccm'.
  Plan is clear. You may proceed to the next lifecycle step.

  Next steps:
    - extract-plan approved + no conflicts → run: rh-skills promote derive diabetes-ccm ...
    - formalize-plan approved + no conflicts → run: rh-skills formalize diabetes-ccm
```

---

## Scenario: Reviewer skips a conflict

```
──────────────────────────────────────────────────────────────────────
Conflict [1 of 2]
  Plan     : extract
  Artifact : hba1c-thresholds
  Index    : 0
  Issue    : ADA <7.0% vs AACE ≤6.5%
──────────────────────────────────────────────────────────────────────

How should this conflict be resolved? (type 'skip' to defer)
> skip
```

**Skill records the skip and continues to the next conflict, then at completion:**

```
⚠ 1 conflict(s) remain open for topic 'diabetes-ccm':

  [plan=extract  artifact=hba1c-thresholds  index=0]
    ADA <7.0% vs AACE ≤6.5%

BLOCKED: Implementation MUST NOT proceed until all conflicts are resolved.
Run 'rh-inf-resolve diabetes-ccm' again when ready to address remaining conflicts.
```
