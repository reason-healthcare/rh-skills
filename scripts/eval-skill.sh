#!/usr/bin/env bash
# eval-skill.sh — run a skill in an isolated temp workspace and capture the
# session transcript for efficiency and quality review.
#
# Usage:
#   scripts/eval-skill.sh --skill rh-inf-discovery --scenario fresh-start \
#                          --agent claude [--model claude-opus-4-5]
#   scripts/eval-skill.sh --skill rh-inf-ingest --scenario open-access-sources \
#                          --agent ollama --model llama3
#   scripts/eval-skill.sh --skill rh-inf-extract --scenario single-source \
#                          --agent generic
#   scripts/eval-skill.sh --help
#
# Scenario files live at eval/scenarios/<skill>/<scenario>.yaml.
# If a matching file exists it seeds the workspace and provides the prompt.
# Pass --topic to override the topic from the scenario file.
#
# After the run, a transcript is written to:
#   eval/transcripts/<skill>/<scenario>-<timestamp>.md
# and a human-review stub to:
#   eval/reviews/<skill>/<scenario>-<timestamp>-review.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── helpers ───────────────────────────────────────────────────────────────────
die() { echo "ERROR: $*" >&2; exit 1; }

# yq-free YAML field extractor (single scalar value at a top-level key).
# Usage: yaml_get <file> <key>
yaml_get() {
  python3 - "$1" "$2" <<'PY'
import sys, re
path, key = sys.argv[1], sys.argv[2]
with open(path) as f:
    for line in f:
        m = re.match(rf'^{re.escape(key)}:\s*(.+)', line)
        if m:
            print(m.group(1).strip().strip('"').strip("'"))
            break
PY
}

# Write inline `content:` blocks from a scenario file into the workspace.
# Also copies any companion fixture directory (same name as scenario, no .yaml
# extension) into the workspace — supports binary files like PDFs.
# Uses Python so we don't need yq.
apply_scenario_files() {
  local scenario_file="$1"
  local workdir="$2"
  python3 - "$scenario_file" "$workdir" <<'PY'
import sys, os
from pathlib import Path

try:
    from ruamel.yaml import YAML
except ImportError:
    import subprocess, sys as _sys
    subprocess.check_call([_sys.executable, "-m", "pip", "install", "-q", "ruamel.yaml"])
    from ruamel.yaml import YAML

yaml = YAML(typ="safe")
with open(sys.argv[1]) as f:
    sc = yaml.load(f)

workdir = Path(sys.argv[2])
workspace = sc.get("workspace") or {}

# Write tracking.yaml
tracking = workspace.get("tracking_yaml")
if tracking:
    dest = workdir / "tracking.yaml"
    dest.write_text(tracking)
    print(f"  wrote tracking.yaml")

# Write declared files
for entry in workspace.get("files") or []:
    rel = entry.get("path")
    content = entry.get("content")
    if rel and content:
        dest = workdir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        print(f"  wrote {rel}")
PY

  # Copy companion fixture directory if present — supports binary files (PDFs, etc.)
  # Convention: eval/scenarios/<skill>/<scenario>/ mirrors what gets copied to workspace root.
  local fixture_dir
  fixture_dir="$(dirname "$scenario_file")/$(basename "$scenario_file" .yaml)"
  if [[ -d "$fixture_dir" ]]; then
    echo "  copying fixture directory: $(basename "$fixture_dir")/"
    cp -r "$fixture_dir/." "$workdir/"
  fi
}

# Render the expected_outputs checklist from a scenario file.
render_expected_outputs() {
  local scenario_file="$1"
  python3 - "$scenario_file" <<'PY'
import sys
try:
    from ruamel.yaml import YAML
except ImportError:
    print("(ruamel.yaml not available — install it to enable output checks)")
    sys.exit(0)

yaml = YAML(typ="safe")
with open(sys.argv[1]) as f:
    sc = yaml.load(f)

outputs = sc.get("expected_outputs") or []
if not outputs:
    print("*(no expected outputs declared in scenario)*")
    sys.exit(0)

for out in outputs:
    path = out.get("path", "?")
    checks = out.get("checks") or []
    print(f"**`{path}`**")
    for c in checks:
        if isinstance(c, str):
            print(f"- [ ] `{c}`")
        elif isinstance(c, dict):
            for k, v in c.items():
                print(f"- [ ] `{k}: {v}`")
    print()
PY
}

# Render efficiency/quality focus items from a scenario file.
render_focus_items() {
  local scenario_file="$1"
  local key="$2"    # efficiency_focus or quality_focus
  python3 - "$scenario_file" "$key" <<'PY'
import sys
try:
    from ruamel.yaml import YAML
except ImportError:
    sys.exit(0)
yaml = YAML(typ="safe")
with open(sys.argv[1]) as f:
    sc = yaml.load(f)
for item in sc.get(sys.argv[2]) or []:
    print(f"- [ ] {item}")
PY
}

# ── defaults ──────────────────────────────────────────────────────────────────
SKILL=""
SCENARIO=""
AGENT="claude"
MODEL=""
TOPIC_OVERRIDE=""
KEEP_WORKDIR=false

usage() {
  sed -n '2,22p' "$0" | sed 's/^# \?//'
  echo
  echo "Options:"
  echo "  --skill <name>       Curated skill to evaluate (required)"
  echo "  --scenario <name>    Scenario name; must match a file in eval/scenarios/<skill>/ (required)"
  echo "  --agent <name>       Agent driver: claude | codex | ollama | generic (default: claude)"
  echo "  --model <name>       Model override passed to agent"
  echo "  --topic <name>       Override the topic from the scenario file"
  echo "  --keep-workdir       Do not delete temp workspace after the run"
  echo "  --help               Show this help"
  exit 0
}

# ── arg parse ─────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill)         SKILL="$2";           shift 2 ;;
    --scenario)      SCENARIO="$2";        shift 2 ;;
    --agent)         AGENT="$2";           shift 2 ;;
    --model)         MODEL="$2";           shift 2 ;;
    --topic)         TOPIC_OVERRIDE="$2";  shift 2 ;;
    --keep-workdir)  KEEP_WORKDIR=true;    shift   ;;
    --help|-h)       usage ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ -n "$SKILL"    ]] || die "--skill is required"
[[ -n "$SCENARIO" ]] || die "--scenario is required"

SKILL_DIR="$REPO_ROOT/skills/.curated/$SKILL"
[[ -d "$SKILL_DIR" ]] || die "Skill not found: $SKILL_DIR"

# ── load scenario file ────────────────────────────────────────────────────────
SCENARIO_FILE="$REPO_ROOT/eval/scenarios/$SKILL/${SCENARIO}.yaml"
SCENARIO_LOADED=false
TOPIC="eval-topic"
CUSTOM_PROMPT=""

if [[ -f "$SCENARIO_FILE" ]]; then
  SCENARIO_LOADED=true
  _topic="$(yaml_get "$SCENARIO_FILE" topic 2>/dev/null || true)"
  # _none means multi-topic or no topic needed — skip rh-skills init
  [[ -n "$_topic" && "$_topic" != "_none" && "$_topic" != "_multiple" ]] && TOPIC="$_topic"
  echo "==> Scenario file: $SCENARIO_FILE"
else
  echo "==> No scenario file found at $SCENARIO_FILE — using generated prompt"
fi

# --topic flag overrides scenario value
[[ -n "$TOPIC_OVERRIDE" ]] && TOPIC="$TOPIC_OVERRIDE"

# ── workspace ─────────────────────────────────────────────────────────────────
WORKDIR="$(mktemp -d -t "rh-skills-eval-XXXXXX")"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
TRANSCRIPT_DIR="$REPO_ROOT/eval/transcripts/$SKILL"
REVIEW_DIR="$REPO_ROOT/eval/reviews/$SKILL"
mkdir -p "$TRANSCRIPT_DIR" "$REVIEW_DIR"
TRANSCRIPT_FILE="$TRANSCRIPT_DIR/${SCENARIO}-${TS}.md"
REVIEW_FILE="$REVIEW_DIR/${SCENARIO}-${TS}-review.md"

cleanup() {
  if [[ "$KEEP_WORKDIR" == "false" ]]; then
    rm -rf "$WORKDIR"
  else
    echo "Workspace kept at: $WORKDIR"
  fi
}
trap cleanup EXIT

echo "==> Workspace : $WORKDIR"
echo "==> Skill     : $SKILL"
echo "==> Scenario  : $SCENARIO"
echo "==> Topic     : $TOPIC"
echo "==> Agent     : $AGENT"
echo "==> Transcript: $TRANSCRIPT_FILE"
echo

# ── bootstrap workspace ───────────────────────────────────────────────────────
cd "$WORKDIR"
uv init --quiet --name eval-project 2>/dev/null || true
# Always install from local repo so any source changes are picked up without
# needing a manual pipx reinstall before running eval.
uv add --quiet "rh-skills @ $REPO_ROOT" 2>/dev/null

# Apply scenario workspace fixtures before rh-skills init so that any
# pre-seeded tracking.yaml is in place.
if [[ "$SCENARIO_LOADED" == "true" ]]; then
  echo "==> Applying scenario workspace fixtures…"
  apply_scenario_files "$SCENARIO_FILE" "$WORKDIR"
fi

# Install the skill into .agents/skills/ so the agent can find it.
uv run rh-skills skills install \
  --from "$REPO_ROOT/skills/.curated" \
  --force 2>/dev/null || true

# Initialise topic (unless scenario says none/multiple — tracking.yaml already seeded).
if [[ -n "$TOPIC" && "$TOPIC" != "eval-topic" ]]; then
  uv run rh-skills init "$TOPIC" 2>/dev/null || true
elif [[ ! -f "$WORKDIR/tracking.yaml" ]]; then
  uv run rh-skills init "$TOPIC" 2>/dev/null || true
fi

echo "Workspace ready. Starting ${AGENT}…"
echo

# ── compose the opening prompt ────────────────────────────────────────────────
SKILL_BODY="$(cat "$SKILL_DIR/SKILL.md")"

if [[ "$SCENARIO_LOADED" == "true" ]]; then
  # Extract the prompt block from the scenario file and substitute placeholders.
  RAW_PROMPT="$(python3 - "$SCENARIO_FILE" <<'PY'
import sys
try:
    from ruamel.yaml import YAML
except ImportError:
    sys.exit(0)
yaml = YAML(typ="safe")
with open(sys.argv[1]) as f:
    sc = yaml.load(f)
print(sc.get("prompt", ""))
PY
)"
  CUSTOM_PROMPT="${RAW_PROMPT/\{workdir\}/$WORKDIR}"
  CUSTOM_PROMPT="${CUSTOM_PROMPT/\{topic\}/$TOPIC}"
  CUSTOM_PROMPT="${CUSTOM_PROMPT/\{skill\}/$SKILL}"
fi

if [[ -n "$CUSTOM_PROMPT" ]]; then
  OPENING_PROMPT="You are a clinical informaticist. The following is your active skill:

$SKILL_BODY

---

$CUSTOM_PROMPT"
else
  OPENING_PROMPT="You are a clinical informaticist using the $SKILL skill.

$SKILL_BODY

---

**Scenario: $SCENARIO**

Working directory: $WORKDIR
Topic: $TOPIC

Please begin the $SKILL workflow now."
fi

# ── agent dispatch ────────────────────────────────────────────────────────────
echo "==> Running agent (output is tee'd to transcript)…"
echo

AGENT_CMD=""
case "$AGENT" in
  claude)
    MODEL_FLAG=""
    [[ -n "$MODEL" ]] && MODEL_FLAG="--model $MODEL"
    AGENT_CMD="claude $MODEL_FLAG --print"
    ;;
  codex)
    MODEL_FLAG=""
    [[ -n "$MODEL" ]] && MODEL_FLAG="-c model=$MODEL"
    AGENT_CMD="codex exec -s workspace-write -C $WORKDIR $MODEL_FLAG"
    ;;
  ollama)
    MODEL="${MODEL:-llama3}"
    AGENT_CMD="ollama run $MODEL"
    ;;
  generic)
    echo "$OPENING_PROMPT" > "$WORKDIR/prompt.txt"
    echo "Prompt written to $WORKDIR/prompt.txt"
    echo "Paste it into your agent, then save the session as:"
    echo "  $TRANSCRIPT_FILE"
    AGENT_CMD=""
    ;;
  *)
    die "Unknown agent: $AGENT. Supported: claude, codex, ollama, generic"
    ;;
esac

# ── capture transcript ────────────────────────────────────────────────────────
SESSION_START=$(date +%s)
{
  echo
  echo "|-------|-------|"
  echo "| skill | \`$SKILL\` |"
  echo "| scenario | $SCENARIO |"
  echo "| agent | $AGENT |"
  echo "| model | ${MODEL:-default} |"
  echo "| timestamp | $TS |"
  echo "| rh_skills_version | $(cd "$REPO_ROOT" && uv run python -c 'import rh_skills; print(rh_skills.__version__)' 2>/dev/null || echo unknown) |"
  echo
  echo "## Opening Prompt"
  echo
  echo '```'
  echo "$OPENING_PROMPT"
  echo '```'
  echo
  echo "## Session"
  echo
} > "$TRANSCRIPT_FILE"

if [[ -n "$AGENT_CMD" ]]; then
  echo "$OPENING_PROMPT" | $AGENT_CMD 2>&1 | tee -a "$TRANSCRIPT_FILE"
fi

echo >> "$TRANSCRIPT_FILE"
echo "*(session end)*" >> "$TRANSCRIPT_FILE"

# ── compute session stats ─────────────────────────────────────────────────────
SESSION_END=$(date +%s)
ELAPSED_SECS=$(( SESSION_END - SESSION_START ))
ELAPSED_DISPLAY="$(( ELAPSED_SECS / 60 ))m $(( ELAPSED_SECS % 60 ))s"
TRANSCRIPT_LINES=$(wc -l < "$TRANSCRIPT_FILE" | tr -d ' ')
TRANSCRIPT_BYTES=$(wc -c < "$TRANSCRIPT_FILE" | tr -d ' ')
APPROX_TOKENS=$(( TRANSCRIPT_BYTES / 4 ))

# ── write review stub ─────────────────────────────────────────────────────────
EFFICIENCY_ITEMS=""
QUALITY_ITEMS=""
EXPECTED_OUTPUTS_BLOCK=""
if [[ "$SCENARIO_LOADED" == "true" ]]; then
  EFFICIENCY_ITEMS="$(render_focus_items "$SCENARIO_FILE" efficiency_focus 2>/dev/null || true)"
  QUALITY_ITEMS="$(render_focus_items "$SCENARIO_FILE" quality_focus 2>/dev/null || true)"
  EXPECTED_OUTPUTS_BLOCK="$(render_expected_outputs "$SCENARIO_FILE" 2>/dev/null || true)"
fi

[[ -z "$EFFICIENCY_ITEMS" ]] && EFFICIENCY_ITEMS="- [ ] Ambiguity: agent asked for clarification a clearer prompt would have answered
- [ ] Churn: retried steps or looped on the same sub-task
- [ ] CLI gaps: agent wrote inline scripts for work that belongs in rh-skills
- [ ] Token waste: verbose preambles or repeated tool calls"

[[ -z "$QUALITY_ITEMS" ]] && QUALITY_ITEMS="- [ ] Completeness: all expected files/sections are present
- [ ] Clinical accuracy: terminology, evidence levels, and citations are correct
- [ ] Schema compliance: YAML/FHIR structure matches schemas/
- [ ] Traceability: claims link back to cited sources
- [ ] No hallucinations: no fabricated citations or lab values"

cat > "$REVIEW_FILE" <<REVIEW_STUB
# Skill Eval Review

| Field | Value |
|-------|-------|
| skill | \`$SKILL\` |
| scenario | $SCENARIO |
| transcript | \`$(basename "$TRANSCRIPT_FILE")\` |
| elapsed | $ELAPSED_DISPLAY |
| transcript_lines | $TRANSCRIPT_LINES |
| approx_tokens | ~$APPROX_TOKENS |
| reviewer | <!-- your name --> |
| reviewed_at | <!-- date --> |

---

## 1. Efficiency (objective)

Score: <!-- 1–5 -->

$EFFICIENCY_ITEMS

Notes:
<!-- free text -->

---

## 2. Output Quality (subjective)

Score: <!-- 1–5 -->

### Expected outputs

$EXPECTED_OUTPUTS_BLOCK
### Quality checks

$QUALITY_ITEMS

Notes:
<!-- free text -->

---

## 3. Recommended Changes

<!-- List specific changes to SKILL.md, reference.md, examples/, or CLI commands
     that would address issues found above. -->

REVIEW_STUB

echo
echo "==> Transcript : $TRANSCRIPT_FILE"
echo "==> Review stub: $REVIEW_FILE"
echo
echo "Open the review file, work through the checklist, and commit both files:"
echo "  git add eval/ && git commit -m 'eval($SKILL/$SCENARIO): <summary>'"

# eval-skill.sh — run a skill in an isolated temp workspace and capture the
# session transcript for efficiency and quality review.
#
# Usage:
#   scripts/eval-skill.sh --skill rh-inf-discovery --scenario sources-identified \
#                          --agent claude [--model claude-opus-4-5]
#   scripts/eval-skill.sh --skill rh-inf-ingest   --scenario ingest-pdf \
#                          --agent ollama --model llama3
#   scripts/eval-skill.sh --help
#
# After the run, a transcript is written to:
#   eval/transcripts/<skill>/<scenario>-<timestamp>.md
# and a human-review stub to:
#   eval/reviews/<skill>/<scenario>-<timestamp>-review.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── defaults ──────────────────────────────────────────────────────────────────
SKILL=""
SCENARIO=""
AGENT="claude"
MODEL=""
TOPIC="eval-topic"
KEEP_WORKDIR=false

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \?//'
  echo
  echo "Options:"
  echo "  --skill <name>       Curated skill to evaluate (required)"
  echo "  --scenario <name>    Scenario label for transcript naming (required)"
  echo "  --agent <name>       Agent driver: claude | codex | ollama | generic (default: claude)"
  echo "  --keep-workdir       Do not delete temp workspace after the run"
  echo "  --help               Show this help"
  exit 0
}

die() { echo "ERROR: $*" >&2; exit 1; }

# ── arg parse ─────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill)       SKILL="$2";      shift 2 ;;
    --scenario)    SCENARIO="$2";   shift 2 ;;
    --agent)       AGENT="$2";      shift 2 ;;
    --model)       MODEL="$2";      shift 2 ;;
    --topic)       TOPIC="$2";      shift 2 ;;
    --keep-workdir) KEEP_WORKDIR=true; shift ;;
    --help|-h)     usage ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ -n "$SKILL"    ]] || die "--skill is required"
[[ -n "$SCENARIO" ]] || die "--scenario is required"

SKILL_DIR="$REPO_ROOT/skills/.curated/$SKILL"
[[ -d "$SKILL_DIR" ]] || die "Skill not found: $SKILL_DIR"

# ── workspace ─────────────────────────────────────────────────────────────────
WORKDIR="$(mktemp -d -t "rh-skills-eval-XXXXXX")"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
TRANSCRIPT_DIR="$REPO_ROOT/eval/transcripts/$SKILL"
REVIEW_DIR="$REPO_ROOT/eval/reviews/$SKILL"
mkdir -p "$TRANSCRIPT_DIR" "$REVIEW_DIR"
TRANSCRIPT_FILE="$TRANSCRIPT_DIR/${SCENARIO}-${TS}.md"
REVIEW_FILE="$REVIEW_DIR/${SCENARIO}-${TS}-review.md"

cleanup() {
  if [[ "$KEEP_WORKDIR" == "false" ]]; then
    rm -rf "$WORKDIR"
  else
    echo "Workspace kept at: $WORKDIR"
  fi
}
trap cleanup EXIT

echo "==> Workspace : $WORKDIR"
echo "==> Skill     : $SKILL"
echo "==> Scenario  : $SCENARIO"
echo "==> Agent     : $AGENT"
echo "==> Transcript: $TRANSCRIPT_FILE"
echo

# ── bootstrap workspace ───────────────────────────────────────────────────────
# Install rh-skills and the chosen skill into the temp workspace so the agent
# sees a realistic project layout.
cd "$WORKDIR"
uv init --quiet --name "$TOPIC" 2>/dev/null || true
# Always install from local repo so any source changes are picked up without
# needing a manual pipx reinstall before running eval.
uv add --quiet "rh-skills @ $REPO_ROOT" 2>/dev/null

# Install the skill for the target agent
uv run rh-skills skills install \
  --from "$REPO_ROOT/skills/.curated" \
  --force 2>/dev/null || true

# Initialise a topic for the agent to work against
uv run rh-skills init "$TOPIC" 2>/dev/null || true

echo "Workspace ready. Starting ${AGENT}…"
echo

# ── compose the opening prompt ────────────────────────────────────────────────
SKILL_BODY="$(cat "$SKILL_DIR/SKILL.md")"
OPENING_PROMPT="You are a clinical informaticist using the $SKILL skill.

$SKILL_BODY

---

**Scenario: $SCENARIO**

Working directory: $WORKDIR
Topic: $TOPIC

Please begin the $SKILL workflow now."

# ── agent dispatch ────────────────────────────────────────────────────────────
echo "==> Running agent (output is tee'd to transcript)…"
echo

AGENT_CMD=""
case "$AGENT" in
  claude)
    MODEL_FLAG=""
    [[ -n "$MODEL" ]] && MODEL_FLAG="--model $MODEL"
    # claude CLI: https://docs.anthropic.com/claude-code
    AGENT_CMD="claude $MODEL_FLAG --print"
    ;;
  codex)
    MODEL_FLAG=""
    [[ -n "$MODEL" ]] && MODEL_FLAG="-c model=$MODEL"
    AGENT_CMD="codex exec -s workspace-write -C $WORKDIR $MODEL_FLAG"
    ;;
  ollama)
    MODEL="${MODEL:-llama3}"
    AGENT_CMD="ollama run $MODEL"
    ;;
  generic)
    # Fallback: write the prompt to a file and open it for manual use
    echo "$OPENING_PROMPT" > "$WORKDIR/prompt.txt"
    echo "Prompt written to $WORKDIR/prompt.txt"
    echo "Paste it into your agent, then save the session as:"
    echo "  $TRANSCRIPT_FILE"
    echo
    echo "When done, run the review scaffold command:"
    echo "  scripts/eval-skill.sh --review $TRANSCRIPT_FILE"
    AGENT_CMD=""
    ;;
  *)
    die "Unknown agent: $AGENT. Supported: claude, codex, ollama, generic"
    ;;
esac

# ── capture transcript ────────────────────────────────────────────────────────
SESSION_START=$(date +%s)
{
  echo "# Skill Eval Transcript"
  echo
  echo "| Field | Value |"
  echo "|-------|-------|"
  echo "| skill | \`$SKILL\` |"
  echo "| scenario | $SCENARIO |"
  echo "| agent | $AGENT |"
  echo "| model | ${MODEL:-default} |"
  echo "| timestamp | $TS |"
  echo "| rh_skills_version | $(cd "$REPO_ROOT" && uv run python -c 'import rh_skills; print(rh_skills.__version__)' 2>/dev/null || echo unknown) |"
  echo
  echo "## Opening Prompt"
  echo
  echo '```'
  echo "$OPENING_PROMPT"
  echo '```'
  echo
  echo "## Session"
  echo
} > "$TRANSCRIPT_FILE"

if [[ -n "$AGENT_CMD" ]]; then
  echo "$OPENING_PROMPT" | $AGENT_CMD 2>&1 | tee -a "$TRANSCRIPT_FILE"
fi

echo >> "$TRANSCRIPT_FILE"
echo "*(session end)*" >> "$TRANSCRIPT_FILE"

# ── compute session stats ─────────────────────────────────────────────────────
SESSION_END=$(date +%s)
ELAPSED_SECS=$(( SESSION_END - SESSION_START ))
ELAPSED_DISPLAY="$(( ELAPSED_SECS / 60 ))m $(( ELAPSED_SECS % 60 ))s"
TRANSCRIPT_LINES=$(wc -l < "$TRANSCRIPT_FILE" | tr -d ' ')
TRANSCRIPT_BYTES=$(wc -c < "$TRANSCRIPT_FILE" | tr -d ' ')
APPROX_TOKENS=$(( TRANSCRIPT_BYTES / 4 ))

# ── write review stub ─────────────────────────────────────────────────────────
cat > "$REVIEW_FILE" <<REVIEW_STUB
# Skill Eval Review

| Field | Value |
|-------|-------|
| skill | \`$SKILL\` |
| scenario | $SCENARIO |
| transcript | \`$TRANSCRIPT_FILE\` |
| elapsed | $ELAPSED_DISPLAY |
| transcript_lines | $TRANSCRIPT_LINES |
| approx_tokens | ~$APPROX_TOKENS |
| reviewer | <!-- your name --> |
| reviewed_at | <!-- date --> |

---

## 1. Efficiency (objective)

Score: <!-- 1–5 -->

Examine the transcript for:

- [ ] **Ambiguity** — did the agent ask for clarification that a better prompt would have pre-empted?
- [ ] **Churn** — did the agent retry steps, redo work, or loop on the same sub-task?
- [ ] **CLI gaps** — did the agent write a shell/Python script for something that could (or should) be a \`rh-skills\` command?
- [ ] **Over-instruction** — did the agent read the same file or call the same tool more than twice?
- [ ] **Token waste** — verbose re-statements of what it was about to do vs. doing it

Notes:
<!-- free text -->

---

## 2. Output Quality (subjective)

Score: <!-- 1–5 -->

Check the artifacts produced in the workspace against expected outputs for this scenario:

- [ ] **Completeness** — all expected sections/files are present
- [ ] **Clinical accuracy** — terminology, evidence levels, and references are correct
- [ ] **Schema compliance** — YAML/FHIR structure matches schemas in \`schemas/\`
- [ ] **Traceability** — claims link back to cited sources
- [ ] **No hallucinations** — no fabricated citations, guidelines, or lab values

Notes:
<!-- free text -->

---

## 3. Recommended Changes

<!-- List specific changes to SKILL.md, reference.md, examples/, or CLI commands that
     would address the issues found above. Link to skill design rules where applicable. -->

REVIEW_STUB

echo
echo "==> Transcript : $TRANSCRIPT_FILE"
echo "==> Review stub: $REVIEW_FILE"
echo
echo "Open the review file, work through the checklist, and commit both files:"
echo "  git add eval/ && git commit -m 'eval($SKILL/$SCENARIO): <summary>'"
