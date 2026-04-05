#!/usr/bin/env python3
"""追加 JSONL 日志到 .claude/logs/skill_events.jsonl。静默失败，不阻塞主流程。"""
import os, json, datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_SCRIPT_DIR)
LOG_DIR = os.path.join(_CLAUDE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "skill_events.jsonl")


def log_event(event: dict):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        event["ts"] = datetime.datetime.now().isoformat()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
