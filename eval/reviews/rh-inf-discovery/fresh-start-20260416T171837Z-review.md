# Skill Eval Review

| Field | Value |
|-------|-------|
| skill | `rh-inf-discovery` |
| scenario | fresh-start |
| transcript | `fresh-start-20260416T171837Z.md` |
| elapsed | 3m 31s |
| transcript_lines | 4518 |
| approx_tokens | ~52558 |
| reviewer | <!-- your name --> |
| reviewed_at | <!-- date --> |

---

## 1. Efficiency (objective)

Score: <!-- 1–5 -->

- [ ] Does the agent search more than one database before saving the plan?
- [ ] Does it ask for clarification about the clinical question that RESEARCH.md already answers?
- [ ] Does it re-run the same search query more than once?
- [ ] Does it write any inline scripts for file I/O instead of using rh-skills CLI commands?

Notes:
<!-- free text -->

---

## 2. Output Quality (subjective)

Score: <!-- 1–5 -->

### Expected outputs

**`topics/diabetes-ccm/process/plans/discovery-plan.yaml`**
- [ ] `exists`
- [ ] `contains: sources:`
- [ ] `contains: clinical-guideline`
- [ ] `contains: government-program`

**`tracking.yaml`**
- [ ] `event: discovery_planned`
### Quality checks

- [ ] Are there at least 5 sources covering distinct evidence types (guideline, RCT, systematic review, government program, health economics)?
- [ ] Is a CMS quality measure source present (e.g., eCQM, MIPS)?
- [ ] Are evidence levels assigned correctly (ia/ib/iia/iib/iii/iv)?
- [ ] Does the plan include a health-economics source?
- [ ] Are all rationale fields non-empty?

Notes:
<!-- free text -->

---

## 3. Recommended Changes

<!-- List specific changes to SKILL.md, reference.md, examples/, or CLI commands
     that would address issues found above. -->

