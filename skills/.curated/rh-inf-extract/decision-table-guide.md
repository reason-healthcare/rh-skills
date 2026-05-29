# Decision Table Extraction Guide

**Purpose**: Guide for extracting event-driven decision logic (L2 decision tables) from normalized guideline content (L1) using rh-inf-extract skill.

**Audience**: Clinical informaticists authoring L2 structured artifacts

**Important**: This guide provides extraction **heuristics**, not rigid requirements. Adapt patterns to fit your guideline's structure.

---

## Table of Contents

1. [Guideline Structure Types](#guideline-structure-types)
2. [Extraction Workflow](#extraction-workflow)
3. [Event Extraction](#event-extraction)
4. [Event Sequencing](#event-sequencing)
5. [Condition Extraction & Reuse](#condition-extraction--reuse)
6. [Condition Role Classification](#condition-role-classification)
7. [Decision Type Inference](#decision-type-inference)
8. [Action Extraction](#action-extraction)
9. [Evidence Traceability](#evidence-traceability)
10. [Pathway Phase Metadata](#pathway-phase-metadata)
11. [Common Patterns](#common-patterns)
12. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Guideline Structure Types

**BEFORE extracting events, identify your guideline's structure type.** Different guideline types require different extraction strategies.

### Type 1: Procedural/Workflow Guidelines

**Characteristics**:
- Describes **temporal sequence** of clinical activities
- Clear workflow phases (assessment → planning → execution → follow-up)
- Recommendations often include temporal markers: "before surgery", "at time of", "postoperatively"

**Examples**:
- Surgical protocols
- Perioperative care guidelines
- Procedural checklists

**Extraction strategy**:
- Events map to workflow phases
- Use `pathway_phases` metadata (enables care pathway auto-derivation)
- Sequencing is temporal/linear

---

### Type 2: Diagnostic Guidelines

**Characteristics**:
- Describes **hierarchical decision tree** for diagnosis
- Branching logic: "if positive, then...", "if negative, then..."
- Milestones: "initial evaluation", "confirmatory testing", "staging"

**Examples**:
- Cancer diagnosis algorithms
- Infectious disease workup
- Differential diagnosis trees

**Extraction strategy**:
- Events represent decision nodes in diagnostic tree
- Sequencing is hierarchical/branching (not linear)
- `pathway_phases` optional (may not fit temporal model)

---

### Type 3: Screening Guidelines

**Characteristics**:
- Describes **risk stratification** followed by conditional testing
- Skip logic: Not all patients enter all events
- Recommendations often conditional on risk level

**Examples**:
- Cancer screening eligibility
- CVD risk assessment
- Population health screening protocols

**Extraction strategy**:
- Events may have conditional entry criteria
- Sequencing includes skip logic
- `pathway_phases` optional (not all patients follow same path)

---

### Type 4: Treatment Optimization Guidelines

**Characteristics**:
- Describes **iterative adjustment cycles**
- Reassessment loops: "assess response", "adjust dose", "reassess"
- Same event may occur multiple times per patient

**Examples**:
- Chronic disease management (diabetes, hypertension)
- Pain control titration
- Medication dose optimization

**Extraction strategy**:
- Events may repeat or loop
- Sequencing includes cycles (reassessment event can occur multiple times)
- `pathway_phases` may represent treatment phases rather than temporal sequence

---

### Hybrid/Custom

**If your guideline doesn't fit the above types**, document its structure and define custom event patterns. Consult with team before proceeding.

---

## Extraction Workflow

**Step 1**: Read normalized guideline (L1) thoroughly  
**Step 2**: Identify guideline structure type (see above)  
**Step 3**: Extract events using type-specific heuristics  
**Step 4**: Extract ALL actions from guideline recommendations (conditional AND unconditional)  
**Step 5**: Extract conditions from event contexts  
**Step 6**: Identify condition reuse opportunities  
**Step 7**: Build rules mapping events → conditions → actions  
**Step 8**: Add evidence traceability for each rule  
**Step 9**: Add pathway phase metadata (if temporal workflow)  
**Step 10**: Validate extraction completeness  

### Completeness Checklist

Before finalizing extraction, verify:

- [ ] **ALL Key Action Statements extracted** (not just conditional ones)
- [ ] **Unconditional recommendations captured** as rules with `when: {}`
- [ ] **Every action** has corresponding entry in `actions` section
- [ ] **Every rule** references valid action IDs in `then: [...]`
- [ ] **Every guideline "should/shall" statement** appears as an action
- [ ] **Evidence traceability** present for all rules
- [ ] **Pathway phases** defined (if workflow guideline)
- [ ] **No duplicate conditions** (check for semantic equivalence)

---

## Event Extraction

**Events** are clinical decision points or workflow milestones where recommendations apply.

### For Procedural/Workflow Guidelines

**Look for**:
- Workflow transitions: "at evaluation", "when planning surgery", "during follow-up"
- Recommendation triggers: "should counsel", "should obtain", "should assess"
- Temporal markers: "before", "at time of", "after", "preoperatively", "postoperatively"

**Pattern**: One event per workflow phase or major decision point

**Example** (synthetic surgical protocol):
```yaml
events:
  - id: e1
    label: "Preoperative Assessment"
    description: "Patient evaluation before surgery"
    phase: "assessment"
    
  - id: e2
    label: "Surgical Planning"
    description: "Planning surgical approach and anesthesia"
    phase: "planning"
```

---

### For Diagnostic Guidelines

**Look for**:
- Decision branches: "if positive, then...", "if negative, then..."
- Diagnostic milestones: "initial screening", "confirmatory test", "staging"
- Test result interpretation points

**Pattern**: Events represent decision nodes in diagnostic tree

**Example** (synthetic diabetes screening):
```yaml
events:
  - id: e1
    label: "Initial Screening"
    description: "Fasting glucose or HbA1c screening"
    
  - id: e2
    label: "Confirmatory Testing"
    description: "Repeat testing or oral glucose tolerance test"
    note: "Enter only if initial screen abnormal"
```

---

### For Screening Guidelines

**Look for**:
- Risk stratification steps: "assess eligibility", "calculate risk score"
- Conditional screening: "if high-risk, screen", "if low-risk, reassure"

**Pattern**: Events may have skip logic

**Example** (synthetic cancer screening):
```yaml
events:
  - id: e1
    label: "Risk Assessment"
    description: "Assess patient eligibility and risk factors"
    
  - id: e2
    label: "Screening Test"
    description: "Order screening test"
    note: "Enter only if patient meets eligibility and risk criteria"
```

---

### For Treatment Optimization Guidelines

**Look for**:
- Assessment cycles: "initial treatment", "reassess at X weeks", "adjust dose"
- Response criteria: "if inadequate response", "if adverse effects"

**Pattern**: Events may repeat

**Example** (synthetic chronic disease management):
```yaml
events:
  - id: e1
    label: "Initial Treatment"
    description: "Start first-line medication"
    
  - id: e2
    label: "Response Assessment"
    description: "Evaluate treatment response"
    note: "Occurs at specified intervals; may repeat multiple times"
```

---

## Event Sequencing

### Temporal Sequencing (Procedural/Workflow)

**Strategy**: Map events to clinical workflow phases

**Pattern**: Define `pathway_phases` with `order`; link events via `event.phase` and `event.phase_order`

**Example**:
```yaml
pathway_phases:
  - id: "assessment"
    label: "Assessment Phase"
    description: "Patient evaluation and candidacy"
    order: 1
    
  - id: "intervention"
    label: "Intervention Phase"
    description: "Therapeutic intervention"
    order: 2
    
events:
  - id: e1
    label: "Initial Evaluation"
    phase: "assessment"
    phase_order: 1
    
  - id: e2
    label: "Treatment Decision"
    phase: "assessment"
    phase_order: 2
    
  - id: e3
    label: "Intervention"
    phase: "intervention"
    phase_order: 1
```

---

### Hierarchical Sequencing (Diagnostic)

**Strategy**: Events represent levels in diagnostic tree

**Pattern**: Document parent-child relationships in event descriptions; `pathway_phases` not required

**Example**:
```yaml
events:
  - id: e1
    label: "Screening Level"
    description: "Initial screening test"
    
  - id: e2
    label: "Confirmation Level"
    description: "Confirmatory testing if screen positive"
    note: "Follows e1 if positive"
    
  - id: e3
    label: "Staging Level"
    description: "Disease staging if confirmed"
    note: "Follows e2 if confirmed"
```

---

### Conditional Sequencing (Screening, Treatment Optimization)

**Strategy**: Document skip logic and branching paths

**Pattern**: Use event descriptions to specify entry criteria; `pathway_phases` optional

**Example**:
```yaml
events:
  - id: e1
    label: "Risk Stratification"
    description: "All patients assessed for risk"
    
  - id: e2
    label: "High-Risk Testing"
    description: "Screening for high-risk patients only"
    note: "Conditional entry: risk score ≥ threshold"
    
  - id: e3
    label: "Low-Risk Counseling"
    description: "Reassurance for low-risk patients"
    note: "Alternative path: risk score < threshold"
```

---

## Condition Extraction & Reuse

**Conditions** are clinical criteria that determine whether a recommendation applies.

### Extraction Strategy

1. **Extract from "when" clauses** in recommendations
2. **Look for repeated criteria** across multiple recommendations
3. **Define once, reference multiple times** (don't duplicate)

### Example

**Guideline text** (synthetic):
> "When diabetes is confirmed and patient has inadequate glycemic control, initiate insulin therapy."
> 
> "When diabetes is confirmed and patient develops complications, refer to endocrinology."

**Extraction**:
```yaml
conditions:
  # Shared condition (used in multiple rules)
  - id: diabetes-confirmed
    label: "Diabetes diagnosis confirmed"
    description: "HbA1c ≥6.5% on two occasions or fasting glucose ≥126 mg/dL"
    values: ["true", "false"]
    
  # Specific conditions
  - id: inadequate-glycemic-control
    label: "Inadequate glycemic control"
    description: "HbA1c >8% despite oral medications"
    values: ["true", "false"]
    
  - id: complications-present
    label: "Diabetes complications present"
    description: "Retinopathy, nephropathy, or neuropathy documented"
    values: ["true", "false"]
```

**Usage in rules**:
```yaml
rules:
  - rule_id: r1
    event: e1
    when: {diabetes-confirmed: "true", inadequate-glycemic-control: "true"}
    then: [initiate-insulin]
    
  - rule_id: r2
    event: e1
    when: {diabetes-confirmed: "true", complications-present: "true"}
    then: [refer-endocrinology]
```

---

### Condition Reuse Detection

**Before defining a new condition**, check if a semantically similar condition already exists.

**Anti-pattern** (duplicated conditions):
```yaml
conditions:
  - id: has-diagnosis
    label: "Diagnosis established"
    
  - id: diagnosis-confirmed
    label: "Diagnosis confirmed"
    
  - id: diagnosis-verified
    label: "Diagnosis verified"
```

**Better** (single shared condition):
```yaml
conditions:
  - id: diagnosis-established
    label: "Diagnosis established"
    description: "Confirmed via diagnostic criteria, used across multiple rules"
```

---

## Condition Role Classification

Conditions serve different roles depending on context:

### Pre-requisite Conditions

**Definition**: Must be satisfied before event can occur  
**Pattern**: Appears in ALL rules at an event

**Example**:
```yaml
# Event e2 requires diagnosis for all rules
rules:
  - rule_id: r1
    event: e2
    when: {diagnosis-established: "true", criterion-a: "true"}
    then: [action-1]
    
  - rule_id: r2
    event: e2
    when: {diagnosis-established: "true", criterion-b: "true"}
    then: [action-2]
```

**Consider**: Move pre-requisite to event-level metadata or create triggered rule at earlier event

---

### Branch Conditions

**Definition**: Determines which action to take at an event  
**Pattern**: Appears in SOME rules at an event

**Example**:
```yaml
# Event e1 branches on risk level
rules:
  - rule_id: r1
    event: e1
    when: {risk-level: "high"}
    then: [intensive-screening]
    
  - rule_id: r2
    event: e1
    when: {risk-level: "low"}
    then: [standard-screening]
```

---

### Layered Conditions

**Definition**: Same condition serves as pre-requisite in one rule, branch criterion in another

**Example**:
```yaml
# diagnosis-established is pre-requisite at e2, branch criterion at e4
rules:
  - rule_id: r1
    event: e2
    when: {diagnosis-established: "true"}  # Pre-requisite
    then: [counseling]
    
  - rule_id: r2
    event: e4
    when: {diagnosis-established: "true", complication-present: "true"}  # Branch criterion
    then: [intensive-intervention]
    
  - rule_id: r3
    event: e4
    when: {diagnosis-established: "true", complication-present: "false"}  # Branch criterion
    then: [standard-intervention]
```

---

## Decision Type Inference

Rules fall into two categories:

### Triggered Decisions

**Definition**: Always fire at an event, regardless of conditions  
**When**: Recommendation says "should always...", "all patients should..."  
**Pattern**: `when: {}`

**Example**:
```yaml
rules:
  - rule_id: r1
    event: e1
    when: {}  # No conditions = always fires
    then: [verify-diagnosis]
    rationale: "All patients at initial evaluation should have diagnosis verified"
    decision_type: "triggered"
```

---

### Branching Decisions

**Definition**: Conditional logic determining which action to take  
**When**: Recommendation says "when X, then Y", "if..., then..."  
**Pattern**: `when: {cond: val, ...}`

**Example**:
```yaml
rules:
  - rule_id: r2
    event: e1
    when: {purulent-discharge: "false"}  # Condition present
    then: [avoid-antibiotics]
    rationale: "Avoid antibiotics when purulent discharge absent"
    decision_type: "branching"
```

---

## Action Extraction

**Actions** are the outcomes or recommendations to be executed.

### Critical Extraction Rule

**EXTRACT EVERY GUIDELINE RECOMMENDATION AS AN ACTION** — even if it has no conditions.

- **Conditional recommendations** → actions with `when: {condition: value}`
- **Unconditional recommendations** → actions with `when: {}` (triggered/always-applicable)
- **Don't skip** recommendations that "should always be done" — those are triggered actions

### Extraction Strategy

1. **Extract from "then" clauses** in recommendations
2. **Map to FHIR resource types** (ServiceRequest, Procedure, MedicationRequest, CommunicationRequest, etc.)
3. **Derive fhir_activity_definition ID** from action name
4. **Include ALL guideline recommendations** — if guideline says "surgeon should X", create an action for X

### Example: Conditional Action

**Guideline text** (synthetic):
> "When diabetes is confirmed, initiate metformin therapy."

**Extraction**:
```yaml
actions:
  - id: initiate-metformin
    name: "initiate-metformin"
    type: "MedicationRequest"
    description: "Initiate metformin therapy"
    details: "Start metformin 500mg twice daily with meals"
    fhir_activity_definition: "diabetes-initiate-metformin"

rules:
  - rule_id: r1
    event: e1
    when: {diabetes-confirmed: "true"}
    then: [initiate-metformin]
```

### Example: Unconditional Action (Triggered)

**Guideline text** (synthetic):
> "Obtain CT imaging for surgical planning."

**Extraction**:
```yaml
actions:
  - id: obtain-ct-imaging
    name: "obtain-ct-imaging"
    type: "ServiceRequest"
    description: "Obtain CT imaging"
    details: "Fine-cut CT for surgical planning and anatomy definition"
    fhir_activity_definition: "surgical-ct-imaging"

rules:
  - rule_id: r1
    event: e1
    when: {}  # No conditions = always perform
    then: [obtain-ct-imaging]
    decision_type: "triggered"
```

### Common Action Types

| Guideline Language | Action Type | FHIR Type |
|-------------------|-------------|-----------|
| "offer surgery" | Recommendation | ServiceRequest |
| "perform procedure" | Intervention | Procedure |
| "prescribe medication" | Prescription | MedicationRequest |
| "counsel patient" | Communication | CommunicationRequest |
| "assess/evaluate" | Assessment | Observation/Assessment |
| "verify diagnosis" | Diagnostic | DiagnosticReport |
| "educate patient" | Education | CommunicationRequest |
| "refer to specialist" | Referral | ServiceRequest |

---

## Evidence Traceability

**Every rule** must link back to source guideline recommendation.

### Pattern

1. **rationale field**: Short statement with source locator
2. **evidence_traceability section**: Detailed claim→evidence mapping

### Example

```yaml
rules:
  - rule_id: r1
    event: e1
    when: {purulent-discharge: "false"}
    then: [avoid-antibiotics]
    rationale: "KAS 3: Avoid antibiotics when purulent discharge absent"
    
evidence_traceability:
  - claim_id: antibacterial-guardrail
    statement: "Antibacterial therapy should be avoided when purulent discharge absent"
    evidence:
      - source: "guideline-name"
        locator: "KAS 3, Page 12"
```

---

## Pathway Phase Metadata

**When to use**: Only for **procedural/workflow guidelines** with clear temporal sequence

**Why**: Enables auto-derivation of care pathway artifact (eliminates manual pathway authoring)

### Pattern

```yaml
pathway_phases:
  - id: "assessment"
    label: "Assessment Phase"
    description: "Patient evaluation and candidacy assessment"
    order: 1
    
  - id: "intervention"
    label: "Intervention Phase"
    description: "Therapeutic intervention"
    order: 2
    
events:
  - id: e1
    label: "Initial Evaluation"
    phase: "assessment"
    phase_order: 1
    fhir_plan_definition_id: "InitialEvaluation"
    
  - id: e2
    label: "Treatment"
    phase: "intervention"
    phase_order: 1
    fhir_plan_definition_id: "TreatmentIntervention"
```

**Result**: Care pathway can be auto-generated via `rh-skills derive pathway --from-decision-table <id>`

---

## Common Patterns

### Pattern 1: Simple Binary Branch

**Use when**: Recommendation has if-then-else logic

```yaml
rules:
  - rule_id: r1
    event: e1
    when: {criterion: "true"}
    then: [action-a]
    
  - rule_id: r2
    event: e1
    when: {criterion: "false"}
    then: [action-b]
```

---

### Pattern 2: Multi-Criterion Branch

**Use when**: Multiple conditions determine action

```yaml
rules:
  - rule_id: r1
    event: e1
    when: {criterion-a: "true", criterion-b: "true", criterion-c: "true"}
    then: [intensive-action]
    
  - rule_id: r2
    event: e1
    when: {criterion-a: "true", criterion-b: "false"}
    then: [standard-action]
```

---

### Pattern 3: Triggered Activity + Branching Decision

**Use when**: Event always triggers data collection, then branches based on results

```yaml
rules:
  # Triggered rule: always collect data
  - rule_id: r1
    event: e1
    when: {}
    then: [collect-assessment-data]
    decision_type: "triggered"
    
  # Branching rules: use collected data
  - rule_id: r2
    event: e1
    when: {assessment-positive: "true"}
    then: [intervention-a]
    decision_type: "branching"
    
  - rule_id: r3
    event: e1
    when: {assessment-positive: "false"}
    then: [intervention-b]
    decision_type: "branching"
```

---

## Anti-Patterns to Avoid

### ❌ Anti-Pattern 1: Duplicated Conditions

**Problem**: Same clinical criterion defined multiple times with different IDs

**Example**:
```yaml
conditions:
  - id: has-diagnosis
  - id: diagnosis-confirmed
  - id: diagnosis-verified
```

**Fix**: Define once, reuse across rules
```yaml
conditions:
  - id: diagnosis-established
```

---

### ❌ Anti-Pattern 4: Skipping Unconditional Actions

**Problem**: Omitting recommendations because they "don't have conditions"

**Example** (incomplete extraction):
```yaml
# Guideline says:
# "Obtain CT imaging for surgical planning."
# "If polyps present, perform extensive surgery."

# ❌ WRONG: Only extracted the conditional action
actions:
  - id: perform-extensive-surgery
    type: "Procedure"

rules:
  - rule_id: r1
    when: {polyps-present: "true"}
    then: [perform-extensive-surgery]
```

**Fix**: Extract ALL guideline recommendations — unconditional ones use `when: {}`
```yaml
# ✅ CORRECT: Both actions extracted
actions:
  - id: obtain-ct-imaging
    type: "ServiceRequest"
    description: "Obtain CT imaging for surgical planning"
  - id: perform-extensive-surgery
    type: "Procedure"
    description: "Perform extensive sinus surgery"

rules:
  - rule_id: r1
    event: e1
    when: {}  # Always perform
    then: [obtain-ct-imaging]
    decision_type: "triggered"
    
  - rule_id: r2
    event: e1
    when: {polyps-present: "true"}
    then: [perform-extensive-surgery]
    decision_type: "branching"
```

---

### ❌ Anti-Pattern 2: Over-Granular Events

**Problem**: Too many events for minor workflow steps

**Example** (too granular):
```yaml
events:
  - id: e1
    label: "Greet Patient"
  - id: e2
    label: "Review Chart"
  - id: e3
    label: "Perform Exam"
  - id: e4
    label: "Document Findings"
```

**Fix**: Group into meaningful decision points
```yaml
events:
  - id: e1
    label: "Initial Evaluation"
    description: "Patient encounter including history, exam, and documentation"
```

---

### ❌ Anti-Pattern 3: Missing Evidence Links

**Problem**: Rules lack rationale field

**Fix**: Always include rationale with source locator
```yaml
rules:
  - rule_id: r1
    # ... event, when, then ...
    rationale: "Recommendation 5: Counsel patients on expectations"
```

---

### ❌ Anti-Pattern 4: Forcing Temporal Pattern onto Non-Temporal Guideline

**Problem**: Adding `pathway_phases` to diagnostic or screening guideline that doesn't have linear workflow

**Fix**: Only use `pathway_phases` for procedural/workflow guidelines; omit for diagnostic/screening guidelines

---

### ❌ Anti-Pattern 5: Orphaned Conditions

**Problem**: Condition defined but never used in any rule

**Example**:
```yaml
conditions:
  - id: unused-condition  # Not referenced in any rule

rules:
  - rule_id: r1
    when: {other-condition: "true"}
    # ...
```

**Fix**: Remove unused conditions or add missing rules

---

## Validation Checklist

Before finalizing decision table extraction, verify:

- [ ] All events have clear labels and descriptions
- [ ] Event sequencing strategy matches guideline structure type
- [ ] Conditions are reused (no duplicates)
- [ ] All conditions are used in at least one rule
- [ ] All rules have rationale field with source locator
- [ ] evidence_traceability section exists
- [ ] Actions have FHIR activity definition IDs
- [ ] pathway_phases included only if temporal workflow guideline
- [ ] All events in pathway_phases have phase and phase_order

---

**Next**: See pattern library in `examples/decision-tables/` for synthetic worked examples.

