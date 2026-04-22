# Case 001 — Basic Positive: IsAdult

## What this case tests

`IsAdult` should return `true` for a patient born in 1975 when the
Measurement Period starts in 2024 (age = 48 at period start).

## Fixture design

- **Patient**: born 1975-06-15 (male)
- **Measurement Period**: 2024-01-01 to 2024-12-31 (default parameter)
- **No clinical events**: this case tests age-only logic

## Expected results

| Define   | Expected | Reason |
|----------|----------|--------|
| IsAdult  | true     | Age 48 ≥ 18 at start of measurement period |

## Failure analysis

If `IsAdult` returns `false` or `null`, check:
1. `AgeInYearsAt(start of "Measurement Period")` — is `start of` used correctly?
2. Is the Measurement Period parameter defaulting as expected?
3. Does `birthDate` parse correctly in the FHIR bundle?
