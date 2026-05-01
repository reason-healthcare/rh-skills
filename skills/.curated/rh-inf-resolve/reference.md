# rh-inf-resolve Reference

## CLI Commands

### List open concerns

```sh
rh-skills promote concerns <topic>
```

Lists all concern/conflict entries with an empty or absent `resolution` field, across
both `extract-plan.yaml` and `formalize-plan.yaml` (whichever exist).

**Output format (one block per open concern):**

```
Open concerns for topic '<topic>':

  plan=extract  artifact=screening-decisions  index=0
    Concern   : ADA interval language is more explicit than USPSTF interval framing.
    Resolution: _pending_

Total: 1 open concern(s). Use 'rh-skills promote resolve-concern' to record resolutions.
```

If no open concerns exist:

```
No open concerns for topic '<topic>'.
```

---

### Record a resolution

```sh
rh-skills promote resolve-concern <topic> \
  --plan <extract|formalize> \
  --artifact <artifact_name> \
  --index <N> \
  --resolution "<resolution text>"
```

| Option        | Description                                              |
|---------------|----------------------------------------------------------|
| `--plan`      | `extract` (extract-plan.yaml) or `formalize`             |
| `--artifact`  | Artifact name as shown in the concerns listing           |
| `--index`     | 0-based index of the concern within that artifact        |
| `--resolution`| Human-supplied resolution text                           |

**Example:**

```sh
rh-skills promote resolve-concern diabetes-ccm \
  --plan extract \
  --artifact screening-decisions \
  --index 0 \
  --resolution "ADA 2024 is the primary source; USPSTF interval framing is \
supplementary and does not override the primary recommendation."
```

**Confirmation output:**

```
Resolved concern 0 on 'screening-decisions' in extract-plan.yaml.
No open concerns remain in extract-plan.yaml.
```

---

## Concern Data Model

Extract plans store `concerns[]`; formalize plans continue to store
`conflicts[]`, and the CLI surfaces both through the `concerns` command:

```yaml
artifacts:
  - name: screening-decisions
    concerns:
      - concern: "ADA interval language is more explicit than USPSTF."
        resolution: ""           # empty = open
      - concern: "ADA <7.0% vs AACE ≤6.5%"
        resolution: "ADA 2024 preferred per clinical lead."   # filled = resolved
```

A concern is **open** when `resolution` is absent, null, or empty string.

---

## Integration with Other Skills

### rh-inf-extract

After `promote plan`, before `promote approve`:

```sh
rh-skills promote concerns <topic>
# If any open → invoke rh-inf-resolve <topic> before approving
```

### rh-inf-formalize

After `promote formalize-plan`, before `formalize`:

```sh
rh-skills promote concerns <topic>
# If any open → invoke rh-inf-resolve <topic> before formalizing
```

---

## Plan Files

| Plan file                    | Covers                        |
|------------------------------|-------------------------------|
| `process/plans/extract-plan.yaml`    | L1→L2 extraction planning     |
| `process/plans/formalize-plan.yaml`  | L2→L3 formalization planning  |
