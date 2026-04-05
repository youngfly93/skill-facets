# vNext Beta TODO

This file turns the current vNext-alpha roadmap into concrete implementation work for `skill-facets`.

## P0 Runtime 固化

- [x] Add `.claude/requirements.txt`
  Include at least `PyYAML`.
- [x] Add `.claude/bootstrap_env.sh`
  Create `.claude/.venv` and install dependencies from `requirements.txt`.
- [x] Add `.claude/scripts/doctor.py`
  Checks:
  - project Python path
  - `import yaml`
  - readable `.claude/skills.yaml`
  - validator CLI runnable
  - hook registration state
- [x] Update hook examples in [README.md](/Volumes/KINGSTON/work/research/skill_change/skill-facets/README.md)
  Use `.claude/.venv/bin/python` instead of ambient `python3`.

Acceptance:
- A fresh clone can run one command to prepare runtime.
- The same Python interpreter is used by hooks, validator, and router.

## P1 Router 安装体验

- [x] Add `.claude/install_local.sh`
  Idempotently create or update `.claude/settings.local.json`.
- [x] Inject `UserPromptSubmit` hook automatically
  Preserve existing settings where possible.
- [x] Upgrade [skill_switch.sh](/Volumes/KINGSTON/work/research/skill_change/skill-facets/.claude/skill_switch.sh)
  Turn it into a real status/doctor entrypoint.

Acceptance:
- Hook enablement no longer requires manual copy-paste.
- `bash .claude/install_local.sh` is safe to rerun.

## P2 Deliver Runner

- [x] Add `.claude/scripts/runner.py`
  Start with `deliver-v4` only.
- [x] Read from [skills.yaml](/Volumes/KINGSTON/work/research/skill_change/skill-facets/.claude/skills.yaml)
  Use:
  - `tools`
  - `workflow.states`
  - `workflow.transitions`
- [x] Enforce mandatory gates
  - missing `plan.md` aborts
  - failed audit aborts
  - failed ZIP verification blocks `done`
- [x] Write step events to `.claude/logs/*.jsonl`

Acceptance:
- `deliver-v4` can be executed by runtime state progression rather than prose alone.
- Mandatory tool calls are no longer advisory.

## P3 Validator 语义重构

- [x] Extend contract schema in [skills.yaml](/Volumes/KINGSTON/work/research/skill_change/skill-facets/.claude/skills.yaml)
  Add either:
  - `enforcement: machine|heuristic|human`
  or explicit buckets:
  - `machine_enforced`
  - `heuristic_review`
  - `human_review`
- [x] Make manifest lint reject fake hard constraints
  Rule: `hard_fail` without checker must fail lint or be downgraded.
- [x] Update [cli.py](/Volumes/KINGSTON/work/research/skill_change/skill-facets/.claude/scripts/constraint_validator/cli.py)
  Output:
  - `evidence`
  - `repair_hint`
  - `enforcement`

Acceptance:
- Hard constraints are consistently machine-backed or explicitly downgraded.
- Validation reports explain not only failure, but why and how to repair.

## P4 Checker 扩充

- [x] `sci-fig`
  Add:
  - axis label detection
  - legend detection
  - gridline detection
- [x] `bio-report`
  Add:
  - line spacing checker
  - margin checker
  - heading-level checker
  - figure-reference consistency checker
- [x] `ppt`
  Add:
  - title/summary structure checker
  - pure-bullet-page checker
  - image aspect-ratio checker

Acceptance:
- [x] Coverage of high-value machine-checkable constraints increases materially.
- [x] At least one flagship checker exists for each major command family.

## P5 Manifest 治理

- [ ] Add `.claude/scripts/lint_manifest.py`
  Checks:
  - `source` exists
  - `tool.script` exists
  - `checker` is registered
  - workflow states/transitions are internally consistent
  - trigger-only external entries are explicitly marked
- [ ] Integrate lint into `doctor.py`

Acceptance:
- Manifest errors are caught before runtime.
- `skills.yaml` becomes a reliable source of truth instead of a best-effort declaration.

## Beta Gate

Ship `vNext beta` only when all of the following are true:

- [x] Fresh project setup is one-command
- [x] Hook enablement is one-command
- [x] `cli.py <skill>` is manifest-first and stable
- [x] `deliver-v4` has runtime-enforced workflow execution
- [ ] A meaningful subset of hard constraints is machine-checkable
- [ ] `doctor.py` identifies environment and configuration problems quickly

## Suggested Order

1. Runtime bootstrap
2. Hook installer
3. Deliver runner
4. Validator schema/enforcement split
5. Checker expansion
6. Manifest lint
