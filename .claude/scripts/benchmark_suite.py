#!/usr/bin/env python3
"""Benchmark harness for router precision, compile drift, and MCP bridge smoke."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CLAUDE_DIR = SCRIPT_PATH.parents[1]
PROJECT_DIR = CLAUDE_DIR.parent
HOOKS_DIR = CLAUDE_DIR / "hooks"
BENCH_DIR = PROJECT_DIR / "benchmarks"

sys.path.insert(0, str(CLAUDE_DIR / "scripts"))
sys.path.insert(0, str(HOOKS_DIR))

from manifest import ManifestLoadError, load_manifest
from runtime_profile import load_runtime_profile
from skill_compile import compile_command_md, compile_skill_md, get_output_path
from mcp_bridge import generate_mcp_server, get_tools_skills
from skill_router import match_skill


def _load_yaml_manifest(cwd: Path):
    return load_manifest(cwd=str(cwd), search_paths=[str(cwd)], allow_legacy=False)


def run_router_benchmark(profile_name: str = "core") -> dict:
    cases_path = BENCH_DIR / "router_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    manifest = _load_yaml_manifest(PROJECT_DIR)
    profile = load_runtime_profile(cwd=str(PROJECT_DIR), override=profile_name)
    triggers = {}
    for name, defn in manifest.get("skills", {}).items():
        trigger = defn.get("trigger")
        if trigger:
            triggers[name] = {**trigger, "type": defn.get("type", "command")}

    results = []
    correct_top1 = 0
    correct_top2 = 0
    correct_none = 0

    for case in cases:
        cwd = (PROJECT_DIR / case["cwd"]).resolve()
        prompt = case["prompt"]
        matches = []
        for name, defn in triggers.items():
            hit = match_skill(name, defn, prompt, str(cwd))
            if hit:
                matches.append(hit)
        matches.sort(key=lambda m: (-m["score"], m["priority"]))
        top_names = [m["name"] for m in matches[:2]]

        case_result = {
            "id": case["id"],
            "prompt": prompt,
            "cwd": str(cwd),
            "expected_top": case.get("expected_top"),
            "expect_none": case.get("expect_none", False),
            "top1": top_names[0] if top_names else None,
            "top2": top_names[1] if len(top_names) > 1 else None,
            "candidates": top_names,
        }

        if case.get("expect_none"):
            case_result["passed"] = len(top_names) == 0
            if case_result["passed"]:
                correct_none += 1
        else:
            expected = case["expected_top"]
            case_result["top1_correct"] = case_result["top1"] == expected
            case_result["top2_hit"] = expected in top_names
            case_result["passed"] = case_result["top1_correct"]
            if case_result["top1_correct"]:
                correct_top1 += 1
            if case_result["top2_hit"]:
                correct_top2 += 1

        results.append(case_result)

    labeled_cases = [c for c in cases if not c.get("expect_none")]
    none_cases = [c for c in cases if c.get("expect_none")]

    return {
        "benchmark": "router",
        "profile": profile["name"],
        "case_count": len(cases),
        "top1_accuracy": round(correct_top1 / len(labeled_cases), 4) if labeled_cases else None,
        "top2_recall": round(correct_top2 / len(labeled_cases), 4) if labeled_cases else None,
        "none_accuracy": round(correct_none / len(none_cases), 4) if none_cases else None,
        "results": results,
    }


def _normalize_text(text: str) -> list[str]:
    return [line.rstrip() for line in text.strip().splitlines()]


def run_compile_benchmark() -> dict:
    manifest = _load_yaml_manifest(PROJECT_DIR)
    skills = manifest.get("skills", {})
    results = []
    exact_matches = 0
    comparable = 0
    external_wrappers = 0

    for name, defn in skills.items():
        if not defn.get("contract"):
            continue
        skill_type = defn.get("type", "command")
        compiled = compile_command_md(name, defn) if skill_type == "command" else compile_skill_md(name, defn)
        out_path = Path(get_output_path(name, defn, None, str(CLAUDE_DIR)))
        wrapped_source = defn.get("wraps")
        result = {
            "skill": name,
            "type": skill_type,
            "source": str(out_path),
            "source_exists": out_path.exists(),
        }
        if not out_path.exists():
            if wrapped_source:
                external_wrappers += 1
                result["status"] = "external_wrapper"
                result["wrapped_source"] = wrapped_source
            else:
                result["status"] = "missing_source"
            results.append(result)
            continue

        existing = out_path.read_text(encoding="utf-8")
        comparable += 1
        compiled_lines = _normalize_text(compiled)
        existing_lines = _normalize_text(existing)
        exact = compiled_lines == existing_lines
        diff = list(difflib.unified_diff(existing_lines, compiled_lines, lineterm=""))
        change_lines = [line for line in diff if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]

        result.update(
            {
                "status": "exact" if exact else "drift",
                "exact_match": exact,
                "line_count_compiled": len(compiled_lines),
                "line_count_existing": len(existing_lines),
                "changed_line_count": len(change_lines),
                "sample_diff": diff[:20],
            }
        )
        if exact:
            exact_matches += 1
        results.append(result)

    return {
        "benchmark": "compile",
        "comparable_count": comparable,
        "exact_match_count": exact_matches,
        "exact_match_rate": round(exact_matches / comparable, 4) if comparable else None,
        "external_wrapper_count": external_wrappers,
        "results": results,
    }


def _run_json_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, object]:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    output = proc.stdout.strip() or proc.stderr.strip()
    try:
        data = json.loads(output) if output else None
    except json.JSONDecodeError:
        data = output
    return proc.returncode, data


def run_mcp_benchmark() -> dict:
    manifest = _load_yaml_manifest(PROJECT_DIR)
    skills = get_tools_skills(manifest)
    results = []

    for name, defn in skills.items():
        with tempfile.TemporaryDirectory(prefix=f"skill_facets_mcp_{name}_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            fake_claude_dir = tmpdir_path / ".claude"
            fake_mcp_dir = fake_claude_dir / "mcp"
            fake_skills_dir = fake_claude_dir / "skills"
            fake_mcp_dir.mkdir(parents=True, exist_ok=True)
            fake_skills_dir.mkdir(parents=True, exist_ok=True)

            src_skill_dir = CLAUDE_DIR / "skills" / name
            dst_skill_dir = fake_skills_dir / name
            if src_skill_dir.exists():
                shutil.copytree(src_skill_dir, dst_skill_dir, dirs_exist_ok=True)

            server_path = fake_mcp_dir / f"{name}_server.py"
            code = generate_mcp_server(name, defn, str(CLAUDE_DIR))
            server_path.write_text(code, encoding="utf-8")

            py_compile.compile(str(server_path), doraise=True)

            smoke = {"skill": name, "generated": str(server_path), "compiled": True}

            if name == "deliver-v4":
                scan_dir = tmpdir_path / "scan_target"
                scan_dir.mkdir()
                (scan_dir / "note.md").write_text("This file was generated by ChatGPT.\n", encoding="utf-8")

                delivery_dir = tmpdir_path / "delivery"
                delivery_dir.mkdir()
                (delivery_dir / "report.txt").write_text("delivery artifact\n", encoding="utf-8")

                scan_rc, scan_data = _run_json_command(
                    [sys.executable, str(server_path), "--call", "ai_trace_scan_scan", str(scan_dir)]
                )
                checksum_rc, checksum_data = _run_json_command(
                    [sys.executable, str(server_path), "--call", "zip_pack_checksum", str(delivery_dir)]
                )
                pack_rc, pack_data = _run_json_command(
                    [sys.executable, str(server_path), "--call", "zip_pack_pack", str(delivery_dir), "Demo"]
                )

                smoke.update(
                    {
                        "scan_exit": scan_rc,
                        "scan_detected": isinstance(scan_data, list) and len(scan_data) > 0,
                        "scan_sample": scan_data[:1] if isinstance(scan_data, list) else scan_data,
                        "checksum_exit": checksum_rc,
                        "checksum_ok": isinstance(checksum_data, dict) and "checksum_path" in checksum_data,
                        "checksum_data": checksum_data,
                        "pack_exit": pack_rc,
                        "pack_ok": isinstance(pack_data, dict) and "zip_path" in pack_data,
                        "pack_data": pack_data,
                    }
                )
                smoke["passed"] = all(
                    [smoke["compiled"], smoke["scan_detected"], smoke["checksum_ok"], smoke["pack_ok"]]
                )
            else:
                smoke["passed"] = smoke["compiled"]

            results.append(smoke)

    passed = sum(1 for x in results if x.get("passed"))
    return {
        "benchmark": "mcp",
        "skill_count": len(results),
        "passed_count": passed,
        "pass_rate": round(passed / len(results), 4) if results else None,
        "results": results,
    }


def run_all(profile_name: str = "core") -> dict:
    return {
        "router": run_router_benchmark(profile_name=profile_name),
        "compile": run_compile_benchmark(),
        "mcp": run_mcp_benchmark(),
    }


def main():
    parser = argparse.ArgumentParser(description="Run skill-facets benchmark suite")
    parser.add_argument("target", choices=["router", "compile", "mcp", "all"], nargs="?", default="all")
    parser.add_argument("--profile", default="core", help="runtime profile for router benchmark")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    parser.add_argument("--write-report", help="optional path to write JSON report")
    args = parser.parse_args()

    if args.target == "router":
        report = run_router_benchmark(profile_name=args.profile)
    elif args.target == "compile":
        report = run_compile_benchmark()
    elif args.target == "mcp":
        report = run_mcp_benchmark()
    else:
        report = run_all(profile_name=args.profile)

    if args.write_report:
        Path(args.write_report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
