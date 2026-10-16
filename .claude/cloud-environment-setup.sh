#!/usr/bin/env bash
# Setup script for the Claude project's cloud environment, "programme"
# (delphside/tile-lite-elite#485, R4). Pasted into the environment's settings
# by the owner; this file is the reviewed copy.
#
# Cloud threads start in the workspace folder ($CLAUDE_PROJECT_DIR) with every
# project repository cloned beside each other, so no repository's own
# .claude/settings.json hooks run.
# This writes a user-level SessionStart hook that runs each repository's
# .claude/cloud-setup.sh with CLAUDE_PROJECT_DIR set to that repository.
# Only cloud-setup.sh is wired: the other repository hooks call gh, which
# cannot sign in from a cloud thread.
#
# It also installs the desktop client's libraries, which are slow and so
# belong here, where the result is cached (Tile Lite Elite's docs/4.3.1).
#
# Never fails: a non-zero exit would stop every session starting.

mkdir -p /root/.claude
python3 - <<'PY' || echo "setup: could not write /root/.claude/settings.json" >&2
import json, os
p = "/root/.claude/settings.json"
try:
    s = json.load(open(p))
except Exception:
    s = {}
cmd = ('for f in "${CLAUDE_PROJECT_DIR:-$PWD}"/*/.claude/cloud-setup.sh; do '
       '[ -x "$f" ] && CLAUDE_PROJECT_DIR="$(dirname "$(dirname "$f")")" "$f" </dev/null; '
       'done; exit 0')
entry = {"matcher": "startup|resume",
         "hooks": [{"type": "command", "command": cmd, "timeout": 300,
                    "statusMessage": "Installing each repository's build and test tools..."}]}
hooks = s.setdefault("hooks", {}).setdefault("SessionStart", [])
hooks[:] = [h for h in hooks if "cloud-setup.sh" not in json.dumps(h)] + [entry]
json.dump(s, open(p, "w"), indent=2)
PY

apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    libwebkit2gtk-4.1-dev libgtk-3-dev libxdo-dev \
    || echo "setup: desktop libraries not installed" >&2

exit 0
