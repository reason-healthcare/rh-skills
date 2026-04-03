#!/usr/bin/env bash
# bin/common.sh — Shared utilities for the hi CLI
# Source this file from other bin scripts: source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# ── Logging ──────────────────────────────────────────────────────────────────

hi_log_info() {
  printf '✓ %s\n' "$*"
}

hi_log_warn() {
  printf '! [WARN] %s\n' "$*"
}

hi_log_error() {
  printf '[ERROR] %s\n' "$*" >&2
}

# ── Timestamps ────────────────────────────────────────────────────────────────

hi_timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

hi_date() {
  date -u +"%Y-%m-%d"
}

# ── Topic resolution ─────────────────────────────────────────────────────────

# Resolve the topics root directory (repo root / topics/)
# Respects HI_TOPICS_ROOT env var for test overrides
hi_topics_root() {
  if [[ -n "${HI_TOPICS_ROOT:-}" ]]; then
    echo "$HI_TOPICS_ROOT"
    return
  fi
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  echo "$(dirname "$script_dir")/topics"
}

# Validate a topic exists; exit 2 if not (usage error — wrong name given)
hi_require_topic() {
  local topic_name="$1"
  local topics_root
  topics_root="$(hi_topics_root)"
  if [[ ! -d "$topics_root/$topic_name" ]]; then
    hi_log_error "Topic '$topic_name' not found in $topics_root"
    exit 2
  fi
}

# Return full path to a topic directory
hi_topic_dir() {
  local topic_name="$1"
  local topics_root
  topics_root="$(hi_topics_root)"
  echo "$topics_root/$topic_name"
}

# ── Name validation ───────────────────────────────────────────────────────────

# Validate topic name is kebab-case (lowercase letters, digits, hyphens only)
hi_kebab_validate() {
  local name="$1"
  if [[ ! "$name" =~ ^[a-z][a-z0-9-]*$ ]]; then
    return 1
  fi
  return 0
}

# ── yq helpers ────────────────────────────────────────────────────────────────

# Safe yq field read — returns empty string instead of "null"
hi_yq_get() {
  local file="$1"
  local field="$2"
  local val
  val=$(yq eval ".$field" "$file" 2>/dev/null)
  if [[ "$val" == "null" || -z "$val" ]]; then
    echo ""
  else
    echo "$val"
  fi
}

# Append a YAML list item to a field using yq
hi_yq_append() {
  local file="$1"
  local field="$2"
  local value="$3"
  yq eval -i ".$field += [\"$value\"]" "$file" 2>/dev/null
}

# ── Tracking artifact helpers ─────────────────────────────────────────────────

# Return path to the repo-level tracking.yaml
# Respects HI_TRACKING_FILE env var for test isolation
hi_tracking_file() {
  if [[ -n "${HI_TRACKING_FILE:-}" ]]; then
    echo "$HI_TRACKING_FILE"
    return
  fi
  echo "$(hi_repo_root)/tracking.yaml"
}

# Append an event to the tracking.yaml events list.
# When topic_name is empty, appends to root .events list.
# When topic_name is non-empty, appends to the named topic's .events list.
# Usage: hi_tracking_append_event <tracking_file> <topic_name> <type> <description>
hi_tracking_append_event() {
  local tracking_file="$1"
  local topic_name="$2"
  local event_type="$3"
  local description="$4"
  local timestamp
  timestamp="$(hi_timestamp)"

  if [[ -z "$topic_name" ]]; then
    yq eval -i ".events += [{\"timestamp\": \"$timestamp\", \"type\": \"$event_type\", \"description\": \"$description\"}]" \
      "$tracking_file" 2>/dev/null
  else
    yq eval -i "(.topics[] | select(.name == \"$topic_name\") | .events) += [{\"timestamp\": \"$timestamp\", \"type\": \"$event_type\", \"description\": \"$description\"}]" \
      "$tracking_file" 2>/dev/null
  fi
}

# Convenience wrapper: append an event to the root .events list.
# Usage: hi_tracking_append_root_event <tracking_file> <type> <description>
hi_tracking_append_root_event() {
  local tracking_file="$1"
  local event_type="$2"
  local description="$3"
  hi_tracking_append_event "$tracking_file" "" "$event_type" "$description"
}

# ── Schema / templates root ───────────────────────────────────────────────────

# Return path to the repo-level l1/ directory (shared raw sources)
# Respects HI_L1_ROOT env var for test isolation
hi_l1_root() {
  if [[ -n "${HI_L1_ROOT:-}" ]]; then
    echo "$HI_L1_ROOT"
    return
  fi
  echo "$(hi_repo_root)/l1"
}

hi_repo_root() {
  if [[ -n "${HI_REPO_ROOT:-}" ]]; then
    echo "$HI_REPO_ROOT"
    return
  fi
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  dirname "$script_dir"
}

hi_schemas_dir() {
  echo "$(hi_repo_root)/schemas"
}

hi_templates_dir() {
  echo "$(hi_repo_root)/templates"
}

# ── SHA-256 portability ────────────────────────────────────────────────────────

# Compute SHA-256 hex digest of a file (portable: macOS + Linux)
# Usage: hi_sha256 <file>
hi_sha256() {
  local file="$1"
  if command -v sha256sum > /dev/null 2>&1; then
    sha256sum "$file" | cut -d' ' -f1
  else
    shasum -a 256 "$file" | cut -d' ' -f1
  fi
}

# ── Markdown front matter helpers ─────────────────────────────────────────────
# Front matter is the YAML block between the first and second '---' delimiters.

# Extract the YAML front matter block from a Markdown file (content only, no delimiters)
# Usage: hi_markdown_get_frontmatter_block <file>
# Returns: YAML text on stdout; exits 1 if file missing or no front matter found
hi_markdown_get_frontmatter_block() {
  local md_file="$1"
  if [[ ! -f "$md_file" ]]; then
    return 1
  fi
  local count
  count=$(grep -c "^---$" "$md_file" 2>/dev/null || echo 0)
  if [[ "$count" -lt 2 ]]; then
    return 1
  fi
  # Print lines between first and second '---'
  sed -n '1,/^---$/p' "$md_file" | sed '1d;$d'
}

# Read a single field from a Markdown file's YAML front matter
# Usage: hi_markdown_get_field <file> <yq-field>
# Returns: field value on stdout; empty string if missing or null
hi_markdown_get_field() {
  local md_file="$1"
  local field="$2"
  local front val
  front=$(hi_markdown_get_frontmatter_block "$md_file") || return 1
  val=$(printf '%s\n' "$front" | yq eval ".$field" - 2>/dev/null)
  if [[ "$val" == "null" || -z "$val" ]]; then
    echo ""
  else
    echo "$val"
  fi
}

# Get the prose body of a Markdown file (everything after the closing ---)
# Usage: hi_markdown_get_content <file>
# Returns: body text on stdout; exits 1 if file missing or no closing ---
hi_markdown_get_content() {
  local md_file="$1"
  if [[ ! -f "$md_file" ]]; then
    return 1
  fi
  local line
  line=$(grep -n "^---$" "$md_file" | tail -1 | cut -d: -f1)
  if [[ -z "$line" ]]; then
    return 1
  fi
  tail -n +"$((line + 1))" "$md_file"
}
