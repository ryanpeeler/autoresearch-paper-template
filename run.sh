#!/usr/bin/env bash
# ============================================================================
# AutoResearch Paper Template — Run Pipeline
# ============================================================================
# Runs the AutoResearchClaw 23-stage pipeline and generates a PDF.
#
# Usage:
#   ./run.sh                    # Full pipeline run
#   ./run.sh --from PAPER_DRAFT # Resume from a specific stage
#   ./run.sh --pdf-only         # Skip pipeline, just regenerate PDF
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Parse args ──
FROM_STAGE=""
PDF_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --from)
            FROM_STAGE="$2"
            shift 2
            ;;
        --pdf-only)
            PDF_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./run.sh [--from STAGE_NAME] [--pdf-only]"
            exit 1
            ;;
    esac
done

# ── Activate venv ──
if [ ! -d ".venv" ]; then
    echo "ERROR: .venv not found. Run ./setup.sh first."
    exit 1
fi
source .venv/bin/activate

# ── Check config ──
if [ ! -f "config.yaml" ]; then
    echo "ERROR: config.yaml not found. Copy config.template.yaml and customize it."
    exit 1
fi

# Check if topic is still the placeholder
if grep -q "Replace this with your research topic" config.yaml; then
    echo "ERROR: config.yaml still has the placeholder topic."
    echo "Edit config.yaml with your actual research topic before running."
    exit 1
fi

# ── Run pipeline (unless --pdf-only) ──
if [ "$PDF_ONLY" = false ]; then
    echo "=== Running AutoResearchClaw Pipeline ==="
    echo ""

    EXTRA_ARGS=""
    if [ -n "$FROM_STAGE" ]; then
        EXTRA_ARGS="--from-stage $FROM_STAGE --resume"
        # Find the most recent artifact dir for resume
        LATEST_RUN=$(ls -td artifacts/rc-* 2>/dev/null | head -1)
        if [ -n "$LATEST_RUN" ]; then
            EXTRA_ARGS="$EXTRA_ARGS --output $LATEST_RUN"
            echo "Resuming from $FROM_STAGE in $LATEST_RUN"
        fi
    fi

    researchclaw run \
        --config config.yaml \
        --auto-approve \
        --skip-preflight \
        $EXTRA_ARGS

    echo ""
    echo "Pipeline complete."
fi

# ── Generate PDF ──
echo ""
echo "=== Generating PDF ==="

# Find the most recent run directory
LATEST_RUN=$(ls -td artifacts/rc-* 2>/dev/null | head -1)

if [ -z "$LATEST_RUN" ]; then
    echo "ERROR: No artifact runs found in artifacts/"
    exit 1
fi

echo "Using artifacts from: $LATEST_RUN"

# Look for paper_final.md in the deliverables or stage-22
PAPER_MD=""
for candidate in \
    "$LATEST_RUN/stage-22/paper_final.md" \
    "$LATEST_RUN/deliverables/paper_final.md" \
    "$LATEST_RUN/stage-19/paper_revised.md" \
    "$LATEST_RUN/stage-17/paper_draft.md" \
    "paper_final.md"; do
    if [ -f "$candidate" ]; then
        PAPER_MD="$candidate"
        break
    fi
done

if [ -z "$PAPER_MD" ]; then
    echo "ERROR: No paper markdown found in $LATEST_RUN"
    exit 1
fi

echo "Source: $PAPER_MD"

# Run PDF generator
python3 generate_pdf.py --input "$PAPER_MD" --config config.yaml --output paper.pdf

echo ""
echo "=== Done ==="
echo "PDF: paper.pdf"
echo ""
