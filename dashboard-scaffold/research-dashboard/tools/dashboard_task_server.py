# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from datetime import datetime
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from build_dashboard import (
    DATA_FILE,
    PROJECTS_DIR,
    ROOT,
    TASK_REQUESTS_DIR,
    TASK_STATUSES,
    dashboard_payload,
    load_projects,
    load_tasks,
    task_metrics,
)


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_SLUG = re.compile(r"^[A-Za-z0-9_.-]+$")
MAX_BODY_BYTES = 256 * 1024
TOKEN_ENV = "DASHBOARD_AGENT_TOKEN"


def now_minute() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def compact_title(value: str, fallback: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return fallback
    return text[:120]


def project_slugs() -> set[str]:
    if not PROJECTS_DIR.exists():
        return set()
    return {path.stem for path in PROJECTS_DIR.glob("*.md") if not path.name.startswith("_")}


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{secrets.token_hex(4)}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp_path, path)


def refresh_dashboard_data() -> None:
    DATA_FILE.write_text(
        json.dumps(dashboard_payload(load_projects()), ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def tasks_response() -> dict[str, Any]:
    tasks = load_tasks()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "metrics": task_metrics(tasks),
        "tasks": tasks,
    }


def bool_payload(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def normalized_permissions(raw_permissions: Any) -> dict[str, bool]:
    if not isinstance(raw_permissions, dict):
        raw_permissions = {}
    defaults = {
        "allow_code_edit": True,
        "allow_shell": True,
        "allow_network": False,
        "allow_long_running": False,
        "allow_delete_files": False,
    }
    return {
        key: bool_payload(raw_permissions, key, default)
        for key, default in defaults.items()
    }


def make_task(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    project = str(payload.get("project") or "").strip()
    if not SAFE_SLUG.match(project):
        return None, "project 必须是已有项目 slug"
    if project not in project_slugs():
        return None, f"未知项目: {project}"

    instruction = str(payload.get("instruction") or "").strip()
    if not instruction:
        return None, "instruction 不能为空"

    title = compact_title(str(payload.get("title") or ""), short_instruction_title(instruction))
    priority = str(payload.get("priority") or "medium").strip().lower()
    if priority not in {"high", "medium", "low"}:
        priority = "medium"

    permissions = normalized_permissions(payload.get("permissions"))
    high_risk = permissions["allow_delete_files"] or permissions["allow_long_running"]
    requires_confirmation = bool_payload(payload, "requires_confirmation", False) or high_risk
    created_at = now_minute()
    task_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{project}-{secrets.token_hex(3)}"

    task = {
        "id": task_id,
        "status": "blocked" if requires_confirmation else "pending",
        "project": project,
        "source": "dashboard",
        "title": title,
        "instruction": instruction,
        "priority": priority,
        "created_at": created_at,
        "updated_at": created_at,
        "created_by": "DD",
        "cwd": str(ROOT.parent),
        "preferred_thread": project,
        "permissions": permissions,
        "requires_confirmation": requires_confirmation,
        "expected_output": str(
            payload.get("expected_output")
            or "更新对应项目 Markdown，并在任务 JSON 中写 result_summary。"
        ).strip(),
        "result_summary": "",
        "error_summary": "包含高风险权限，需人工确认后执行。" if requires_confirmation else "",
        "related_files": [],
    }
    return task, None


def short_instruction_title(instruction: str) -> str:
    return compact_title(instruction, "未命名任务")


class DashboardTaskHandler(SimpleHTTPRequestHandler):
    server_version = "DashboardTaskServer/0.1"

    def __init__(self, *args: Any, token: str = "", **kwargs: Any) -> None:
        self.required_token = token
        super().__init__(*args, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Dashboard-Agent-Token, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/tasks":
            if not self.authorized():
                return
            self.send_json(tasks_response())
            return
        super().do_GET()

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route != "/api/tasks":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.authorized():
            return

        payload = self.read_json_body()
        if payload is None:
            return
        task, error = make_task(payload)
        if error or task is None:
            self.send_json({"error": error or "任务创建失败"}, status=HTTPStatus.BAD_REQUEST)
            return

        write_json_atomic(TASK_REQUESTS_DIR / f"{task['id']}.json", task)
        refresh_dashboard_data()
        self.send_json({"task": task, **tasks_response()}, status=HTTPStatus.CREATED)

    def do_PATCH(self) -> None:
        route = urlparse(self.path).path
        prefix = "/api/tasks/"
        if not route.startswith(prefix):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.authorized():
            return

        task_id = unquote(route[len(prefix) :]).strip()
        if not SAFE_TASK_ID.match(task_id):
            self.send_json({"error": "非法 task id"}, status=HTTPStatus.BAD_REQUEST)
            return

        task_path = TASK_REQUESTS_DIR / f"{task_id}.json"
        if not task_path.exists():
            self.send_json({"error": "任务不存在"}, status=HTTPStatus.NOT_FOUND)
            return

        payload = self.read_json_body()
        if payload is None:
            return

        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if not isinstance(task, dict):
            self.send_json({"error": "任务 JSON 必须是对象"}, status=HTTPStatus.BAD_REQUEST)
            return

        if "status" in payload:
            status = str(payload["status"]).lower()
            if status not in TASK_STATUSES:
                self.send_json({"error": "非法 status"}, status=HTTPStatus.BAD_REQUEST)
                return
            task["status"] = status

        for key in ("result_summary", "error_summary"):
            if key in payload:
                task[key] = str(payload[key])[:12000]

        if "related_files" in payload:
            related_files = payload["related_files"]
            if not isinstance(related_files, list):
                self.send_json({"error": "related_files 必须是数组"}, status=HTTPStatus.BAD_REQUEST)
                return
            task["related_files"] = [str(item)[:600] for item in related_files[:80]]

        task["updated_at"] = str(payload.get("updated_at") or now_minute())
        write_json_atomic(task_path, task)
        refresh_dashboard_data()
        self.send_json({"task": task, **tasks_response()})

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean_path = unquote(parsed.path).lstrip("/")
        if not clean_path:
            clean_path = "index.html"
        target = (ROOT / clean_path).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            return str(ROOT / "index.html")
        return str(target)

    def authorized(self) -> bool:
        if not self.required_token:
            return True
        header_token = self.headers.get("X-Dashboard-Agent-Token", "").strip()
        authorization = self.headers.get("Authorization", "").strip()
        if authorization.lower().startswith("bearer "):
            header_token = authorization[7:].strip()
        if secrets.compare_digest(header_token, self.required_token):
            return True
        self.send_json({"error": "token_required"}, status=HTTPStatus.UNAUTHORIZED)
        return False

    def read_json_body(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "非法 Content-Length"}, status=HTTPStatus.BAD_REQUEST)
            return None
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self.send_json({"error": "请求体大小不合法"}, status=HTTPStatus.BAD_REQUEST)
            return None
        try:
            raw = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return None
        if not isinstance(payload, dict):
            self.send_json({"error": "请求体必须是 JSON 对象"}, status=HTTPStatus.BAD_REQUEST)
            return None
        return payload

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the research dashboard task console.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host, default: 127.0.0.1")
    parser.add_argument("--port", default=8765, type=int, help="Bind port, default: 8765")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.environ.get(TOKEN_ENV, "").strip()
    if args.host not in LOCAL_HOSTS and not token:
        raise SystemExit(
            f"Refusing to bind {args.host} without {TOKEN_ENV}. "
            "Set a token or use --host 127.0.0.1 with Tailscale/SSH/remote desktop forwarding."
        )

    TASK_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    handler = partial(DashboardTaskHandler, directory=str(ROOT), token=token)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Research dashboard task server: http://{args.host}:{args.port}/")
    if token:
        print(f"API token required via X-Dashboard-Agent-Token or Authorization: Bearer <token>.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
