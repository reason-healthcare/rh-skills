#!/usr/bin/env bash
# bin/llm-lib.sh — LLM invocation abstraction for hi CLI
# Source this file: source "$(dirname "${BASH_SOURCE[0]}")/llm-lib.sh"
#
# Required env vars (set in .env):
#   LLM_PROVIDER — ollama | anthropic | openai (default: ollama)
#
# Provider-specific env vars:
#   OLLAMA_ENDPOINT, OLLAMA_MODEL
#   ANTHROPIC_API_KEY, ANTHROPIC_MODEL
#   OPENAI_API_KEY, OPENAI_ENDPOINT, OPENAI_MODEL

# ── Provider dispatch ─────────────────────────────────────────────────────────

# invoke_llm <system_prompt> <user_prompt>
# Outputs LLM response to stdout; exits non-zero on curl/network failure.
invoke_llm() {
  local system_prompt="$1"
  local user_prompt="$2"
  local provider="${LLM_PROVIDER:-ollama}"

  case "$provider" in
    ollama)     _invoke_ollama "$system_prompt" "$user_prompt" ;;
    anthropic)  _invoke_anthropic "$system_prompt" "$user_prompt" ;;
    openai)     _invoke_openai "$system_prompt" "$user_prompt" ;;
    stub)       _invoke_stub "$system_prompt" "$user_prompt" ;;
    *)
      echo "[llm-lib] Unknown LLM_PROVIDER: $provider" >&2
      return 2
      ;;
  esac
}

# ── Stub (testing) ────────────────────────────────────────────────────────────
# Used when LLM_PROVIDER=stub. Returns a minimal valid L2 or L3 YAML artifact.
# HI_STUB_RESPONSE env var overrides output if set.

_invoke_stub() {
  if [[ -n "${HI_STUB_RESPONSE:-}" ]]; then
    printf '%s\n' "$HI_STUB_RESPONSE"
    return 0
  fi
  # Default: emit a minimal valid L2 artifact
  cat <<'YAML'
id: stub-artifact
name: StubArtifact
title: "Stub Artifact"
version: "1.0.0"
status: draft
domain: testing
description: |
  Stub LLM output for automated testing.
derived_from:
  - stub-l1
YAML
}

# ── Ollama ────────────────────────────────────────────────────────────────────

_invoke_ollama() {
  local system_prompt="$1"
  local user_prompt="$2"
  local endpoint="${OLLAMA_ENDPOINT:-http://localhost:11434}"
  local model="${OLLAMA_MODEL:-mistral}"

  local payload
  payload=$(jq -n \
    --arg model "$model" \
    --arg system "$system_prompt" \
    --arg user "$user_prompt" \
    '{model: $model, prompt: ($system + "\n\n" + $user), stream: false}')

  local response
  response=$(curl -sf --max-time 120 \
    -X POST "$endpoint/api/generate" \
    -H "Content-Type: application/json" \
    -d "$payload") || return 2

  echo "$response" | jq -r '.response // ""'
}

# ── Anthropic ─────────────────────────────────────────────────────────────────

_invoke_anthropic() {
  local system_prompt="$1"
  local user_prompt="$2"
  local model="${ANTHROPIC_MODEL:-claude-3-5-sonnet-20241022}"
  local api_key="${ANTHROPIC_API_KEY:-}"

  if [[ -z "$api_key" ]]; then
    echo "[llm-lib] ANTHROPIC_API_KEY not set" >&2
    return 2
  fi

  local payload
  payload=$(jq -n \
    --arg model "$model" \
    --arg system "$system_prompt" \
    --arg user "$user_prompt" \
    '{
      model: $model,
      max_tokens: 4096,
      system: $system,
      messages: [{role: "user", content: $user}]
    }')

  local response
  response=$(curl -sf --max-time 120 \
    -X POST "https://api.anthropic.com/v1/messages" \
    -H "x-api-key: $api_key" \
    -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" \
    -d "$payload") || return 2

  echo "$response" | jq -r '.content[0].text // ""'
}

# ── OpenAI-compatible ─────────────────────────────────────────────────────────

_invoke_openai() {
  local system_prompt="$1"
  local user_prompt="$2"
  local endpoint="${OPENAI_ENDPOINT:-https://api.openai.com/v1/chat/completions}"
  local model="${OPENAI_MODEL:-gpt-4o-mini}"
  local api_key="${OPENAI_API_KEY:-}"

  if [[ -z "$api_key" ]]; then
    echo "[llm-lib] OPENAI_API_KEY not set" >&2
    return 2
  fi

  local payload
  payload=$(jq -n \
    --arg model "$model" \
    --arg system "$system_prompt" \
    --arg user "$user_prompt" \
    '{
      model: $model,
      messages: [
        {role: "system", content: $system},
        {role: "user", content: $user}
      ]
    }')

  local response
  response=$(curl -sf --max-time 120 \
    -X POST "$endpoint" \
    -H "Authorization: Bearer $api_key" \
    -H "Content-Type: application/json" \
    -d "$payload") || return 2

  echo "$response" | jq -r '.choices[0].message.content // ""'
}

# ── Response comparison ───────────────────────────────────────────────────────

# compare_llm_response <actual> <expected> [mode]
# Modes: exact | normalized (default) | case_insensitive | contains | keywords
# Returns 0 (match), 1 (mismatch)
compare_llm_response() {
  local actual="$1"
  local expected="$2"
  local mode="${3:-normalized}"

  case "$mode" in
    exact)
      [[ "$actual" == "$expected" ]]
      ;;
    normalized)
      local a_norm e_norm
      a_norm=$(echo "$actual"   | tr -s '[:space:]' ' ' | sed -e 's/^ //' -e 's/ $//' | tr '[:upper:]' '[:lower:]')
      e_norm=$(echo "$expected" | tr -s '[:space:]' ' ' | sed -e 's/^ //' -e 's/ $//' | tr '[:upper:]' '[:lower:]')
      [[ "$a_norm" == "$e_norm" ]]
      ;;
    case_insensitive)
      local a_ci e_ci
      a_ci=$(echo "$actual"   | tr '[:upper:]' '[:lower:]')
      e_ci=$(echo "$expected" | tr '[:upper:]' '[:lower:]')
      [[ "$a_ci" == "$e_ci" ]]
      ;;
    contains)
      echo "$actual" | grep -qF "$expected"
      ;;
    keywords)
      local kw
      local all_found=0
      while IFS= read -r kw; do
        [[ -z "$kw" ]] && continue
        if ! echo "$actual" | grep -qiF "$kw"; then
          all_found=1; break
        fi
      done <<< "$expected"
      return $all_found
      ;;
    *)
      echo "[llm-lib] Unknown comparison mode: $mode" >&2
      return 2
      ;;
  esac
}
