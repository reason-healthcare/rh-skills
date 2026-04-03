#!/usr/bin/env bats
# tests/integration/skill-lifecycle.bats — End-to-end skill workflow tests
# Tests the full L1 → L2 → L3 lifecycle without LLM calls (--dry-run)

load '../test_helper'

setup() {
  setup_skills_dir
  export HI_SKILLS_ROOT="$SKILLS_DIR"
  export HI_REPO_ROOT="$REPO_ROOT"
  export PATH="$REPO_ROOT/bin:$PATH"
}

# ── Phase 1: Init ─────────────────────────────────────────────────────────────

@test "lifecycle: hi init creates a valid skill scaffold" {
  run hi-init test-workflow-skill
  [ "$status" -eq 0 ]
  [ -d "$SKILLS_DIR/test-workflow-skill" ]
  [ -f "$SKILLS_DIR/test-workflow-skill/tracking.yaml" ]
  [ -f "$SKILLS_DIR/test-workflow-skill/SKILL.md" ]
}

@test "lifecycle: tracking.yaml is valid YAML after init" {
  hi-init test-workflow-skill
  yq eval '.' "$SKILLS_DIR/test-workflow-skill/tracking.yaml" > /dev/null
}

@test "lifecycle: l1 directory ready for artifacts after init" {
  hi-init test-workflow-skill
  [ -d "$SKILLS_DIR/test-workflow-skill/l1" ]
}

# ── Phase 2: L1 artifact ──────────────────────────────────────────────────────

@test "lifecycle: L1 artifact can be added manually" {
  hi-init test-workflow-skill
  echo "Clinical guideline content." > "$SKILLS_DIR/test-workflow-skill/l1/guideline.md"
  [ -f "$SKILLS_DIR/test-workflow-skill/l1/guideline.md" ]
}

# ── Phase 3: L2 promotion (dry-run — no LLM) ─────────────────────────────────

@test "lifecycle: hi promote derive dry-run prints prompt without LLM" {
  hi-init test-workflow-skill
  echo "Clinical content." > "$SKILLS_DIR/test-workflow-skill/l1/guideline.md"
  run hi-promote derive test-workflow-skill --source guideline --name criteria --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"DRY RUN"* ]]
}

# ── Phase 4: L2 validation ────────────────────────────────────────────────────

@test "lifecycle: hi validate accepts a well-formed L2 artifact" {
  hi-init test-workflow-skill
  cat > "$SKILLS_DIR/test-workflow-skill/l2/criteria.yaml" <<YAML
id: criteria
name: Criteria
title: "Screening Criteria"
version: "1.0.0"
status: draft
domain: testing
description: |
  A test L2 artifact for lifecycle validation.
derived_from:
  - guideline
YAML
  run hi-validate test-workflow-skill l2 criteria
  [ "$status" -eq 0 ]
}

@test "lifecycle: hi validate rejects L2 artifact missing required fields" {
  hi-init test-workflow-skill
  cat > "$SKILLS_DIR/test-workflow-skill/l2/bad.yaml" <<YAML
name: Bad
YAML
  run hi-validate test-workflow-skill l2 bad
  [ "$status" -eq 1 ]
}

# ── Phase 5: L3 promotion (dry-run) ───────────────────────────────────────────

@test "lifecycle: hi promote combine dry-run prints prompt without LLM" {
  hi-init test-workflow-skill
  cat > "$SKILLS_DIR/test-workflow-skill/l2/criteria.yaml" <<YAML
id: criteria
name: Criteria
title: "Screening Criteria"
version: "1.0.0"
status: draft
domain: testing
description: Test L2 artifact.
derived_from:
  - guideline
YAML
  run hi-promote combine test-workflow-skill --sources criteria --name computable --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"DRY RUN"* ]]
}

# ── Phase 6: L3 validation ────────────────────────────────────────────────────

@test "lifecycle: hi validate accepts a well-formed L3 artifact" {
  hi-init test-workflow-skill
  cat > "$SKILLS_DIR/test-workflow-skill/l3/computable.yaml" <<YAML
artifact_schema_version: "1.0"
metadata:
  id: computable
  name: Computable
  title: "Test Computable Artifact"
  version: "1.0.0"
  status: draft
  domain: testing
  created_date: "2026-04-03"
  description: |
    A test L3 artifact for lifecycle validation.
converged_from:
  - criteria
YAML
  run hi-validate test-workflow-skill l3 computable
  [ "$status" -eq 0 ]
}

# ── Tracking audit log ────────────────────────────────────────────────────────

@test "lifecycle: tracking.yaml l1/l2/l3 arrays are lists" {
  hi-init test-workflow-skill
  local l1_type l2_type l3_type
  l1_type=$(yq eval '.artifacts.l1 | type' "$SKILLS_DIR/test-workflow-skill/tracking.yaml")
  l2_type=$(yq eval '.artifacts.l2 | type' "$SKILLS_DIR/test-workflow-skill/tracking.yaml")
  l3_type=$(yq eval '.artifacts.l3 | type' "$SKILLS_DIR/test-workflow-skill/tracking.yaml")
  [ "$l1_type" = "!!seq" ]
  [ "$l2_type" = "!!seq" ]
  [ "$l3_type" = "!!seq" ]
}
