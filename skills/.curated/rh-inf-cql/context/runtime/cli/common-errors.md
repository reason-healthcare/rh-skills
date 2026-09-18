# Common Errors

Frequently encountered CLI failures and their most common root causes.

## Syntax Errors

```
error: unexpected token ')'
  --> Library.cql:42:18
```

**Category**: `syntax`
**Cause**: Malformed CQL expression, often unmatched parentheses or quotes.
**Fix**: Check the indicated line; look for unclosed brackets or string literals.

---

## Missing Include

```
error: could not resolve library 'FHIRHelpers'
```

**Category**: `translation`
**Cause**: `FHIRHelpers` or another included library is not on the include path.
**Fix**: Confirm the exact versioned CQL include exists in the topic's `computable/` directory. For a pinned external helper, use `rh-skills cql import-library <topic> <manifest.json>`; do not rely on implicit downloads.

---

## Type Mismatch

```
error: cannot apply operator 'during' to types 'DateTime' and 'Interval<Date>'
```

**Category**: `type-mismatch`
**Cause**: Interval boundary type does not match the operand type.
**Fix**: Use `Interval<DateTime>` consistently, or convert with `ToDateTime()`.

---

## Null Output (unexpected)

**Symptom**: Expression evaluates to `null` but should return `true` or `false`.
**Category**: `null-propagation` or `fixture-or-data-shape`
**Cause**: Missing fixture data, incorrect evaluation subject/context, or a missing helper conversion.
**Fix**:
1. Check fixture — does the bundle include the expected resource type?
2. Check `input/evaluation-context.json` for the intended subject and evaluation date.
3. If the expression converts a FHIR primitive or choice, include and resolve the pinned FHIRHelpers version; use FHIR logical types for choice values.

---

## Missing Binary

```
Error: rh CLI not found. Install with: cargo install rh
```

**Category**: `missing-binary`
**Fix**: Install with `cargo install rh`, or set `RH_CLI_PATH` in environment or `.rh-skills.toml`.

---

## Model Mismatch

```
error: element 'category' not found in type 'FHIR.Condition'
```

**Category**: `model-mismatch`
**Cause**: CQL written against QI-Core but evaluated with FHIR ModelInfo (or vice versa).
**Fix**: Align the `using` declaration in CQL with the actual ModelInfo version used by the evaluator.

---

## Terminology Resolution Failure

```
warning: value set 'http://cts.nlm.nih.gov/...' could not be resolved
```

**Category**: `terminology-resolution`
**Cause**: Value set not pre-expanded and no terminology service available.
**Fix**: Bundle a pre-expanded value set in the fixture, or configure a terminology service.

---

## FHIR Member Access Not Resolved (qualified identifier error)

```
✗ Could not resolve qualified identifier: ConditionResource.clinicalStatus
✗ Could not resolve qualified identifier: EncounterResource.status
```

**Category**: `model-mismatch` / `translation`

**Cause**: The `rh cql validate` tool requires **explicit parenthetical member access** for FHIR resource
fields inside query aliases. Standard dot-notation (e.g., `C.clinicalStatus`) does not resolve even when
`FHIRHelpers` is included.

**Wrong** (dot-notation on alias):
```cql
[Condition: "ASCVD"] C
  where C.clinicalStatus.coding StatusCoding
    where StatusCoding.code in { 'active' }
```

**Working** (explicit parenthetical nesting):
```cql
[Condition: "ASCVD"] C
  where exists (
    (((C).clinicalStatus).coding) StatusCoding
      where ((StatusCoding).code).value in { 'active' }
  )
```

**Pattern rules**:
- Wrap the alias in parens before accessing a field: `(C).field`
- Chain nested access with parens at each level: `((C).field).subfield`
- For primitive-valued FHIR fields (String, Code, Boolean), access `.value` explicitly
- `AgeInYearsAt()`, `exists`, `is not null`, and interval arithmetic work without special handling
- Direct status-code comparison on string enum fields: `((R).status).value in { 'active', 'completed' }`
