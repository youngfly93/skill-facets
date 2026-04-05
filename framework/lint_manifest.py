#!/usr/bin/env python3
"""Manifest lint focused on constraint enforcement semantics."""

from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from manifest import ManifestLoadError, load_manifest


VALID_ENFORCEMENTS = {"machine", "heuristic", "human"}
VALID_ENFORCED_BY = {"checker", "runtime", "human"}
VALID_STABILITIES = {"core", "experimental"}


def lint_constraints(manifest):
    errors = []
    warnings = []

    for skill_name, skill in manifest.get("skills", {}).items():
        contract = skill.get("contract") or {}
        for idx, constraint in enumerate(contract.get("constraints", []), start=1):
            cid = constraint.get("id") or f"constraint_{idx}"
            prefix = f"{skill_name}.{cid}"
            severity = constraint.get("severity", "manual_review")
            enforcement = constraint.get("enforcement")
            checker = constraint.get("checker")
            enforced_by = constraint.get("enforced_by")
            stability = constraint.get("stability")

            if not enforcement:
                errors.append(f"{prefix}: missing enforcement")
                continue

            if enforcement not in VALID_ENFORCEMENTS:
                errors.append(f"{prefix}: invalid enforcement={enforcement}")
                continue

            if enforced_by and enforced_by not in VALID_ENFORCED_BY:
                errors.append(f"{prefix}: invalid enforced_by={enforced_by}")

            if not stability:
                errors.append(f"{prefix}: missing stability (core|experimental)")
            elif stability not in VALID_STABILITIES:
                errors.append(f"{prefix}: invalid stability={stability}")

            if severity == "hard_fail":
                if enforcement != "machine":
                    errors.append(
                        f"{prefix}: hard_fail must use enforcement=machine or be downgraded"
                    )
                elif not checker and enforced_by != "runtime":
                    errors.append(
                        f"{prefix}: hard_fail machine constraint needs checker or enforced_by=runtime"
                    )

            if checker and enforced_by == "runtime":
                warnings.append(f"{prefix}: checker is ignored when enforced_by=runtime")

    return {
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Lint skills.yaml constraint enforcement semantics")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--cwd", default=os.getcwd(), help="Project root or search anchor")
    args = parser.parse_args()

    try:
        manifest = load_manifest(cwd=args.cwd, search_paths=[args.cwd])
    except ManifestLoadError as exc:
        report = {"error_count": 1, "warning_count": 0, "errors": [str(exc)], "warnings": []}
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"[FAIL] {exc}")
        return 2

    report = lint_constraints(manifest)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for msg in report["errors"]:
            print(f"[FAIL] {msg}")
        for msg in report["warnings"]:
            print(f"[WARN] {msg}")
        if report["error_count"] == 0 and report["warning_count"] == 0:
            print("[OK] manifest lint passed")

    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
