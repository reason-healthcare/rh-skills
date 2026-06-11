# Pattern: Procedural / Workflow Decision Table

## Guideline Type

Use this pattern for guidelines with major temporal or workflow phases such as:
- assessment
- planning
- intervention selection
- follow-up

The key modeling rule is:
- keep `events[]` at the level of major workflow contexts
- deconstruct distinct recommendations into separate `rules[]` and `actions[]`

---

## Synthetic Example

```yaml
id: antibiotic-stewardship-protocol
artifact_type: decision-table
domain: infectious-disease
clinical_question: "What recommendation-scoped antibiotic management decisions occur across the stewardship workflow?"
sections:
  pathway_phases:
    - id: assessment
      label: Initial evaluation
      description: Assess infection likelihood and obtain cultures
    - id: empiric
      label: Empiric treatment
      description: Initiate broad-spectrum therapy
    - id: deescalation
      label: De-escalation
      description: Narrow therapy based on culture results
    - id: duration
      label: Duration assessment
      description: Determine treatment endpoint
  events:
    - id: infection-evaluation
      label: Initial infection evaluation
      description: Assess clinical criteria for bacterial infection
      phase: assessment
    - id: culture-review
      label: Culture obtainment review
      description: Determine need for diagnostic cultures
      phase: assessment
    - id: empiric-selection
      label: Empiric antibiotic selection
      description: Select initial broad-spectrum therapy
      phase: empiric
    - id: deescalation-review
      label: De-escalation review
      description: Narrow therapy based on culture results
      phase: deescalation
    - id: duration-review
      label: Treatment duration review
      description: Determine whether to stop or extend therapy
      phase: duration
  conditions:
    - id: suspected-infection
      label: Bacterial infection suspected
      values: [Yes, No]
    - id: cultures-obtained
      label: Cultures obtained before antibiotics
      values: [Yes, No]
    - id: suspected-pneumonia
      label: Pneumonia suspected
      values: [Yes, No]
    - id: suspected-uti
      label: Urinary tract infection suspected
      values: [Yes, No]
    - id: suspected-ssti
      label: Skin or soft tissue infection suspected
      values: [Yes, No]
    - id: organism-identified
      label: Organism identified with susceptibilities
      values: [Yes, No]
    - id: cultures-negative
      label: Cultures negative at 48 to 72 hours
      values: [Yes, No]
    - id: clinical-improvement
      label: Clinical improvement achieved
      values: [Yes, No]
    - id: persistent-infection
      label: Persistent infection despite therapy
      values: [Yes, No]
  actions:
    - id: assess-infection
      label: Assess clinical criteria for bacterial infection
    - id: obtain-cultures
      label: Obtain blood and site-specific cultures
    - id: start-ceftriaxone-azithromycin
      label: Initiate ceftriaxone plus azithromycin
    - id: start-ceftriaxone
      label: Initiate ceftriaxone
    - id: start-vancomycin
      label: Initiate vancomycin
    - id: deescalate-targeted-therapy
      label: Narrow to targeted therapy
    - id: discontinue-antibiotics
      label: Discontinue antibiotics
    - id: extend-therapy
      label: Extend current antibiotic therapy
    - id: consult-infectious-disease
      label: Request infectious disease consultation
  rules:
    - id: rule-assess-infection
      event: infection-evaluation
      phase: assessment
      when: {}
      then: [assess-infection]
    - id: rule-obtain-cultures
      event: culture-review
      phase: assessment
      when: {suspected-infection: Yes}
      then: [obtain-cultures]
    - id: rule-start-pneumonia-coverage
      event: empiric-selection
      phase: empiric
      when:
        cultures-obtained: Yes
        suspected-pneumonia: Yes
      then: [start-ceftriaxone-azithromycin]
    - id: rule-start-uti-coverage
      event: empiric-selection
      phase: empiric
      when:
        cultures-obtained: Yes
        suspected-uti: Yes
      then: [start-ceftriaxone]
    - id: rule-start-ssti-coverage
      event: empiric-selection
      phase: empiric
      when:
        cultures-obtained: Yes
        suspected-ssti: Yes
      then: [start-vancomycin]
    - id: rule-deescalate-targeted-therapy
      event: deescalation-review
      phase: deescalation
      when: {organism-identified: Yes}
      then: [deescalate-targeted-therapy]
    - id: rule-discontinue-negative-cultures
      event: deescalation-review
      phase: deescalation
      when:
        cultures-negative: Yes
        clinical-improvement: Yes
      then: [discontinue-antibiotics]
    - id: rule-discontinue-when-improved
      event: duration-review
      phase: duration
      when: {clinical-improvement: Yes}
      then: [discontinue-antibiotics]
    - id: rule-extend-therapy
      event: duration-review
      phase: duration
      when: {persistent-infection: Yes}
      then: [extend-therapy]
    - id: rule-consult-id
      event: duration-review
      phase: duration
      when: {persistent-infection: Yes}
      then: [consult-infectious-disease]
```

---

## Extraction Takeaways

1. Use `pathway_phases[]` only when the source really has major temporal phases.
2. Keep each recommendation branch explicit as its own rule.
3. Reuse conditions across rules rather than redefining the same criterion.
4. Use `when: {}` for true workflow-triggered recommendations that do not need
   additional branch conditions.
