#!/usr/bin/env bats
# tests/unit/promote.bats — Unit tests for hi-promote command

load '../test_helper'

setup() {
  setup_topics_dir
  export HI_TOPICS_ROOT="$TOPICS_DIR"
  export HI_REPO_ROOT="$REPO_ROOT"
  export LLM_PROVIDER=stub
  HI_PROMOTE="$REPO_ROOT/bin/hi-promote"
}

# ── Fixtures ──────────────────────────────────────────────────────────────────

make_skill_with_l1() {
  local skill="$1" l1_name="${2:-ada-guidelines}"
  local skill_dir="$TOPICS_DIR/$skill"
  mkdir -p "$skill_dir/l2" "$skill_dir/l3" "$skill_dir/fixtures/results"

  local _entry="$TOPICS_DIR/._${skill}_entry.yaml"
  cat > "$_entry" <<YAML
name: $skill
title: Test Skill
description: A test skill
author: test
created_at: "2026-04-03T00:00:00Z"
artifacts:
  l2: []
  l3: []
events:
  - timestamp: "2026-04-03T00:00:00Z"
    type: created
    description: scaffolded
YAML

  if [[ ! -f "$HI_TRACKING_FILE" ]]; then
    printf 'schema_version: "1.0"\nl1: []\ntopics: []\nevents: []\n' > "$HI_TRACKING_FILE"
  fi

  local _merged="$TOPICS_DIR/._${skill}_merged.yaml"
  yq eval-all 'select(fileIndex==0).topics += [select(fileIndex==1)] | select(fileIndex==0)' \
    "$HI_TRACKING_FILE" "$_entry" > "$_merged"
  mv "$_merged" "$HI_TRACKING_FILE"
  rm -f "$_entry"

  echo "Raw clinical content for testing." > "$HI_L1_ROOT/$l1_name.md"
}

make_skill_with_l2() {
  local skill="$1"
  make_skill_with_l1 "$skill"
  local skill_dir="$TOPICS_DIR/$skill"
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
    yq eval -i "(.topics[] | select(.name == \"$skill\") | .artifacts.l2) += [{\"name\": \"$name\", \"created_at\": \"2026-04-03T00:00:00Z\", \"derived_from\": [\"ada-guidelines\"]}]" \
      "$HI_TRACKING_FILE"
  done
}

# ── Derive mode ───────────────────────────────────────────────────────────────

@test "hi promote derive: creates L2 artifact file" {
  make_skill_with_l1 my-skill
  run "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria
  [ "$status" -eq 0 ]
  [ -f "$TOPICS_DIR/my-skill/l2/criteria.yaml" ]
}

@test "hi promote derive: updates tracking.yaml l2 list" {
  make_skill_with_l1 my-skill
  "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria
  local count
  count=$(yq eval '.topics[] | select(.name == "my-skill") | .artifacts.l2 | length' "$HI_TRACKING_FILE")
  [ "$count" -eq 1 ]
}

@test "hi promote derive: records l2_derived event in tracking" {
  make_skill_with_l1 my-skill
  "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria
  local event_type
  event_type=$(yq eval '.topics[] | select(.name == "my-skill") | .events[-1].type' "$HI_TRACKING_FILE")
  [ "$event_type" = "l2_derived" ]
}

@test "hi promote derive: --count creates N artifacts" {
  make_skill_with_l1 my-skill
  "$HI_PROMOTE" derive my-skill --source ada-guidelines --name risk --count 3
  [ -f "$TOPICS_DIR/my-skill/l2/risk-1.yaml" ]
  [ -f "$TOPICS_DIR/my-skill/l2/risk-2.yaml" ]
  [ -f "$TOPICS_DIR/my-skill/l2/risk-3.yaml" ]
}

@test "hi promote derive: --dry-run does not create file" {
  make_skill_with_l1 my-skill
  run "$HI_PROMOTE" derive my-skill --source ada-guidelines --name criteria --dry-run
  [ "$status" -eq 0 ]
  [ ! -f "$TOPICS_DIR/my-skill/l2/criteria.yaml" ]
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
  [ -f "$TOPICS_DIR/my-skill/l3/computable.yaml" ]
}

@test "hi promote combine: updates tracking.yaml l3 list" {
  make_skill_with_l2 my-skill
  "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable
  local count
  count=$(yq eval '.topics[] | select(.name == "my-skill") | .artifacts.l3 | length' "$HI_TRACKING_FILE")
  [ "$count" -eq 1 ]
}

@test "hi promote combine: records l3_converged event" {
  make_skill_with_l2 my-skill
  "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable
  local event_type
  event_type=$(yq eval '.topics[] | select(.name == "my-skill") | .events[-1].type' "$HI_TRACKING_FILE")
  [ "$event_type" = "l3_converged" ]
}

@test "hi promote combine: converged_from recorded in tracking" {
  make_skill_with_l2 my-skill
  "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable
  local count
  count=$(yq eval '.topics[] | select(.name == "my-skill") | .artifacts.l3[0].converged_from | length' "$HI_TRACKING_FILE")
  [ "$count" -eq 2 ]
}

@test "hi promote combine: --dry-run does not create file" {
  make_skill_with_l2 my-skill
  run "$HI_PROMOTE" combine my-skill --sources l2-artifact-a,l2-artifact-b --name computable --dry-run
  [ "$status" -eq 0 ]
  [ ! -f "$TOPICS_DIR/my-skill/l3/computable.yaml" ]
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
