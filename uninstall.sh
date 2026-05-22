#!/usr/bin/env bash
# Cursor Slime uninstaller — removes everything install.sh added.
# Does NOT touch the user's other Cursor hooks; only removes our log-stats hook.

set -u

GREEN='\033[32m'; YELLOW='\033[33m'; RESET='\033[0m'
say()  { printf "${GREEN}==>${RESET} %s\n" "$*"; }
warn() { printf "${YELLOW}!!${RESET}  %s\n" "$*"; }

PET_DIR="$HOME/.cursor/pet"
HOOKS_DIR="$HOME/.cursor/hooks"
HOOKS_JSON="$HOME/.cursor/hooks.json"

say "Stopping any running slime"
pkill -f "pet/slime.py" 2>/dev/null || true

say "Removing app symlink"
rm -f "$HOME/Applications/CursorSlime.app"

say "Removing hook script"
rm -f "$HOOKS_DIR/log-stats.sh"

if [ -f "$HOOKS_JSON" ] && [ -x "$PET_DIR/venv/bin/python3" ]; then
    say "Stripping slime entries from $HOOKS_JSON (other hooks preserved)"
    cp "$HOOKS_JSON" "$HOOKS_JSON.bak.$(date +%s)"
    "$PET_DIR/venv/bin/python3" - <<'PY' || true
import json, os
p = os.path.expanduser("~/.cursor/hooks.json")
with open(p) as f: cfg = json.load(f)
for ev, arr in list(cfg.get("hooks", {}).items()):
    cfg["hooks"][ev] = [h for h in arr if h.get("command") != "./hooks/log-stats.sh"]
    if not cfg["hooks"][ev]:
        del cfg["hooks"][ev]
with open(p, "w") as f:
    json.dump(cfg, f, indent=2)
PY
fi

say "Removing $PET_DIR (this includes venv, sprites, app bundle, slimectl)"
rm -rf "$PET_DIR"

warn "Log file kept at ~/.cursor/pet-stats.jsonl. Delete manually if desired:"
warn "    rm ~/.cursor/pet-stats.jsonl"

echo ""
echo "Done. Cursor Slime is fully uninstalled."
