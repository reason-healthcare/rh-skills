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
- Use `sections.pathway_phases[]` metadata when the narrative is phase-organized
- Reference the canonical phase ids from `event.phase` and `rule.phase`
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
- [ ] **Distinct recommendations deconstructed** into separate rules/actions even when they share the same visit, phase, or workflow moment
- [ ] **Unconditional recommendations captured** as rules with `when: {}`
- [ ] **Paired care-pathway coverage preserved** when a care-pathway artifact also exists: every recommendation-scoped rule remains linkable to at least one care-pathway leaf step, singly or via grouped `rule_ids[]`
- [ ] **Every action** has corresponding entry in `actions` section
- [ ] **Every rule** references valid action IDs in `then: [...]`
- [ ] **Every guideline "should/shall" statement** appears as an action
- [ ] **Recommendation rules include required `evidence_traceability_ids[]`** pointing to `sections.evidence_traceability[].claim_id`
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

Prefer one event per major workflow context, not one event per child task.
If questionnaire review, imaging review, counseling, phenotype review, and
other narrow tasks all occur within the same broader staged context, keep one
event and represent the finer distinction through separate recommendation-scoped
rules and child actions. Split into separate events only when the workflow
moment or trigger actually changes.
When the source provides activation metadata, keep it on `event.trigger`
instead of splitting the event. Use `type`, `name`, `source`, `resource`,
`moment`, `resource_criteria`, and `timing_window` when the source supports
those details.

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

**Pattern**: Define `sections.pathway_phases[]`; link events via `event.phase` and `rule.phase`

**Example**:
```yaml
sections:
  pathway_phases:
    - id: assessment
      label: Assessment Phase
      description: Patient evaluation and candidacy
    - id: intervention
      label: Intervention Phase
      description: Therapeutic intervention
  events:
    - id: e1
      label: Initial Evaluation
      phase: assessment
    - id: e2
      label: Treatment Decision
      phase: assessment
    - id: e3
      label: Intervention
      phase: intervention
```

---

### Hierarchical Sequencing (Diagnostic)

**Strategy**: Events represent levels in diagnostic tree

**Pattern**: Document parent-child relationships in event descriptions; `pathway_phases` is optional

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
    values: ["Yes", "No"]
    
  # Specific conditions
  - id: inadequate-glycemic-control
    label: "Inadequate glycemic control"
    description: "HbA1c >8% despite oral medications"
    values: ["Yes", "No"]
    
  - id: complications-present
    label: "Diabetes complications present"
    description: "Retinopathy, nephropathy, or neuropathy documented"
    values: ["Yes", "No"]
```

**Usage in rules**:
```yaml
rules:
  - rule_id: r1
    event: e1
    when: {diabetes-confirmed: "Yes", inadequate-glycemic-control: "Yes"}
    then: [initiate-insulin]
    
  - rule_id: r2
    event: e1
    when: {diabetes-confirmed: "Yes", complications-present: "Yes"}
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
    when: {diagnosis-established: "Yes", criterion-a: "Yes"}
    then: [action-1]
    
  - rule_id: r2
    event: e2
    when: {diagnosis-established: "Yes", criterion-b: "Yes"}
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
    when: {diagnosis-established: "Yes"}  # Pre-requisite
    then: [counseling]
    
  - rule_id: r2
    event: e4
    when: {diagnosis-established: "Yes", complication-present: "Yes"}  # Branch criterion
    then: [intensive-intervention]
    
  - rule_id: r3
    event: e4
    when: {diagnosis-established: "Yes", complication-present: "No"}  # Branch criterion
    then: [standard-intervention]
```

---

### Persistent Prerequisites (Workflow Pattern)

**Definition**: Clinical state established at an earlier event that remains true for later sequential steps  
**Pattern**: Condition appears at event N and should be repeated in ALL downstream events N+1, N+2, etc.  
**When to use**: Procedural/workflow guidelines with temporal sequencing

**Critical Rule**: If an earlier event establishes a prerequisite clinical state that remains true for later steps, downstream rules should repeat that state explicitly in `when`, unless the later step intentionally re-evaluates or relaxes it.

**Example** (surgical workflow):
```yaml
events:
  - id: e1
    label: "Initial CRS Evaluation"
    phase: "assessment"
    
  - id: e2
    label: "Surgical Decision Point"
    phase: "planning"
    
  - id: e3
    label: "Pre-Operative Clearance"
    phase: "planning"

conditions:
  - id: crs-diagnosis-confirmed
    label: "CRS diagnosis confirmed"
    description: "Patient meets diagnostic criteria for chronic rhinosinusitis"
    values: ["Yes", "No"]
    role: "persistent-prerequisite"  # Established at e1, required through e3
    
  - id: objective-inflammation-present
    label: "Objective inflammation documented"
    description: "Endoscopic or imaging evidence of inflammation"
    values: ["Yes", "No"]
    role: "persistent-prerequisite"  # Established at e1, required through e3
    
  - id: surgical-criteria-met
    label: "Surgical candidacy criteria met"
    description: "Failed medical therapy and meets clinical criteria"
    values: ["Yes", "No"]
    role: "branch-condition"  # Only checked at e2
    
rules:
  # Event 1: Establish prerequisites
  - id: r1
    event: e1
    when: {crs-diagnosis-confirmed: "Yes", objective-inflammation-present: "Yes"}
    then: [verify-diagnostic-workup]
    rationale: "Confirm diagnosis before proceeding"
    
  # Event 2: Prerequisites CARRIED FORWARD + new branch condition
  - id: r2
    event: e2
    when: {crs-diagnosis-confirmed: "Yes", objective-inflammation-present: "Yes", surgical-criteria-met: "Yes"}
    then: [offer-surgery]
    rationale: "Offer surgery when persistent prerequisites confirmed AND surgical criteria met"
    
  # Event 3: Prerequisites CARRIED FORWARD again
  - id: r3
    event: e3
    when: {crs-diagnosis-confirmed: "Yes", objective-inflammation-present: "Yes"}
    then: [obtain-pre-op-clearance]
    rationale: "Clearance requires confirmed diagnosis and inflammation"
```

**Why carry forward?** Prevents logic gaps where formalization might assume prerequisites persist implicitly, when the L2 artifact should be explicit.

**Abstraction vs. Carry-Forward**:
- **Prefer** explicit carry-forward of original conditions (e.g., `crs-diagnosis-confirmed`, `objective-inflammation-present`)
- **Avoid** creating abstract summary conditions (e.g., `diagnosis-confirmed-and-meets-criteria`) unless reviewer-approved
- **Do** allow diagnosis-confirmation conditions as branch criteria when the execution context is evaluating whether diagnosis is present
- **Do not** use diagnosis as a prerequisite to assess whether diagnosis is present; treat that as the branch logic itself, not upstream context
- **If abstracting**, keep both the original conditions AND the abstraction, or document why abstraction replaces them

**Condition Role Values**:
- `entry-prerequisite`: Must be true to enter the decision table at all
- `persistent-prerequisite`: Established early, carried forward through sequential events
- `branch-condition`: Determines which action at a specific event
- `terminal-condition`: Final check before completion

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
    when: {purulent-discharge: "No"}  # Condition present
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
    when: {diabetes-confirmed: "Yes"}
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
    when: {purulent-discharge: "No"}
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

**Why**: Provides the canonical phase model that can support fallback
care-pathway derivation if manual pathway authoring struggles to preserve
recommendation linkage cleanly.

### Pattern

```yaml
sections:
  pathway_phases:
    - id: assessment
      label: Assessment phase
      description: Patient evaluation and candidacy assessment
    - id: intervention
      label: Intervention phase
      description: Therapeutic intervention
  events:
    - id: e1
      label: Initial evaluation
      phase: assessment
    - id: e2
      label: Treatment
      phase: intervention
```

**Result**: The paired care-pathway can mirror the same major phase model while
keeping recommendation logic in the decision-table.

---

## Common Patterns

### Pattern 1: Simple Binary Branch

**Use when**: Recommendation has if-then-else logic

```yaml
rules:
  - rule_id: r1
    event: e1
    when: {criterion: "Yes"}
    then: [action-a]
    
  - rule_id: r2
    event: e1
    when: {criterion: "No"}
    then: [action-b]
```

---

### Pattern 2: Multi-Criterion Branch

**Use when**: Multiple conditions determine action

```yaml
rules:
  - rule_id: r1
    event: e1
    when: {criterion-a: "Yes", criterion-b: "Yes", criterion-c: "Yes"}
    then: [intensive-action]
    
  - rule_id: r2
    event: e1
    when: {criterion-a: "Yes", criterion-b: "No"}
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
    when: {assessment-positive: "Yes"}
    then: [intervention-a]
    decision_type: "branching"
    
  - rule_id: r3
    event: e1
    when: {assessment-positive: "No"}
    then: [intervention-b]
    decision_type: "branching"
```

---

### Pattern 4: Workflow Prerequisite Propagation

**Use when**: Procedural/temporal guidelines where clinical state persists across multiple sequential events

**Critical**: Carry forward prerequisite conditions established at earlier events

```yaml
# Event 1: Diagnosis established
rules:
  - id: r1
    event: e1
    when: {adult-patient: "Yes", crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes"}
    then: [confirm-crs-diagnosis]
    
# Event 2: Prerequisites REPEATED + new branch logic
rules:
  - id: r2
    event: e2
    when: {adult-patient: "Yes", crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes", purulent-discharge: "No"}
    then: [avoid-antibacterials]
    
  - id: r3
    event: e2
    when: {adult-patient: "Yes", crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes", purulent-discharge: "Yes"}
    then: [consider-antibacterials]
    
# Event 3: Prerequisites STILL REPEATED
rules:
  - id: r4
    event: e3
    when: {adult-patient: "Yes", crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes", surgical-criteria-met: "Yes"}
    then: [offer-sinus-surgery]
```

**Comment in YAML**:
```yaml
rules:
  # Event 2: Surgical planning checkpoint
  # Note: adult-patient, crs-diagnostic-criteria-met, objective-inflammation carried forward from e1
  - id: r2
    event: e2
    when: {adult-patient: "Yes", crs-diagnostic-criteria-met: "Yes", ...}
```

**Validation Note**: Extract validation should warn if downstream events omit persistent prerequisites established earlier.

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

### ❌ Anti-Pattern 2: Missing Prerequisite Carry-Forward (Workflow Gap)

**Problem**: Sequential events in a workflow omit persistent prerequisites established earlier, creating implicit logic gaps

**Example** (incomplete extraction):
```yaml
events:
  - id: e1
    label: "CRS Diagnosis"
    phase: "assessment"
  - id: e2
    label: "Treatment Decision"
    phase: "planning"
  - id: e3
    label: "Surgical Planning"
    phase: "intervention"

rules:
  # Event 1: Prerequisites established
  - id: r1
    event: e1
    when: {crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes"}
    then: [confirm-diagnosis]
    
  # ❌ WRONG: Event 2 omits prerequisites (assumes they persist implicitly)
  - id: r2
    event: e2
    when: {failed-medical-therapy: "Yes"}  # Missing: crs-diagnostic-criteria-met, objective-inflammation
    then: [consider-surgery]
    
  # ❌ WRONG: Event 3 also omits prerequisites
  - id: r3
    event: e3
    when: {fine-cut-ct-available: "Yes"}  # Missing: all earlier prerequisites
    then: [order-imaging]
```

**Fix**: Carry forward persistent prerequisites to downstream events
```yaml
rules:
  # Event 1: Prerequisites established
  - id: r1
    event: e1
    when: {crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes"}
    then: [confirm-diagnosis]
    
  # ✓ CORRECT: Event 2 repeats prerequisites
  - id: r2
    event: e2
    when: {crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes", failed-medical-therapy: "Yes"}
    then: [consider-surgery]
    rationale: "Prerequisites carried forward from e1; branch on medical therapy failure"
    
  # ✓ CORRECT: Event 3 repeats prerequisites
  - id: r3
    event: e3
    when: {crs-diagnostic-criteria-met: "Yes", objective-inflammation: "Yes", fine-cut-ct-available: "Yes"}
    then: [order-imaging]
    rationale: "Prerequisites carried forward from e1; branch on CT availability"
```

**When to carry forward**:
- Procedural/workflow guidelines with temporal sequencing
- Clinical state established at event N remains true at N+1, N+2, etc.
- Guideline doesn't explicitly re-evaluate the prerequisite at later events

**When NOT to carry forward**:
- Later event intentionally re-evaluates the condition (e.g., "reassess diagnosis")
- Abstraction is reviewer-approved (e.g., `diagnosis-confirmed` replaces individual criteria)
- Diagnostic tree guidelines (not workflow/procedural)

---

### ❌ Anti-Pattern 3: Abstract Summaries Without Source Traceability

**Problem**: Creating abstract summary conditions that hide the original source criteria

**Example** (over-abstraction):
```yaml
conditions:
  # ❌ WRONG: Abstract condition without preserving originals
  - id: diagnosis-confirmed
    label: "Diagnosis confirmed and patient eligible"
    description: "All diagnostic and eligibility criteria met"
    values: ["Yes", "No"]

rules:
  - id: r1
    event: e2
    when: {diagnosis-confirmed: "Yes"}  # What criteria? Lost traceability
    then: [proceed-to-treatment]
```

**Fix Option 1**: Keep both original conditions AND abstraction
```yaml
conditions:
  # Original conditions (traceable to guideline)
  - id: crs-diagnostic-criteria-met
    label: "CRS diagnostic criteria met"
    description: "Patient meets clinical diagnostic criteria per guideline section 2.1"
    values: ["Yes", "No"]
    
  - id: adult-patient
    label: "Adult patient"
    description: "Age ≥18 years"
    values: ["Yes", "No"]
    
  # Abstraction (if reviewer-approved for readability)
  - id: diagnosis-and-eligibility-confirmed
    label: "Diagnosis and eligibility confirmed"
    description: "Combines crs-diagnostic-criteria-met AND adult-patient (abstraction approved by reviewer)"
    values: ["Yes", "No"]
    note: "Abstraction of crs-diagnostic-criteria-met AND adult-patient"

rules:
  - id: r1
    event: e2
    when: {crs-diagnostic-criteria-met: "Yes", adult-patient: "Yes"}  # Use originals
    then: [proceed-to-treatment]
```

**Fix Option 2**: Document why abstraction replaces originals
```yaml
conditions:
  - id: diagnosis-confirmed
    label: "Diagnosis confirmed"
    description: "CRS diagnostic criteria met AND adult patient (approved abstraction replaces individual conditions: crs-diagnostic-criteria-met, adult-patient)"
    values: ["Yes", "No"]
    note: "Replaces: crs-diagnostic-criteria-met, adult-patient (reviewer decision: abstract for readability)"
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
    when: {polyps-present: "Yes"}
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
    when: {polyps-present: "Yes"}
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
    when: {other-condition: "Yes"}
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
- [ ] All events in pathway_phases have a matching `phase` value

---

**Next**: See pattern library in `examples/decision-tables/` for synthetic worked examples.

---

## Formalization Output (L2 → L3)

When your decision table is formalized via `rh-skills formalize`, it generates CPG-on-FHIR resources using state-based action tree patterns:

### PlanDefinition Structure

**One PlanDefinition per event** (not per rule):
- Events with multiple rules generate sibling actions under one PlanDefinition
- Each action represents one rule with its specific `when` conditions
- Actions reference ActivityDefinitions via `definitionCanonical`

Example formalization:
```yaml
# L2 Input
events:
  - id: surgical-decision
rules:
  - rule_id: r1
    event: surgical-decision
    when: {candidacy-met: Yes}
    then: [offer-surgery]
  - rule_id: r2
    event: surgical-decision
    when: {candidacy-met: No}
    then: [continue-medical-management]
```

```json
// L3 Output
{
  "resourceType": "PlanDefinition",
  "id": "surgical-decision",
  "action": [
    {
      "id": "r1",
      "condition": [{"expression": "CandidacyMet"}],
      "definitionCanonical": ".../ActivityDefinition/offer-surgery"
    },
    {
      "id": "r2",
      "condition": [{"expression": "not CandidacyMet"}],
      "definitionCanonical": ".../ActivityDefinition/continue-medical-management"
    }
  ]
}
```

### CQL Library: Explicit Conditions First

Keep the L2 artifact explicit. If multiple downstream rules depend on the same
clinically meaningful state, repeat that state in `rules.when{}` where it is
clinically required rather than inventing a new composite state in the L2
artifact.

```yaml
# L2: Shared prerequisite repeated explicitly where needed
when:
  has-diagnosis: Yes
  objective-findings: Yes
  medical-therapy-inadequate: Yes
```

The formalization layer may later optimize generated logic, but that is not an
L2 authoring contract. The L2 artifact should stay readable on its own.

### Polarity-Aware Conditions

**Negative conditions** (`when: {condition: No}`) automatically generate `not` expressions:

```yaml
# L2 Input
when: {contraindications-present: No}
```

```json
// L3 Output
{
  "condition": [{
    "expression": { "expression": "not ContraindicationsPresent" }
  }]
}
```

### Shared Prerequisites

If later rules truly require the same prerequisite state, keep that prerequisite
explicit in those later `rules.when{}` entries. Do not assume implicit carry
forward, and do not rely on hoisting behavior as part of the L2 model.

### Key Principles

- ✅ **One PlanDefinition per event** (not per rule)
- ✅ **L2 conditions stay explicit and readable**
- ✅ **Polarity-aware condition handling** (not X for false values)
- ✅ **Actions may branch OR execute, never both**
- ✅ **Shared prerequisites stay explicit where clinically required**

---
