#!/usr/bin/env bash
# Cursor Slime installer — sets up the desktop pet for the current user.
# Idempotent: safe to re-run; existing Cursor hooks are preserved.

set -euo pipefail

# ---- locate the dist directory we're running from ---------------------------
DIST_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---- destination layout -----------------------------------------------------
PET_DIR="$HOME/.cursor/pet"
HOOKS_DIR="$HOME/.cursor/hooks"
HOOKS_JSON="$HOME/.cursor/hooks.json"
APP_DST="$PET_DIR/CursorSlime.app"
APPS_LINK="$HOME/Applications/CursorSlime.app"

GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; DIM='\033[90m'; RESET='\033[0m'
say()  { printf "${GREEN}==>${RESET} %s\n" "$*"; }
warn() { printf "${YELLOW}!!${RESET}  %s\n" "$*"; }
die()  { printf "${RED}xx${RESET}  %s\n" "$*"; exit 1; }

# ---- 1. preflight checks ----------------------------------------------------
say "Checking macOS"
[ "$(uname -s)" = "Darwin" ] || die "This installer is for macOS only."

say "Looking for a usable Python (>= 3.11 with Tk 9.0 if possible)"
PYTHON_BIN=""
for candidate in \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /usr/local/bin/python3.13 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    "$(command -v python3.13 || true)" \
    "$(command -v python3.12 || true)" \
    "$(command -v python3.11 || true)" \
    "$(command -v python3 || true)"; do
    [ -z "$candidate" ] && continue
    [ -x "$candidate" ] || continue
    version=$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || echo "")
    case "$version" in
        3.11|3.12|3.13|3.14)
            PYTHON_BIN="$candidate"
            break
            ;;
    esac
done

if [ -z "$PYTHON_BIN" ]; then
    warn "No Python 3.11+ found. Install one and re-run:"
    warn "    brew install python@3.13"
    die "Aborting."
fi

PYTHON_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
say "Using Python: $PYTHON_BIN  (v$PYTHON_VER)"

if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
    die "Your Python doesn't have venv support. Try: brew install python@3.13"
fi

# ---- 2. install code --------------------------------------------------------
say "Creating $PET_DIR"
mkdir -p "$PET_DIR" "$HOOKS_DIR" "$HOME/Applications"

say "Copying source files"
install -m 0755 "$DIST_DIR/slime.py"      "$PET_DIR/slime.py"
install -m 0755 "$DIST_DIR/make_icon.py"  "$PET_DIR/make_icon.py"
install -m 0755 "$DIST_DIR/slimectl"      "$PET_DIR/slimectl"
install -m 0755 "$DIST_DIR/hooks/log-stats.sh" "$HOOKS_DIR/log-stats.sh"

# Bundle skeleton (icon generated later in step 5)
rm -rf "$APP_DST"
mkdir -p "$APP_DST/Contents/MacOS" "$APP_DST/Contents/Resources"
install -m 0644 "$DIST_DIR/app/Contents/Info.plist"     "$APP_DST/Contents/Info.plist"
install -m 0755 "$DIST_DIR/app/Contents/MacOS/CursorSlime" "$APP_DST/Contents/MacOS/CursorSlime"

# ---- 3. venv ----------------------------------------------------------------
say "Creating venv in $PET_DIR/venv"
if [ -d "$PET_DIR/venv" ] && "$PET_DIR/venv/bin/python3" -c "from PyQt6.QtCore import Qt" >/dev/null 2>&1; then
    say "  venv already has PyQt6 — skipping pip install"
else
    rm -rf "$PET_DIR/venv"
    "$PYTHON_BIN" -m venv "$PET_DIR/venv"
    say "Installing PyQt6 + pyobjc-framework-Cocoa (this takes ~30s)"
    "$PET_DIR/venv/bin/pip" install --quiet --upgrade pip
    "$PET_DIR/venv/bin/pip" install --quiet "PyQt6" "pyobjc-framework-Cocoa"
fi

# ---- 4. hook config ---------------------------------------------------------
say "Wiring Cursor hooks → $HOOKS_JSON"
if [ -f "$HOOKS_JSON" ]; then
    say "  existing hooks.json found — merging slime hook entries"
    cp "$HOOKS_JSON" "$HOOKS_JSON.bak.$(date +%s)"
    "$PET_DIR/venv/bin/python3" - <<'PY'
import json, os
p = os.path.expanduser("~/.cursor/hooks.json")
try:
    with open(p) as f:
        cfg = json.load(f)
except Exception:
    cfg = {}
cfg.setdefault("version", 1)
cfg.setdefault("hooks", {})
events = ["preToolUse", "postToolUse", "afterAgentResponse",
          "afterAgentThought", "stop", "sessionStart"]
for ev in events:
    arr = cfg["hooks"].setdefault(ev, [])
    if not any(h.get("command") == "./hooks/log-stats.sh" for h in arr):
        arr.append({"command": "./hooks/log-stats.sh"})
with open(p, "w") as f:
    json.dump(cfg, f, indent=2)
print("  merged.")
PY
else
    say "  creating fresh hooks.json"
    cat > "$HOOKS_JSON" <<'JSON'
{
  "version": 1,
  "hooks": {
    "preToolUse":         [ { "command": "./hooks/log-stats.sh" } ],
    "postToolUse":        [ { "command": "./hooks/log-stats.sh" } ],
    "afterAgentResponse": [ { "command": "./hooks/log-stats.sh" } ],
    "afterAgentThought":  [ { "command": "./hooks/log-stats.sh" } ],
    "stop":               [ { "command": "./hooks/log-stats.sh" } ],
    "sessionStart":       [ { "command": "./hooks/log-stats.sh" } ]
  }
}
JSON
fi

# ---- 5. generate icon -------------------------------------------------------
say "Generating pixel-art .icns"
"$PET_DIR/venv/bin/python3" "$PET_DIR/make_icon.py" >/dev/null

# ---- 6. register with Launch Services + Applications symlink ---------------
say "Installing into ~/Applications/"
rm -rf "$APPS_LINK"
ln -s "$APP_DST" "$APPS_LINK"

LS_REG="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
if [ -x "$LS_REG" ]; then
    "$LS_REG" -f "$APP_DST" >/dev/null 2>&1 || true
fi

# ---- 7. check for jq (required by hook) ------------------------------------
if ! command -v jq >/dev/null 2>&1; then
    warn "jq not found — the hook will silently no-op until you install it:"
    warn "    brew install jq"
fi

# ---- done -------------------------------------------------------------------
echo ""
printf "${GREEN}===========================================${RESET}\n"
printf "${GREEN} Cursor Slime installed.${RESET}\n"
printf "${GREEN}===========================================${RESET}\n"
cat <<EOF

Launch it:
  ${DIM}# from Spotlight${RESET}   Cmd+Space  →  Cursor Slime
  ${DIM}# from Finder${RESET}     open ~/Applications/CursorSlime.app
  ${DIM}# from terminal${RESET}   ~/.cursor/pet/slimectl start

Stop it:  click the ✕ button on the slime, or
          ~/.cursor/pet/slimectl stop

Files:
  app code     ~/.cursor/pet/
  hook script  ~/.cursor/hooks/log-stats.sh
  hook config  ~/.cursor/hooks.json
  app bundle   ~/Applications/CursorSlime.app  (symlink)

EOF
