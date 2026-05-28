# Pattern: Procedural/Workflow Decision Table

## Guideline Type: Temporal Workflow

This pattern applies to guidelines with **sequential clinical phases** (assessment → planning → execution → follow-up).

**Example domains**: Surgical protocols, perioperative care, chronic disease management workflows

---

## Recognition Criteria

✅ **Use this pattern when guideline has:**
- Clear temporal progression (before/during/after structure)
- Workflow milestones ("at initial encounter", "during planning phase", "at follow-up")
- Sequential dependencies (step B requires completion of step A)
- Distinct clinical phases with ordered activities

❌ **Do NOT use for:**
- Diagnostic decision trees (hierarchical, not temporal)
- Screening eligibility (conditional, not sequential)
- Treatment optimization (iterative, may loop)

---

## Synthetic Example: Antibiotic Stewardship Workflow

### Source Guideline Narrative (Simplified)

> **Antibiotic Stewardship Protocol for Suspected Bacterial Infection**
>
> **Phase 1: Initial Evaluation**
> - At initial encounter, clinicians should assess clinical criteria for bacterial infection (fever, elevated WBC, localizing symptoms).
> - If bacterial infection suspected, obtain cultures before initiating empiric antibiotics.
>
> **Phase 2: Empiric Treatment**
> - When cultures are obtained, initiate empiric broad-spectrum antibiotic therapy based on suspected source.
> - For suspected pneumonia, use ceftriaxone + azithromycin.
> - For suspected UTI, use ceftriaxone.
> - For suspected skin/soft tissue, use vancomycin.
>
> **Phase 3: De-Escalation**
> - At 48-72 hours, review culture results.
> - If organism identified and susceptible, de-escalate to narrow-spectrum agent.
> - If cultures negative and clinical improvement, consider discontinuation.
>
> **Phase 4: Duration Assessment**
> - At treatment day 5-7, reassess clinical response.
> - If improved and afebrile >48h, discontinue antibiotics.
> - If persistent infection, extend therapy and consider ID consult.

---

## Extracted Decision Table

```yaml
id: antibiotic-stewardship-protocol
artifact_type: decision-table
domain: infectious-disease
clinical_question: "What are the key antibiotic management decisions for suspected bacterial infection?"

# CRITICAL: pathway_phases enables care pathway auto-derivation
pathway_phases:
  - id: assessment
    label: "Initial Evaluation"
    description: "Assess infection likelihood and obtain cultures"
    order: 1
  - id: empiric
    label: "Empiric Treatment"
    description: "Initiate broad-spectrum therapy"
    order: 2
  - id: deescalation
    label: "De-Escalation"
    description: "Narrow therapy based on culture results"
    order: 3
  - id: duration
    label: "Duration Assessment"
    description: "Determine treatment endpoint"
    order: 4

sections:
  events:
    # PHASE 1: ASSESSMENT
    - id: e1-eval
      label: "Initial Infection Evaluation"
      description: "Assess clinical criteria for bacterial infection"
      phase: assessment
      phase_order: 1
      fhir_plan_definition_id: "InfectionEvaluation"
    
    - id: e2-cultures
      label: "Culture Obtainment Decision"
      description: "Determine need for diagnostic cultures"
      phase: assessment
      phase_order: 2
      fhir_plan_definition_id: "CultureDecision"
    
    # PHASE 2: EMPIRIC
    - id: e3-empiric
      label: "Empiric Antibiotic Selection"
      description: "Select initial broad-spectrum therapy"
      phase: empiric
      phase_order: 1
      fhir_plan_definition_id: "EmpiricAntibioticSelection"
    
    # PHASE 3: DE-ESCALATION
    - id: e4-deescalate
      label: "De-Escalation Decision"
      description: "Narrow therapy based on culture results"
      phase: deescalation
      phase_order: 1
      fhir_plan_definition_id: "DeEscalationDecision"
    
    # PHASE 4: DURATION
    - id: e5-duration
      label: "Treatment Duration Decision"
      description: "Determine treatment endpoint"
      phase: duration
      phase_order: 1
      fhir_plan_definition_id: "DurationDecision"
  
  conditions:
    # NOTE: Condition reuse across multiple rules
    - id: suspected-infection
      description: "Clinical criteria for bacterial infection present"
      cql_stub: "define SuspectedInfection: ..."
    
    - id: cultures-obtained
      description: "Diagnostic cultures collected before antibiotics"
      cql_stub: "define CulturesObtained: ..."
    
    - id: suspected-pneumonia
      description: "Localizing symptoms suggest pneumonia"
      cql_stub: "define SuspectedPneumonia: ..."
    
    - id: suspected-uti
      description: "Localizing symptoms suggest urinary tract infection"
      cql_stub: "define SuspectedUTI: ..."
    
    - id: suspected-ssti
      description: "Localizing symptoms suggest skin/soft tissue infection"
      cql_stub: "define SuspectedSSTI: ..."
    
    - id: organism-identified
      description: "Culture grew organism with sensitivities available"
      cql_stub: "define OrganismIdentified: ..."
    
    - id: cultures-negative
      description: "All cultures negative at 48-72 hours"
      cql_stub: "define CulturesNegative: ..."
    
    - id: clinical-improvement
      description: "Patient afebrile >48h with symptom resolution"
      cql_stub: "define ClinicalImprovement: ..."
    
    - id: persistent-infection
      description: "Ongoing fever or worsening symptoms despite therapy"
      cql_stub: "define PersistentInfection: ..."
  
  actions:
    - id: assess-infection
      description: "Evaluate clinical criteria for bacterial infection"
      fhir_activity_definition: "AssessInfectionCriteria"
    
    - id: obtain-cultures
      description: "Order blood cultures and site-specific cultures"
      fhir_activity_definition: "ObtainCultures"
    
    - id: start-ceftriaxone-azithro
      description: "Initiate ceftriaxone + azithromycin (pneumonia coverage)"
      fhir_activity_definition: "CeftriaxoneAzithromycinRegimen"
    
    - id: start-ceftriaxone
      description: "Initiate ceftriaxone (UTI coverage)"
      fhir_activity_definition: "CeftriaxoneRegimen"
    
    - id: start-vancomycin
      description: "Initiate vancomycin (SSTI coverage)"
      fhir_activity_definition: "VancomycinRegimen"
    
    - id: deescalate-targeted
      description: "Narrow to organism-specific targeted therapy"
      fhir_activity_definition: "TargetedTherapy"
    
    - id: discontinue-abx
      description: "Discontinue antibiotic therapy"
      fhir_activity_definition: "DiscontinueAntibiotics"
    
    - id: extend-therapy
      description: "Continue current antibiotic regimen"
      fhir_activity_definition: "ExtendTherapy"
    
    - id: consult-id
      description: "Request infectious disease consultation"
      fhir_activity_definition: "IDConsult"
  
  rules:
    # PHASE 1: ASSESSMENT (triggered — always perform)
    - id: r1
      event: e1-eval
      when: {}  # Triggered rule (no conditions)
      action: assess-infection
      rationale: "IDSA Antibiotic Stewardship Guidelines, Recommendation 3.1"
    
    - id: r2
      event: e2-cultures
      when: {suspected-infection: true}
      action: obtain-cultures
      rationale: "IDSA Antibiotic Stewardship Guidelines, Recommendation 3.2"
    
    # PHASE 2: EMPIRIC (branching — select based on source)
    - id: r3a
      event: e3-empiric
      when:
        cultures-obtained: true
        suspected-pneumonia: true
      action: start-ceftriaxone-azithro
      rationale: "IDSA CAP Guidelines 2024, Recommendation 5.1"
    
    - id: r3b
      event: e3-empiric
      when:
        cultures-obtained: true
        suspected-uti: true
      action: start-ceftriaxone
      rationale: "IDSA UTI Guidelines 2024, Recommendation 7.2"
    
    - id: r3c
      event: e3-empiric
      when:
        cultures-obtained: true
        suspected-ssti: true
      action: start-vancomycin
      rationale: "IDSA SSTI Guidelines 2024, Recommendation 8.3"
    
    # PHASE 3: DE-ESCALATION (branching — based on culture results)
    - id: r4a
      event: e4-deescalate
      when: {organism-identified: true}
      action: deescalate-targeted
      rationale: "IDSA Antibiotic Stewardship Guidelines, Recommendation 4.1"
    
    - id: r4b
      event: e4-deescalate
      when:
        cultures-negative: true
        clinical-improvement: true
      action: discontinue-abx
      rationale: "IDSA Antibiotic Stewardship Guidelines, Recommendation 4.2"
    
    # PHASE 4: DURATION (branching — based on clinical response)
    - id: r5a
      event: e5-duration
      when: {clinical-improvement: true}
      action: discontinue-abx
      rationale: "IDSA Antibiotic Stewardship Guidelines, Recommendation 5.1"
    
    - id: r5b
      event: e5-duration
      when: {persistent-infection: true}
      action: extend-therapy
      rationale: "IDSA Antibiotic Stewardship Guidelines, Recommendation 5.2a"
    
    - id: r5c
      event: e5-duration
      when: {persistent-infection: true}
      action: consult-id
      rationale: "IDSA Antibiotic Stewardship Guidelines, Recommendation 5.2b"
  
  evidence_traceability:
    - claim_id: "c1"
      statement: "Cultures should be obtained before initiating empiric antibiotics"
      evidence:
        - source: "idsa-stewardship-2024"
          locator: "Recommendation 3.2"
          level: "grade-a"
    - claim_id: "c2"
      statement: "De-escalation should occur within 48-72 hours based on culture results"
      evidence:
        - source: "idsa-stewardship-2024"
          locator: "Recommendation 4.1"
          level: "grade-a"
```

---

## Key Extraction Patterns

### 1. pathway_phases Metadata

**Critical for auto-derivation**: Phases enable `rh-skills derive pathway` command.

```yaml
pathway_phases:
  - id: assessment
    order: 1
  - id: empiric
    order: 2
  - id: deescalation
    order: 3
  - id: duration
    order: 4
```

### 2. Event Sequencing

Events are grouped by phase using `phase` and `phase_order` fields:

```yaml
events:
  - id: e1-eval
    phase: assessment
    phase_order: 1  # First event in assessment phase
  - id: e2-cultures
    phase: assessment
    phase_order: 2  # Second event in assessment phase
  - id: e3-empiric
    phase: empiric
    phase_order: 1  # First event in empiric phase
```

### 3. Condition Reuse

Notice `suspected-infection` and `cultures-obtained` are reused across multiple rules:

- `suspected-infection` → used in r2
- `cultures-obtained` → used in r3a, r3b, r3c (all empiric therapy rules)
- `clinical-improvement` → used in r4b, r5a

**Pattern**: Define condition once, reference in multiple rules.

### 4. Triggered vs Branching Rules

**Triggered** (always execute):
```yaml
- id: r1
  event: e1-eval
  when: {}  # Empty conditions → always triggered
  action: assess-infection
```

**Branching** (conditional execution):
```yaml
- id: r3a
  event: e3-empiric
  when:
    cultures-obtained: true
    suspected-pneumonia: true  # Multiple conditions (AND logic)
  action: start-ceftriaxone-azithro
```

### 5. Evidence Traceability

Every rule has `rationale` field linking back to source guideline:

```yaml
- id: r3a
  rationale: "IDSA CAP Guidelines 2024, Recommendation 5.1"
```

Plus top-level `evidence_traceability` section with detailed evidence mapping.

---

## Result: Auto-Generated Care Pathway

After extracting this decision table, run:

```bash
rh-skills derive pathway --from-decision-table antibiotic-stewardship-protocol
```

Output: `antibiotic-stewardship-protocol-pathway.yaml` with 4 phases, 5 substeps.

---

## Summary

**Procedural/workflow pattern**:
1. Identify temporal phases from guideline structure
2. Define `pathway_phases` with sequential order
3. Group events by phase
4. Extract conditions, detect reuse opportunities
5. Map rules to events with evidence traceability
6. Auto-generate care pathway from decision table

**Result**: Consistent, traceable decision logic with auto-derivable workflow structure.
