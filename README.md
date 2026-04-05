# skill-facets

A universal skill enhancement framework for AI agents. Extends the [Anthropic Skills](https://github.com/anthropics/skills) standard with runtime-level capabilities that any domain can use.

## What It Does

The Anthropic Skills standard uses Markdown + YAML frontmatter with description-based semantic matching. skill-facets adds four layers on top — without replacing the standard:

| Layer | Problem Solved | How |
|-------|---------------|-----|
| **Trigger Router** | 250-char description matching is probabilistic | Keyword + file pattern pre-filter via hook |
| **Nested Signals** | Constraints and aspirations conflict in flat prose | CONSTRAINT > ASPIRATION > FREEDOM hierarchy |
| **Constraint Validator** | No post-execution verification | Typed checkers with severity + repair hints |
| **Runtime Runner** | Workflow steps are prose, not enforced | State machine gates + Tool Facet scripts |

## Quick Start

```bash
# Install into your project (empty template)
bash /path/to/skill-facets/install.sh

# Or with a domain example
bash /path/to/skill-facets/install.sh --example bioinformatics
bash /path/to/skill-facets/install.sh --example web-development
```

Then:
```bash
cd your-project
bash .claude/bootstrap_env.sh      # Create venv + install deps
bash .claude/install_local.sh      # Register hook
```

## Project Structure

```
skill-facets/
├── framework/                     # Generic framework (use in any domain)
│   ├── manifest.py                  skills.yaml loader
│   ├── skill_compile.py             YAML → Markdown compiler
│   ├── mcp_bridge.py                Tool Facet → MCP server generator
│   ├── runner.py                    Workflow state machine
│   ├── router/skill_router.py       Trigger router (hook)
│   ├── constraint_validator/        Post-execution checkers
│   │   ├── cli.py
│   │   └── checkers/                font, color, DPI, format, content, layout, ppt
│   ├── runtime_profile.py           Core/Full profile system
│   ├── logger.py                    JSONL observability
│   ├── doctor.py                    Environment health check
│   └── lint_manifest.py             Manifest validation
│
├── templates/                     # Empty templates for new projects
│   ├── skills.yaml.template         Manifest skeleton (0 skills)
│   ├── command.md.template          V4 nested signal template
│   ├── skill.md.template            Dual facet template
│   └── runtime_profile.yaml.template
│
├── examples/                      # Domain-specific examples
│   ├── bioinformatics/              SCI figures, Word reports, delivery packaging
│   └── web-development/            React components, API endpoints
│
├── install.sh                     # One-line installer
├── bin/skill-facets               # CLI entry point
├── tests/                         # 54 tests
└── docs/                          # User documentation
```

## The Three Signals

Traditional skill instructions mix hard requirements with soft goals. skill-facets separates them into a nested hierarchy:

```markdown
## Boundary (CONSTRAINT)
- Font must be SimHei for Chinese        ← must comply, machine-checkable

  ### Aspire within boundary (ASPIRATION)
  - Visually rich: gradients, decorations  ← aim high, model takes initiative

    #### Decide freely (FREEDOM)
    - Color palette (unless user specifies)  ← model's autonomous choice
```

**Why nesting matters**: In flat layout, FREEDOM can override CONSTRAINT. Nesting makes the hierarchy explicit — FREEDOM operates within ASPIRATION, which operates within CONSTRAINT.

## skills.yaml Manifest

All skill definitions live in one file — trigger, contract, tools, and workflow:

```yaml
schema_version: "1.1"
skills:
  my-skill:
    version: "1.0"
    type: command
    source: commands/my-skill.md
    trigger:
      keywords: [keyword1, keyword2]
      priority: 10
    contract:
      constraints:
        - id: output_format
          type: format
          rule: "output must be .png"
          severity: hard_fail
          enforcement: machine
          checker: format_checker
          params: {allowed: [".png"]}
          repair_hint: "Save as .png"
      aspirations:
        - "High quality output"
      freedoms:
        - "Specific approach"
```

## Compiler

skills.yaml is the single authoring source. Markdown is a compilation target:

```bash
skill-facets compile my-skill          # Preview
skill-facets compile --all --write     # Generate all .md files
```

## Validation

```bash
skill-facets validate my-skill ./output/
```

Each constraint has:
- **severity**: hard_fail / soft_warn / manual_review
- **enforcement**: machine / heuristic / human
- **repair_hint**: tells the model how to fix violations

## Domain Examples

### Bioinformatics
SCI figure generation, Word report delivery, audit-fix loops. See [examples/bioinformatics/](examples/bioinformatics/).

### Web Development
React component scaffolding, API endpoint creation. See [examples/web-development/](examples/web-development/).

### Create Your Own
1. `bash install.sh` (empty template)
2. Edit `.claude/skills.yaml`
3. `skill-facets compile --all --write`
4. Use your skills in Claude Code

See [docs/authoring-guide.md](docs/authoring-guide.md) for details.

## Runtime Profiles

- **core**: Only machine-enforced constraints (stable, deterministic)
- **full**: Adds heuristic + human review (experimental)

## Requirements

- Python 3.10+
- PyYAML
- Pillow (for image checkers)

## License

MIT
