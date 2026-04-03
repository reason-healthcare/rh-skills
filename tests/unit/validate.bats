#!/usr/bin/env bats
# tests/unit/validate.bats — Unit tests for hi-validate command

load '../test_helper'

setup() {
  setup_skills_dir
  export HI_SKILLS_ROOT="$SKILLS_DIR"
  export HI_REPO_ROOT="$REPO_ROOT"
  HI_VALIDATE="$REPO_ROOT/bin/hi-validate"
}

# ── Fixture helpers ───────────────────────────────────────────────────────────

make_valid_l2() {
  local skill="$1" artifact="${2:-test-artifact}"
  mkdir -p "$SKILLS_DIR/$skill/l2"
  cat > "$SKILLS_DIR/$skill/l2/$artifact.yaml" <<YAML
id: $artifact
name: TestArtifact
title: "Test Artifact Title"
version: "1.0.0"
status: draft
domain: diabetes
description: |
  A test artifact for validation testing.
derived_from:
  - source-l1
YAML
}

make_invalid_l2() {
  local skill="$1" artifact="${2:-bad-artifact}"
  mkdir -p "$SKILLS_DIR/$skill/l2"
  cat > "$SKILLS_DIR/$skill/l2/$artifact.yaml" <<YAML
# Missing required fields: id, title, version, status, domain, derived_from
name: BadArtifact
description: "Incomplete artifact"
YAML
}

make_valid_l3() {
  local skill="$1" artifact="${2:-test-l3}"
  mkdir -p "$SKILLS_DIR/$skill/l3"
  cat > "$SKILLS_DIR/$skill/l3/$artifact.yaml" <<YAML
artifact_schema_version: "1.0"
metadata:
  id: $artifact
  name: TestL3
  title: "Test L3 Artifact"
  version: "1.0.0"
  status: draft
  domain: diabetes
  created_date: "2026-04-03"
  description: |
    A valid L3 artifact for testing.
converged_from:
  - test-l2-artifact
YAML
}

# ── L2 validation tests ───────────────────────────────────────────────────────

@test "hi validate: valid L2 artifact exits 0" {
  make_valid_l2 my-skill
  run "$HI_VALIDATE" my-skill l2 test-artifact
  [ "$status" -eq 0 ]
  [[ "$output" == *"VALID"* ]]
}

@test "hi validate: invalid L2 artifact exits 1" {
  make_invalid_l2 my-skill
  run "$HI_VALIDATE" my-skill l2 bad-artifact
  [ "$status" -eq 1 ]
  [[ "$output" == *"INVALID"* ]]
}

@test "hi validate: missing required field reported" {
  make_invalid_l2 my-skill missing-fields
  run "$HI_VALIDATE" my-skill l2 missing-fields
  [ "$status" -eq 1 ]
  [[ "$output" == *"MISSING required field"* || "$stderr" == *"MISSING required field"* ]]
}

@test "hi validate: unknown skill exits 2" {
  run "$HI_VALIDATE" nonexistent-skill l2 artifact
  [ "$status" -eq 2 ]
}

@test "hi validate: unknown artifact exits 2" {
  mkdir -p "$SKILLS_DIR/my-skill"
  run "$HI_VALIDATE" my-skill l2 nonexistent-artifact
  [ "$status" -eq 2 ]
}

@test "hi validate: invalid level exits 2" {
  mkdir -p "$SKILLS_DIR/my-skill"
  run "$HI_VALIDATE" my-skill l1 some-artifact
  [ "$status" -eq 2 ]
}

# ── L3 validation tests ───────────────────────────────────────────────────────

@test "hi validate: valid L3 artifact exits 0" {
  make_valid_l3 my-skill
  run "$HI_VALIDATE" my-skill l3 test-l3
  [ "$status" -eq 0 ]
  [[ "$output" == *"VALID"* ]]
}

@test "hi validate: L3 missing artifact_schema_version exits 1" {
  local skill="my-skill" artifact="bad-l3"
  mkdir -p "$SKILLS_DIR/$skill/l3"
  cat > "$SKILLS_DIR/$skill/l3/$artifact.yaml" <<YAML
metadata:
  id: $artifact
  name: BadL3
  title: "Bad L3"
  version: "1.0.0"
  status: draft
  domain: testing
  created_date: "2026-04-03"
  description: "Missing artifact_schema_version"
converged_from:
  - some-l2
YAML
  run "$HI_VALIDATE" $skill l3 $artifact
  [ "$status" -eq 1 ]
}

# ── Help / usage ──────────────────────────────────────────────────────────────

@test "hi validate: --help exits 0 and prints usage" {
  run "$HI_VALIDATE" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "hi validate: no args exits 0 and prints usage" {
  run hi-validate
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}
