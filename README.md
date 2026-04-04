# skill-facets

A project-level skill sandbox for Claude Code that extends the [Anthropic Skills](https://github.com/anthropics/skills) standard with three architectural layers:

1. **Nested Signal Specification** — CONSTRAINT > ASPIRATION > FREEDOM (V4)
2. **Dual Facet Architecture** — Tool Facet (scripts) + Prompt Facet (Markdown)
3. **Trigger Router + Constraint Validator** — deterministic pre-filter and post-execution checks

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
├── skill_triggers.yaml                # Trigger Manifest (11 skills)
│
└── scripts/constraint_validator/      # Validation Layer
    ├── cli.py                           CLI entry point
    ├── parser.py                        CONSTRAINT extractor (13 patterns)
    └── checkers/                        Automated checkers
        ├── font_checker.py                OOXML font validation
        ├── color_checker.py               background color (PIL)
        ├── dpi_checker.py                 resolution check
        └── content_checker.py             numbering, Markdown residue
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

### Enable Trigger Router (optional)

Add to your project's `.claude/settings.local.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/skill_router.py",
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

## Usage

Once installed, use commands as normal — the V4 versions activate automatically:

```
/ppt              → V4 nested signal PPT creation
/sci-fig          → V4 nested signal SCI figure
/audit-fix        → V4 nested signal audit-fix loop
/bio-report       → V4 nested signal Word report
/validate sci-fig → check figures against CONSTRAINT
```

## Current Limitations

- **Trigger router** requires project-level hook registration (not auto-enabled)
- **Validator coverage** is ~15% of all constraints (font, color, DPI, numbering, Markdown residue). Layout, logic clarity, and visual richness still require human review.
- **Nested signal** is still prompt discipline, not runtime semantics — the model reads Markdown headings, not a type system
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
