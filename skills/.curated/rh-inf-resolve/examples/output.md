# rh-inf-resolve Example Output

## Scenario: Extract plan with one open concern

**Topic:** `diabetes-ccm`

---

### Step 1 — List open concerns

```sh
$ rh-skills promote concerns diabetes-ccm
Open concerns for topic 'diabetes-ccm':

  plan=extract  artifact=screening-decisions  index=0
    Concern   : ADA interval language is more explicit than USPSTF interval framing.
    Resolution: _pending_

Total: 1 open concern(s). Use 'rh-skills promote resolve-concern' to record resolutions.
```

---

### Step 2 — Present to reviewer

```
──────────────────────────────────────────────────────────────────────
Concern [1 of 1]
  Plan     : extract-plan.yaml
  Artifact : screening-decisions
  Index    : 0
  Issue    : ADA interval language is more explicit than USPSTF interval framing.
──────────────────────────────────────────────────────────────────────

How should this concern be resolved?
Please describe the preferred interpretation and rationale.
```

**Reviewer response:**

> ADA 2024 is the primary guideline for this population. The USPSTF framing
> is supplementary context only. Use ADA interval language (every 3 years
> for low-risk; annually for high-risk) as the authoritative specification.

---

### Step 3 — Record resolution

```sh
$ rh-skills promote resolve-concern diabetes-ccm \
    --plan extract \
    --artifact screening-decisions \
    --index 0 \
    --resolution "ADA 2024 is the primary guideline; use ADA interval language \
(every 3 years low-risk, annually high-risk). USPSTF framing is supplementary context only."
Resolved concern 0 on 'screening-decisions' in extract-plan.yaml.
No open concerns remain in extract-plan.yaml.
```

---

### Step 4 — Final confirmation

```sh
$ rh-skills promote concerns diabetes-ccm
No open concerns for topic 'diabetes-ccm'.
```

**Skill output:**

```
✓ All concerns resolved for topic 'diabetes-ccm'.
  Plan is clear. You may proceed to the next lifecycle step.

  Next steps:
    - extract-plan approved + no concerns → run: rh-skills promote derive diabetes-ccm ...
    - formalize-plan approved + no concerns → run: rh-skills formalize diabetes-ccm
```

---

## Scenario: Reviewer skips a concern

```
──────────────────────────────────────────────────────────────────────
Concern [1 of 2]
  Plan     : extract
  Artifact : hba1c-thresholds
  Index    : 0
  Issue    : ADA <7.0% vs AACE ≤6.5%
──────────────────────────────────────────────────────────────────────

How should this concern be resolved? (type 'skip' to defer)
> skip
```

**Skill records the skip and continues to the next concern, then at completion:**

```
⚠ 1 concern(s) remain open for topic 'diabetes-ccm':

  [plan=extract  artifact=hba1c-thresholds  index=0]
    ADA <7.0% vs AACE ≤6.5%

BLOCKED: Implementation MUST NOT proceed until all concerns are resolved.
Run 'rh-inf-resolve diabetes-ccm' again when ready to address remaining concerns.
```
