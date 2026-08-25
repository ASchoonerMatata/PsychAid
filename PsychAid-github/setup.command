#!/bin/bash
echo "╔══════════════════════════════╗"
echo "║     PsychAid Setup           ║"
echo "╚══════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:$PATH"

# ── Find Python 3 ──
PYTHON3=$(which python3 2>/dev/null)
if [ -z "$PYTHON3" ]; then
    osascript -e 'display alert "Python 3 Required" message "Please install Python 3 from python.org, then run setup.command again." as critical'
    exit 1
fi
echo "✓  Python found: $PYTHON3 ($(python3 --version 2>&1))"

# ── Install Python dependencies ──
echo ""
echo "Installing dependencies (first run may take a minute)..."
"$PYTHON3" -m pip install \
    flask reportlab pypdf anthropic python-docx mammoth \
    pywebview pyobjc pyobjc-framework-WebKit \
    --break-system-packages --quiet 2>&1 | grep -v "already satisfied" | grep -v "^$"
echo "✓  Dependencies ready"

# ── Make app launcher executable ──
chmod +x "$SCRIPT_DIR/PsychAid.app/Contents/MacOS/PsychAid"
echo "✓  App launcher ready"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Setup complete!                     ║"
echo "║  Double-click PsychAid.app to launch ║"
echo "╚══════════════════════════════════════╝"

osascript -e 'display alert "PsychAid Ready" message "Setup complete. Double-click PsychAid.app to launch." as informational'
