# Eval Scenarios

Scenarios define the starting workspace state, the opening prompt, and the
expected outputs for a skill eval run. `scripts/eval-skill.sh` reads a scenario
file when you pass `--scenario <name>`.

## File location

```
eval/scenarios/<skill>/<scenario-name>.yaml
```

## Schema

```yaml
# ── Identity ─────────────────────────────────────────────────────────────────
name: string          # kebab-case, matches the filename stem
skill: string         # curated skill name, e.g. rh-inf-discovery
description: string   # one sentence: what this scenario tests

# ── Workspace setup ──────────────────────────────────────────────────────────
topic: string         # topic slug to initialise in the temp workspace

workspace:
  # Inline content for tracking.yaml. Omit to start from a blank slate.
  tracking_yaml: |
    ...

  # Files to write into the workspace before the agent starts.
  # Each entry needs either `content` (inline) or `fixture` (path relative to
  # eval/fixtures/).
  files:
    - path: relative/path/in/workspace
      content: |
        ...
      # OR
      fixture: fixtures/some-file.pdf

# ── Agent prompt ─────────────────────────────────────────────────────────────
# The opening message sent to the agent. Use {topic} and {skill} placeholders.
prompt: |
  ...

# ── Expected outputs ─────────────────────────────────────────────────────────
# Used to pre-populate the quality checklist in the review stub.
expected_outputs:
  - path: relative/path           # relative to workspace root
    checks:
      - exists                    # file must be present
      - contains: "some string"   # file content must include this string
      - event: event_name         # tracking.yaml must record this event

# ── Evaluation guidance ──────────────────────────────────────────────────────
efficiency_focus:
  - "Specific thing to watch for in the transcript (efficiency dimension)"

quality_focus:
  - "Specific thing to check in the output artifacts (quality dimension)"
```
