# Benchmark Suite

This directory holds fixture data for the `skill-facets` benchmark harness.

## Scope

The current suite measures three things:

1. `router`
   Top-1 / top-2 routing quality against a curated prompt dataset.
2. `compile`
   Drift between `skills.yaml` as source-of-truth and checked-in Markdown artifacts.
3. `mcp`
   Smoke-test generation and direct invocation of MCP bridge outputs for Tool Facet skills.

## Files

- [router_cases.json](/Volumes/KINGSTON/work/research/skill_change/skill-facets/benchmarks/router_cases.json)
  Curated routing cases. Each case contains:
  - `prompt`
  - `cwd`
  - `expected_top` or `expect_none`

## Run

```bash
.claude/.venv/bin/python .claude/scripts/benchmark_suite.py all --json
.claude/.venv/bin/python .claude/scripts/benchmark_suite.py router --profile core --json
.claude/.venv/bin/python .claude/scripts/benchmark_suite.py compile --json
.claude/.venv/bin/python .claude/scripts/benchmark_suite.py mcp --json
```

## Interpretation

- `router`
  Focus on `top1_accuracy` first. `top2_recall` is useful when the router intentionally returns two candidates.
- `compile`
  `exact_match_rate` should trend upward for author-owned Markdown assets if `skills.yaml` is truly becoming the authoring source of truth.
  `external_wrapper_count` is reported separately for skills that intentionally wrap external/global skills and therefore are not expected to have checked-in local Markdown sources.
- `mcp`
  This is a smoke suite, not a full protocol compliance test. It is meant to catch generation regressions and obvious invocation failures.
