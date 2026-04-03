#!/usr/bin/env bats
# tests/unit/status.bats — Unit tests for hi-status and hi-list commands

load '../test_helper'

setup() {
  setup_skills_dir
  export HI_SKILLS_ROOT="$SKILLS_DIR"
  export HI_REPO_ROOT="$REPO_ROOT"
  HI_STATUS="$REPO_ROOT/bin/hi-status"
  HI_LIST="$REPO_ROOT/bin/hi-list"
}

make_skill() {
  local skill="$1" stage="${2:-initialized}"
  local skill_dir="$SKILLS_DIR/$skill"
  mkdir -p "$skill_dir/l1" "$skill_dir/l2" "$skill_dir/l3" "$skill_dir/fixtures/results"

  local l1_yaml="[]" l2_yaml="[]" l3_yaml="[]"
  if [[ "$stage" == "l1-discovery" || "$stage" == "l2-semi-structured" || "$stage" == "l3-computable" ]]; then
    l1_yaml='[{name: discovery-1, created_at: "2026-04-03T00:00:00Z"}]'
    echo "Raw content" > "$skill_dir/l1/discovery-1.md"
  fi
  if [[ "$stage" == "l2-semi-structured" || "$stage" == "l3-computable" ]]; then
    l2_yaml='[{name: criteria-1, created_at: "2026-04-03T00:00:00Z", derived_from: [discovery-1]}]'
  fi
  if [[ "$stage" == "l3-computable" ]]; then
    l3_yaml='[{name: computable-1, created_at: "2026-04-03T00:00:00Z", converged_from: [criteria-1]}]'
  fi

  cat > "$skill_dir/tracking.yaml" <<YAML
schema_version: "1.0"
skill:
  name: $skill
  title: "Test Skill"
  description: "A test skill"
  author: "Test Author"
  created_at: "2026-04-03T00:00:00Z"
artifacts:
  l1: $l1_yaml
  l2: $l2_yaml
  l3: $l3_yaml
events:
  - timestamp: "2026-04-03T00:00:00Z"
    type: created
    description: scaffolded
YAML
}

# ── hi-status tests ───────────────────────────────────────────────────────────

@test "hi status: exits 0 for valid skill" {
  make_skill my-skill
  run "$HI_STATUS" my-skill
  [ "$status" -eq 0 ]
}

@test "hi status: shows skill name" {
  make_skill my-skill
  run "$HI_STATUS" my-skill
  [[ "$output" == *"my-skill"* ]]
}

@test "hi status: shows stage initialized when no artifacts" {
  make_skill my-skill initialized
  run "$HI_STATUS" my-skill
  [[ "$output" == *"initialized"* ]]
}

@test "hi status: shows stage l1-discovery after L1" {
  make_skill my-skill l1-discovery
  run "$HI_STATUS" my-skill
  [[ "$output" == *"l1-discovery"* ]]
}

@test "hi status: shows stage l2-semi-structured after L2" {
  make_skill my-skill l2-semi-structured
  run "$HI_STATUS" my-skill
  [[ "$output" == *"l2-semi-structured"* ]]
}

@test "hi status: shows stage l3-computable after L3" {
  make_skill my-skill l3-computable
  run "$HI_STATUS" my-skill
  [[ "$output" == *"l3-computable"* ]]
}

@test "hi status: --json outputs valid JSON" {
  make_skill my-skill l2-semi-structured
  run "$HI_STATUS" my-skill --json
  [ "$status" -eq 0 ]
  echo "$output" | jq . > /dev/null
}

@test "hi status: --json includes artifact counts" {
  make_skill my-skill l2-semi-structured
  run "$HI_STATUS" my-skill --json
  local l2
  l2=$(echo "$output" | jq '.artifacts.l2')
  [ "$l2" = "1" ]
}

@test "hi status: exits 2 for unknown skill" {
  run "$HI_STATUS" ghost-skill
  [ "$status" -eq 2 ]
}

@test "hi status: --help exits 0" {
  run "$HI_STATUS" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}

# ── hi-list tests ─────────────────────────────────────────────────────────────

@test "hi list: exits 0 with no skills" {
  run "$HI_LIST"
  [ "$status" -eq 0 ]
}

@test "hi list: shows skill names" {
  make_skill alpha-skill
  make_skill beta-skill
  run "$HI_LIST"
  [[ "$output" == *"alpha-skill"* ]]
  [[ "$output" == *"beta-skill"* ]]
}

@test "hi list: --json outputs valid JSON array" {
  make_skill my-skill
  run "$HI_LIST" --json
  [ "$status" -eq 0 ]
  local is_array
  is_array=$(echo "$output" | jq 'type')
  [ "$is_array" = '"array"' ]
}

@test "hi list: --json includes skill name and stage" {
  make_skill my-skill l1-discovery
  run "$HI_LIST" --json
  local name stage
  name=$(echo "$output" | jq -r '.[0].name')
  stage=$(echo "$output" | jq -r '.[0].stage')
  [ "$name" = "my-skill" ]
  [ "$stage" = "l1-discovery" ]
}

@test "hi list: --stage filters by lifecycle stage" {
  make_skill alpha-skill l1-discovery
  make_skill beta-skill l2-semi-structured
  run "$HI_LIST" --stage l1-discovery
  [[ "$output" == *"alpha-skill"* ]]
  [[ "$output" != *"beta-skill"* ]]
}

@test "hi list: --stage l3-computable shows only L3 skills" {
  make_skill alpha-skill l1-discovery
  make_skill beta-skill l3-computable
  run "$HI_LIST" --stage l3-computable
  [[ "$output" != *"alpha-skill"* ]]
  [[ "$output" == *"beta-skill"* ]]
}

@test "hi list: --help exits 0" {
  run "$HI_LIST" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]]
}
