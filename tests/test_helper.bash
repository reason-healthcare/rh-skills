#!/usr/bin/env bash
# tests/test_helper.bash — Shared setup for bats test suites

# Resolve repo root relative to this file
TEST_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$TEST_HELPER_DIR")"
BIN_DIR="$REPO_ROOT/bin"

# Set SKILLS_DIR to a unique per-test temp location for isolation
# Uses BATS_TEST_TMPDIR (bats 1.3+) when available, falls back to BATS_TMPDIR subdir
setup_skills_dir() {
  local base_tmp="${BATS_TEST_TMPDIR:-$BATS_TMPDIR/test-$$-$RANDOM}"
  mkdir -p "$base_tmp"
  export SKILLS_DIR="$base_tmp/skills"
  mkdir -p "$SKILLS_DIR"
}

# Create a minimal initialized skill for use in tests
# Usage: create_test_skill <skill-name>
create_test_skill() {
  local name="$1"
  local skill_dir="$SKILLS_DIR/$name"
  mkdir -p "$skill_dir/l1" "$skill_dir/l2" "$skill_dir/l3" "$skill_dir/fixtures/results"
  cat > "$skill_dir/tracking.yaml" <<YAML
schema_version: "1.0"
skill:
  name: $name
  title: Test Skill
  description: A test skill
  author: test-user
  created_at: "2026-04-03T00:00:00Z"
artifacts:
  l1: []
  l2: []
  l3: []
events:
  - timestamp: "2026-04-03T00:00:00Z"
    type: created
    description: Skill initialized
YAML
  cat > "$skill_dir/SKILL.md" <<MD
---
name: "$name"
description: "Test skill"
---

## Instructions
Test skill instructions.
MD
}

# Add an L1 artifact to an existing test skill
add_l1_artifact() {
  local skill_name="$1"
  local artifact_name="$2"
  local content="${3:-Raw discovery content for testing.}"
  echo "$content" > "$SKILLS_DIR/$skill_name/l1/$artifact_name.md"
  yq eval -i ".artifacts.l1 += [{\"name\": \"$artifact_name\", \"created_at\": \"2026-04-03T00:00:00Z\"}]" \
    "$SKILLS_DIR/$skill_name/tracking.yaml"
}

# Add an L2 artifact to an existing test skill
add_l2_artifact() {
  local skill_name="$1"
  local artifact_name="$2"
  cat > "$SKILLS_DIR/$skill_name/l2/$artifact_name.yaml" <<YAML
id: $artifact_name
name: TestArtifact
title: "Test L2 Artifact"
version: "1.0.0"
status: draft
domain: "Testing"
description: |
  A test L2 artifact for unit testing purposes.
  Used to verify promotion and validation logic.
derived_from:
  - discovery
YAML
  yq eval -i ".artifacts.l2 += [{\"name\": \"$artifact_name\", \"created_at\": \"2026-04-03T00:00:00Z\", \"derived_from\": [\"discovery\"]}]" \
    "$SKILLS_DIR/$skill_name/tracking.yaml"
}

# Override hi_skills_root for tests by patching PATH to use test wrappers
# The bin scripts use hi_skills_root() which reads relative to BASH_SOURCE.
# In tests, we override by setting HI_SKILLS_ROOT env var.
export HI_SKILLS_ROOT=""  # set per-test via setup_skills_dir

# Make bin/ scripts available on PATH
export PATH="$BIN_DIR:$PATH"
