#!/usr/bin/env sh
# Blueprint installer.
#
# Drops the seven bp-* skills and the tools they call into a target project,
# so a Claude Code session working in that project loads them automatically.
#
#   Run it from inside a clone of this repo:
#       sh install.sh /path/to/your/project      # defaults to the current dir
#
#   Or bootstrap it straight into the current project without cloning first:
#       (see the one-paste snippet in the README / INSTALL.md)
#
# The skills call the tools by the relative path `tools/…`, so the tools land
# at the project root next to `.claude/`. That is deliberate: it keeps the
# skill files identical whether they run here or in the project you install to.
set -eu

DEST="${1:-.}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$HERE/skills" ] || [ ! -d "$HERE/tools" ]; then
  echo "error: run this from a clone of the Blueprint repo (skills/ and tools/ not found next to install.sh)" >&2
  exit 1
fi

mkdir -p "$DEST/.claude/skills"
cp -r "$HERE"/skills/bp-* "$DEST/.claude/skills/"
mkdir -p "$DEST/tools"
cp "$HERE"/tools/*.py "$HERE"/tools/*.mjs "$DEST/tools/"

echo "Blueprint installed into: $DEST"
echo "  skills -> $DEST/.claude/skills/bp-{recon,tokens,model,spec,build,verify,brand}"
echo "  tools  -> $DEST/tools/"
echo
echo "Next, in that project, the capture step needs a browser:"
echo "  npm install playwright && npx playwright install chromium"
echo
echo "Then start a Claude Code session there and say, for example:"
echo "  use bp-recon on https://your-target.example"
