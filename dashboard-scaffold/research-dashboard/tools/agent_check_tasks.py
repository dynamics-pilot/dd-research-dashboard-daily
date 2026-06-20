# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from build_dashboard import (
    TASK_REQUESTS_DIR,
    TASK_STATUSES,
    load_tasks,
)


SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def now_minute() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(f"{path.name}.{secrets.token_hex(4)}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp_path, path)


def list_tasks(status: str | None, project: str | None) -> None:
    tasks = load_tasks()
    if status:
        tasks = [task for task in tasks if task.get("status") == status]
    if project:
        tasks = [task for task in tasks if task.get("project") == project]

    for task in tasks:
        print(
            f"{task.get('id')} | {task.get('status')} | {task.get('project')} | "
            f"{task.get('priority')} | {task.get('updated_at') or task.get('created_at')} | {task.get('title')}"
        )


def show_task(task_id: str) -> None:
    task = read_task(task_id)
    print(json.dumps(task, ensure_ascii=False, indent=2))


def read_task(task_id: str) -> dict[str, Any]:
    if not SAFE_TASK_ID.match(task_id):
        raise SystemExit("Illegal task id.")
    task_path = TASK_REQUESTS_DIR / f"{task_id}.json"
    if not task_path.exists():
        raise SystemExit(f"Task not found: {task_id}")
    task = json.loads(task_path.read_text(encoding="utf-8"))
    if not isinstance(task, dict):
        raise SystemExit("Task JSON must be an object.")
    return task


def update_task(args: argparse.Namespace) -> None:
    task = read_task(args.task_id)
    if args.status:
        if args.status not in TASK_STATUSES:
            raise SystemExit(f"Illegal status: {args.status}")
        task["status"] = args.status
    if args.result_summary is not None:
        task["result_summary"] = args.result_summary
    if args.error_summary is not None:
        task["error_summary"] = args.error_summary
    task["updated_at"] = now_minute()
    write_json_atomic(TASK_REQUESTS_DIR / f"{args.task_id}.json", task)
    print(f"Updated {args.task_id}: {task.get('status')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect or safely update dashboard task JSON files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List queued dashboard tasks.")
    list_parser.add_argument("--status", choices=TASK_STATUSES)
    list_parser.add_argument("--project")

    show_parser = subparsers.add_parser("show", help="Show one task JSON.")
    show_parser.add_argument("task_id")

    update_parser = subparsers.add_parser("update", help="Update safe task result fields.")
    update_parser.add_argument("task_id")
    update_parser.add_argument("--status", choices=TASK_STATUSES)
    update_parser.add_argument("--result-summary")
    update_parser.add_argument("--error-summary")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "list":
        list_tasks(args.status, args.project)
    elif args.command == "show":
        show_task(args.task_id)
    elif args.command == "update":
        update_task(args)


if __name__ == "__main__":
    main()
