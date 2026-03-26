#!/usr/bin/env bash
# ============================================================================
# AutoResearch Paper Template — Setup
# ============================================================================
# Clones the AutoResearchClaw framework, creates a Python venv, installs
# dependencies, and applies patches for reliable operation.
#
# Usage: ./setup.sh
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== AutoResearch Paper Template Setup ==="
echo ""

# ── 1. Check prerequisites ──
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is required. Install Python 3.11+ first."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PY_VERSION"

if ! command -v git &>/dev/null; then
    echo "ERROR: git is required."
    exit 1
fi

# ── 2. Clone AutoResearchClaw framework (if not already present) ──
if [ ! -d "researchclaw" ]; then
    echo ""
    echo "Cloning AutoResearchClaw framework..."
    # Clone into a temp dir, then move just what we need
    TEMP_CLONE=$(mktemp -d)
    git clone --depth 1 https://github.com/aiming-lab/AutoResearchClaw.git "$TEMP_CLONE" 2>&1 | tail -1

    # Move framework source into place
    mv "$TEMP_CLONE/researchclaw" ./researchclaw
    mv "$TEMP_CLONE/pyproject.toml" ./pyproject.toml
    mv "$TEMP_CLONE/prompts.default.yaml" ./prompts.default.yaml 2>/dev/null || true
    mv "$TEMP_CLONE/config.researchclaw.example.yaml" ./config.researchclaw.example.yaml 2>/dev/null || true

    rm -rf "$TEMP_CLONE"
    echo "Framework cloned."
else
    echo "Framework already present (researchclaw/ exists)."
fi

# ── 3. Create config.yaml if not present ──
if [ ! -f "config.yaml" ]; then
    echo ""
    echo "Creating config.yaml from template..."
    cp config.template.yaml config.yaml
    echo "IMPORTANT: Edit config.yaml with your topic, domains, and author before running."
else
    echo "config.yaml already exists."
fi

# ── 4. Create Python venv and install ──
if [ ! -d ".venv" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo ""
echo "Installing dependencies..."
source .venv/bin/activate
pip install -q -e ".[all]" 2>&1 | tail -3
pip install -q reportlab 2>&1 | tail -1
echo "Dependencies installed."

# ── 5. Apply patches ──
echo ""
echo "Applying patches..."

# Patch 1: ACP client — use claude CLI directly instead of acpx
if [ -f "patches/acp_client.py" ]; then
    cp patches/acp_client.py researchclaw/llm/acp_client.py
    echo "  Applied: ACP client (claude --print mode)"
fi

# Patch 2: Paper writing stage — docs-first bypass for simulated data + no-metrics blocks
if [ -f "patches/apply_docs_first_bypass.py" ]; then
    python3 patches/apply_docs_first_bypass.py
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml with your topic, domains, and author"
echo "  2. Run: ./run.sh"
echo ""
