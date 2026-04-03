#!/usr/bin/env bats
# tests/unit/test-cmd.bats — Unit tests for hi-test command

load '../test_helper'

setup() {
  setup_skills_dir
  export HI_SKILLS_ROOT="$SKILLS_DIR"
  export HI_REPO_ROOT="$REPO_ROOT"
  export LLM_PROVIDER=stub
  HI_TEST="$REPO_ROOT/bin/hi-test"
}

make_skill_with_fixture() {
  local skill="$1" fixture="${2:-my-fixture}"
  local skill_dir="$SKILLS_DIR/$skill"
  mkdir -p "$skill_dir/fixtures/results" "$skill_dir/l1" "$skill_dir/l2" "$skill_dir/l3"
  cat > "$skill_dir/tracking.yaml" <<YAML
schema_version: "1.0"
skill:
  name: $skill
  title: Test Skill
  author: test
  created_at: "2026-04-03T00:00:00Z"
artifacts:
  l1: []
  l2: []
  l3: []
events: []
YAML
  # Default stub response matches this expected value (stub uses "contains" mode)
  cat > "$skill_dir/fixtures/$fixture.yaml" <<YAML
system_prompt: "You are a clinical assistant."
user_prompt: "What is HbA1c used for?"
expected_response: "Stub"
compare_mode: contains
YAML
}

# ── Basic functionality ───────────────────────────────────────────────────────

@test "hi test: runs all fixtures and exits 0 when all pass" {
  make_skill_with_fixture my-skill
  run "$HI_TEST" my-skill --mode contains
  [ "$status" -eq 0 ]
  [[ "$output" == *"passed"* ]]
}

@test "hi test: writes a results JSON file" {
  make_skill_with_fixture my-skill
  "$HI_TEST" my-skill --mode contains
  local count
  count=$(find "$SKILLS_DIR/my-skill/fixtures/results" -name '*.json' | wc -l | tr -d ' ')
  [ "$count" -ge 1 ]
}

@test "hi test: result JSON has correct structure" {
  make_skill_with_fixture my-skill
  "$HI_TEST" my-skill --mode contains
  local result_file
  result_file=$(find "$SKILLS_DIR/my-skill/fixtures/results" -name '*.json' | head -1)
  local skill_val
  skill_val=$(jq -r '.skill' "$result_file")
  [ "$skill_val" = "my-skill" ]
}

@test "hi test: result JSON summary has passed/failed/errored" {
  make_skill_with_fixture my-skill
  "$HI_TEST" my-skill --mode contains
  local result_file
  result_file=$(find "$SKILLS_DIR/my-skill/fixtures/results" -name '*.json' | head -1)
  local has_summary
  has_summary=$(jq 'has("summary")' "$result_file")
  [ "$has_summary" = "true" ]
}

@test "hi test: --fixture runs only named fixture" {
  make_skill_with_fixture my-skill fixture-a
  make_skill_with_fixture my-skill fixture-b
  run "$HI_TEST" my-skill --fixture fixture-a --mode contains
  [ "$status" -eq 0 ]
  [[ "$output" == *"passed"* ]]
}

@test "hi test: exits 1 when a fixture fails" {
  make_skill_with_fixture my-skill
  # Override stub to return something that won't contain "NOMATCH"
  export HI_STUB_RESPONSE="completely different answer"
  cat > "$SKILLS_DIR/my-skill/fixtures/my-fixture.yaml" <<YAML
system_prompt: "You are a clinical assistant."
user_prompt: "What is HbA1c?"
expected_response: "NOMATCH_STRING_XYZ"
YAML
  run "$HI_TEST" my-skill
  [ "$status" -eq 1 ]
}

@test "hi test: exits 0 with no fixtures (warns)" {
  mkdir -p "$SKILLS_DIR/my-skill/fixtures/results" "$SKILLS_DIR/my-skill/l1"
  cat > "$SKILLS_DIR/my-skill/tracking.yaml" <<YAML
schema_version: "1.0"
skill:
  name: my-skill
artifacts:
  l1: []
  l2: []
  l3: []
events: []
YAML
  run "$HI_TEST" my-skill
  [ "$status" -eq 0 ]
}

@test "hi test: exits 2 for unknown skill" {
  run "$HI_TEST" nonexistent-skill
  [ "$status" -eq 2 ]
}

@test "hi test: exits 2 for nonexistent named fixture" {
  make_skill_with_fixture my-skill
  run "$HI_TEST" my-skill --fixture no-such-fixture
  [ "$status" -eq 2 ]
}

# ── Help / usage ──────────────────────────────────────────────────────────────

@test "hi test: --help exits 0" {
  run "$HI_TEST" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "hi test: no args exits 0 and prints usage" {
  run "$HI_TEST"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}
