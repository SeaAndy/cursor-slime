#!/usr/bin/env bash
# Append a structured event line for the desktop pet to consume.
# One JSON object per line at ~/.cursor/pet-stats.jsonl

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

LOG="$HOME/.cursor/pet-stats.jsonl"
INPUT=$(cat)
TS=$(date +%s)

EVENT=$(printf '%s' "$INPUT" | jq -r '.hook_event_name // "unknown"' 2>/dev/null)
MODEL=$(printf '%s' "$INPUT" | jq -r '.model // ""' 2>/dev/null)
TOOL=$(printf  '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
DUR=$(printf   '%s' "$INPUT" | jq -r '.duration // 0'  2>/dev/null)
CONV=$(printf  '%s' "$INPUT" | jq -r '.conversation_id // ""' 2>/dev/null)
TRANS=$(printf '%s' "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null)
WORK=$(printf  '%s' "$INPUT" | jq -r '(.workspace_roots[0] // "")' 2>/dev/null)
EXIT=$(printf  '%s' "$INPUT" | jq -r 'try (.tool_output | fromjson | .exitCode) // 0' 2>/dev/null)

# Live char counters: capture content size from hook payload directly so the
# pet has a real-time token estimate that doesn't have to wait for the
# transcript file to flush.
IN_CHARS=$(printf  '%s' "$INPUT" | jq -r '.tool_input  // {}  | tostring | length' 2>/dev/null)
OUT_CHARS=$(printf '%s' "$INPUT" | jq -r '.tool_output // ""  | tostring | length' 2>/dev/null)

jq -nc \
  --argjson ts "$TS" \
  --arg event "$EVENT" \
  --arg model "$MODEL" \
  --arg tool  "$TOOL" \
  --argjson duration "${DUR:-0}" \
  --arg conv "$CONV" \
  --arg trans "$TRANS" \
  --arg workspace "$WORK" \
  --argjson exit "${EXIT:-0}" \
  --argjson in_chars  "${IN_CHARS:-0}" \
  --argjson out_chars "${OUT_CHARS:-0}" \
  '{ts:$ts, event:$event, model:$model, tool:$tool, duration:$duration, conversation_id:$conv, transcript_path:$trans, workspace:$workspace, exit:$exit, in_chars:$in_chars, out_chars:$out_chars}' \
  >> "$LOG" 2>/dev/null

echo '{}'
