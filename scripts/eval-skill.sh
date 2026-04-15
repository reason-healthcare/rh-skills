#!/usr/bin/env bash
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
  echo "  --agent <name>       Agent driver: claude | ollama | generic (default: claude)"
  echo "  --model <name>       Model override passed to agent"
  echo "  --topic <name>       Topic name to initialise in the workspace (default: eval-topic)"
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
uv add --quiet rh-skills 2>/dev/null || \
  uv add --quiet "rh-skills @ $REPO_ROOT" 2>/dev/null

# Install the skill for the target agent
uv run rh-skills skills init \
  --from "$REPO_ROOT/skills/.curated" \
  --platforms generic \
  --yes 2>/dev/null || true

# Initialise a topic for the agent to work against
uv run rh-skills init "$TOPIC" 2>/dev/null || true

echo "Workspace ready. Starting $AGENT…"
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
    die "Unknown agent: $AGENT. Supported: claude, ollama, generic"
    ;;
esac

# ── capture transcript ────────────────────────────────────────────────────────
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

# ── write review stub ─────────────────────────────────────────────────────────
cat > "$REVIEW_FILE" <<REVIEW_STUB
# Skill Eval Review

| Field | Value |
|-------|-------|
| skill | \`$SKILL\` |
| scenario | $SCENARIO |
| transcript | \`$TRANSCRIPT_FILE\` |
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
