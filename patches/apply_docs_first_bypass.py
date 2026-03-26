#!/usr/bin/env python3
"""Apply docs-first bypass patches to _paper_writing.py.

Patches two hard blocks that prevent paper writing in docs-first (review article) mode:
1. R10: "all data is simulated" block
2. R4-2: "no real metrics" block for empirical domains

These blocks are designed for empirical papers but incorrectly fire for review articles
where no experiments are expected.
"""

import re
import sys
from pathlib import Path

TARGET = Path("researchclaw/pipeline/stage_impls/_paper_writing.py")

if not TARGET.exists():
    print(f"  ERROR: {TARGET} not found. Run setup.sh first.")
    sys.exit(1)

content = TARGET.read_text(encoding="utf-8")
changed = False

# ── Patch 1: R10 "all simulated" block ──
# Wrap the entire block in a project mode check
OLD_R10 = '''    # R10: HARD BLOCK — refuse to write paper when all data is simulated
    all_simulated = True
    for stage_subdir in sorted(run_dir.glob("stage-*/runs")):'''

NEW_R10 = '''    # R10: HARD BLOCK — refuse to write paper when all data is simulated
    # For docs-first / review articles, simulated data is expected — skip this block
    _project_mode_r10 = getattr(getattr(config, "project", None), "mode", "").lower()
    if _project_mode_r10 not in ("docs-first",):
        all_simulated = True
        for stage_subdir in sorted(run_dir.glob("stage-*/runs")):'''

if OLD_R10 in content and "_project_mode_r10" not in content:
    # Need to indent the entire R10 block by 4 spaces and add the else clause
    # Find the end of the R10 block (the return statement)
    r10_start = content.index(OLD_R10)

    # Find "    if all_simulated:" after the loop
    all_sim_check = "    if all_simulated:"
    all_sim_idx = content.index(all_sim_check, r10_start)

    # Find the end of the return StageResult block
    # Look for the closing paren of StageResult followed by a blank line
    return_pattern = re.compile(
        r"        return StageResult\(\s*\n"
        r"            stage=Stage\.PAPER_DRAFT,\s*\n"
        r"            status=StageStatus\.FAILED,\s*\n"
        r"            artifacts=\(\"paper_draft\.md\",\),\s*\n"
        r"            evidence_refs=\(\),\s*\n"
        r"        \)",
        re.MULTILINE,
    )
    match = return_pattern.search(content, all_sim_idx)
    if match:
        block_end = match.end()
        # Extract the block from all_simulated=True to the return
        old_block = content[r10_start:block_end]

        # Indent the loop and conditional by 4 spaces
        lines = old_block.split("\n")
        new_lines = []
        new_lines.append("    # R10: HARD BLOCK — refuse to write paper when all data is simulated")
        new_lines.append("    # For docs-first / review articles, simulated data is expected — skip this block")
        new_lines.append('    _project_mode_r10 = getattr(getattr(config, "project", None), "mode", "").lower()')
        new_lines.append('    if _project_mode_r10 not in ("docs-first",):')
        for line in lines:
            if line.startswith("    # R10:"):
                continue  # skip original comment, already added
            if line.strip() == "":
                new_lines.append(line)
            else:
                new_lines.append("    " + line)
        new_lines.append("    else:")
        new_lines.append('        logger.info(')
        new_lines.append('            "Docs-first mode: skipping simulated data check (review article)."')
        new_lines.append('        )')

        new_block = "\n".join(new_lines)
        content = content[:r10_start] + new_block + content[block_end:]
        changed = True
        print("  Patched: R10 simulated data block (docs-first bypass)")
    else:
        print("  WARNING: Could not find R10 return block pattern")
elif "_project_mode_r10" in content:
    print("  Skipped: R10 bypass (already applied)")
else:
    print("  WARNING: Could not find R10 block to patch")

# ── Patch 2: R4-2 "no real metrics" block ──
OLD_R4 = """    _empirical_domains = {"ml", "engineering", "biology", "chemistry"}
    if not has_real_metrics:
        if _domain_id in _empirical_domains:"""

NEW_R4 = """    _empirical_domains = {"ml", "engineering", "biology", "chemistry"}
    _project_mode_r4 = getattr(getattr(config, "project", None), "mode", "").lower()
    if not has_real_metrics:
        if _project_mode_r4 in ("docs-first",):
            logger.info(
                "No experiment metrics found, but project mode is '%s' (review article). "
                "Proceeding with paper draft based on literature synthesis.",
                _project_mode_r4,
            )
        elif _domain_id in _empirical_domains:"""

if OLD_R4 in content and "_project_mode_r4" not in content:
    content = content.replace(OLD_R4, NEW_R4, 1)
    changed = True
    print("  Patched: R4-2 no-metrics block (docs-first bypass)")
elif "_project_mode_r4" in content:
    print("  Skipped: R4-2 bypass (already applied)")
else:
    print("  WARNING: Could not find R4-2 block to patch")

if changed:
    TARGET.write_text(content, encoding="utf-8")
    print("  Patches written successfully.")
else:
    print("  No changes needed.")
