#!/usr/bin/env bash
# tests/test_helper.bash — Shared setup for bats test suites

# Resolve repo root relative to this file
TEST_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$TEST_HELPER_DIR")"
BIN_DIR="$REPO_ROOT/bin"

# Source common.sh for shared helpers (hi_sha256, etc.)
# shellcheck source=../bin/common.sh
source "$BIN_DIR/common.sh"

# Set TOPICS_DIR to a unique per-test temp location for isolation
# Also sets HI_TRACKING_FILE to the repo-level tracking.yaml in that temp location
# and HI_L1_ROOT to the repo-level l1/ directory in that temp location
setup_topics_dir() {
  local base_tmp="${BATS_TEST_TMPDIR:-$BATS_TMPDIR/test-$$-$RANDOM}"
  mkdir -p "$base_tmp"
  export TOPICS_DIR="$base_tmp/topics"
  mkdir -p "$TOPICS_DIR"
  export HI_TRACKING_FILE="$base_tmp/tracking.yaml"
  export HI_L1_ROOT="$base_tmp/l1"
  mkdir -p "$HI_L1_ROOT"
}

# Create a minimal initialized topic for use in tests
# Usage: create_test_topic <topic-name>
create_test_topic() {
  local name="$1"
  local topic_dir="$TOPICS_DIR/$name"
  mkdir -p "$topic_dir/l2" "$topic_dir/l3" "$topic_dir/fixtures/results"

  # Write topic entry YAML to temp file in TOPICS_DIR
  local _entry="$TOPICS_DIR/._${name}_entry.yaml"
  cat > "$_entry" <<YAML
name: $name
title: Test Skill
description: A test skill
author: test-user
created_at: "2026-04-03T00:00:00Z"
artifacts:
  l2: []
  l3: []
events:
  - timestamp: "2026-04-03T00:00:00Z"
    type: created
    description: Skill initialized
YAML

  if [[ ! -f "$HI_TRACKING_FILE" ]]; then
    printf 'schema_version: "1.0"\nl1: []\ntopics: []\nevents: []\n' > "$HI_TRACKING_FILE"
  fi

  local _merged="$TOPICS_DIR/._${name}_merged.yaml"
  yq eval-all 'select(fileIndex==0).topics += [select(fileIndex==1)] | select(fileIndex==0)' \
    "$HI_TRACKING_FILE" "$_entry" > "$_merged"
  mv "$_merged" "$HI_TRACKING_FILE"
  rm -f "$_entry"

  cat > "$topic_dir/SKILL.md" <<MD
---
name: "$name"
description: "Test skill"
---

## Instructions
Test skill instructions.
MD
}

# Add an L1 artifact to the repo-level l1/ directory and root tracking.yaml
add_l1_artifact() {
  local topic_name="$1"
  local artifact_name="$2"
  local content="${3:-Raw discovery content for testing.}"
  local artifact_file="$HI_L1_ROOT/$artifact_name.md"
  echo "$content" > "$artifact_file"
  local checksum
  checksum=$(hi_sha256 "$artifact_file")
  yq eval -i ".l1 += [{\"name\": \"$artifact_name\", \"file\": \"l1/$artifact_name.md\", \"created_at\": \"2026-04-03T00:00:00Z\", \"checksum\": \"$checksum\"}]" \
    "$HI_TRACKING_FILE"
  yq eval -i ".events += [{\"timestamp\": \"2026-04-03T00:00:00Z\", \"type\": \"l1_added\", \"description\": \"Added $artifact_name\"}]" \
    "$HI_TRACKING_FILE"
}

# Add an L2 artifact to an existing test topic
add_l2_artifact() {
  local topic_name="$1"
  local artifact_name="$2"
  local artifact_file="$TOPICS_DIR/$topic_name/l2/$artifact_name.yaml"
  cat > "$artifact_file" <<YAML
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
  local checksum
  checksum=$(hi_sha256 "$artifact_file")
  yq eval -i "(.topics[] | select(.name == \"$topic_name\") | .artifacts.l2) += [{\"name\": \"$artifact_name\", \"created_at\": \"2026-04-03T00:00:00Z\", \"checksum\": \"$checksum\", \"derived_from\": [\"discovery\"]}]" \
    "$HI_TRACKING_FILE"
}

# Override hi_topics_root for tests via HI_TOPICS_ROOT env var
export HI_TOPICS_ROOT=""  # set per-test via setup_topics_dir
export HI_TRACKING_FILE="" # set per-test via setup_topics_dir
export HI_L1_ROOT=""       # set per-test via setup_topics_dir

# Make bin/ scripts available on PATH
export PATH="$BIN_DIR:$PATH"
