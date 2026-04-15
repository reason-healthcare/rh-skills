#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="${RH_SKILLS_REPO_ROOT:-$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)}"
CURATED_DIR="${RH_SKILLS_CURATED_DIR:-${REPO_ROOT}/skills/.curated}"
PROFILES_DIR="${RH_SKILLS_PROFILES_DIR:-${REPO_ROOT}/skills/_profiles}"
OUTPUT_ROOT="${RH_SKILLS_OUTPUT_DIR:-${REPO_ROOT}/dist}"

PLATFORM=""
BUILD_ALL=0
DRY_RUN=0
RUN_VALIDATE=0

WARNINGS=0
ERRORS=0
BUILT=0
SKIPPED=0

TMP_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  scripts/build-skills.sh --platform <name> [--dry-run] [--validate]
  scripts/build-skills.sh --all [--dry-run] [--validate]

Options:
  --platform <name>  Build a single platform profile from skills/_profiles/<name>.yaml
  --all              Build all bundled platform profiles
  --dry-run          Render and validate in a temporary staging area without writing dist/
  --validate         Run structural validation and installability checks on staged bundles
  --help             Show this help
EOF
}

log() {
  printf '%s\n' "$*"
}

warn() {
  WARNINGS=$((WARNINGS + 1))
  printf 'WARN: %s\n' "$*" >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [ -n "${TMP_ROOT}" ] && [ -d "${TMP_ROOT}" ]; then
    rm -rf "${TMP_ROOT}"
  fi
}

trap cleanup EXIT

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required tool '$1' is not installed or not on PATH."
  fi
}

relative_path() {
  python3 - "$1" "$2" <<'PY'
from pathlib import Path
import sys
base = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
print(target.relative_to(base))
PY
}

path_to_yq_expr() {
  local path="$1"
  local expr="."
  local segment
  local old_ifs="${IFS}"
  IFS='.'
  for segment in $path; do
    expr="${expr}[\"${segment}\"]"
  done
  IFS="${old_ifs}"
  printf '%s' "${expr}"
}

profile_scalar() {
  local profile="$1"
  local expr="$2"
  yq eval -r "${expr}" "${profile}"
}

profile_text() {
  local profile="$1"
  local expr="$2"
  local value
  value="$(yq eval -r "${expr}" "${profile}")"
  if [ "${value}" = "null" ]; then
    printf ''
  else
    printf '%s' "${value}"
  fi
}

profile_has_key() {
  local profile="$1"
  local expr="$2"
  [ "$(yq -r "${expr} | type" "${profile}" 2>/dev/null || printf 'null')" != "null" ]
}

load_inline_or_file_text() {
  local profile="$1"
  local prefix="$2"
  local inline_expr=".${prefix}.inline // null"
  local file_expr=".${prefix}.file // null"
  local inline_value
  local file_value
  inline_value="$(profile_text "${profile}" "${inline_expr}")"
  file_value="$(profile_text "${profile}" "${file_expr}")"

  if [ -n "${inline_value}" ] && [ -n "${file_value}" ]; then
    fail "Profile '$(profile_scalar "${profile}" '.platform // "unknown"')' defines both ${prefix}.inline and ${prefix}.file."
  fi

  if [ -n "${file_value}" ]; then
    local resolved="${REPO_ROOT}/${file_value}"
    [ -f "${resolved}" ] || fail "Profile '$(profile_scalar "${profile}" '.platform // "unknown"')' references missing ${prefix} file: ${file_value}"
    cat "${resolved}"
    return 0
  fi

  printf '%s' "${inline_value}"
}

extract_markdown_parts() {
  local input_file="$1"
  local frontmatter_file="$2"
  local body_file="$3"
  python3 - "$input_file" "$frontmatter_file" "$body_file" <<'PY'
from pathlib import Path
import sys

input_path = Path(sys.argv[1])
frontmatter_path = Path(sys.argv[2])
body_path = Path(sys.argv[3])
text = input_path.read_text()

if text.startswith("---\n"):
    parts = text.split("---\n", 2)
    if len(parts) >= 3:
        frontmatter_path.write_text(parts[1])
        body_path.write_text(parts[2].lstrip("\n"))
        raise SystemExit(0)

frontmatter_path.write_text("")
body_path.write_text(text)
PY
}

remove_sections() {
  local input_file="$1"
  local output_file="$2"
  local omit_file="$3"
  python3 - "$input_file" "$output_file" "$omit_file" <<'PY'
from pathlib import Path
import sys

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
omit_path = Path(sys.argv[3])
omit_titles = {
    line.strip() for line in omit_path.read_text().splitlines() if line.strip()
}

lines = input_path.read_text().splitlines()
result = []
skip = False
for line in lines:
    if line.startswith("## "):
        title = line[3:].strip()
        skip = title in omit_titles
        if skip:
            continue
    if not skip:
        result.append(line)

output_path.write_text("\n".join(result).rstrip() + "\n")
PY
}

assemble_skill_markdown() {
  local frontmatter_file="$1"
  local body_file="$2"
  local preamble_file="$3"
  local suffix_file="$4"
  local output_file="$5"
  local frontmatter_policy="$6"

  : > "${output_file}"

  if [ "${frontmatter_policy}" != "strip" ] && [ -s "${frontmatter_file}" ]; then
    printf '%s\n' '---' >> "${output_file}"
    cat "${frontmatter_file}" >> "${output_file}"
    if [ "$(tail -c 1 "${frontmatter_file}" 2>/dev/null || printf '')" != "" ]; then
      printf '\n' >> "${output_file}"
    fi
    printf '%s\n\n' '---' >> "${output_file}"
  fi

  if [ -s "${preamble_file}" ]; then
    cat "${preamble_file}" >> "${output_file}"
    printf '\n\n' >> "${output_file}"
  fi

  cat "${body_file}" >> "${output_file}"

  if [ -s "${suffix_file}" ]; then
    printf '\n\n' >> "${output_file}"
    cat "${suffix_file}" >> "${output_file}"
  fi
}

transform_frontmatter() {
  local source_frontmatter="$1"
  local profile="$2"
  local output_frontmatter="$3"
  local frontmatter_policy="$4"

  if [ "${frontmatter_policy}" = "strip" ]; then
    : > "${output_frontmatter}"
    return 0
  fi

  if [ ! -s "${source_frontmatter}" ]; then
    fail "Source skill is missing YAML frontmatter required by profile '$(profile_scalar "${profile}" '.platform // "unknown"')'."
  fi

  if [ "${frontmatter_policy}" = "keep" ]; then
    cp "${source_frontmatter}" "${output_frontmatter}"
    return 0
  fi

  if [ "${frontmatter_policy}" != "transform" ]; then
    fail "Unsupported frontmatter policy '${frontmatter_policy}' in profile '$(profile_scalar "${profile}" '.platform // "unknown"')'."
  fi

  local expr='.'
  local field_count
  field_count="$(yq -r '(.field_map // {}) | keys | length' "${profile}")"

  if [ "${field_count}" = "0" ]; then
    cp "${source_frontmatter}" "${output_frontmatter}"
    return 0
  fi

  local from_path
  while IFS= read -r from_path; do
    [ -n "${from_path}" ] || continue
    local to_path
    to_path="$(yq -r ".field_map.\"${from_path}\"" "${profile}")"
    [ -n "${to_path}" ] || fail "Profile '$(profile_scalar "${profile}" '.platform // "unknown"')' has an empty field_map target for '${from_path}'."

    local from_expr
    local to_expr
    from_expr="$(path_to_yq_expr "${from_path}")"
    to_expr="$(path_to_yq_expr "${to_path}")"

    local current_value
    current_value="$(yq -r "${from_expr} // \"__RH_SKILLS_MISSING__\"" "${source_frontmatter}")"
    [ "${current_value}" != "__RH_SKILLS_MISSING__" ] || fail "Profile '$(profile_scalar "${profile}" '.platform // "unknown"')' maps missing frontmatter field '${from_path}'."

    expr="${expr} | ${to_expr} = ${from_expr} | del(${from_expr})"
  done <<EOF
$(yq -r '(.field_map // {}) | keys | .[]' "${profile}")
EOF

  yq eval "${expr}" "${source_frontmatter}" > "${output_frontmatter}"
}

check_for_placeholders() {
  local skill_dir="$1"
  local skill_name="$2"

  if grep -R -n -E '<skill-name>|<Author Name|<One sentence|<One-line>|Modes: plan · implement · verify\.$' "${skill_dir}" >/dev/null 2>&1; then
    fail "Canonical skill '${skill_name}' contains unresolved placeholder text."
  fi
}

profile_root_path() {
  local profile="$1"
  local bundle_mode="$2"
  local pattern="$3"

  if [ "${bundle_mode}" = "aggregate" ]; then
    printf '%s' "${pattern}"
    return 0
  fi

  local root="${pattern%%\{skill_name\}*}"
  root="${root%/}"
  printf '%s' "${root}"
}

render_path() {
  local pattern="$1"
  local platform="$2"
  local skill_name="$3"
  local rendered="${pattern//\{platform\}/${platform}}"
  rendered="${rendered//\{skill_name\}/${skill_name}}"
  printf '%s' "${rendered}"
}

copy_companion_files() {
  local source_skill_dir="$1"
  local destination_dir="$2"
  local relative_file

  while IFS= read -r relative_file; do
    [ -n "${relative_file}" ] || continue
    mkdir -p "${destination_dir}/$(dirname "${relative_file}")"
    cp "${source_skill_dir}/${relative_file}" "${destination_dir}/${relative_file}"
  done <<EOF
$(cd "${source_skill_dir}" && find . -type f ! -path './SKILL.md' ! -path './.DS_Store' | LC_ALL=C sort | sed 's#^\./##')
EOF
}

validate_file_contains() {
  local file_path="$1"
  local needle_file="$2"
  python3 - "$file_path" "$needle_file" <<'PY'
from pathlib import Path
import sys
haystack = Path(sys.argv[1]).read_text()
needle = Path(sys.argv[2]).read_text()
if needle and needle not in haystack:
    raise SystemExit(1)
PY
}

validate_file_suffix() {
  local file_path="$1"
  local suffix_file="$2"
  python3 - "$file_path" "$suffix_file" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text().rstrip()
suffix = Path(sys.argv[2]).read_text().rstrip()
if suffix and not text.endswith(suffix):
    raise SystemExit(1)
PY
}

run_rule() {
  local scope="$1"
  local rule="$2"
  local platform="$3"
  local skill_name="$4"
  local bundle_mode="$5"
  local bundle_path="$6"
  local preamble_file="$7"
  local suffix_file="$8"
  local entry_file

  if [ "${bundle_mode}" = "aggregate" ]; then
    entry_file="${bundle_path}"
  else
    entry_file="${bundle_path}/SKILL.md"
  fi

  case "${rule}" in
    skill_entry_exists)
      [ -f "${entry_file}" ] || {
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s missing %s\n' "${scope}" "${platform}" "${skill_name}" "${rule}" "$(relative_path "${REPO_ROOT}" "${entry_file}")" >&2
        return 1
      }
      ;;
    frontmatter_present)
      python3 - "${entry_file}" <<'PY' || {
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
if not text.startswith("---\n"):
    raise SystemExit(1)
PY
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s expected frontmatter\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    frontmatter_absent)
      python3 - "${entry_file}" <<'PY' || {
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
if text.startswith("---\n"):
    raise SystemExit(1)
PY
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s expected frontmatter to be stripped\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    preamble_present)
      validate_file_contains "${entry_file}" "${preamble_file}" || {
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s expected configured preamble\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    suffix_present)
      validate_file_suffix "${entry_file}" "${suffix_file}" || {
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s expected configured suffix\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    companion_files_present)
      [ -f "${bundle_path}/reference.md" ] && [ -f "${bundle_path}/examples/plan.md" ] && [ -f "${bundle_path}/examples/output.md" ] || {
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s expected companion files\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    bundle_directory_exists)
      [ -d "${bundle_path}" ] || {
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s missing bundle directory\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    file_nonempty)
      [ -s "${entry_file}" ] || {
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s expected non-empty output\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    aggregate_contains_skills)
      python3 - "${entry_file}" "${skill_name}" <<'PY' || {
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
skill = sys.argv[2]
needle = f"## {skill}\n"
if needle not in text:
    raise SystemExit(1)
PY
        ERRORS=$((ERRORS + 1))
        printf 'FAIL [%s] %s/%s rule=%s expected aggregate entry\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
        return 1
      }
      ;;
    *)
      ERRORS=$((ERRORS + 1))
      printf 'FAIL [%s] %s/%s rule=%s unsupported validation rule\n' "${scope}" "${platform}" "${skill_name}" "${rule}" >&2
      return 1
      ;;
  esac

  printf 'PASS [%s] %s/%s rule=%s\n' "${scope}" "${platform}" "${skill_name}" "${rule}"
}

validate_profile() {
  local profile="$1"
  local platform
  local bundle_mode
  local frontmatter_policy
  local output_path_pattern
  local key

  platform="$(profile_scalar "${profile}" '.platform // ""')"
  [ -n "${platform}" ] || fail "Profile file '$(basename "${profile}")' is missing required field 'platform'."

  bundle_mode="$(profile_scalar "${profile}" '.bundle_mode // ""')"
  [ -n "${bundle_mode}" ] || fail "Profile '${platform}' is missing required field 'bundle_mode'."

  output_path_pattern="$(profile_scalar "${profile}" '.output_path_pattern // ""')"
  [ -n "${output_path_pattern}" ] || fail "Profile '${platform}' is missing required field 'output_path_pattern'."

  frontmatter_policy="$(profile_scalar "${profile}" '.frontmatter_policy // ""')"
  [ -n "${frontmatter_policy}" ] || fail "Profile '${platform}' is missing required field 'frontmatter_policy'."

  if [ "$(yq -r '(.validation_rules // []) | length' "${profile}")" = "0" ]; then
    fail "Profile '${platform}' must define at least one validation rule."
  fi

  case "${bundle_mode}" in
    per_skill|aggregate) ;;
    *) fail "Profile '${platform}' has unsupported bundle_mode '${bundle_mode}'." ;;
  esac

  case "${frontmatter_policy}" in
    keep|strip|transform) ;;
    *) fail "Profile '${platform}' has unsupported frontmatter_policy '${frontmatter_policy}'." ;;
  esac

  if [ "${bundle_mode}" = "per_skill" ] && [[ "${output_path_pattern}" != *"{skill_name}"* ]]; then
    fail "Profile '${platform}' must include {skill_name} in output_path_pattern for per_skill bundles."
  fi

  if [ "${bundle_mode}" = "aggregate" ] && [[ "${output_path_pattern}" == *"{skill_name}"* ]]; then
    fail "Profile '${platform}' cannot include {skill_name} in output_path_pattern for aggregate bundles."
  fi

  while IFS= read -r key; do
    [ -n "${key}" ] || continue
    case "${key}" in
      platform|bundled|bundle_mode|output_path_pattern|frontmatter_policy|preamble|suffix|omit_sections|field_map|validation_rules|installability_checks)
        ;;
      *)
        warn "Profile '${platform}' ignores unsupported field '${key}'."
        ;;
    esac
  done <<EOF
$(yq -r 'keys | .[]' "${profile}")
EOF

  load_inline_or_file_text "${profile}" "preamble" >/dev/null
  load_inline_or_file_text "${profile}" "suffix" >/dev/null
}

collect_selected_profiles() {
  local selected_file="$1"
  : > "${selected_file}"

  if [ "${BUILD_ALL}" -eq 1 ]; then
    local profile
    for profile in "${PROFILES_DIR}"/*.yaml; do
      [ -e "${profile}" ] || continue
      if [ "$(profile_scalar "${profile}" '.bundled // false')" = "true" ]; then
        printf '%s\n' "${profile}" >> "${selected_file}"
      fi
    done
  else
    local requested="${PROFILES_DIR}/${PLATFORM}.yaml"
    [ -f "${requested}" ] || fail "No profile found for platform '${PLATFORM}' at $(relative_path "${REPO_ROOT}" "${requested}")."
    printf '%s\n' "${requested}" >> "${selected_file}"
  fi

  if [ ! -s "${selected_file}" ]; then
    fail "No platform profiles were selected."
  fi
}

collect_skill_dirs() {
  local skills_file="$1"
  : > "${skills_file}"
  if [ ! -d "${CURATED_DIR}" ]; then
    fail "Curated skill directory not found at $(relative_path "${REPO_ROOT}" "${CURATED_DIR}")."
  fi

  while IFS= read -r skill_file; do
    printf '%s\n' "$(dirname "${skill_file}")" >> "${skills_file}"
  done <<EOF
$(find "${CURATED_DIR}" -mindepth 2 -maxdepth 2 -type f -name 'SKILL.md' | LC_ALL=C sort)
EOF

  if [ ! -s "${skills_file}" ]; then
    fail "No buildable curated skills found under $(relative_path "${REPO_ROOT}" "${CURATED_DIR}")."
  fi
}

detect_conflicting_outputs() {
  local profiles_file="$1"
  local skills_file="$2"
  local paths_file="$3"
  : > "${paths_file}"

  local profile
  while IFS= read -r profile; do
    [ -n "${profile}" ] || continue
    local platform
    local bundle_mode
    local pattern
    platform="$(profile_scalar "${profile}" '.platform')"
    bundle_mode="$(profile_scalar "${profile}" '.bundle_mode')"
    pattern="$(profile_scalar "${profile}" '.output_path_pattern')"

    if [ "${bundle_mode}" = "aggregate" ]; then
      printf '%s\t%s\t%s\n' "$(render_path "${pattern}" "${platform}" "__aggregate__")" "${platform}" "__aggregate__" >> "${paths_file}"
      continue
    fi

    local skill_dir
    while IFS= read -r skill_dir; do
      [ -n "${skill_dir}" ] || continue
      local skill_name
      skill_name="$(basename "${skill_dir}")"
      printf '%s\t%s\t%s\n' "$(render_path "${pattern}" "${platform}" "${skill_name}")" "${platform}" "${skill_name}" >> "${paths_file}"
    done < "${skills_file}"
  done < "${profiles_file}"

  local duplicate
  duplicate="$(cut -f1 "${paths_file}" | LC_ALL=C sort | uniq -d | head -n 1 || true)"
  if [ -n "${duplicate}" ]; then
    fail "Conflicting output destination detected: ${duplicate}"
  fi
}

build_per_skill_bundle() {
  local profile="$1"
  local skill_dir="$2"
  local destination_dir="$3"
  local frontmatter_policy="$4"

  local work_dir="${TMP_ROOT}/work/$(basename "${profile}")-$(basename "${skill_dir}")"
  mkdir -p "${work_dir}"

  local source_frontmatter="${work_dir}/source-frontmatter.yaml"
  local source_body="${work_dir}/source-body.md"
  local transformed_frontmatter="${work_dir}/frontmatter.yaml"
  local transformed_body="${work_dir}/body.md"
  local preamble_file="${work_dir}/preamble.md"
  local suffix_file="${work_dir}/suffix.md"

  extract_markdown_parts "${skill_dir}/SKILL.md" "${source_frontmatter}" "${source_body}"
  transform_frontmatter "${source_frontmatter}" "${profile}" "${transformed_frontmatter}" "${frontmatter_policy}"

  : > "${work_dir}/omit-sections.txt"
  yq eval -r '.omit_sections[]?' "${profile}" > "${work_dir}/omit-sections.txt"
  remove_sections "${source_body}" "${transformed_body}" "${work_dir}/omit-sections.txt"

  load_inline_or_file_text "${profile}" "preamble" > "${preamble_file}"
  load_inline_or_file_text "${profile}" "suffix" > "${suffix_file}"

  mkdir -p "${destination_dir}"
  copy_companion_files "${skill_dir}" "${destination_dir}"
  assemble_skill_markdown "${transformed_frontmatter}" "${transformed_body}" "${preamble_file}" "${suffix_file}" "${destination_dir}/SKILL.md" "${frontmatter_policy}"

  printf '%s\t%s\n' "${preamble_file}" "${suffix_file}"
}

build_aggregate_bundle() {
  local profile="$1"
  local skills_file="$2"
  local output_file="$3"
  local frontmatter_policy="$4"
  local work_dir="${TMP_ROOT}/work/$(basename "${profile}")-aggregate"
  mkdir -p "${work_dir}"

  local aggregate_preamble="${work_dir}/aggregate-preamble.md"
  local aggregate_suffix="${work_dir}/aggregate-suffix.md"
  load_inline_or_file_text "${profile}" "preamble" > "${aggregate_preamble}"
  load_inline_or_file_text "${profile}" "suffix" > "${aggregate_suffix}"

  mkdir -p "$(dirname "${output_file}")"
  : > "${output_file}"

  if [ -s "${aggregate_preamble}" ]; then
    cat "${aggregate_preamble}" >> "${output_file}"
    printf '\n\n' >> "${output_file}"
  fi

  local skill_dir
  while IFS= read -r skill_dir; do
    [ -n "${skill_dir}" ] || continue
    local skill_name
    skill_name="$(basename "${skill_dir}")"
    local source_frontmatter="${work_dir}/${skill_name}-frontmatter.yaml"
    local source_body="${work_dir}/${skill_name}-body.md"
    local transformed_frontmatter="${work_dir}/${skill_name}-transformed-frontmatter.yaml"
    local transformed_body="${work_dir}/${skill_name}-transformed-body.md"
    local rendered_file="${work_dir}/${skill_name}-rendered.md"
    local empty_file="${work_dir}/${skill_name}-empty.md"

    extract_markdown_parts "${skill_dir}/SKILL.md" "${source_frontmatter}" "${source_body}"
    transform_frontmatter "${source_frontmatter}" "${profile}" "${transformed_frontmatter}" "${frontmatter_policy}"
    : > "${work_dir}/${skill_name}-omit-sections.txt"
    yq eval -r '.omit_sections[]?' "${profile}" > "${work_dir}/${skill_name}-omit-sections.txt"
    remove_sections "${source_body}" "${transformed_body}" "${work_dir}/${skill_name}-omit-sections.txt"
    : > "${empty_file}"
    assemble_skill_markdown "${transformed_frontmatter}" "${transformed_body}" "${empty_file}" "${empty_file}" "${rendered_file}" "${frontmatter_policy}"

    printf '## %s\n\n' "${skill_name}" >> "${output_file}"
    cat "${rendered_file}" >> "${output_file}"
    printf '\n\n' >> "${output_file}"
  done < "${skills_file}"

  if [ -s "${aggregate_suffix}" ]; then
    cat "${aggregate_suffix}" >> "${output_file}"
    printf '\n' >> "${output_file}"
  fi
}

sync_stage_to_repo() {
  local profiles_file="$1"

  local roots_file="${TMP_ROOT}/profile-roots.txt"
  : > "${roots_file}"

  local profile
  while IFS= read -r profile; do
    [ -n "${profile}" ] || continue
    local bundle_mode
    local pattern
    bundle_mode="$(profile_scalar "${profile}" '.bundle_mode')"
    pattern="$(profile_scalar "${profile}" '.output_path_pattern')"
    printf '%s\n' "$(profile_root_path "${profile}" "${bundle_mode}" "${pattern}")" >> "${roots_file}"
  done < "${profiles_file}"

  while IFS= read -r root_path; do
    [ -n "${root_path}" ] || continue
    rm -rf "${REPO_ROOT}/${root_path}"
  done <<EOF
$(LC_ALL=C sort -u "${roots_file}")
EOF

  while IFS= read -r staged_root; do
    [ -n "${staged_root}" ] || continue
    local source="${TMP_ROOT}/stage/${staged_root}"
    local destination="${REPO_ROOT}/${staged_root}"
    [ -e "${source}" ] || continue
    mkdir -p "$(dirname "${destination}")"
    cp -R "${source}" "${destination}"
  done <<EOF
$(LC_ALL=C sort -u "${roots_file}")
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --platform)
      [ "$#" -ge 2 ] || {
        usage >&2
        exit 2
      }
      PLATFORM="$2"
      shift 2
      ;;
    --all)
      BUILD_ALL=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --validate)
      RUN_VALIDATE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      printf '\nUnknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -n "${PLATFORM}" ] && [ "${BUILD_ALL}" -eq 1 ]; then
  usage >&2
  fail "Use either --platform or --all, not both."
fi

if [ -z "${PLATFORM}" ] && [ "${BUILD_ALL}" -ne 1 ]; then
  usage >&2
  fail "You must pass either --platform <name> or --all."
fi

require_tool python3
require_tool yq

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/rh-skills-build.XXXXXX")"
mkdir -p "${TMP_ROOT}/stage" "${TMP_ROOT}/work"

PROFILES_FILE="${TMP_ROOT}/profiles.txt"
SKILLS_FILE="${TMP_ROOT}/skills.txt"
OUTPUT_PATHS_FILE="${TMP_ROOT}/output-paths.txt"

collect_selected_profiles "${PROFILES_FILE}"
collect_skill_dirs "${SKILLS_FILE}"

while IFS= read -r skill_dir; do
  [ -n "${skill_dir}" ] || continue
  check_for_placeholders "${skill_dir}" "$(basename "${skill_dir}")"
done < "${SKILLS_FILE}"

while IFS= read -r profile; do
  [ -n "${profile}" ] || continue
  validate_profile "${profile}"
done < "${PROFILES_FILE}"

detect_conflicting_outputs "${PROFILES_FILE}" "${SKILLS_FILE}" "${OUTPUT_PATHS_FILE}"

log "Building RH skills from $(relative_path "${REPO_ROOT}" "${CURATED_DIR}")"
if [ "${DRY_RUN}" -eq 1 ]; then
  log "Mode: dry-run"
else
  log "Mode: write"
fi
if [ "${RUN_VALIDATE}" -eq 1 ]; then
  log "Validation: enabled"
fi

while IFS= read -r profile; do
  [ -n "${profile}" ] || continue
  local_platform="$(profile_scalar "${profile}" '.platform')"
  local_bundle_mode="$(profile_scalar "${profile}" '.bundle_mode')"
  local_output_pattern="$(profile_scalar "${profile}" '.output_path_pattern')"
  local_frontmatter_policy="$(profile_scalar "${profile}" '.frontmatter_policy')"

  log ""
  log "Platform: ${local_platform}"

  if [ "${local_bundle_mode}" = "aggregate" ]; then
    aggregate_relative_path="$(render_path "${local_output_pattern}" "${local_platform}" "__aggregate__")"
    aggregate_stage_path="${TMP_ROOT}/stage/${aggregate_relative_path}"
    build_aggregate_bundle "${profile}" "${SKILLS_FILE}" "${aggregate_stage_path}" "${local_frontmatter_policy}" >/dev/null
    BUILT=$((BUILT + 1))
    log "  $( [ "${DRY_RUN}" -eq 1 ] && printf 'PREVIEW' || printf 'BUILD' ) ${local_platform}/__aggregate__ -> ${aggregate_relative_path}"

    if [ "${RUN_VALIDATE}" -eq 1 ]; then
      preamble_file="${TMP_ROOT}/work/$(basename "${profile}")-aggregate/aggregate-preamble.md"
      suffix_file="${TMP_ROOT}/work/$(basename "${profile}")-aggregate/aggregate-suffix.md"
      while IFS= read -r skill_dir; do
        [ -n "${skill_dir}" ] || continue
        skill_name="$(basename "${skill_dir}")"
        while IFS= read -r validation_rule; do
          [ -n "${validation_rule}" ] || continue
          run_rule "validation" "${validation_rule}" "${local_platform}" "${skill_name}" "${local_bundle_mode}" "${aggregate_stage_path}" "${preamble_file}" "${suffix_file}"
        done <<EOF
$(yq eval -r '.validation_rules[]?' "${profile}")
EOF
        while IFS= read -r installability_rule; do
          [ -n "${installability_rule}" ] || continue
          run_rule "installability" "${installability_rule}" "${local_platform}" "${skill_name}" "${local_bundle_mode}" "${aggregate_stage_path}" "${preamble_file}" "${suffix_file}"
        done <<EOF
$(yq eval -r '.installability_checks[]?' "${profile}")
EOF
      done < "${SKILLS_FILE}"
    fi

    continue
  fi

  while IFS= read -r skill_dir; do
    [ -n "${skill_dir}" ] || continue
    skill_name="$(basename "${skill_dir}")"
    stage_relative_path="$(render_path "${local_output_pattern}" "${local_platform}" "${skill_name}")"
    stage_path="${TMP_ROOT}/stage/${stage_relative_path}"
    preamble_suffix_paths="$(build_per_skill_bundle "${profile}" "${skill_dir}" "${stage_path}" "${local_frontmatter_policy}")"
    preamble_file="$(printf '%s' "${preamble_suffix_paths}" | cut -f1)"
    suffix_file="$(printf '%s' "${preamble_suffix_paths}" | cut -f2)"

    BUILT=$((BUILT + 1))
    log "  $( [ "${DRY_RUN}" -eq 1 ] && printf 'PREVIEW' || printf 'BUILD' ) ${local_platform}/${skill_name} -> ${stage_relative_path}/SKILL.md"

    if [ "${RUN_VALIDATE}" -eq 1 ]; then
      while IFS= read -r validation_rule; do
        [ -n "${validation_rule}" ] || continue
        run_rule "validation" "${validation_rule}" "${local_platform}" "${skill_name}" "${local_bundle_mode}" "${stage_path}" "${preamble_file}" "${suffix_file}"
      done <<EOF
$(yq eval -r '.validation_rules[]?' "${profile}")
EOF
      while IFS= read -r installability_rule; do
        [ -n "${installability_rule}" ] || continue
        run_rule "installability" "${installability_rule}" "${local_platform}" "${skill_name}" "${local_bundle_mode}" "${stage_path}" "${preamble_file}" "${suffix_file}"
      done <<EOF
$(yq eval -r '.installability_checks[]?' "${profile}")
EOF
    fi
  done < "${SKILLS_FILE}"
done < "${PROFILES_FILE}"

if [ "${ERRORS}" -gt 0 ]; then
  log ""
  log "Summary: built=${BUILT} skipped=${SKIPPED} warnings=${WARNINGS} errors=${ERRORS}"
  exit 1
fi

if [ "${DRY_RUN}" -eq 0 ]; then
  sync_stage_to_repo "${PROFILES_FILE}"
fi

log ""
log "Summary: built=${BUILT} skipped=${SKIPPED} warnings=${WARNINGS} errors=${ERRORS}"
if [ "${DRY_RUN}" -eq 1 ]; then
  log "No files were written because --dry-run was enabled."
else
  log "Generated output root: $(relative_path "${REPO_ROOT}" "${OUTPUT_ROOT}")"
fi
