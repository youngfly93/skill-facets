#!/usr/bin/env python3
"""vNext runtime runner.

P2 starts with a single manifest-driven runner for `deliver-v4`.
The runner enforces:
- required project inputs (`plan.md`)
- audit gate (`P0 == 0 and P1 == 0`)
- deterministic tool calls for AI scan, checksum, pack, and ZIP verify
- explicit handling of the still-partial `collect` and `verify_doc` states
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

from logger import log_event
from manifest import ManifestLoadError, get_skill, load_manifest


EXIT_OK = 0
EXIT_WORKFLOW_FAIL = 1
EXIT_CONFIG_ERROR = 2

DELIVER_SKILL = "deliver-v4"
EXCLUDE_NAMES = {".DS_Store", "__MACOSX", ".git", ".Rhistory", ".RData", "Thumbs.db"}
EXCLUDE_SUFFIXES = (
    ".rdata",
    ".rds",
    ".bam",
    ".sam",
    ".cram",
    ".fastq",
    ".fq",
    ".fastq.gz",
    ".fq.gz",
)


def _json_dump(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _status(step, status, details, **extra):
    item = {"step": step, "status": status, "details": details}
    item.update(extra)
    return item


def _log_runner(run_id, event_type, **payload):
    log_event({"type": event_type, "run_id": run_id, **payload})


def _resolve_paths(project_root: Path):
    try:
        manifest = load_manifest(cwd=str(project_root), search_paths=[str(project_root)])
    except ManifestLoadError:
        raise

    skill = get_skill(DELIVER_SKILL, cwd=str(project_root), search_paths=[str(project_root)])
    if not skill:
        raise RuntimeError(f"未在 skills.yaml 中找到 {DELIVER_SKILL}")

    source = manifest.get("_source")
    if not source:
        raise RuntimeError("manifest 缺少 _source，无法定位 skill 目录")

    claude_dir = Path(source).resolve().parent
    skill_source = skill.get("source")
    if not skill_source:
        raise RuntimeError(f"{DELIVER_SKILL} 缺少 source")

    skill_dir = (claude_dir / Path(skill_source).parent).resolve()
    return manifest, skill, claude_dir, skill_dir


def _resolve_tool_scripts(skill, skill_dir: Path):
    tools = {}
    for tool in skill.get("tools", []):
        name = tool.get("name")
        script = tool.get("script")
        if not name or not script:
            continue
        tools[name] = {
            **tool,
            "_script_path": (skill_dir / script).resolve(),
        }
    return tools


def _require_within(root: Path, target: Path) -> Path:
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"路径超出项目根目录: {target}") from exc
    return resolved


def _load_audit(args):
    if args.audit_json:
        with open(args.audit_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise RuntimeError("audit JSON 必须是对象")
        normalized = {}
        for key in ("p0", "p1", "p2", "p3"):
            candidates = [key, key.upper(), f"{key}_count", f"{key.upper()}_count"]
            value = None
            for candidate in candidates:
                if candidate in data:
                    value = data[candidate]
                    break
            if value is None and "counts" in data and isinstance(data["counts"], dict):
                value = data["counts"].get(key, data["counts"].get(key.upper()))
            if value is None:
                raise RuntimeError(f"audit JSON 缺少 {key}")
            normalized[key] = int(value)
        return normalized

    inline = {key: getattr(args, key) for key in ("p0", "p1", "p2", "p3")}
    if all(value is not None for value in inline.values()):
        return {key: int(value) for key, value in inline.items()}

    raise RuntimeError("必须提供 --audit-json，或同时提供 --p0 --p1 --p2 --p3")


def _safe_rel(root: Path, target: Path) -> str:
    return str(target.resolve().relative_to(root.resolve()))


def _should_exclude(rel_path: Path):
    parts = set(rel_path.parts)
    hit = parts & EXCLUDE_NAMES
    if hit:
        return True, f"name:{sorted(hit)[0]}"
    lower_name = rel_path.name.lower()
    for suffix in EXCLUDE_SUFFIXES:
        if lower_name.endswith(suffix):
            return True, f"suffix:{suffix}"
    return False, None


def _copy_file(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _find_excluded_in_delivery(delivery_dir: Path):
    violations = []
    for path in sorted(delivery_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(delivery_dir)
        excluded, reason = _should_exclude(rel)
        if excluded:
            violations.append({"path": str(rel), "reason": reason})
    return violations


def _collect_inputs(project_root: Path, delivery_dir: Path, includes, existing_mode: str):
    reused = False
    copied = []
    skipped = []
    existing_files = []

    if delivery_dir.exists():
        if any(delivery_dir.iterdir()):
            if existing_mode == "fail":
                raise RuntimeError(f"delivery 目录已存在且非空: {delivery_dir}")
            if existing_mode == "replace":
                shutil.rmtree(delivery_dir)
                delivery_dir.mkdir(parents=True, exist_ok=True)
            else:
                reused = True
                existing_files = [
                    _safe_rel(delivery_dir, path)
                    for path in sorted(delivery_dir.rglob("*"))
                    if path.is_file()
                ]
        else:
            delivery_dir.mkdir(parents=True, exist_ok=True)
    else:
        delivery_dir.mkdir(parents=True, exist_ok=True)

    normalized = []
    seen = set()
    for item in includes:
        src = _require_within(project_root, (project_root / item) if not os.path.isabs(item) else Path(item))
        if src == delivery_dir or delivery_dir in src.parents:
            raise RuntimeError("不允许把 delivery/ 自己作为 collect 输入")
        if src not in seen:
            seen.add(src)
            normalized.append(src)

    for src in normalized:
        if src.is_dir():
            for path in sorted(src.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(project_root)
                excluded, reason = _should_exclude(rel)
                if excluded:
                    skipped.append({"path": str(rel), "reason": reason})
                    continue
                dest = delivery_dir / rel
                _copy_file(path, dest)
                copied.append(str(rel))
        elif src.is_file():
            rel = src.relative_to(project_root)
            excluded, reason = _should_exclude(rel)
            if excluded:
                skipped.append({"path": str(rel), "reason": reason})
                continue
            dest = delivery_dir / rel
            _copy_file(src, dest)
            copied.append(str(rel))
        else:
            raise RuntimeError(f"collect 输入不存在: {src}")

    if not copied and not reused:
        raise RuntimeError("collect 阶段没有可用文件。请提供 --include，或使用 --existing reuse 复用已有 delivery/")

    forbidden = _find_excluded_in_delivery(delivery_dir)
    if forbidden:
        raise RuntimeError(f"delivery/ 中发现应排除文件: {forbidden}")

    final_files = [
        _safe_rel(delivery_dir, path)
        for path in sorted(delivery_dir.rglob("*"))
        if path.is_file()
    ]
    total_size_mb = round(sum(path.stat().st_size for path in delivery_dir.rglob("*") if path.is_file()) / 1024 / 1024, 3)
    return {
        "reused": reused,
        "copied": copied,
        "skipped": skipped,
        "existing_files": existing_files,
        "file_count": len(final_files),
        "total_size_mb": total_size_mb,
        "files": final_files,
    }


def _run_tool(run_id, step, script_path: Path, *tool_args, expect=(0,)):
    cmd = [sys.executable, str(script_path), *tool_args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    payload = None
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": stdout}
    else:
        payload = {}

    _log_runner(
        run_id,
        "runner_tool",
        step=step,
        command=cmd,
        exit_code=proc.returncode,
        stderr=stderr,
    )

    if proc.returncode not in expect:
        raise RuntimeError(
            f"{step} 失败: exit={proc.returncode}"
            + (f", stderr={stderr}" if stderr else "")
        )
    return proc.returncode, payload


def _docx_verify_one(path: Path):
    required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
    issues = []
    fonts = set()
    media_targets = []
    media_count = 0

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            bad = zf.testzip()
            if bad is not None:
                issues.append(f"ZIP CRC 失败: {bad}")
            missing = sorted(required - names)
            if missing:
                issues.append(f"缺少关键部件: {missing}")

            doc_xml = ""
            if "word/document.xml" in names:
                doc_xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
                fonts.update(re.findall(r'w:eastAsia=\"([^\"]+)\"', doc_xml))
                fonts.update(re.findall(r'w:ascii=\"([^\"]+)\"', doc_xml))

            rels_map = {}
            if "word/_rels/document.xml.rels" in names:
                rels_xml = zf.read("word/_rels/document.xml.rels").decode("utf-8", errors="ignore")
                for rid, target in re.findall(r'Id=\"([^\"]+)\"[^>]+Target=\"([^\"]+)\"', rels_xml):
                    rels_map[rid] = target

            if doc_xml:
                for rid in re.findall(r'r:embed=\"([^\"]+)\"', doc_xml):
                    target = rels_map.get(rid)
                    if not target:
                        issues.append(f"图片关系缺失: {rid}")
                        continue
                    normalized = posixpath.normpath(posixpath.join("word", target))
                    media_targets.append(normalized)
                    if normalized not in names:
                        issues.append(f"缺少图片资源: {normalized}")

            media_count = sum(1 for name in names if name.startswith("word/media/") and not name.endswith("/"))
    except zipfile.BadZipFile:
        issues.append("不是有效的 .docx ZIP 容器")
    except Exception as exc:
        issues.append(f"校验异常: {exc}")

    return {
        "file": str(path),
        "passed": len(issues) == 0,
        "issues": issues,
        "media_count": media_count,
        "media_targets": media_targets,
        "fonts_detected": sorted(fonts),
    }


def _verify_docx_set(delivery_dir: Path):
    docx_files = sorted(path for path in delivery_dir.rglob("*.docx") if path.is_file())
    if not docx_files:
        return {
            "passed": True,
            "mode": "auto",
            "doc_count": 0,
            "details": "未发现 .docx 文件，跳过结构校验",
            "results": [],
        }

    results = [_docx_verify_one(path) for path in docx_files]
    passed = all(item["passed"] for item in results)
    return {
        "passed": passed,
        "mode": "auto",
        "doc_count": len(docx_files),
        "details": f"校验 {len(docx_files)} 个 .docx 文件",
        "results": results,
    }


def _manual_doc_verify(mode: str):
    mapping = {
        "pass": (True, "manual_pass", "用户显式确认 Word 文档校验通过"),
        "fail": (False, "manual_fail", "用户显式标记 Word 文档校验失败"),
        "skip": (True, "manual_pending", "Word 文档校验被显式跳过；流程继续但留下人工待办"),
    }
    passed, status, details = mapping[mode]
    return {
        "passed": passed,
        "status": status,
        "mode": mode,
        "details": details,
        "results": [],
    }


def _validate_workflow_shape(workflow):
    states = workflow.get("states", [])
    transitions = workflow.get("transitions", {})
    expected_next = {
        "init": "audit",
        "audit": "collect",
        "collect": "scan",
        "scan": "verify_doc",
        "verify_doc": "checksum",
        "checksum": "pack",
        "pack": "verify_zip",
        "verify_zip": "done",
    }

    if not isinstance(states, list) or not isinstance(transitions, dict):
        raise RuntimeError("workflow.states/transitions 格式错误")

    missing_states = [state for state in expected_next if state not in states] + (["done"] if "done" not in states else [])
    if missing_states:
        raise RuntimeError(f"workflow 缺少状态: {sorted(set(missing_states))}")

    for state, next_state in expected_next.items():
        step = transitions.get(state)
        if not isinstance(step, dict):
            raise RuntimeError(f"workflow.transitions 缺少 {state}")
        if step.get("next") != next_state:
            raise RuntimeError(f"workflow transition 错误: {state} -> {step.get('next')} (期望 {next_state})")

    return states, transitions


def _run_deliver_v4(args):
    run_id = f"deliver-{_dt.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    project_root = Path(args.project_root).resolve()
    project_name = args.project_name or project_root.name
    requested_delivery = Path(args.delivery_dir).resolve() if args.delivery_dir else (project_root / "delivery").resolve()
    delivery_dir = _require_within(project_root, requested_delivery)

    summary = {
        "skill": DELIVER_SKILL,
        "run_id": run_id,
        "project_root": str(project_root),
        "project_name": project_name,
        "delivery_dir": str(delivery_dir),
        "manifest_source": None,
        "workflow_states": [],
        "steps": [],
        "artifacts": {},
        "overall_status": "failed",
    }

    _log_runner(run_id, "runner_start", skill=DELIVER_SKILL, project_root=str(project_root))

    try:
        manifest, skill, _, skill_dir = _resolve_paths(project_root)
        summary["manifest_source"] = manifest.get("_source")
        workflow = skill.get("workflow", {})
        states, transitions = _validate_workflow_shape(workflow)
        summary["workflow_states"] = states
        summary["workflow_transitions"] = transitions
        tools = _resolve_tool_scripts(skill, skill_dir)

        plan_path = project_root / "plan.md"
        if not plan_path.exists():
            step = _status("init", "failed", "缺少 plan.md", missing=str(plan_path))
            summary["steps"].append(step)
            _log_runner(run_id, "runner_step", **step)
            _json_dump(summary)
            return EXIT_WORKFLOW_FAIL

        step = _status("init", "passed", "发现 plan.md", plan=str(plan_path))
        summary["steps"].append(step)
        _log_runner(run_id, "runner_step", **step)

        audit = _load_audit(args)
        audit_passed = audit["p0"] == 0 and audit["p1"] == 0
        step = _status(
            "audit",
            "passed" if audit_passed else "failed",
            f"P0:{audit['p0']} P1:{audit['p1']} P2:{audit['p2']} P3:{audit['p3']}",
            audit=audit,
        )
        summary["steps"].append(step)
        _log_runner(run_id, "runner_step", **step)
        if not audit_passed:
            summary["overall_status"] = "failed"
            _json_dump(summary)
            return EXIT_WORKFLOW_FAIL

        collect_result = _collect_inputs(
            project_root=project_root,
            delivery_dir=delivery_dir,
            includes=args.include or [],
            existing_mode=args.existing,
        )
        step = _status(
            "collect",
            "passed",
            f"{collect_result['file_count']} files, {collect_result['total_size_mb']} MB",
            reused=collect_result["reused"],
            copied_count=len(collect_result["copied"]),
            skipped=collect_result["skipped"],
        )
        summary["steps"].append(step)
        summary["artifacts"]["delivery_files"] = collect_result["files"]
        _log_runner(run_id, "runner_step", **step)

        ai_scan = tools.get("ai_trace_scan", {})
        ai_script = Path(ai_scan.get("_script_path", ""))
        if not ai_script.exists():
            raise RuntimeError("ai_trace_scan 脚本不存在")

        scan_code, scan_payload = _run_tool(run_id, "scan_1", ai_script, "scan", str(delivery_dir), expect=(0, 1))
        cleaned_payload = []
        final_scan = scan_payload
        if scan_code == 1:
            _, cleaned_payload = _run_tool(run_id, "scan_clean", ai_script, "clean", str(delivery_dir), expect=(0,))
            _, final_scan = _run_tool(run_id, "scan_2", ai_script, "scan", str(delivery_dir), expect=(0, 1))
            if final_scan:
                step = _status(
                    "scan",
                    "failed",
                    f"清理后仍有 {len(final_scan)} 处 AI 痕迹",
                    initial_issues=scan_payload,
                    cleaned=cleaned_payload,
                    remaining=final_scan,
                )
                summary["steps"].append(step)
                _log_runner(run_id, "runner_step", **step)
                _json_dump(summary)
                return EXIT_WORKFLOW_FAIL

        step = _status(
            "scan",
            "passed",
            "AI 痕迹扫描完成",
            initial_issue_count=len(scan_payload) if isinstance(scan_payload, list) else 0,
            cleaned=cleaned_payload,
            remaining=final_scan,
        )
        summary["steps"].append(step)
        _log_runner(run_id, "runner_step", **step)

        if args.doc_verify == "auto":
            doc_result = _verify_docx_set(delivery_dir)
            doc_status = "passed" if doc_result["passed"] else "failed"
            step = _status("verify_doc", doc_status, doc_result["details"], result=doc_result)
            summary["steps"].append(step)
            _log_runner(run_id, "runner_step", **step)
            if not doc_result["passed"]:
                _json_dump(summary)
                return EXIT_WORKFLOW_FAIL
        else:
            doc_result = _manual_doc_verify(args.doc_verify)
            step = _status("verify_doc", doc_result["status"], doc_result["details"], result=doc_result)
            summary["steps"].append(step)
            _log_runner(run_id, "runner_step", **step)
            if not doc_result["passed"]:
                _json_dump(summary)
                return EXIT_WORKFLOW_FAIL

        zip_pack = tools.get("zip_pack", {})
        zip_script = Path(zip_pack.get("_script_path", ""))
        if not zip_script.exists():
            raise RuntimeError("zip_pack 脚本不存在")

        _, checksum_payload = _run_tool(run_id, "checksum", zip_script, "checksum", str(delivery_dir), expect=(0,))
        checksum_path = checksum_payload.get("checksum_path")
        step = _status("checksum", "passed", "生成校验和文件", checksum_path=checksum_path)
        summary["steps"].append(step)
        summary["artifacts"]["checksum_path"] = checksum_path
        _log_runner(run_id, "runner_step", **step)

        _, pack_payload = _run_tool(run_id, "pack", zip_script, "pack", str(delivery_dir), project_name, expect=(0,))
        zip_path = pack_payload.get("zip_path")
        if not zip_path:
            raise RuntimeError("pack 未返回 zip_path")
        zip_name = Path(zip_path).name
        if not re.fullmatch(re.escape(project_name) + r"_交付_\d{8}\.zip", zip_name):
            raise RuntimeError(f"ZIP 文件名不符合约定: {zip_name}")

        step = _status("pack", "passed", zip_name, zip_path=zip_path)
        summary["steps"].append(step)
        summary["artifacts"]["zip_path"] = zip_path
        _log_runner(run_id, "runner_step", **step)

        _, verify_payload = _run_tool(run_id, "verify_zip", zip_script, "verify", str(zip_path), expect=(0,))
        crc_ok = bool(verify_payload.get("crc_ok"))
        step = _status(
            "verify_zip",
            "passed" if crc_ok else "failed",
            f"CRC {'通过' if crc_ok else '失败'}",
            result=verify_payload,
        )
        summary["steps"].append(step)
        summary["artifacts"]["verify_zip"] = verify_payload
        _log_runner(run_id, "runner_step", **step)
        if not crc_ok:
            _json_dump(summary)
            return EXIT_WORKFLOW_FAIL

        done_step = _status("done", "passed", "deliver-v4 运行完成")
        summary["steps"].append(done_step)
        summary["overall_status"] = "warning" if args.doc_verify == "skip" else "passed"
        _log_runner(run_id, "runner_step", **done_step)
        _log_runner(run_id, "runner_complete", overall_status=summary["overall_status"], zip_path=zip_path)
        _json_dump(summary)
        return EXIT_OK

    except ManifestLoadError as exc:
        summary["error"] = str(exc)
        summary["overall_status"] = "failed"
        _log_runner(run_id, "runner_error", stage="manifest", error=str(exc))
        _json_dump(summary)
        return EXIT_CONFIG_ERROR
    except Exception as exc:
        summary["error"] = str(exc)
        summary["overall_status"] = "failed"
        _log_runner(run_id, "runner_error", stage="runtime", error=str(exc))
        _json_dump(summary)
        return EXIT_WORKFLOW_FAIL


def _build_parser():
    parser = argparse.ArgumentParser(description="vNext runtime runner")
    subparsers = parser.add_subparsers(dest="skill", required=True)

    deliver = subparsers.add_parser("deliver-v4", help="Run deliver-v4 workflow")
    deliver.add_argument("--project-root", required=True, help="项目根目录，必须包含 plan.md")
    deliver.add_argument("--project-name", help="ZIP 命名中的项目名，默认使用项目目录名")
    deliver.add_argument("--delivery-dir", help="交付目录，默认 <project-root>/delivery")
    deliver.add_argument("--audit-json", help="审计结果 JSON，需包含 p0/p1/p2/p3")
    deliver.add_argument("--p0", type=int, help="内联审计结果 P0")
    deliver.add_argument("--p1", type=int, help="内联审计结果 P1")
    deliver.add_argument("--p2", type=int, help="内联审计结果 P2")
    deliver.add_argument("--p3", type=int, help="内联审计结果 P3")
    deliver.add_argument(
        "--doc-verify",
        choices=("auto", "pass", "fail", "skip"),
        default="auto",
        help="Word 校验策略：auto 使用内建结构校验；pass/fail/skip 为显式人工门控",
    )
    deliver.add_argument(
        "--existing",
        choices=("fail", "replace", "reuse"),
        default="fail",
        help="delivery/ 已存在且非空时的处理方式",
    )
    deliver.add_argument(
        "--include",
        action="append",
        default=[],
        help="要收集进 delivery/ 的相对路径；可重复传入。为空时只能复用已有 delivery/",
    )
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.skill == DELIVER_SKILL:
        sys.exit(_run_deliver_v4(args))

    parser.error(f"未支持的 skill: {args.skill}")


if __name__ == "__main__":
    main()
