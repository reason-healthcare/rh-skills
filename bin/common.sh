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

# ── Skill resolution ──────────────────────────────────────────────────────────

# Resolve the skills root directory (repo root / skills/)
# Respects HI_SKILLS_ROOT env var for test overrides
hi_skills_root() {
  if [[ -n "${HI_SKILLS_ROOT:-}" ]]; then
    echo "$HI_SKILLS_ROOT"
    return
  fi
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  echo "$(dirname "$script_dir")/skills"
}

# Validate a skill exists; exit 2 if not (usage error — wrong name given)
hi_require_skill() {
  local skill_name="$1"
  local skills_root
  skills_root="$(hi_skills_root)"
  if [[ ! -d "$skills_root/$skill_name" ]]; then
    hi_log_error "Skill '$skill_name' not found in $skills_root"
    exit 2
  fi
}

# Return full path to a skill directory
hi_skill_dir() {
  local skill_name="$1"
  local skills_root
  skills_root="$(hi_skills_root)"
  echo "$skills_root/$skill_name"
}

# ── Name validation ───────────────────────────────────────────────────────────

# Validate skill name is kebab-case (lowercase letters, digits, hyphens only)
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

# Append an event to tracking.yaml events list
# Usage: hi_tracking_append_event <tracking_file> <type> <description> [details_yaml]
hi_tracking_append_event() {
  local tracking_file="$1"
  local event_type="$2"
  local description="$3"
  local timestamp
  timestamp="$(hi_timestamp)"

  # Build the event block and append via yq
  yq eval -i ".events += [{\"timestamp\": \"$timestamp\", \"type\": \"$event_type\", \"description\": \"$description\"}]" \
    "$tracking_file" 2>/dev/null
}

# ── Schema / templates root ───────────────────────────────────────────────────

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
