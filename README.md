# AutoResearch Paper Template

A clean template for generating research papers using [AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw) with a Claude Max subscription (no API keys needed).

## Quick Start

```bash
# 1. Clone this template for your new paper
gh repo create my-new-paper --private --clone
cd my-new-paper
cp -r /path/to/autoresearch-paper-template/* .
cp /path/to/autoresearch-paper-template/.gitignore .

# 2. Set up the environment
chmod +x setup.sh run.sh
./setup.sh

# 3. Edit config.yaml with your topic, domains, and author
#    (setup.sh creates it from config.template.yaml)

# 4. Run the pipeline
./run.sh
```

## What's Included

| File | Purpose |
|---|---|
| `config.template.yaml` | Paper configuration template — copy to `config.yaml` and customize |
| `setup.sh` | One-command setup: clones framework, creates venv, installs deps, applies patches |
| `run.sh` | One-command pipeline run + PDF generation |
| `generate_pdf.py` | Parameterized PDF generator (reads author/title from config) |
| `patches/` | Fixes for known framework issues |

## Configuration

Edit `config.yaml` before running. Key fields:

```yaml
project:
  name: "my-paper"
  mode: "docs-first"        # "docs-first" for review articles, "full-auto" for empirical

research:
  topic: >-
    Your detailed research topic here...
  domains:
    - "domain 1"
    - "domain 2"

author: "Your Name"
```

## Pipeline Modes

- **`docs-first`** — Review/analytical articles. Skips experiment execution. Paper is written from literature synthesis only. No fabricated statistics.
- **`full-auto`** — Empirical papers with code generation and experiment execution. Requires experiment sandbox configuration.
- **`semi-auto`** — Pauses at gate stages (5, 9, 20) for human review before proceeding.

## Resuming a Failed Run

```bash
# Resume from a specific stage
./run.sh --from PAPER_DRAFT

# Regenerate PDF without rerunning the pipeline
./run.sh --pdf-only
```

## Output

After a successful run:

- `paper.pdf` — Final PDF at repo root
- `paper_final.md` — Markdown source (if manually written or extracted)
- `artifacts/rc-YYYYMMDD-HHMMSS-HASH/` — Full pipeline outputs (23 stages)

## Patches Applied by setup.sh

1. **ACP Client** (`patches/acp_client.py`) — Replaces the `acpx` bridge with direct `claude --print` calls. No `@zed-industries/claude-agent-acp` dependency needed.
2. **Docs-First Bypass** (`patches/paper_writing_bypass.patch`) — Allows paper writing to proceed without experiment metrics when `mode: "docs-first"`.

## Requirements

- Python 3.11+
- Claude Code CLI (`claude`) — authenticated with a Claude Max subscription
- `git`, `gh` (GitHub CLI)

## Generated with

[AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw) v0.3.1
