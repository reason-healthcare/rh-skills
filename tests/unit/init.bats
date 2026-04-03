#!/usr/bin/env bats
# tests/unit/init.bats — Unit tests for hi-init command

load '../test_helper'

setup() {
  setup_topics_dir
  export HI_TOPICS_ROOT="$TOPICS_DIR"
  export HI_REPO_ROOT="$REPO_ROOT"
  HI_INIT="$REPO_ROOT/bin/hi-init"
}

# ── Basic scaffolding ─────────────────────────────────────────────────────────

@test "hi init: creates skill directory structure" {
  run "$HI_INIT" test-skill
  [ "$status" -eq 0 ]
  [ -d "$TOPICS_DIR/test-skill" ]
  [ -d "$TOPICS_DIR/test-skill/l2" ]
  [ -d "$TOPICS_DIR/test-skill/l3" ]
  [ -d "$TOPICS_DIR/test-skill/fixtures" ]
  [ -d "$HI_L1_ROOT" ]
}

@test "hi init: creates tracking.yaml" {
  run "$HI_INIT" test-skill
  [ "$status" -eq 0 ]
  [ -f "$HI_TRACKING_FILE" ]
}

@test "hi init: tracking.yaml has correct schema_version" {
  "$HI_INIT" test-skill
  local val
  val=$(yq eval '.schema_version' "$HI_TRACKING_FILE")
  [ "$val" = "1.0" ]
}

@test "hi init: tracking.yaml records skill name" {
  "$HI_INIT" my-skill
  local val
  val=$(yq eval '.topics[] | select(.name == "my-skill") | .name' "$HI_TRACKING_FILE")
  [ "$val" = "my-skill" ]
}

@test "hi init: tracking.yaml has created event" {
  "$HI_INIT" test-skill
  local event_type
  event_type=$(yq eval '.topics[] | select(.name == "test-skill") | .events[0].type' "$HI_TRACKING_FILE")
  [ "$event_type" = "created" ]
}

@test "hi init: creates TOPIC.md" {
  run "$HI_INIT" test-skill
  [ "$status" -eq 0 ]
  [ -f "$TOPICS_DIR/test-skill/TOPIC.md" ]
}

@test "hi init: TOPIC.md contains skill name in frontmatter" {
  "$HI_INIT" test-skill
  grep -q 'name: "test-skill"' "$TOPICS_DIR/test-skill/TOPIC.md"
}

# ── Flag handling ─────────────────────────────────────────────────────────────

@test "hi init: --title sets tracking.yaml skill title" {
  "$HI_INIT" test-skill --title "My Custom Title"
  local val
  val=$(yq eval '.topics[] | select(.name == "test-skill") | .title' "$HI_TRACKING_FILE")
  [ "$val" = "My Custom Title" ]
}

@test "hi init: --description sets skill description" {
  "$HI_INIT" test-skill --description "A clinical decision support skill"
  local val
  val=$(yq eval '.topics[] | select(.name == "test-skill") | .description' "$HI_TRACKING_FILE")
  [ "$val" = "A clinical decision support skill" ]
}

@test "hi init: --author sets skill author" {
  "$HI_INIT" test-skill --author "Clinical Informatics Team"
  local val
  val=$(yq eval '.topics[] | select(.name == "test-skill") | .author' "$HI_TRACKING_FILE")
  [ "$val" = "Clinical Informatics Team" ]
}

@test "hi init: default title derived from kebab name" {
  "$HI_INIT" diabetes-screening
  local val
  val=$(yq eval '.topics[] | select(.name == "diabetes-screening") | .title' "$HI_TRACKING_FILE")
  [ "$val" = "Diabetes Screening" ]
}

# ── Error handling ────────────────────────────────────────────────────────────

@test "hi init: fails with exit 1 if skill already exists" {
  "$HI_INIT" test-skill
  run "$HI_INIT" test-skill
  [ "$status" -eq 1 ]
}

@test "hi init: fails with exit 2 for invalid name (uppercase)" {
  run "$HI_INIT" MySkill
  [ "$status" -eq 2 ]
}

@test "hi init: fails with exit 2 for invalid name (spaces)" {
  run "$HI_INIT" "my skill"
  [ "$status" -eq 2 ]
}

@test "hi init: fails with exit 2 for unknown flag" {
  run "$HI_INIT" test-skill --unknown-flag
  [ "$status" -eq 2 ]
}

# ── Help / usage ──────────────────────────────────────────────────────────────

@test "hi init: --help exits 0 and prints usage" {
  run "$HI_INIT" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "hi init: no args exits 0 and prints usage" {
  run "$HI_INIT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}
