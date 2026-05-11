---
name: reasonhub-snomed-semantic
description: >
  Use SNOMED CT's semantic attribute relationships to answer clinical questions.
  Finds concepts by relationship attribute (finding site, causative agent,
  associated morphology, procedure site), navigates the IS-A hierarchy, and
  composes property-filtered ValueSets. Use when the user asks things like
  "all disorders of the heart", "all procedures on the kidney", "all conditions
  caused by bacteria", "subtypes of hypertension", "symptoms of X",
  "complications of X", or any query that involves clinical relationships
  between concepts rather than simple text search.
license: MIT
compatibility: Requires ReasonHub MCP server. Sign up at reasonhub.app.
---

# SNOMED Semantic Query

## Overview

SNOMED CT is unique among clinical terminologies: every fully-defined concept
carries explicit **attribute relationships** encoded as FHIR properties.  These
let you answer questions like "all disorders of the cardiovascular system" or
"all conditions with infarct morphology" using structured queries rather than
keyword search.

This skill walks through the full workflow: find the pivot concept, inspect its
relationships, choose the right attribute type, and build a `valueset_expand`
filter that returns exactly the right set of codes.

---

## Output

Every query produces two deliverables.

### 1. FHIR ValueSet JSON (always deliver this)

Return a complete `ValueSet` resource with `name`, `title`, `status`, and a
populated `compose.include`. This is the primary artifact — useful whether or
not expansion succeeds.

```json
{
  "resourceType": "ValueSet",
  "name": "AllInfarctDisorders",
  "title": "All Infarct Disorders",
  "status": "draft",
  "compose": {
    "include": [
      {
        "system": "http://snomed.info/sct",
        "version": "<from list_available_codesystem_versions>",
        "filter": [
          { "property": "116676008", "op": "=", "value": "55641003" },
          { "property": "inactive",  "op": "=", "value": "false" }
        ]
      }
    ]
  }
}
```

### 2. Expansion (ask the user)

After delivering the ValueSet JSON, ask:

> "Would you like me to expand this and show the matching codes?
> I can format the results as a **markdown table** or **CSV**."

If the user says yes, attempt `valueset_expand` **once**. On failure,
**immediately run `reasonhub-skills expand`** with the same ValueSet JSON
— do not explain, do not offer alternatives, just run it.

If expansion succeeds, check the response for a `total` count. The MCP
transport layer truncates returned rows regardless of the `count` parameter,
and `offset`-based paging is unreliable. **If rows returned are fewer than
`total`, label the output explicitly and stop:**

> ⚠️ Partial result — {n} of {total} codes shown. The full set is defined
> by the ValueSet JSON above; run it against any FHIR terminology server
> for the complete expansion.

Do not retry with different `count` or `offset` values — this will not
retrieve additional rows.

If expansion succeeds, use the requested format:

**Markdown table** (default):
| Code | Display |
|---|---|
| `22298006` | Myocardial infarction |
| `432504007` | Cerebral infarction |

**CSV** (when the user asks to download, import, or use in a spreadsheet):
```csv
code,display
22298006,"Myocardial infarction"
432504007,"Cerebral infarction"
```

For SNOMED results, adding `semanticTag` as a third column is useful when
the expansion mixes disorders, findings, and procedures:
```csv
code,display,semanticTag
22298006,"Myocardial infarction",disorder
432504007,"Cerebral infarction",disorder
```

---

## SNOMED's Semantic Model

### Common relationship attributes

This table lists frequently encountered attributes. It is **not exhaustive** —
SNOMED CT defines hundreds of attribute types, and the exact set on any concept
depends on its definition. Always use `codesystem_lookup` on a representative
concept to discover the actual attributes present (see
[Discovering Attributes by Lookup](#discovering-attributes-by-lookup) below).

| Attribute typeId | Name | Applies to | Example |
|---|---|---|---|
| `363698007` | Finding site | Disorders, findings | Finding site = Heart structure (`80891009`) |
| `246075003` | Causative agent | Disorders, infections | Causative agent = Staphylococcus (`65119002`) |
| `116676008` | Associated morphology | Disorders, findings | Associated morphology = Infarct (`55641003`) |
| `363704007` | Procedure site - Direct | Procedures | The structure directly incised/excised. Kidney biopsy uses `405813007` (Indirect) instead — look up first. |
| `405813007` | Procedure site - Indirect | Procedures | The target organ reached through another structure. Often used where `363704007` might be expected. |
| `370135005` | Pathological process | Disorders | Pathological process = Inflammatory (`441862004`) |
| `47429007`  | Associated with | Findings, disorders | Associated with = Hypertension (`38341003`) |
| `42752001`  | Due to | Disorders, findings | Due to = Type 2 diabetes mellitus (`44054006`) — links complications to causal condition |
| `363713009` | Interprets | Findings | Interprets = Blood pressure (`75367002`) |
| `363714003` | Has interpretation | Findings | Has interpretation = Increased (`35105006`) |
| `255234002` | After | Procedures | After = General anaesthesia |

### How the filter works

Relationship filters are **outbound**: they find concepts where a given
attribute *points to* a target concept.

```
concept --[363698007 Finding site]--> 80891009 Heart structure
```

So `filter: property=363698007, op==, value=80891009` returns all concepts
whose "finding site" attribute equals "Heart structure".

### ⚠️ `=` is exact match, not subsumption

The `=` operator matches only concepts that store **exactly** the specified
concept ID as their attribute value. It does **not** apply subsumption to the
value side — filtering by `363698007 = 321667001` (respiratory tract) will
**not** automatically include concepts coded to `39607008` (lung structure) or
`113255004` (lung parenchyma), even though both are subtypes of respiratory tract.

SNOMED concepts are coded to specific anatomical sites, not to tidy ancestor
concepts. For example:

| Concept | `363698007` finding site coded to |
|---|---|
| Bacterial pneumonia (`53084003`) | `113255004` Structure of parenchyma of lung |
| Bacterial respiratory infection (`312117008`) | `20139000` Structure of respiratory system |
| Pneumoconiosis (`40122008`) | `39607008` Lung structure |

A query for `363698007 = 321667001` (respiratory tract) matches **none** of
these, because none are coded to that exact concept ID.

**Practical rule:** always call `codesystem_lookup` on a few representative
concepts in your target clinical domain first. Read the actual value stored for
your attribute, then use that concept ID — or its closest common ancestor that
concepts in that domain actually share — as your filter value.

> **What you cannot do directly:** reverse lookups ("find all concepts that
> hypertension causes"). SNOMED doesn't have a `has-symptom` attribute.
> Use the IS-A hierarchy or causative-agent filter instead.

---

## Workflow

### Step 1 — Identify the pivot concept

The *pivot* is the concept you want to filter **by** (the attribute value).

Use `search_snomed` with a descriptive query:

```
search_snomed(query="heart structure anatomy")
search_snomed(query="infarct morphology")
search_snomed(query="staphylococcus aureus organism")
```

Pick the best match. Body structures usually have semantic tag `(body structure)`,
organisms have `(organism)`, morphologies have `(morphologic abnormality)`.

### Step 2 — Confirm with `codesystem_lookup`

```
codesystem_lookup(code="80891009", system="http://snomed.info/sct")
```

Check:
- `display` matches what you expect
- `semanticTag` confirms the concept type
- `inactive` is `false`

### Step 3 — Discover the attribute type via lookup

Do not rely solely on the table above. **Always look up a representative
concept** in the target domain to see which attribute typeIds are actually
present:

```
codesystem_lookup(code="22298006", system="http://snomed.info/sct")
# Returns properties including:
#   363698007 (Finding site) = 74281007 (Myocardium structure)
#   116676008 (Associated morphology) = 55641003 (Infarct)
```

Properties whose `code` is a bare numeric SNOMED ID are attribute
relationships. Named properties (`parent`, `inactive`, `semanticTag`, etc.)
are metadata, not clinical attributes.

**Example — discovering hypertension's attributes:**
```
codesystem_lookup(code="38341003", system="http://snomed.info/sct")
# Reveals:
#   363698007 (Finding site)      = 51840005 (Systemic circulatory system)
#   363713009 (Interprets)        = 35105006 (Increased)
#   363714003 (Has interpretation)= 75367002 (Blood pressure)
# Note: sufficientlyDefined=false — primitive concept, sparse attributes
```

Hypertension's attributes describe *what it is* (elevated BP in the
circulatory system), not its clinical associations. This is why the
`associated with` filter for "symptoms of hypertension" returns sparse
results — see [Translating Clinical Questions](#translating-clinical-questions).

### Step 4 — Expand with a property filter

```json
{
  "resourceType": "ValueSet",
  "compose": {
    "include": [{
      "system": "http://snomed.info/sct",
      "version": "<use list_available_codesystem_versions>",
      "filter": [
        {
          "property": "363698007",
          "op": "=",
          "value": "80891009"
        }
      ]
    }]
  }
}
```

Pass this to `valueset_expand`.

> **⚠️ pi limitation:** In the pi agent the `valueset` parameter is always
> received as a string due to `$ref` type serialization, causing
> `valueset: must be object`. **Do not retry. Do not offer alternatives.
> Immediately run `reasonhub-skills expand` with the ValueSet JSON.**
> If the CLI is missing:
> `curl -fsSL https://raw.githubusercontent.com/reason-healthcare/reasonhub-skills/main/bin/reasonhub-skills -o ~/.local/bin/reasonhub-skills && chmod +x ~/.local/bin/reasonhub-skills`

### Step 5 — Refine with stacked filters

Filters in the same `include` are combined with AND:

```json
"filter": [
  { "property": "concept",   "op": "is-a", "value": "64572001" },
  { "property": "363698007", "op": "=",    "value": "80891009" },
  { "property": "inactive",  "op": "=",    "value": "false"    }
]
```

→ Active disorders (`is-a 64572001`) whose finding site is the heart.

---

## Common Clinical Patterns

### All disorders of a body structure
```json
{ "property": "363698007", "op": "=", "value": "<body_structure_id>" }
```

### All disorders caused by an agent
```json
{ "property": "246075003", "op": "=", "value": "<organism_or_substance_id>" }
```

### All disorders with a morphology
```json
{ "property": "116676008", "op": "=", "value": "<morphology_id>" }
```

### All procedures on a body site
```json
{ "property": "363704007", "op": "=", "value": "<body_structure_id>" }
```
> Check with `codesystem_lookup` whether the procedure uses `363704007` (Direct)
> or `405813007` (Indirect) — kidney biopsy, for example, uses Indirect.

### All subtypes of a condition (hierarchy)
```json
{ "property": "concept", "op": "is-a", "value": "<parent_concept_id>" }
```

> ⚠️ **`is-a` captures clinical subtypes only, NOT complications.**
> Concepts like "retinopathy due to T2DM" are NOT IS-A children of T2DM — they link
> via `42752001` (Due to). Use the two-include compose pattern below for complete eCQM sets.

### Strict descendants only (exclude the parent itself)
```json
{ "property": "concept", "op": "descendent-of", "value": "<parent_concept_id>" }
```

### All disorders caused by / due to a condition
```json
{ "property": "42752001", "op": "=", "value": "<condition_id>" }
```
Captures complication concepts encoded with "Due to" (e.g., retinopathy/neuropathy due to T2DM).

### Complete eCQM ValueSet: condition subtypes + their complications (two-include compose)
```json
{
  "compose": {
    "include": [
      {
        "system": "http://snomed.info/sct",
        "filter": [{ "property": "concept",  "op": "is-a", "value": "<condition_id>" }]
      },
      {
        "system": "http://snomed.info/sct",
        "filter": [{ "property": "42752001", "op": "=",   "value": "<condition_id>" }]
      }
    ]
  }
}
```

### Active concepts only (add to any filter set)
```json
{ "property": "inactive", "op": "=", "value": "false" }
```

---

## Translating Clinical Questions

Natural language clinical questions often don't map cleanly to a single
SNOMED attribute. Use this table to pick the best strategy, with fallbacks
when attribute coverage is thin.

| Clinical question | Best strategy | Coverage | Fallback |
|---|---|---|---|
| "All disorders of [body part]" | `363698007 = <body_structure>` + `is-a 64572001` | ⚠️ `=` is exact match — look up a representative concept first to find the actual concept ID used. See note below. | `is-a` on the body-site disorder parent |
| "All conditions caused by [agent]" | `246075003 = <organism/substance>` | ✅ Good — infections well-modelled | `is-a` on infectious disease hierarchy |
| "All procedures on [body part]" | `363704007 = <body_structure>` + `is-a 71388002` | ⚠️ Look up first — many procedures use `405813007` (Indirect) instead of Direct | `is-a` on the procedure hierarchy |
| "Subtypes of [condition]" | `concept is-a <condition>` | ✅ Always works | — |
| "Symptoms / findings associated with [condition]" | `47429007 = <condition>` + `is-a 404684003` | ⚠️ Sparse — only explicitly encoded associations | See note below |
| "Complications of [condition]" | `42752001 = <condition>` + `is-a 64572001` | ✅ Good — fully-defined complication concepts encode this | `47429007 = <condition>` (broader "associated with") |
| "Risk factors for [condition]" | `47429007 = <condition>` + `is-a 229819007` | ⚠️ Sparse | Semantic search |

### The `associated with` pattern and its limits

The filter for "symptoms/findings associated with X" is:

```json
"filter": [
  { "property": "47429007", "op": "=", "value": "<condition_id>" },
  { "property": "concept",  "op": "is-a", "value": "404684003" }
]
```

This returns **only concepts that explicitly encode the association** as an
outbound attribute. Coverage depends entirely on how well that condition is
modelled in SNOMED:

- **Well-modelled conditions** (many fully-defined descendants): returns
  useful results. Example: specific infectious diseases, metabolic disorders.
- **Primitive conditions** (`sufficientlyDefined = false`, e.g., hypertension):
  the condition itself has few outbound attributes, and few concepts encode
  hypertension as their `associated with` value. The expansion will likely
  be empty or very small.

**When `associated with` returns thin results, use these strategies instead:**

1. **Subtypes** — the condition's descendants often *are* its more specific
   presentations:
   ```json
   { "property": "concept", "op": "is-a", "value": "<condition_id>" }
   ```

2. **Finding site** — find all findings at the same anatomical site:
   ```json
   { "property": "363698007", "op": "=", "value": "<site_from_lookup>" }
   ```
   Use `codesystem_lookup` on the condition first to extract its finding site.

3. **Semantic search** — use `search_snomed` with the condition name plus
   context terms (`"hypertension complication"`, `"elevated blood pressure
   finding"`) to find individual concepts, then build an explicit list.

### Worked example: "All infarct disorders" — discovering associated morphology

This example shows how a single non-hierarchy attribute filter crosses every
organ system to return a clinically precise, exhaustive result set — the
capability that most distinguishes SNOMED from ICD-10 or text search.

```
# Step 1 — look up a known, fully-defined infarct disorder to discover the attribute
codesystem_lookup("22298006")  # Myocardial infarction
  → 116676008 (Associated morphology) = 55641003 (Infarct)
  → 363698007 (Finding site)          = 74281007 (Myocardium structure)
  → sufficientlyDefined = true  ← fully defined, complete attribute set

# Step 2 — confirm the morphology concept is active and correctly typed
codesystem_lookup("55641003")  # Infarct
  → semanticTag = "morphologic abnormality"  ← correct type for 116676008 values
  → inactive = false

# Step 3 — verify the same morphology value appears on a different organ
codesystem_lookup("432504007")  # Cerebral infarction
  → 116676008 (Associated morphology) = 55641003 (Infarct)  ← same value
  → 363698007 (Finding site)          = 83678007 (Cerebrum)  ← different site

# Step 4 — confirm generic stroke uses a DIFFERENT morphology
codesystem_lookup("230690007")  # Cerebrovascular accident (stroke, CVA)
  → 116676008 (Associated morphology) = 37782003 (Damage)  ← NOT Infarct
  # → the filter will correctly exclude hemorrhagic stroke and generic CVA
```

**Step 5 — expand all infarct disorders (cross-organ)**
```json
{
  "filter": [
    { "property": "116676008", "op": "=", "value": "55641003" },
    { "property": "inactive",  "op": "=", "value": "false"    }
  ]
}
```
→ Myocardial infarction, cerebral infarction, renal infarction, pulmonary
  infarction, splenic infarction, mesenteric infarction, bone infarction…
  One filter. Every organ. No text matching.

**Step 6 — narrow to ischemic stroke only (stacked filters)**
```json
{
  "filter": [
    { "property": "116676008", "op": "=", "value": "55641003" },
    { "property": "363698007", "op": "=", "value": "83678007" },
    { "property": "inactive",  "op": "=", "value": "false"    }
  ]
}
```
→ Cerebral infarction and its subtypes (thrombotic, embolic, lacunar,
  pontine) — ischemic stroke only, hemorrhagic stroke excluded by design.

---

## Worked Examples

### "All infarct disorders across every organ"
1. Lookup: `codesystem_lookup("22298006")` → `116676008 = 55641003` (morphology = Infarct)
2. Verify: `codesystem_lookup("432504007")` → same morphology on cerebral infarction
3. Contrast: `codesystem_lookup("230690007")` → CVA has morphology = `37782003` (Damage), not Infarct
4. Filter: `116676008 = 55641003` → MI, cerebral infarction, renal infarction, pulmonary infarction…
5. Stack: add `363698007 = 83678007` (Cerebrum) to narrow to ischemic stroke subtypes only

### "All cardiac disorders"
1. Lookup: `codesystem_lookup("22298006")` → confirms `363698007 = 74281007` (Myocardium) — note this is the myocardium, not heart. Check several concepts to find the broadest commonly-used site.
2. Search: `search_snomed("heart structure body structure")` → `80891009` Heart structure
3. Filter: `363698007 = 80891009` inside `is-a 64572001` (Disorder)
   > `=` is exact match. Concepts coded to `74281007` (Myocardium) or `40527003` (Left ventricle) are missed. Use causative-agent or `is-a` as a broader net if coverage is thin.

### "All bacterial infections"
1. Search: `search_snomed("bacteria organism")` → `409822003` Bacterium
2. Filter: `246075003 = 409822003` inside `is-a 40733004` (Infectious disease)

### "All ischemic conditions"
1. Search: `search_snomed("ischemic process pathological")` → `255426005`
2. Filter: `370135005 = 255426005`

### "All renal procedures"
1. Lookup: `codesystem_lookup("7246002")` (Kidney biopsy) → `405813007 = 64033007` — uses **Indirect** site, not Direct
2. Search: `search_snomed("kidney structure body structure")` → `64033007`
3. Filter: try both `363704007 = 64033007` and `405813007 = 64033007`; use `is-a 71388002` (Procedure) in both

### eCQM denominator/numerator: all T2DM concepts (subtypes + complications)

This is the canonical example for building exhaustive eCQM criteria.

**Step 1 — Verify the root concept**
```
codesystem_lookup("44054006")  →  display = "Type 2 diabetes mellitus"
                                   sufficientlyDefined = false  ← primitive
                                   parent = 73211009 (Diabetes mellitus)
```

**Step 2 — Check which concepts are IS-A children vs. complication-linked**

| Concept | Code | In `is-a 44054006`? | Link |
|---|---|---|---|
| T2DM in obese | `81531005` | ✅ Yes | direct `parent = 44054006` |
| Insulin-treated T2DM | `237599002` | ✅ Yes | direct `parent = 44054006` |
| Retinopathy due to T2DM | `422034002` | ❌ No | `42752001` (Due to) = `44054006` |
| Neuropathy due to T2DM | `368581000119106` | ❌ No | `42752001` (Due to) = `44054006` |
| CAD due to T2DM | `16891151000119103` | ❌ No | `42752001` (Due to) = `44054006` |

> `is-a` alone misses all complication concepts. For a complete eCQM set,
> use a two-include ValueSet that unions both trees.

**Step 3 — Build the complete ValueSet**
```json
{
  "resourceType": "ValueSet",
  "compose": {
    "include": [
      {
        "system": "http://snomed.info/sct",
        "version": "<see list_available_codesystem_versions>",
        "filter": [
          { "property": "concept", "op": "is-a", "value": "44054006" },
          { "property": "inactive", "op": "=",   "value": "false" }
        ]
      },
      {
        "system": "http://snomed.info/sct",
        "version": "<see list_available_codesystem_versions>",
        "filter": [
          { "property": "42752001", "op": "=",   "value": "44054006" },
          { "property": "inactive", "op": "=",   "value": "false" }
        ]
      }
    ]
  }
}
```

- **Include 1** captures the root code `44054006` plus all IS-A subtypes (clinical variants of T2DM)
- **Include 2** captures all complications encoded with "Due to = T2DM" (retinopathy, neuropathy, nephropathy, peripheral vascular disease, etc.)
- Together they form the exhaustive denominator or numerator set most eCQMs require

**Scope note:** use `descendent-of` instead of `is-a` in include 1 if the measure
exclicitly excludes the root code (uncommon but possible in pre-coordinated IGs).

---

## Discovering Attributes by Lookup

The attribute table earlier is a starting point, not a complete list. The
authoritative source is the concept data itself.

**Protocol:**

1. Pick a well-known, fully-defined (`sufficientlyDefined = true`) example
   concept from the target clinical domain.
2. Call `codesystem_lookup` on it.
3. In the response, find `property` entries whose `code` is a bare numeric
   SNOMED concept ID — those are attribute relationships.
4. The `description` field names the attribute (e.g., `"Myocardium structure"`).
   To get the attribute *type* name, call `codesystem_lookup` on the typeId
   itself (e.g., `codesystem_lookup("363698007")` → `"Finding site"`).
5. Use those typeIds in your `valueset_expand` filter.

**Prefer fully-defined concepts for discovery.** Primitive concepts
(`sufficientlyDefined = false`) have fewer or no attribute relationships and
will not reveal the full attribute set used by their clinical class.

```
# Good discovery target: Myocardial infarction (sufficientlyDefined=true)
codesystem_lookup("22298006")  →  363698007, 116676008 present

# Poor discovery target: Hypertensive disorder (sufficientlyDefined=false)
codesystem_lookup("38341003")  →  only 363698007, 363713009, 363714003
                                   (incomplete picture of disorder attributes)
```

---

## Hierarchy Checks

Before building a hierarchy filter, verify the relationship:

```
codesystem_subsumes(
  code_a="64572001",   # Disease
  code_b="22298006",   # Myocardial infarction
  system="http://snomed.info/sct"
)
# Expected: subsumed-by (MI is a subtype of Disease)
```

---

## Getting the Full Property Reference

```
codesystem_filter_properties(system="http://snomed.info/sct")
```

---

## Important Constraints

- Only **active** relationships are stored. Inactive concept attributes are
  excluded.
- **Primitive concepts** (`sufficientlyDefined = false`) may have no or fewer
  attribute relationships — they're defined only by IS-A.
- Relationship **role groups** are flattened during import. Combined attributes
  within a single role group (e.g., "finding site + associated morphology")
  are not enforced together in filters.
- No `has-symptom` attribute exists in SNOMED. Use the
  [Translating Clinical Questions](#translating-clinical-questions) section
  for the recommended strategies, including `associated with` filters,
  finding-site pivots, and hierarchy traversal.