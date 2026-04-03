#!/usr/bin/env bats
# tests/unit/promote.bats — Unit tests for hi-promote command

load '../test_helper'

setup() {
  setup_skills_dir
  export HI_SKILLS_ROOT="$SKILLS_DIR"
  export HI_REPO_ROOT="$REPO_ROOT"
  export LLM_PROVIDER=stub
  HI_PROMOTE="$REPO_ROOT/bin/hi-promote"
}

# ── Fixtures ──────────────────────────────────────────────────────────────────

make_skill_with_l1() {
  local skill="$1" l1_name="${2:-ada-guidelines}"
  local skill_dir="$SKILLS_DIR/$skill"
  mkdir -p "$skill_dir/l1" "$skill_dir/l2" "$skill_dir/l3" "$skill_dir/fixtures/results"
  cat > "$skill_dir/tracking.yaml" <<YAML
schema_version: "1.0"
skill:
  name: $skill
  title: Test Skill
  description: A test skill
  author: test
  created_at: "2026-04-03T00:00:00Z"
artifacts:
  l1: [{name: $l1_name, created_at: "2026-04-03T00:00:00Z"}]
  l2: []
  l3: []
events:
  - timestamp: "2026-04-03T00:00:00Z"
    type: created
    description: scaffolded
YAML
  echo "Raw clinical content for testing." > "$skill_dir/l1/$l1_name.md"
}

make_skill_with_l2() {
  local skill="$1"
  make_skill_with_l1 "$skill"
  local skill_dir="$SKILLS_DIR/$skill"
  for name in l2-artifact-a l2-artifact-b; do
    cat > "$skill_dir/l2/$name.yaml" <<YAML
id: $name
name: ${name//-/}
title: "Test L2 ${name}"
version: "1.0.0"
status: draft
domain: testing
description: |
  Test L2 artifact.
derived_from:
  - ada-guidelines
YAML
    yq eval -i ".artifacts.l2 += [{\"name\": \"$name\", \"created_at\": \"2026-04-03T00:00:00Z\", \"derived_from\": [\"ada-guidelines\"]}]" \
      "$skill_dir/tracking.yaml"
  done
}

# ── Derive mode ───────────────────────────────────────────────────────────────

@test "hi promote derive: creates L2 artifact file" {
  make_skill_with_l1 my-skill
  run "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria
  [ "$status" -eq 0 ]
  [ -f "$SKILLS_DIR/my-skill/l2/criteria.yaml" ]
}

@test "hi promote derive: updates tracking.yaml l2 list" {
  make_skill_with_l1 my-skill
  "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria
  local count
  count=$(yq eval '.artifacts.l2 | length' "$SKILLS_DIR/my-skill/tracking.yaml")
  [ "$count" -eq 1 ]
}

@test "hi promote derive: records l2_derived event in tracking" {
  make_skill_with_l1 my-skill
  "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria
  local event_type
  event_type=$(yq eval '.events[-1].type' "$SKILLS_DIR/my-skill/tracking.yaml")
  [ "$event_type" = "l2_derived" ]
}

@test "hi promote derive: --count creates N artifacts" {
  make_skill_with_l1 my-skill
  "$HI_PROMOTE" derive my-skill --source ada-guidelines --name risk --count 3
  [ -f "$SKILLS_DIR/my-skill/l2/risk-1.yaml" ]
  [ -f "$SKILLS_DIR/my-skill/l2/risk-2.yaml" ]
  [ -f "$SKILLS_DIR/my-skill/l2/risk-3.yaml" ]
}

@test "hi promote derive: --dry-run does not create file" {
  make_skill_with_l1 my-skill
  run "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria --dry-run
  [ "$status" -eq 0 ]
  [ ! -f "$SKILLS_DIR/my-skill/l2/criteria.yaml" ]
  [[ "$output" == *"DRY RUN"* ]]
}

@test "hi promote derive: fails exit 2 if L1 not found" {
  make_skill_with_l1 my-skill
  run "$HI_PROMOTE" derive my-skill --source nonexistent --name criteria
  [ "$status" -eq 2 ]
}

@test "hi promote derive: fails exit 2 if skill not found" {
  run "$HI_PROMOTE" derive ghost-skill --source l1-art --name l2-art
  [ "$status" -eq 2 ]
}

@test "hi promote derive: fails exit 2 with missing --source" {
  make_skill_with_l1 my-skill
  run "$HI_PROMOTE" derive my-skill --name criteria
  [ "$status" -eq 2 ]
}

# ── Combine mode ──────────────────────────────────────────────────────────────

@test "hi promote combine: creates L3 artifact file" {
  make_skill_with_l2 my-skill
  run "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable
  [ "$status" -eq 0 ]
  [ -f "$SKILLS_DIR/my-skill/l3/computable.yaml" ]
}

@test "hi promote combine: updates tracking.yaml l3 list" {
  make_skill_with_l2 my-skill
  "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable
  local count
  count=$(yq eval '.artifacts.l3 | length' "$SKILLS_DIR/my-skill/tracking.yaml")
  [ "$count" -eq 1 ]
}

@test "hi promote combine: records l3_converged event" {
  make_skill_with_l2 my-skill
  "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable
  local event_type
  event_type=$(yq eval '.events[-1].type' "$SKILLS_DIR/my-skill/tracking.yaml")
  [ "$event_type" = "l3_converged" ]
}

@test "hi promote combine: converged_from recorded in tracking" {
  make_skill_with_l2 my-skill
  "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable
  local count
  count=$(yq eval '.artifacts.l3[0].converged_from | length' "$SKILLS_DIR/my-skill/tracking.yaml")
  [ "$count" -eq 2 ]
}

@test "hi promote combine: --dry-run does not create file" {
  make_skill_with_l2 my-skill
  run "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable --dry-run
  [ "$status" -eq 0 ]
  [ ! -f "$SKILLS_DIR/my-skill/l3/computable.yaml" ]
  [[ "$output" == *"DRY RUN"* ]]
}

@test "hi promote combine: fails exit 2 if L2 not found" {
  make_skill_with_l2 my-skill
  run "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,ghost --name computable
  [ "$status" -eq 2 ]
}

@test "hi promote combine: fails exit 2 with missing --sources" {
  make_skill_with_l2 my-skill
  run "$HI_PROMOTE" combine my-skill --name computable
  [ "$status" -eq 2 ]
}

# ── Help / usage ──────────────────────────────────────────────────────────────

@test "hi promote: --help exits 0" {
  run "$HI_PROMOTE" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "hi promote: unknown mode exits 2" {
  run "$HI_PROMOTE" explode my-skill
  [ "$status" -eq 2 ]
}
