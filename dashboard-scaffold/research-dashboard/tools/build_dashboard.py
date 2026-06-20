# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "projects"
TASKS_DIR = ROOT / "tasks"
TASK_REQUESTS_DIR = TASKS_DIR / "requests"
TASK_LOGS_DIR = TASKS_DIR / "logs"
OUTPUT_FILE = ROOT / "index.html"
DATA_FILE = ROOT / "dashboard-data.json"
CODEX_USAGE_FILE = ROOT / "config" / "codex-usage-summary.json"

TASK_STATUSES = ("pending", "running", "blocked", "done", "failed")
DATA_SCHEMA_VERSION = "2026-05-26-dashboard-only-v3"
CARD_RENDER_VERSION = "2026-05-26-dashboard-only-v3"
SECTION_PAGE_SIZE = 5
HIDDEN_PROJECT_SLUGS = {"codex-usage-monitor"}
INACTIVE_STATUSES = {"waiting", "paused", "archived"}

SECTION_ALIASES = {
    "当前问题": "issues",
    "current issues": "issues",
    "current problems": "issues",
    "problems": "issues",
    "已解决": "resolved",
    "solved": "resolved",
    "resolved": "resolved",
    "done": "resolved",
    "下一步计划": "next",
    "next steps": "next",
    "plan": "next",
    "维护文件": "files",
    "maintained files": "files",
    "files": "files",
    "关键记录": "history",
    "history": "history",
    "notes": "history",
}

SECTION_TITLES = {
    "issues": "当前问题",
    "resolved": "已解决",
    "next": "下一步计划",
    "files": "维护文件",
    "history": "关键记录",
}

STATUS_LABELS = {
    "active": "Active",
    "waiting": "Waiting",
    "paused": "Paused",
    "archived": "Archived",
}


@dataclass
class Project:
    path: Path
    slug: str
    title: str
    status: str
    priority: str
    owner: str
    order: int | None
    updated: str
    content_hash: str
    render_hash: str
    tags: list[str]
    summary: str
    sections: dict[str, list[str]]
    total_tasks: int
    done_tasks: int
    open_issues: int
    open_next_steps: int


def parse_value(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"').strip("'") for item in inner.split(",")]
    return value


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return {}, text

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, text

    meta: dict[str, Any] = {}
    for raw_line in lines[1:end_index]:
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = parse_value(value)

    return meta, "\n".join(lines[end_index + 1 :])


def normalize_heading(heading: str) -> str:
    return re.sub(r"\s+", " ", heading.strip().lower())


def parse_sections(body: str) -> tuple[dict[str, list[str]], str | None]:
    sections = {key: [] for key in SECTION_TITLES}
    current_key: str | None = None
    title: str | None = None

    for line in body.splitlines():
        h1 = re.match(r"^#\s+(.+?)\s*$", line)
        if h1 and title is None:
            title = h1.group(1).strip()
            continue

        h2 = re.match(r"^##\s+(.+?)\s*$", line)
        if h2:
            heading_key = SECTION_ALIASES.get(normalize_heading(h2.group(1)))
            current_key = heading_key
            continue

        if current_key is not None:
            sections[current_key].append(line)

    return sections, title


def count_tasks(lines: list[str]) -> tuple[int, int]:
    total = 0
    done = 0
    for line in lines:
        match = re.match(r"^\s*-\s+\[([ xX])\]\s+", line)
        if match:
            total += 1
            if match.group(1).lower() == "x":
                done += 1
    return total, done


def count_open_tasks(lines: list[str]) -> int:
    total, done = count_tasks(lines)
    return total - done


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def parse_order(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_nonempty_paragraph(lines: list[str]) -> str:
    paragraph: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith("- ") or stripped.startswith("#"):
            continue
        paragraph.append(stripped)
    return " ".join(paragraph)


def inline_markdown(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def plain_inline_text(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def current_issue_brief(project: Project) -> str:
    for line in project.sections["issues"]:
        task = re.match(r"^\s*-\s+\[ \]\s+(.+)$", line)
        if task:
            brief = plain_inline_text(task.group(1))
            if project.open_issues > 1:
                brief = f"{brief}（另有 {project.open_issues - 1} 项）"
            return brief

    for line in project.sections["issues"]:
        bullet = re.match(r"^\s*-\s+(.+)$", line)
        if bullet:
            return plain_inline_text(bullet.group(1))

    return "暂无未解决问题"


def markdown_lines_to_html(lines: list[str], paginate_id: str | None = None) -> str:
    if not any(line.strip() for line in lines):
        return '<p class="muted">暂无记录</p>'

    entries: list[str] = []

    def list_entry(class_name: str, content: str) -> str:
        class_attr = f' class="{html.escape(class_name)}"' if class_name else ""
        return f'<ul class="item-list"><li{class_attr}>{content}</li></ul>'

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        heading = re.match(r"^###\s+(.+?)\s*$", stripped)
        if heading:
            entries.append(f"<h4>{inline_markdown(heading.group(1))}</h4>")
            continue

        task = re.match(r"^\s*-\s+\[([ xX])\]\s+(.+)$", line)
        if task:
            done = task.group(1).lower() == "x"
            class_name = "task done" if done else "task open"
            entries.append(
                list_entry(
                    class_name,
                    f'<span class="box"></span><span>{inline_markdown(task.group(2))}</span>',
                )
            )
            continue

        bullet = re.match(r"^\s*-\s+(.+)$", line)
        if bullet:
            entries.append(list_entry("", inline_markdown(bullet.group(1))))
            continue

        entries.append(f"<p>{inline_markdown(stripped)}</p>")

    if paginate_id is None or len(entries) <= SECTION_PAGE_SIZE:
        return "\n".join(entries)

    list_id = f"{paginate_id}-list-0"
    page_count = (len(entries) + SECTION_PAGE_SIZE - 1) // SECTION_PAGE_SIZE
    parts = [
        f'<div class="paged-list" id="{html.escape(list_id, quote=True)}" '
        f'data-page-size="{SECTION_PAGE_SIZE}" data-page="1" data-pages="{page_count}">'
    ]
    for index, entry in enumerate(entries):
        page = index // SECTION_PAGE_SIZE + 1
        parts.append(f'<div class="paged-item" data-page="{page}">{entry}</div>')
    parts.append(
        f"""
        <div class="pager" aria-label="列表分页">
          <button type="button" class="pager-prev" aria-controls="{html.escape(list_id, quote=True)}">上一页</button>
          <span class="pager-info">1 / {page_count}</span>
          <button type="button" class="pager-next" aria-controls="{html.escape(list_id, quote=True)}">下一页</button>
        </div>
        """
    )
    parts.append("</div>")
    return "\n".join(parts)


def read_project(path: Path) -> Project:
    text = path.read_text(encoding="utf-8-sig")
    content_hash = short_hash(text)
    meta, body = parse_front_matter(text)
    sections, body_title = parse_sections(body)

    title = str(meta.get("title") or body_title or path.stem)
    status = str(meta.get("status") or "active").lower()
    priority = str(meta.get("priority") or "medium").lower()
    owner = str(meta.get("owner") or "")
    order = parse_order(meta.get("order"))
    updated = str(meta.get("updated") or "")
    raw_tags = meta.get("tags") or []
    if isinstance(raw_tags, str):
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    else:
        tags = [str(tag) for tag in raw_tags]

    summary = str(meta.get("summary") or first_nonempty_paragraph(body.splitlines()) or "")

    total_tasks = 0
    done_tasks = 0
    for lines in sections.values():
        section_total, section_done = count_tasks(lines)
        total_tasks += section_total
        done_tasks += section_done

    open_issues = count_open_tasks(sections["issues"])
    open_next_steps = count_open_tasks(sections["next"])
    render_hash = short_hash(
        json.dumps(
            {
                "version": CARD_RENDER_VERSION,
                "slug": path.stem,
                "title": title,
                "status": status,
                "priority": priority,
                "owner": owner,
                "order": order,
                "updated": updated,
                "tags": tags,
                "summary": summary,
                "sections": sections,
                "total_tasks": total_tasks,
                "done_tasks": done_tasks,
                "open_issues": open_issues,
                "open_next_steps": open_next_steps,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return Project(
        path=path,
        slug=path.stem,
        title=title,
        status=status,
        priority=priority,
        owner=owner,
        order=order,
        updated=updated,
        content_hash=content_hash,
        render_hash=render_hash,
        tags=tags,
        summary=summary,
        sections=sections,
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        open_issues=open_issues,
        open_next_steps=open_next_steps,
    )


def error_project(path: Path, error: Exception) -> Project:
    message = f"{type(error).__name__}: {error}"
    sections = {key: [] for key in SECTION_TITLES}
    sections["issues"] = [
        f"- [ ] 项目文件 `{path.name}` 读取或解析失败，需要检查 UTF-8 编码和 front matter。错误：{message}"
    ]
    digest_source = f"{path}:{message}"
    render_hash = short_hash(
        json.dumps(
            {
                "version": CARD_RENDER_VERSION,
                "slug": path.stem,
                "error": message,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return Project(
        path=path,
        slug=path.stem,
        title=f"项目文件读取失败：{path.stem}",
        status="paused",
        priority="high",
        owner="dashboard",
        order=None,
        updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        content_hash=short_hash(digest_source),
        render_hash=render_hash,
        tags=["dashboard-error"],
        summary="这个项目文件暂时无法解析，dashboard 已保留占位行，其他项目仍可正常显示。",
        sections=sections,
        total_tasks=1,
        done_tasks=0,
        open_issues=1,
        open_next_steps=0,
    )


def parse_date_key(value: str) -> tuple[int, str]:
    if not value:
        return (0, "")
    try:
        normalized = value.replace("/", "-")
        return (1, datetime.fromisoformat(normalized).isoformat())
    except ValueError:
        return (0, value)


def load_projects() -> list[Project]:
    projects: list[Project] = []
    for path in sorted(PROJECTS_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        if path.stem in HIDDEN_PROJECT_SLUGS:
            continue
        try:
            projects.append(read_project(path))
        except Exception as error:
            projects.append(error_project(path, error))

    def sort_key(project: Project) -> tuple[int, int, int, str, str]:
        has_order = 0 if project.order is not None else 1
        order = project.order if project.order is not None else 0
        date_known, date_value = parse_date_key(project.updated)
        return (has_order, order, -date_known, date_value, project.slug)

    ordered = sorted(projects, key=sort_key)
    manual = [project for project in ordered if project.order is not None]
    automatic = sorted(
        [project for project in ordered if project.order is None],
        key=lambda item: parse_date_key(item.updated),
        reverse=True,
    )
    return manual + automatic


def task_datetime_key(value: str) -> tuple[int, str]:
    if not value:
        return (0, "")
    try:
        normalized = value.replace("/", "-")
        return (1, datetime.fromisoformat(normalized).isoformat())
    except ValueError:
        return (0, value)


def normalize_task(raw_task: dict[str, Any], path: Path) -> dict[str, Any]:
    task_id = str(raw_task.get("id") or path.stem)
    status = str(raw_task.get("status") or "pending").lower()
    if status not in TASK_STATUSES:
        status = "pending"

    permissions = raw_task.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}

    log_path = TASK_LOGS_DIR / f"{task_id}.md"
    relative_log_path = ""
    if log_path.exists():
        relative_log_path = log_path.relative_to(ROOT).as_posix()

    related_files = raw_task.get("related_files") or []
    if not isinstance(related_files, list):
        related_files = []

    return {
        "id": task_id,
        "status": status,
        "project": str(raw_task.get("project") or ""),
        "source": str(raw_task.get("source") or ""),
        "title": str(raw_task.get("title") or "未命名任务"),
        "instruction": str(raw_task.get("instruction") or ""),
        "priority": str(raw_task.get("priority") or "medium").lower(),
        "created_at": str(raw_task.get("created_at") or ""),
        "updated_at": str(raw_task.get("updated_at") or ""),
        "created_by": str(raw_task.get("created_by") or ""),
        "cwd": str(raw_task.get("cwd") or ""),
        "preferred_thread": str(raw_task.get("preferred_thread") or ""),
        "permissions": {str(key): bool(value) for key, value in permissions.items()},
        "requires_confirmation": bool(raw_task.get("requires_confirmation") or False),
        "expected_output": str(raw_task.get("expected_output") or ""),
        "result_summary": str(raw_task.get("result_summary") or ""),
        "error_summary": str(raw_task.get("error_summary") or ""),
        "related_files": [str(item) for item in related_files],
        "path": path.relative_to(ROOT).as_posix(),
        "log_path": relative_log_path,
    }


def load_tasks() -> list[dict[str, Any]]:
    if not TASK_REQUESTS_DIR.exists():
        return []

    tasks: list[dict[str, Any]] = []
    for path in sorted(TASK_REQUESTS_DIR.glob("*.json")):
        try:
            raw_task = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            tasks.append(
                {
                    "id": path.stem,
                    "status": "failed",
                    "project": "",
                    "source": "dashboard",
                    "title": f"无法读取任务 JSON: {path.name}",
                    "instruction": "",
                    "priority": "medium",
                    "created_at": "",
                    "updated_at": "",
                    "created_by": "",
                    "cwd": "",
                    "preferred_thread": "",
                    "permissions": {},
                    "requires_confirmation": True,
                    "expected_output": "",
                    "result_summary": "",
                    "error_summary": str(error),
                    "related_files": [],
                    "path": path.relative_to(ROOT).as_posix(),
                    "log_path": "",
                }
            )
            continue

        if isinstance(raw_task, dict):
            tasks.append(normalize_task(raw_task, path))

    return sorted(
        tasks,
        key=lambda task: (
            task_datetime_key(str(task.get("updated_at") or "")),
            task_datetime_key(str(task.get("created_at") or "")),
            str(task.get("id") or ""),
        ),
        reverse=True,
    )


def task_metrics(tasks: list[dict[str, Any]]) -> dict[str, int]:
    metrics = {status: 0 for status in TASK_STATUSES}
    for task in tasks:
        status = str(task.get("status") or "pending")
        if status in metrics:
            metrics[status] += 1
    metrics["total"] = len(tasks)
    return metrics


def load_codex_usage_summary() -> dict[str, Any]:
    if not CODEX_USAGE_FILE.exists():
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_input_tokens": 0,
            "generated_at": "",
            "source_label": "Codex",
        }
    try:
        data = json.loads(CODEX_USAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_input_tokens": 0,
            "generated_at": "",
            "source_label": "Codex",
        }

    breakdown = data.get("token_usage_breakdown")
    if not isinstance(breakdown, dict):
        breakdown = data
    return {
        "input_tokens": int(breakdown.get("input_tokens") or 0),
        "output_tokens": int(breakdown.get("output_tokens") or 0),
        "cached_input_tokens": int(breakdown.get("cached_input_tokens") or 0),
        "generated_at": str(data.get("generated_at") or ""),
        "source_label": str(data.get("source_label") or "Codex"),
    }


def format_compact_tokens(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def format_million_tokens(value: int) -> str:
    return f"{value / 1_000_000:.1f}M"


def codex_usage_label(usage: dict[str, Any]) -> str:
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cached_input_tokens = int(usage.get("cached_input_tokens") or 0)
    cache_hit_rate = cached_input_tokens / input_tokens if input_tokens else 0.0
    return (
        f"输入 {format_million_tokens(input_tokens)}\n"
        f"输出 {format_million_tokens(output_tokens)}\n"
        f"缓存命中率 {cache_hit_rate:.1%}"
    )


def tag_html(tags: list[str]) -> str:
    if not tags:
        return ""
    return "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in tags)


def project_card(project: Project) -> str:
    progress = 0
    if project.total_tasks:
        progress = round(project.done_tasks / project.total_tasks * 100)

    inactive_class = " inactive-project-card" if project.status in INACTIVE_STATUSES else ""
    issue_brief = current_issue_brief(project)
    rel_path = project.path.relative_to(ROOT).as_posix()
    searchable = " ".join(
        [
            project.title,
            project.summary,
            project.status,
            project.priority,
            project.owner,
            " ".join(project.tags),
            " ".join(" ".join(lines) for lines in project.sections.values()),
        ]
    )
    searchable = re.sub(r"\s+", " ", searchable).strip().lower()

    section_html = []
    for key in ("issues", "resolved", "next", "files"):
        section_html.append(
            f"""
            <section class="project-section">
              <h3>{SECTION_TITLES[key]}</h3>
              {markdown_lines_to_html(project.sections[key], f"{project.slug}-{key}")}
            </section>
            """
        )

    return f"""
    <details class="project-card{inactive_class}" data-slug="{html.escape(project.slug, quote=True)}" data-status="{html.escape(project.status)}" data-updated="{html.escape(project.updated, quote=True)}" data-hash="{html.escape(project.render_hash, quote=True)}" data-source-hash="{html.escape(project.content_hash, quote=True)}" data-search="{html.escape(searchable, quote=True)}" draggable="true">
      <summary class="project-summary">
        <div class="project-head">
          <div>
            <h2>{html.escape(project.title)}</h2>
            <p class="summary">{inline_markdown(project.summary) if project.summary else "暂无摘要"}</p>
          </div>
          <span class="status status-{html.escape(project.status)}">{html.escape(STATUS_LABELS.get(project.status, project.status.title()))}</span>
        </div>

        <div class="project-meta">
          <span class="updated">更新: {html.escape(project.updated or "未知")}</span>
          <span class="current-issue" title="{html.escape(issue_brief, quote=True)}">当前研究问题: {html.escape(issue_brief)}</span>
        </div>

        <div class="tags">{tag_html(project.tags)}</div>

        <div class="progress-row" aria-label="任务完成度">
          <div class="progress-track"><span style="width: {progress}%"></span></div>
          <span>{project.done_tasks}/{project.total_tasks} 完成</span>
        </div>
      </summary>

      <div class="project-body">
        <div class="project-sections">
          {''.join(section_html)}
        </div>

        <details class="history">
          <summary>关键记录</summary>
          {markdown_lines_to_html(project.sections["history"], f"{project.slug}-history")}
        </details>

        <p class="source">源文件: <a href="{html.escape(rel_path)}">{html.escape(rel_path)}</a></p>
      </div>
    </details>
    """


def dashboard_payload(projects: list[Project]) -> dict[str, Any]:
    codex_usage = load_codex_usage_summary()
    open_active = sum(
        project.open_issues + project.open_next_steps
        for project in projects
        if project.status == "active"
    )
    open_all = sum(project.open_issues + project.open_next_steps for project in projects)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "schema_version": DATA_SCHEMA_VERSION,
        "metrics": {
            "total": len(projects),
            "active": sum(1 for project in projects if project.status == "active"),
            "open": open_active,
            "open_all": open_all,
            "codex_usage": codex_usage,
            "codex_usage_label": codex_usage_label(codex_usage),
        },
        "projects": [
            {
                "slug": project.slug,
                "status": project.status,
                "updated": project.updated,
                "hash": project.render_hash,
                "source_hash": project.content_hash,
                "card_html": project_card(project),
            }
            for project in projects
        ],
    }


def render(projects: list[Project]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(projects)
    active = sum(1 for project in projects if project.status == "active")
    open_issues = sum(project.open_issues for project in projects if project.status == "active")
    next_steps = sum(project.open_next_steps for project in projects if project.status == "active")
    codex_usage = load_codex_usage_summary()
    codex_usage_text = codex_usage_label(codex_usage)

    cards = "\n".join(project_card(project) for project in projects)
    if not cards:
        cards = """
        <section class="empty-state">
          <h2>还没有研究项目</h2>
          <p>从 <code>projects/_template.md</code> 新建一个项目 Markdown，然后运行生成脚本。</p>
        </section>
        """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>科研进展 Dashboard</title>
  <link rel="icon" href="data:,">
  <style>
    :root {{
      --bg: #f6f7f3;
      --surface: #ffffff;
      --text: #1c2228;
      --muted: #66717d;
      --line: #d9ded7;
      --blue: #235789;
      --green: #2f7d57;
      --red: #b13d4b;
      --gold: #8a6f24;
      --shadow: 0 16px 44px rgba(37, 44, 51, 0.08);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      line-height: 1.55;
    }}

    a {{ color: var(--blue); }}

    code {{
      background: #eef1ed;
      border: 1px solid #d8ded6;
      border-radius: 5px;
      padding: 0.08rem 0.32rem;
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 0.92em;
    }}

    .wrap {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
    }}

    header {{
      background: #1f2a35;
      color: #f8fbf7;
      border-bottom: 5px solid var(--green);
    }}

    .hero {{
      position: relative;
      min-height: 122px;
      padding: 20px 0 14px;
      display: grid;
      gap: 7px;
      align-content: center;
    }}

    .kicker {{
      margin: 0;
      color: #a9c7b5;
      font-size: 0.84rem;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 0;
      font-size: 2.45rem;
      line-height: 1.02;
      letter-spacing: 0;
    }}

    .hero-links {{
      position: absolute;
      top: 12px;
      right: 0;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}

    button {{
      min-height: 34px;
      border: 1px solid #cfd8d1;
      border-radius: 7px;
      background: #ffffff;
      color: #1f2a35;
      padding: 6px 10px;
      font: inherit;
      font-weight: 650;
      text-decoration: none;
      cursor: pointer;
    }}

    .hero-links a {{
      min-height: 28px;
      border: 1px solid rgba(248, 251, 247, 0.18);
      border-radius: 6px;
      background: transparent;
      color: rgba(248, 251, 247, 0.68);
      padding: 4px 8px;
      font-size: 0.82rem;
      font-weight: 600;
      text-decoration: none;
    }}

    .hero-links a:hover {{
      border-color: rgba(248, 251, 247, 0.35);
      color: #f8fbf7;
    }}

    .system-clock {{
      color: rgba(248, 251, 247, 0.76);
      font-size: 0.92rem;
      font-weight: 650;
    }}

    main {{
      padding: 18px 0 36px;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }}

    .metric {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      box-shadow: var(--shadow);
    }}

    .metric strong {{
      display: block;
      font-size: 1.4rem;
      line-height: 1;
    }}

    .metric span {{
      color: var(--muted);
      font-size: 0.9rem;
    }}

    .metric-token strong {{
      font-size: 1.0rem;
      line-height: 1.25;
      white-space: pre-line;
    }}

    .toolbar {{
      display: flex;
      gap: 8px;
      align-items: center;
      margin: 12px 0;
    }}

    input,
    select {{
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #ffffff;
      color: var(--text);
      padding: 6px 9px;
      font: inherit;
    }}

    input {{
      flex: 1;
      min-width: 180px;
    }}

    .sort-control {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 0.88rem;
      white-space: nowrap;
    }}

    .project-grid {{
      display: grid;
      gap: 10px;
    }}

    .status-divider {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 700;
      margin: 2px 0;
      padding: 9px 12px;
      background: #eef2ee;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(37, 44, 51, 0.05);
    }}

    .inactive-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 26px;
      border: 0;
      background: transparent;
      padding: 0;
      color: var(--text);
      font-size: 0.9rem;
      font-weight: 800;
    }}

    .inactive-toggle::before {{
      content: "▸";
      color: var(--green);
    }}

    .status-divider:not(.is-collapsed) .inactive-toggle::before {{
      content: "▾";
    }}

    .inactive-summary {{
      color: var(--muted);
      font-weight: 650;
      text-align: right;
      white-space: nowrap;
    }}

    .project-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
      transition: border-color 120ms ease, opacity 120ms ease;
    }}

    .project-card.dragging {{
      border-color: var(--blue);
      opacity: 0.55;
    }}

    .project-card.project-updated {{
      background: #fffbea;
      border-color: #e4cd73;
    }}

    .project-card.project-updated > .project-summary {{
      background: #fff7d4;
    }}

    .project-summary {{
      position: relative;
      padding: 12px 14px;
      padding-right: 44px;
      cursor: grab;
      list-style: none;
    }}

    .project-summary:active {{
      cursor: grabbing;
    }}

    .project-summary::-webkit-details-marker {{
      display: none;
    }}

    .project-summary::after {{
      content: "+";
      position: absolute;
      top: 12px;
      right: 14px;
      width: 22px;
      height: 22px;
      border: 1px solid var(--line);
      border-radius: 999px;
      display: grid;
      place-items: center;
      color: var(--blue);
      font-weight: 800;
      line-height: 1;
    }}

    .project-card[open] > .project-summary::after {{
      content: "-";
      color: var(--green);
    }}

    .project-summary:hover {{
      background: #f9fbf7;
    }}

    .inactive-project-card {{
      border-radius: 6px;
      box-shadow: none;
      background: #ffffff;
    }}

    .inactive-project-card > .project-summary {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      align-items: center;
      gap: 14px;
      min-height: 44px;
      padding: 8px 12px;
      cursor: default;
    }}

    .inactive-project-card > .project-summary::after,
    .inactive-project-card[open] > .project-summary::after {{
      content: "";
      display: none;
    }}

    .inactive-project-card .project-head {{
      display: block;
      min-width: 0;
    }}

    .inactive-project-card h2 {{
      margin: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 0.96rem;
      line-height: 1.3;
    }}

    .inactive-project-card .summary,
    .inactive-project-card .status,
    .inactive-project-card .tags,
    .inactive-project-card .current-issue,
    .inactive-project-card .progress-track,
    .inactive-project-card .project-body {{
      display: none;
    }}

    .inactive-project-card .project-meta,
    .inactive-project-card .progress-row {{
      display: block;
      margin: 0;
      color: var(--muted);
      font-size: 0.86rem;
      white-space: nowrap;
    }}

    .inactive-project-card .project-meta .updated {{
      color: var(--muted);
      font-weight: 650;
    }}

    .inactive-project-card .progress-row span:last-child {{
      font-weight: 700;
      color: var(--text);
    }}

    .project-body {{
      padding: 0 14px 14px;
      font-size: 0.82rem;
      line-height: 1.55;
    }}

    .project-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: start;
    }}

    h2 {{
      margin: 0 0 3px;
      font-size: 1.12rem;
      line-height: 1.25;
      letter-spacing: 0;
    }}

    .summary {{
      margin: 0;
      color: var(--muted);
      font-size: 0.93rem;
      overflow-wrap: anywhere;
    }}

    .status,
    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 0.74rem;
      font-weight: 700;
      white-space: nowrap;
    }}

    .status-active {{ background: #e3f3e9; color: var(--green); }}
    .status-waiting {{ background: #fff3cf; color: var(--gold); }}
    .status-paused {{ background: #e9eef3; color: #536170; }}
    .status-archived {{ background: #f5dfe3; color: var(--red); }}

    .project-meta,
    .tags,
    .progress-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px 10px;
      align-items: center;
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.84rem;
    }}

    .project-meta .updated {{
      flex: 0 0 auto;
    }}

    .project-meta .current-issue {{
      flex: 1 1 420px;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .tag {{
      background: #eef3f8;
      color: var(--blue);
    }}

    .progress-row span:last-child {{
      color: var(--muted);
      font-size: 0.84rem;
    }}

    .progress-track {{
      position: relative;
      height: 7px;
      flex: 1 1 180px;
      max-width: 360px;
      background: #edf0ec;
      border-radius: 999px;
      overflow: hidden;
    }}

    .progress-track span {{
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--green), var(--blue));
    }}

    .project-sections {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px 18px;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }}

    .project-section h3,
    .history summary {{
      margin: 0 0 6px;
      color: #27313a;
      font-size: 0.84rem;
      font-weight: 800;
    }}

    .project-section p,
    .history p {{
      margin: 0 0 8px;
      overflow-wrap: anywhere;
    }}

    .item-list {{
      margin: 0;
      padding-left: 1.15rem;
    }}

    .item-list li {{
      margin: 3px 0;
      overflow-wrap: anywhere;
    }}

    .paged-item[hidden] {{
      display: none;
    }}

    .pager {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 8px 0 2px;
      color: var(--muted);
      font-size: 0.76rem;
    }}

    .pager button {{
      border: 1px solid var(--line);
      background: #f9faf7;
      color: #2f3a43;
      border-radius: 6px;
      padding: 3px 9px;
      font: inherit;
      cursor: pointer;
    }}

    .pager button:hover:not(:disabled) {{
      border-color: #aab7c0;
      background: #ffffff;
    }}

    .pager button:disabled {{
      cursor: default;
      opacity: 0.45;
    }}

    .pager-info {{
      min-width: 46px;
      text-align: center;
    }}

    .task {{
      list-style: none;
      display: grid;
      grid-template-columns: 18px minmax(0, 1fr);
      gap: 7px;
      margin-left: -1.15rem;
    }}

    .box {{
      width: 15px;
      height: 15px;
      margin-top: 0.28rem;
      border: 1px solid #aeb8b1;
      border-radius: 4px;
      background: #ffffff;
    }}

    .done .box {{
      border-color: var(--green);
      background: var(--green);
      box-shadow: inset 0 0 0 3px #ffffff;
    }}

    .done span:last-child {{
      color: var(--muted);
    }}

    del {{
      color: var(--muted);
    }}

    .history {{
      margin-top: 10px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }}

    .history summary {{
      cursor: pointer;
    }}

    .source {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 0.78rem;
      overflow-wrap: anywhere;
    }}

    code {{
      overflow-wrap: anywhere;
      word-break: break-word;
    }}

    .muted {{
      color: var(--muted);
    }}

    .empty-state {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
    }}

    footer {{
      margin-top: 24px;
      color: var(--muted);
      font-size: 0.88rem;
    }}

    @media (max-width: 760px) {{
      .metrics,
      .project-sections {{
        grid-template-columns: 1fr;
      }}

      .toolbar {{
        align-items: stretch;
        flex-direction: column;
      }}

      h1 {{
        font-size: 2rem;
      }}

      .hero-links {{
        position: static;
      }}

      .project-head {{
        grid-template-columns: 1fr;
      }}
    }}

    @media (max-width: 480px) {{
      .status-divider {{
        align-items: flex-start;
        flex-direction: column;
      }}

      .inactive-summary {{
        text-align: left;
        white-space: normal;
      }}

      .inactive-project-card > .project-summary {{
        grid-template-columns: minmax(0, 1fr);
        gap: 4px;
      }}

      .inactive-project-card .project-meta,
      .inactive-project-card .progress-row {{
        white-space: normal;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <p class="kicker">Research Management</p>
      <h1>科研进展 Dashboard</h1>
      <div class="system-clock" id="systemClock" aria-label="系统时间"></div>
      <nav class="hero-links" aria-label="dashboard links">
        <a href="README.md">维护说明</a>
        <a href="AGENT_DASHBOARD_GUIDE.md">Agent 约定</a>
        <a href="projects/_template.md">新研究模板</a>
      </nav>
    </div>
  </header>

  <main class="wrap">
    <section class="metrics" aria-label="summary metrics">
      <div class="metric"><strong id="metricTotal">{total}</strong><span>研究项目</span></div>
      <div class="metric"><strong id="metricActive">{active}</strong><span>正在推进</span></div>
      <div class="metric"><strong id="metricOpen">{open_issues + next_steps}</strong><span>进行中未完成问题与计划</span></div>
      <div class="metric metric-token"><strong id="metricCodexUsage">{html.escape(codex_usage_text)}</strong></div>
    </section>

    <section class="toolbar" aria-label="filters">
      <input id="searchInput" type="search" placeholder="搜索题目、问题、文件、标签">
      <select id="statusFilter" aria-label="按状态筛选">
        <option value="all">全部状态</option>
        <option value="active">Active</option>
        <option value="waiting">Waiting</option>
        <option value="paused">Paused</option>
        <option value="archived">Archived</option>
      </select>
      <label class="sort-control">
        <span>排列方式</span>
        <select id="orderModeSelect" aria-label="排列方式">
          <option value="custom">自定义顺序</option>
          <option value="updated">按更新时间</option>
        </select>
      </label>
      <button id="resetButton" type="button">重置</button>
      <button id="expandAllButton" type="button">展开进行中</button>
      <button id="collapseAllButton" type="button">折叠全部</button>
      <button id="clearAlertsButton" type="button">清理全部提醒</button>
    </section>

    <section class="project-grid" id="projectGrid">
      {cards}
    </section>

    <footer>
      Generated at {html.escape(generated_at)} from <code>research-dashboard/projects/*.md</code>.
    </footer>
  </main>

  <script>
    const searchInput = document.getElementById("searchInput");
    const statusFilter = document.getElementById("statusFilter");
    const orderModeSelect = document.getElementById("orderModeSelect");
    const resetButton = document.getElementById("resetButton");
    const expandAllButton = document.getElementById("expandAllButton");
    const collapseAllButton = document.getElementById("collapseAllButton");
    const clearAlertsButton = document.getElementById("clearAlertsButton");
    const projectGrid = document.getElementById("projectGrid");
    const systemClock = document.getElementById("systemClock");
    const metricTotal = document.getElementById("metricTotal");
    const metricActive = document.getElementById("metricActive");
    const metricOpen = document.getElementById("metricOpen");
    const metricCodexUsage = document.getElementById("metricCodexUsage");
    let cards = Array.from(document.querySelectorAll(".project-card"));
    let baseOrder = new Map(cards.map((card, index) => [card.dataset.slug, index]));
    const orderStorageKey = "research-dashboard-project-order-v1";
    const seenStorageKey = "research-dashboard-project-seen-v1";
    const inactiveCollapsedStorageKey = "research-dashboard-inactive-collapsed-v1";
    const inactiveStatuses = new Set(["waiting", "paused", "archived"]);
    const dashboardDataUrl = "dashboard-data.json";
    const pageSchemaVersion = "{html.escape(DATA_SCHEMA_VERSION)}";
    const refreshIntervalMs = 5000;
    const inactiveDivider = document.createElement("div");
    let dragMoved = false;
    let seenHashes = loadSeenHashes();
    let inactiveCollapsed = localStorage.getItem(inactiveCollapsedStorageKey) !== "0";

    function isInactiveStatus(status) {{
      return inactiveStatuses.has(status);
    }}

    inactiveDivider.className = "status-divider";
    inactiveDivider.innerHTML = `
      <button class="inactive-toggle" type="button" aria-expanded="false">未激活 / 暂停 / 归档</button>
      <span class="inactive-summary"></span>
    `;

    function updateSystemClock() {{
      const now = new Date();
      systemClock.textContent = now.toLocaleString("zh-CN", {{
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }});
    }}

    function loadSeenHashes() {{
      try {{
        const saved = JSON.parse(localStorage.getItem(seenStorageKey) || "{{}}");
        return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {{}};
      }} catch {{
        localStorage.removeItem(seenStorageKey);
        return {{}};
      }}
    }}

    function saveSeenHashes() {{
      localStorage.setItem(seenStorageKey, JSON.stringify(seenHashes));
    }}

    function initializeSeenHashes() {{
      let changed = false;
      cards.forEach((card) => {{
        const slug = card.dataset.slug;
        const hash = card.dataset.hash;
        if (slug && hash && !seenHashes[slug]) {{
          seenHashes[slug] = hash;
          changed = true;
        }} else if (slug && hash && seenHashes[slug] !== hash) {{
          card.classList.add("project-updated");
        }}
      }});
      if (changed) saveSeenHashes();
    }}

    function acknowledgeCard(card) {{
      const slug = card.dataset.slug;
      const hash = card.dataset.hash;
      if (!slug || !hash) return;
      seenHashes[slug] = hash;
      saveSeenHashes();
      card.classList.remove("project-updated");
    }}

    function clearAllAlerts() {{
      cards.forEach((card) => {{
        const slug = card.dataset.slug;
        const hash = card.dataset.hash;
        if (slug && hash) seenHashes[slug] = hash;
        card.classList.remove("project-updated");
      }});
      saveSeenHashes();
    }}

    function htmlToCard(markup) {{
      const template = document.createElement("template");
      template.innerHTML = markup.trim();
      return template.content.firstElementChild;
    }}

    function updatePagedList(list, page) {{
      const pages = Number(list.dataset.pages || "1");
      const currentPage = Math.min(Math.max(Number(page) || 1, 1), pages);
      list.dataset.page = String(currentPage);

      list.querySelectorAll(".paged-item").forEach((item) => {{
        item.hidden = Number(item.dataset.page || "1") !== currentPage;
      }});

      const info = list.querySelector(".pager-info");
      const prev = list.querySelector(".pager-prev");
      const next = list.querySelector(".pager-next");
      if (info) info.textContent = `${{currentPage}} / ${{pages}}`;
      if (prev) prev.disabled = currentPage <= 1;
      if (next) next.disabled = currentPage >= pages;
    }}

    function wirePagedLists(root = document) {{
      root.querySelectorAll(".paged-list").forEach((list) => {{
        if (list.dataset.pagerWired === "true") {{
          updatePagedList(list, Number(list.dataset.page || "1"));
          return;
        }}
        list.dataset.pagerWired = "true";
        const prev = list.querySelector(".pager-prev");
        const next = list.querySelector(".pager-next");
        if (prev) {{
          prev.addEventListener("click", () => {{
            updatePagedList(list, Number(list.dataset.page || "1") - 1);
          }});
        }}
        if (next) {{
          next.addEventListener("click", () => {{
            updatePagedList(list, Number(list.dataset.page || "1") + 1);
          }});
        }}
        updatePagedList(list, Number(list.dataset.page || "1"));
      }});
    }}

    function updateMetrics(metrics) {{
      if (!metrics) return;
      metricTotal.textContent = metrics.total ?? metricTotal.textContent;
      metricActive.textContent = metrics.active ?? metricActive.textContent;
      metricOpen.textContent = metrics.open ?? metricOpen.textContent;
      metricCodexUsage.textContent = metrics.codex_usage_label ?? metricCodexUsage.textContent;
    }}

    function savedCustomOrder() {{
      try {{
        const saved = JSON.parse(localStorage.getItem(orderStorageKey) || "[]");
        return Array.isArray(saved) ? saved : [];
      }} catch {{
        localStorage.removeItem(orderStorageKey);
        return [];
      }}
    }}

    function saveOrder() {{
      const order = Array.from(projectGrid.querySelectorAll(".project-card"))
        .map((card) => card.dataset.slug)
        .filter(Boolean);
      localStorage.setItem(orderStorageKey, JSON.stringify(order));
    }}

    function compareUpdated(a, b) {{
      const aTime = Date.parse((a.dataset.updated || "").replace(" ", "T")) || 0;
      const bTime = Date.parse((b.dataset.updated || "").replace(" ", "T")) || 0;
      if (aTime !== bTime) return bTime - aTime;
      return (baseOrder.get(a.dataset.slug) || 0) - (baseOrder.get(b.dataset.slug) || 0);
    }}

    function customOrderedCards() {{
      const saved = savedCustomOrder();
      const bySlug = new Map(cards.map((card) => [card.dataset.slug, card]));
      const used = new Set();
      const ordered = [];

      saved.forEach((slug) => {{
        const card = bySlug.get(slug);
        if (card && !used.has(slug)) {{
          ordered.push(card);
          used.add(slug);
        }}
      }});

      cards
        .filter((card) => !used.has(card.dataset.slug))
        .sort((a, b) => (baseOrder.get(a.dataset.slug) || 0) - (baseOrder.get(b.dataset.slug) || 0))
        .forEach((card) => ordered.push(card));

      return ordered;
    }}

    function orderedCardsForMode() {{
      if (orderModeSelect.value === "updated") {{
        return [...cards].sort(compareUpdated);
      }}
      return customOrderedCards();
    }}

    function renderOrder() {{
      const ordered = orderedCardsForMode();
      const activeCards = ordered.filter((card) => card.dataset.status === "active");
      const inactiveCards = ordered.filter((card) => isInactiveStatus(card.dataset.status));
      const otherCards = ordered.filter((card) =>
        card.dataset.status !== "active" && !isInactiveStatus(card.dataset.status)
      );

      if (inactiveDivider.parentNode) inactiveDivider.remove();
      activeCards.forEach((card) => projectGrid.appendChild(card));
      otherCards.forEach((card) => projectGrid.appendChild(card));
      if (inactiveCards.length > 0) projectGrid.appendChild(inactiveDivider);
      inactiveCards.forEach((card) => projectGrid.appendChild(card));
      applyFilters();
    }}

    function parseUpdatedTime(card) {{
      return Date.parse((card.dataset.updated || "").replace(" ", "T")) || 0;
    }}

    function updateInactiveDivider() {{
      const inactiveMatching = cards.filter((card) =>
        isInactiveStatus(card.dataset.status) && card.dataset.filterMatch === "true"
      );
      inactiveDivider.style.display = inactiveMatching.length ? "" : "none";
      inactiveDivider.classList.toggle("is-collapsed", inactiveCollapsed);

      const toggle = inactiveDivider.querySelector(".inactive-toggle");
      if (toggle) toggle.setAttribute("aria-expanded", String(!inactiveCollapsed));

      const latest = inactiveMatching.reduce((best, card) => {{
        const updated = card.dataset.updated || "";
        const time = parseUpdatedTime(card);
        return time > best.time ? {{ time, updated }} : best;
      }}, {{ time: 0, updated: "" }});

      const summary = inactiveDivider.querySelector(".inactive-summary");
      if (summary) {{
        summary.textContent = `${{inactiveMatching.length}} 个项目 · 最后更新 ${{latest.updated || "未知"}}`;
      }}
    }}

    function collapseInactiveCards() {{
      cards.forEach((card) => {{
        if (isInactiveStatus(card.dataset.status)) card.open = false;
      }});
    }}

    function getDragAfterElement(y, dragging) {{
      const draggingIsActive = dragging.dataset.status === "active";
      const candidates = Array.from(projectGrid.querySelectorAll(".project-card:not(.dragging)"))
        .filter((card) => card.style.display !== "none")
        .filter((card) => (card.dataset.status === "active") === draggingIsActive);

      return candidates.reduce((closest, child) => {{
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {{
          return {{ offset, element: child }};
        }}
        return closest;
      }}, {{ offset: Number.NEGATIVE_INFINITY, element: null }}).element;
    }}

    function applyFilters() {{
      const query = searchInput.value.trim().toLowerCase();
      const status = statusFilter.value;

      cards.forEach((card) => {{
        const matchesStatus = status === "all" || card.dataset.status === status;
        const matchesQuery = !query || card.dataset.search.includes(query);
        const shouldShow = matchesStatus && matchesQuery;
        const isInactive = isInactiveStatus(card.dataset.status);
        card.dataset.filterMatch = shouldShow ? "true" : "false";
        card.style.display = shouldShow && !(isInactive && inactiveCollapsed) ? "" : "none";
        if (isInactive && shouldShow) card.open = false;
      }});

      updateInactiveDivider();
    }}

    searchInput.addEventListener("input", applyFilters);
    statusFilter.addEventListener("change", applyFilters);
    orderModeSelect.addEventListener("change", renderOrder);
    resetButton.addEventListener("click", () => {{
      searchInput.value = "";
      statusFilter.value = "all";
      orderModeSelect.value = "custom";
      renderOrder();
      searchInput.focus();
    }});

    expandAllButton.addEventListener("click", () => {{
      inactiveCollapsed = false;
      localStorage.setItem(inactiveCollapsedStorageKey, "0");
      applyFilters();
      cards.forEach((card) => {{
        if (card.dataset.status === "active" && card.style.display !== "none") card.open = true;
      }});
    }});

    collapseAllButton.addEventListener("click", () => {{
      cards.forEach((card) => {{
        card.open = false;
      }});
      inactiveCollapsed = true;
      localStorage.setItem(inactiveCollapsedStorageKey, "1");
      applyFilters();
    }});

    clearAlertsButton.addEventListener("click", clearAllAlerts);

    inactiveDivider.querySelector(".inactive-toggle").addEventListener("click", () => {{
      inactiveCollapsed = !inactiveCollapsed;
      localStorage.setItem(inactiveCollapsedStorageKey, inactiveCollapsed ? "1" : "0");
      if (!inactiveCollapsed) collapseInactiveCards();
      applyFilters();
    }});

    function wireCard(card) {{
      if (card.dataset.wired === "true") return;
      card.dataset.wired = "true";
      wirePagedLists(card);
      const summary = card.querySelector(".project-summary");

      summary.addEventListener("click", (event) => {{
        if (dragMoved) {{
          event.preventDefault();
          dragMoved = false;
          return;
        }}
        if (isInactiveStatus(card.dataset.status)) {{
          event.preventDefault();
          card.open = false;
          return;
        }}
        acknowledgeCard(card);
      }});

      card.addEventListener("dragstart", (event) => {{
        if (orderModeSelect.value !== "custom") {{
          event.preventDefault();
          return;
        }}
        dragMoved = false;
        card.classList.add("dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", card.dataset.slug || "");
      }});

      card.addEventListener("dragend", () => {{
        card.classList.remove("dragging");
        saveOrder();
        renderOrder();
        window.setTimeout(() => {{
          dragMoved = false;
        }}, 0);
      }});
    }}

    function refreshCardsFromData(data) {{
      if (!data || !Array.isArray(data.projects)) return;
      if (data.schema_version && data.schema_version !== pageSchemaVersion) {{
        window.location.reload();
        return;
      }}

      updateMetrics(data.metrics);
      const existingBySlug = new Map(cards.map((card) => [card.dataset.slug, card]));
      const incomingSlugs = new Set();
      const openSlugs = new Set(cards.filter((card) => card.open).map((card) => card.dataset.slug));

      data.projects.forEach((project) => {{
        if (!project.slug || !project.card_html) return;
        incomingSlugs.add(project.slug);
        const existing = existingBySlug.get(project.slug);

        if (existing && existing.dataset.hash === project.hash) return;

        const nextCard = htmlToCard(project.card_html);
        if (!nextCard) return;
        if (project.status === "active" && openSlugs.has(project.slug)) nextCard.open = true;

        const seenHash = seenHashes[project.slug];
        if (!seenHash || seenHash !== project.hash) {{
          nextCard.classList.add("project-updated");
        }}

        wireCard(nextCard);
        if (existing) {{
          existing.replaceWith(nextCard);
        }} else {{
          projectGrid.appendChild(nextCard);
        }}
      }});

      cards.forEach((card) => {{
        if (!incomingSlugs.has(card.dataset.slug)) {{
          card.remove();
          delete seenHashes[card.dataset.slug];
        }}
      }});

      cards = Array.from(projectGrid.querySelectorAll(".project-card"));
      baseOrder = new Map(data.projects.map((project, index) => [project.slug, index]));
      saveSeenHashes();
      renderOrder();
    }}

    function loadDashboardDataWithXhr(url) {{
      return new Promise((resolve, reject) => {{
        const xhr = new XMLHttpRequest();
        xhr.overrideMimeType("application/json");
        xhr.open("GET", url, true);
        xhr.onload = () => {{
          if (xhr.status === 0 || (xhr.status >= 200 && xhr.status < 300)) {{
            try {{
              resolve(JSON.parse(xhr.responseText));
            }} catch (error) {{
              reject(error);
            }}
          }} else {{
            reject(new Error(`HTTP ${{xhr.status}}`));
          }}
        }};
        xhr.onerror = () => reject(new Error("XHR failed"));
        xhr.send();
      }});
    }}

    async function loadDashboardData() {{
      const url = `${{dashboardDataUrl}}?t=${{Date.now()}}`;
      try {{
        const response = await fetch(url, {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        return await response.json();
      }} catch (fetchError) {{
        try {{
          return await loadDashboardDataWithXhr(url);
        }} catch (xhrError) {{
          if (window.location.protocol === "file:") {{
            return loadDashboardDataWithXhr(dashboardDataUrl);
          }}
          throw xhrError || fetchError;
        }}
      }}
    }}

    let polling = false;
    async function pollDashboardData() {{
      if (polling) return;
      polling = true;
      try {{
        const data = await loadDashboardData();
        refreshCardsFromData(data);
      }} catch (error) {{
        console.debug("Dashboard auto-refresh unavailable:", error);
      }} finally {{
        polling = false;
      }}
    }}

    projectGrid.addEventListener("dragover", (event) => {{
      if (orderModeSelect.value !== "custom") return;
      event.preventDefault();
      dragMoved = true;
      const dragging = document.querySelector(".project-card.dragging");
      if (!dragging) return;
      const afterElement = getDragAfterElement(event.clientY, dragging);
      if (afterElement == null) {{
        if (dragging.dataset.status === "active" && inactiveDivider.parentNode) {{
          projectGrid.insertBefore(dragging, inactiveDivider);
        }} else {{
          projectGrid.appendChild(dragging);
        }}
      }} else {{
        projectGrid.insertBefore(dragging, afterElement);
      }}
    }});

    cards.forEach(wireCard);
    initializeSeenHashes();
    updateSystemClock();
    renderOrder();
    pollDashboardData();
    window.setInterval(updateSystemClock, 1000);
    window.setInterval(pollDashboardData, refreshIntervalMs);
  </script>
</body>
</html>
"""


def main() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = load_projects()
    OUTPUT_FILE.write_text(render(projects), encoding="utf-8", newline="\n")
    DATA_FILE.write_text(
        json.dumps(dashboard_payload(projects), ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"Generated {OUTPUT_FILE} and {DATA_FILE} with {len(projects)} project(s).")


if __name__ == "__main__":
    main()
