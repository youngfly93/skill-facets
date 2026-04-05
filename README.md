# skill-facets

A project-level skill sandbox for Claude Code that extends the [Anthropic Skills](https://github.com/anthropics/skills) standard with three architectural layers:

1. **Nested Signal Specification** — CONSTRAINT > ASPIRATION > FREEDOM (V4)
2. **Dual Facet Architecture** — Tool Facet (scripts) + Prompt Facet (Markdown)
3. **Trigger Router + Constraint Validator** — deterministic pre-filter and post-execution checks

Runtime note: `skills.yaml` now has an explicit `PyYAML` dependency. The previous handwritten YAML fallback was removed because it could not reliably parse nested vNext manifests.

Profile note: the runtime is now split into:

- `core`: the default stable surface — manifest, router, runner, and `machine/runtime` validation
- `full`: experimental extensions — heuristic validators, human-review surfaces, and legacy parser compatibility

Validator note: `skills.yaml` uses explicit `enforcement` semantics:

- `machine`: backed by a checker or runtime gate
- `heuristic`: partly automatable but not yet a hard gate
- `human`: review-only guidance

For runtime-enforced constraints such as `deliver-v4`, `validate` now reports `runtime_enforced` instead of pretending they are manual checks.

Stability note: constraints in [skills.yaml](/Volumes/KINGSTON/work/research/skill_change/skill-facets/.claude/skills.yaml) now also carry explicit `stability: core|experimental`. The runtime profile filters against this field first, rather than inferring everything from `enforcement`.

## Background

The standard Anthropic Skill system uses Markdown + YAML frontmatter with progressive disclosure (Catalog → Instructions → Resources). Through roundtable discussion and blind testing, we identified three structural gaps:

| Gap | Problem | Our Solution |
|-----|---------|--------------|
| **Signal confusion** | CONSTRAINT and ASPIRATION in flat prose → model either over-constrains or over-creates | V4 nested signals with explicit hierarchy |
| **Tool/Knowledge mixing** | Scripts and workflow guidance in one file → code hallucination | Dual Facet: separate Tool (scripts) from Prompt (Markdown) |
| **Trigger unreliability** | 250-char description semantic matching → undertrigger | Keyword + file pattern router via UserPromptSubmit hook |
| **No verification** | CONSTRAINT is prose, not runtime-checkable | Constraint parser + automated checkers |

## Architecture

```
.claude/
├── commands/                          # V4 Nested Signal Commands
│   ├── ppt.md                           CONSTRAINT > ASPIRATION > FREEDOM
│   ├── sci-fig.md                       expanded from 1 line to 25 lines
│   ├── audit-fix.md                     workflow with priority tiers
│   ├── bio-report.md                    11 constraints + 6 aspirations
│   └── validate.md                      post-execution constraint checker
│
├── skills/deliver-v4/                 # Dual Facet Skill
│   ├── SKILL.md                         Prompt Facet (nested signals)
│   └── scripts/                         Tool Facet (deterministic)
│       ├── zip_pack.py                    pack / verify / checksum
│       └── ai_trace_scan.py               scan / clean
│
├── hooks/skill_router.py             # Trigger Layer
├── runtime_profile.yaml              # Core vs Experimental split
├── skill_triggers.yaml                # Experimental compatibility fallback
│
└── scripts/                           # Runtime + Validation Layer
    ├── runner.py                        deliver-v4 manifest-driven runner
    ├── runtime_profile.py               profile loader
    ├── constraint_validator/
    │   ├── cli.py                       CLI entry point
    │   ├── parser.py                    CONSTRAINT extractor (13 patterns)
    │   └── checkers/                    Automated checkers
    │       ├── font_checker.py            OOXML font validation
    │       ├── color_checker.py           background color (PIL)
    │       ├── dpi_checker.py             resolution check
    │       ├── content_checker.py         numbering, Markdown residue
    │       ├── figure_checker.py          axis/legend/gridline heuristics
    │       ├── layout_checker.py          DOCX spacing/margins/headings
    │       └── ppt_checker.py             slide structure / bullet / image ratio
```

## The Three Signals

Traditional skill instructions mix hard requirements with soft goals:

> "配色舒服、逻辑清晰、中文黑体、Times New Roman、图片等比例"

V4 separates them into a nested hierarchy:

```markdown
## Boundary (CONSTRAINT)
- Font: SimHei for Chinese         ← must comply, machine-checkable
- Font: Times New Roman for English

  ### Aspire within boundary (ASPIRATION)
  - Visually rich: gradients, decorations  ← aim high, model takes initiative

    #### Decide freely (FREEDOM)
    - Color palette (unless user specifies)  ← model's autonomous choice
```

**Why nesting matters**: In flat (parallel) layout, FREEDOM can override CONSTRAINT. Nesting makes the hierarchy explicit — FREEDOM operates within ASPIRATION, which operates within CONSTRAINT.

## Blind Test Results

We ran 5 rounds of blind tests (V0 → V2 → V3 → V4) comparing signal architectures on PPT generation:

| Signal Type | CONSTRAINT Hit | Media Assets | Creativity |
|-------------|---------------|--------------|------------|
| V0 (pure ASPIRATION) | partial | 20 | high |
| V2 (pure CONSTRAINT) | **100%** | **0** | suppressed |
| V3 (parallel signals) | 100% | **27** | high |
| V4 (nested signals) | 100% | 24 | high |

Key finding: **CONSTRAINT improves precision but suppresses creativity. ASPIRATION restores it. FREEDOM must be nested under CONSTRAINT to avoid conflicts.**

## Real Project Comparison

Using a mock RNA-seq analysis project (PCA, volcano plot, GO enrichment):

| Dimension | V0 (1-line) | V4 (nested) |
|-----------|-------------|-------------|
| White background | ✅ | ✅ |
| No gridlines | ✅ | ✅ |
| 300 DPI | ✅ | ✅ |
| Chart titles | **0/3** | **3/3** |
| Color-blind friendly | ❌ | ✅ (Okabe-Ito) |
| Confidence ellipses (PCA) | ❌ | ✅ |
| Bubble labels (GO) | ❌ | ✅ |

V4's main gain over V0 is not stricter constraints — it's higher aspirations.

See `examples/real_project/figures/` for side-by-side comparison.

## Installation

Copy `.claude/` into your project root:

```bash
git clone https://github.com/youngfly93/skill-facets.git
cp -r skill-facets/.claude/ your-project/.claude/
```

Project-level `.claude/commands/` will override same-named global commands when Claude Code runs in that directory. Your global `~/.claude/` remains untouched.

### Bootstrap Runtime

Create a project-local virtualenv and install the runtime dependency set:

```bash
bash .claude/bootstrap_env.sh
```

### Install Project Hook

Register the router hook into project-local `.claude/settings.local.json`:

```bash
bash .claude/install_local.sh
```

This command is idempotent. It creates or updates the project-local settings file and points the hook to the project `.claude/.venv`.

### Manual Hook Example

If you prefer to edit settings yourself, use:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/.venv/bin/python $CLAUDE_PROJECT_DIR/.claude/hooks/skill_router.py",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

### Check Status

```bash
bash .claude/skill_switch.sh
```

### Run Doctor

Verify the runtime environment and hook configuration:

```bash
.claude/.venv/bin/python .claude/scripts/doctor.py
```

### Runtime Profiles

The default profile is `core`, configured in [runtime_profile.yaml](/Volumes/KINGSTON/work/research/skill_change/skill-facets/.claude/runtime_profile.yaml).

- `core`
  Minimal stable runtime surface. Includes manifest-driven routing, runner gates, and `machine` / `runtime_enforced` constraints only.
- `full`
  Experimental add-ons. Re-enables `heuristic` and `human` review constraints, plus explicit legacy `--file` parser mode.

In other words:

- `stability=core`
  Part of the default vNext runtime surface.
- `stability=experimental`
  Opt-in only. Usually heuristic checks, noisy validators, or compatibility paths.

Legacy note:

- `skill_triggers.yaml`
  No longer part of the default vNext core path. It is retained only as an experimental compatibility fallback for environments that still need the old V4 trigger manifest shape.

Examples:

```bash
.claude/.venv/bin/python .claude/scripts/constraint_validator/cli.py sci-fig examples/real_project/figures
.claude/.venv/bin/python .claude/scripts/constraint_validator/cli.py --profile full sci-fig examples/real_project/figures
.claude/.venv/bin/python .claude/scripts/constraint_validator/cli.py --profile full --file .claude/commands/sci-fig.md
```

### Lint the Manifest

Check whether hard constraints are honestly classified:

```bash
.claude/.venv/bin/python .claude/scripts/lint_manifest.py --json --cwd .
```

## Usage

Once installed, use commands as normal — the V4 versions activate automatically:

```
/ppt              → V4 nested signal PPT creation
/sci-fig          → V4 nested signal SCI figure
/audit-fix        → V4 nested signal audit-fix loop
/bio-report       → V4 nested signal Word report
/validate sci-fig → core profile validation
/validate --profile full sci-fig → full experimental validation
/validate --profile full --file .claude/commands/sci-fig.md → explicit legacy parser mode
```

### Run `deliver-v4` via Runtime

`deliver-v4` is no longer prompt-only. Use the manifest-driven runner to enforce the workflow gates:

```bash
.claude/.venv/bin/python .claude/scripts/runner.py deliver-v4 \
  --project-root /path/to/project \
  --audit-json /path/to/audit.json \
  --existing replace \
  --include plan.md \
  --include report.docx \
  --include results \
  --doc-verify auto
```

Current `deliver-v4` runtime behavior:

- `init` enforces `plan.md` presence
- `audit` blocks the run unless `P0 == 0` and `P1 == 0`
- `collect` either copies explicit `--include` paths or reuses an existing `delivery/`
- `scan` enforces `scan -> clean -> scan`
- `verify_doc auto` performs a lightweight OOXML integrity check for `.docx`
- `checksum`, `pack`, and `verify_zip` are mandatory tool calls

## Current Limitations

- **Trigger router** requires project-level hook registration (not auto-enabled)
- **Manifest loader** requires `PyYAML`; `bootstrap_env.sh` installs it into the project-local `.claude/.venv`
- **Core is now the default runtime surface** — this keeps day-to-day use smaller and more stable, but it also means some heuristic checks and the legacy trigger manifest path are no longer active unless you opt into `--profile full`
- **Validator coverage** is improved but still incomplete: checker-backed constraints now cover font, color, DPI, numbering, Markdown residue, format, DOCX layout, figure legend/axis/grid heuristics, and PPT structure/image ratio. Some important quality signals remain `human` or `heuristic`.
- **Some heuristics are intentionally noisy**: `no_gridlines` may still soft-warn on figures with dense guide-like marks, and `img_aspect` is currently strict enough to flag intentionally stretched decorative images in PPT.
- **Named validation is manifest-first** — `/validate <skill>` no longer silently falls back to Markdown parsing; use `--file` for explicit legacy validation
- **Legacy parser is now explicitly experimental** — it is disabled in `core` and only available in `full`
- **Single-file validation is supported** — `/validate <skill> path/to/file.docx` now validates that file directly instead of only working in directory mode
- **Constraint semantics are stricter** — `hard_fail` now implies machine enforcement; review-only rules were downgraded rather than left as fake hard constraints
- **Nested signal** is still prompt discipline, not runtime semantics — the model reads Markdown headings, not a type system
- **`deliver-v4` runtime is intentionally partial** — `collect` still depends on explicit `--include` inputs or a prepared `delivery/`, and `.docx` verification is currently a lightweight built-in check rather than a dedicated tool facet
- The example commands are bioinformatics-focused; adapt `skill_triggers.yaml` and commands for your domain

## Project Structure Explained

```
examples/
├── blind_test/              5 rounds of PPT blind test outputs
├── real_project/            RNA-seq figures: V0 vs V4 side-by-side
│   └── figures/               pca_plot.png vs pca_plot_v4.png, etc.
└── v0_baseline/             Original V0 commands for comparison
```

## License

MIT
