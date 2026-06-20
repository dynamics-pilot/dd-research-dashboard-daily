# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DEFAULT_CODEX_HOME = Path.home() / ".codex"
DEFAULT_ZCODE_HOME = Path.home() / ".zcode"
DEFAULT_CHATBOX_HOME = Path.home() / "AppData" / "Roaming" / "xyz.chatboxapp.app"
SUMMARY_JSON = CONFIG_DIR / "codex-usage-summary.json"


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_billions(value: int) -> str:
    return f"{value / 1_000_000_000:.2f}B"


def empty_breakdown() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens_from_rollouts": 0,
        "threads_with_usage_breakdown": 0,
        "threads_without_usage_breakdown": 0,
        "zcode_requests_with_usage": 0,
        "chatbox_messages_with_usage": 0,
        "chatbox_messages_without_usage": 0,
        "unclassified_total_tokens": 0,
    }


def add_breakdown(target: dict[str, int], source: dict[str, Any]) -> None:
    for key in (
        "input_tokens",
        "output_tokens",
        "cached_input_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "reasoning_output_tokens",
        "total_tokens_from_rollouts",
        "threads_with_usage_breakdown",
        "threads_without_usage_breakdown",
        "zcode_requests_with_usage",
        "chatbox_messages_with_usage",
        "chatbox_messages_without_usage",
        "unclassified_total_tokens",
    ):
        target[key] = int(target.get(key) or 0) + int(source.get(key) or 0)


def parse_source(source: str) -> tuple[bool, str | None]:
    try:
        data = json.loads(source) if source else None
    except json.JSONDecodeError:
        return False, None
    if not isinstance(data, dict) or "subagent" not in data:
        return False, None
    spawn = data.get("subagent", {}).get("thread_spawn", {})
    if isinstance(spawn, dict):
        return True, spawn.get("parent_thread_id")
    return True, None


def month_from_epoch(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m")


def read_rollout_usage(path: Path) -> dict[str, int] | None:
    if not path.exists():
        return None

    latest: dict[str, int] | None = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                payload = event.get("payload")
                if not isinstance(payload, dict) or payload.get("type") != "token_count":
                    continue

                info = payload.get("info")
                if not isinstance(info, dict):
                    continue

                usage = info.get("total_token_usage")
                if not isinstance(usage, dict):
                    continue

                latest = {
                    "input_tokens": int(usage.get("input_tokens") or 0),
                    "output_tokens": int(usage.get("output_tokens") or 0),
                    "cached_input_tokens": int(usage.get("cached_input_tokens") or 0),
                    "cache_creation_input_tokens": int(
                        usage.get("cache_creation_input_tokens") or 0
                    ),
                    "cache_read_input_tokens": int(
                        usage.get("cache_read_input_tokens")
                        or usage.get("cached_input_tokens")
                        or 0
                    ),
                    "reasoning_output_tokens": int(
                        usage.get("reasoning_output_tokens") or 0
                    ),
                    "total_tokens": int(usage.get("total_tokens") or 0),
                }
    except OSError:
        return None

    return latest


def read_usage(codex_home: Path) -> dict:
    db_path = codex_home / "state_5.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"Codex state database not found: {db_path}")

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = con.cursor()
    rows = list(
        cur.execute(
            """
            SELECT id, title, tokens_used, created_at, updated_at, source, rollout_path,
                   model, model_provider, reasoning_effort
            FROM threads
            """
        )
    )
    con.close()

    threads: list[dict] = []
    for (
        thread_id,
        title,
        tokens_used,
        created_at,
        updated_at,
        source,
        rollout_path,
        model,
        provider,
        effort,
    ) in rows:
        is_subagent, parent_thread_id = parse_source(source or "")
        created_key = int(created_at or updated_at or 0)
        threads.append(
            {
                "id": thread_id,
                "title": title or "",
                "tokens": int(tokens_used or 0),
                "rollout_path": rollout_path or "",
                "created_at": int(created_at or 0),
                "updated_at": int(updated_at or 0),
                "month": month_from_epoch(created_key) if created_key else "unknown",
                "is_subagent": is_subagent,
                "parent_thread_id": parent_thread_id,
                "model": model or "unknown",
                "provider": provider or "unknown",
                "reasoning_effort": effort or "unknown",
            }
        )

    by_month: dict[str, dict] = defaultdict(
        lambda: {"threads": 0, "tokens": 0, "main_tokens": 0, "subagent_tokens": 0}
    )
    by_model: dict[str, dict] = defaultdict(lambda: {"threads": 0, "tokens": 0})
    by_effort: dict[str, dict] = defaultdict(lambda: {"threads": 0, "tokens": 0})

    for item in threads:
        month = by_month[item["month"]]
        month["threads"] += 1
        month["tokens"] += item["tokens"]
        if item["is_subagent"]:
            month["subagent_tokens"] += item["tokens"]
        else:
            month["main_tokens"] += item["tokens"]

        model = by_model[item["model"]]
        model["threads"] += 1
        model["tokens"] += item["tokens"]

        effort = by_effort[item["reasoning_effort"]]
        effort["threads"] += 1
        effort["tokens"] += item["tokens"]

    total_tokens = sum(item["tokens"] for item in threads)
    main_tokens = sum(item["tokens"] for item in threads if not item["is_subagent"])
    subagent_tokens = sum(item["tokens"] for item in threads if item["is_subagent"])
    nonzero = [item["tokens"] for item in threads if item["tokens"]]

    top_threads = sorted(threads, key=lambda item: item["tokens"], reverse=True)[:20]
    token_usage_breakdown = empty_breakdown()
    for item in threads:
        rollout_path = item.get("rollout_path") or ""
        usage = read_rollout_usage(Path(rollout_path)) if rollout_path else None
        if usage is None:
            token_usage_breakdown["threads_without_usage_breakdown"] += 1
            continue
        token_usage_breakdown["threads_with_usage_breakdown"] += 1
        token_usage_breakdown["input_tokens"] += usage["input_tokens"]
        token_usage_breakdown["output_tokens"] += usage["output_tokens"]
        token_usage_breakdown["cached_input_tokens"] += usage["cached_input_tokens"]
        token_usage_breakdown["cache_creation_input_tokens"] += usage[
            "cache_creation_input_tokens"
        ]
        token_usage_breakdown["cache_read_input_tokens"] += usage[
            "cache_read_input_tokens"
        ]
        token_usage_breakdown["reasoning_output_tokens"] += usage[
            "reasoning_output_tokens"
        ]
        token_usage_breakdown["total_tokens_from_rollouts"] += usage["total_tokens"]

    return {
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "codex_home": str(codex_home),
        "thread_count": len(threads),
        "nonzero_thread_count": len(nonzero),
        "main_thread_count": sum(1 for item in threads if not item["is_subagent"]),
        "subagent_thread_count": sum(1 for item in threads if item["is_subagent"]),
        "total_tokens": total_tokens,
        "token_usage_breakdown": token_usage_breakdown,
        "main_tokens": main_tokens,
        "subagent_tokens": subagent_tokens,
        "by_month": dict(sorted(by_month.items())),
        "by_model": dict(
            sorted(by_model.items(), key=lambda item: item[1]["tokens"], reverse=True)
        ),
        "by_effort": dict(
            sorted(by_effort.items(), key=lambda item: item[1]["tokens"], reverse=True)
        ),
        "top_threads": top_threads,
    }


def usage_from_openai_payload(payload: dict[str, Any]) -> dict[str, int] | None:
    response = payload.get("response")
    if isinstance(response, dict):
        usage = response.get("usage")
        if payload.get("model") is None and response.get("model") is not None:
            payload["model"] = response.get("model")
    else:
        usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None

    input_details = usage.get("input_tokens_details")
    if not isinstance(input_details, dict):
        input_details = {}
    output_details = usage.get("output_tokens_details")
    if not isinstance(output_details, dict):
        output_details = {}

    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(
        usage.get("output_tokens") or usage.get("completion_tokens") or 0
    )
    cached_input_tokens = int(
        usage.get("cached_input_tokens")
        or usage.get("cache_read_input_tokens")
        or input_details.get("cached_tokens")
        or 0
    )
    cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens") or 0)
    reasoning_output_tokens = int(
        usage.get("reasoning_output_tokens")
        or output_details.get("reasoning_tokens")
        or 0
    )
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cached_input_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
    }


def response_payloads_from_text(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return [parsed] if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        pass

    payloads: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payloads.append(parsed)
    return payloads


def read_zcode_capture_usage(captures_dir: Path) -> dict[str, Any]:
    breakdown = empty_breakdown()
    by_month: dict[str, dict[str, int]] = defaultdict(
        lambda: {"requests": 0, "tokens": 0}
    )
    by_model: dict[str, dict[str, int]] = defaultdict(
        lambda: {"requests": 0, "tokens": 0}
    )
    per_request: dict[str, dict[str, Any]] = {}
    files_read = 0

    if not captures_dir.exists():
        return {
            "files_read": 0,
            "request_count": 0,
            "token_usage_breakdown": breakdown,
            "by_month": {},
            "by_model": {},
        }

    for path in sorted(captures_dir.glob("*.ndjson")):
        files_read += 1
        try:
            handle = path.open("r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "http_response_chunk":
                    continue
                data = event.get("data")
                if not isinstance(data, str):
                    continue
                for payload in response_payloads_from_text(data):
                    usage = usage_from_openai_payload(payload)
                    if usage is None:
                        continue
                    request_id = str(
                        event.get("requestId")
                        or event.get("connectionId")
                        or f"{path.name}:{line_number}"
                    )
                    model = str(payload.get("model") or "unknown")
                    at_ms = int(event.get("at") or 0)
                    month = (
                        datetime.fromtimestamp(at_ms / 1000, timezone.utc).strftime(
                            "%Y-%m"
                        )
                        if at_ms
                        else "unknown"
                    )
                    current = per_request.get(request_id)
                    if current is None or usage["total_tokens"] >= int(
                        current["usage"].get("total_tokens") or 0
                    ):
                        per_request[request_id] = {
                            "usage": usage,
                            "model": model,
                            "month": month,
                        }

    for item in per_request.values():
        usage = item["usage"]
        breakdown["input_tokens"] += usage["input_tokens"]
        breakdown["output_tokens"] += usage["output_tokens"]
        breakdown["cached_input_tokens"] += usage["cached_input_tokens"]
        breakdown["cache_creation_input_tokens"] += usage[
            "cache_creation_input_tokens"
        ]
        breakdown["cache_read_input_tokens"] += usage["cache_read_input_tokens"]
        breakdown["reasoning_output_tokens"] += usage["reasoning_output_tokens"]
        breakdown["total_tokens_from_rollouts"] += usage["total_tokens"]
        breakdown["zcode_requests_with_usage"] += 1

        month = by_month[item["month"]]
        month["requests"] += 1
        month["tokens"] += usage["total_tokens"]

        model = by_model[item["model"]]
        model["requests"] += 1
        model["tokens"] += usage["total_tokens"]

    return {
        "files_read": files_read,
        "request_count": len(per_request),
        "token_usage_breakdown": breakdown,
        "by_month": dict(sorted(by_month.items())),
        "by_model": dict(
            sorted(by_model.items(), key=lambda item: item[1]["tokens"], reverse=True)
        ),
    }


def read_zcode_cli_db_usage(db_path: Path) -> dict[str, Any]:
    breakdown = empty_breakdown()
    if not db_path.exists():
        return {
            "db_path": str(db_path),
            "request_count": 0,
            "token_usage_breakdown": breakdown,
            "by_model": {},
        }

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    tables = {
        row["name"]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "model_usage" not in tables:
        con.close()
        return {
            "db_path": str(db_path),
            "request_count": 0,
            "token_usage_breakdown": breakdown,
            "by_model": {},
        }

    by_model: dict[str, dict[str, int]] = defaultdict(
        lambda: {"requests": 0, "tokens": 0}
    )
    request_count = 0
    for row in con.execute(
        """
        SELECT model_id,input_tokens,output_tokens,reasoning_tokens,
               cache_creation_input_tokens,cache_read_input_tokens,
               computed_total_tokens,provider_total_tokens
        FROM model_usage
        """
    ):
        request_count += 1
        input_tokens = int(row["input_tokens"] or 0)
        output_tokens = int(row["output_tokens"] or 0)
        cache_creation = int(row["cache_creation_input_tokens"] or 0)
        cache_read = int(row["cache_read_input_tokens"] or 0)
        reasoning = int(row["reasoning_tokens"] or 0)
        total = int(
            row["computed_total_tokens"]
            or row["provider_total_tokens"]
            or input_tokens + output_tokens
        )
        breakdown["input_tokens"] += input_tokens
        breakdown["output_tokens"] += output_tokens
        breakdown["cached_input_tokens"] += cache_read
        breakdown["cache_creation_input_tokens"] += cache_creation
        breakdown["cache_read_input_tokens"] += cache_read
        breakdown["reasoning_output_tokens"] += reasoning
        breakdown["total_tokens_from_rollouts"] += total
        breakdown["zcode_requests_with_usage"] += 1

        model = by_model[str(row["model_id"] or "unknown")]
        model["requests"] += 1
        model["tokens"] += total
    con.close()

    return {
        "db_path": str(db_path),
        "request_count": request_count,
        "token_usage_breakdown": breakdown,
        "by_model": dict(
            sorted(by_model.items(), key=lambda item: item[1]["tokens"], reverse=True)
        ),
    }


def read_zcode_usage(zcode_home: Path) -> dict[str, Any]:
    v2 = zcode_home / "v2"
    capture_usage = read_zcode_capture_usage(
        v2 / "acp-traffic-proxy" / "captures"
    )
    cli_usage = read_zcode_cli_db_usage(zcode_home / "cli" / "db" / "db.sqlite")
    breakdown = empty_breakdown()
    add_breakdown(breakdown, capture_usage["token_usage_breakdown"])
    add_breakdown(breakdown, cli_usage["token_usage_breakdown"])
    total_tokens = int(breakdown["total_tokens_from_rollouts"])

    return {
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "zcode_home": str(zcode_home),
        "total_tokens": total_tokens,
        "request_count": int(capture_usage["request_count"])
        + int(cli_usage["request_count"]),
        "capture_usage": capture_usage,
        "cli_usage": cli_usage,
        "token_usage_breakdown": breakdown,
    }


CHATBOX_MESSAGE_ID_RE = re.compile(r'"id"\s*:\s*"([0-9a-fA-F-]{36})"')
CHATBOX_TOKENS_USED_RE = re.compile(r'"tokensUsed"\s*:\s*(\d+)')
CHATBOX_MODEL_RE = re.compile(r'"model"\s*:\s*"((?:\\.|[^"\\])*)"')
CHATBOX_ASSISTANT_ROLE_RE = re.compile(r'"role"\s*:\s*"assistant"')


def balanced_json_object(text: str, start: int) -> str | None:
    brace = text.find("{", start)
    if brace < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for idx in range(brace, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[brace : idx + 1]
    return None


def chatbox_file_texts(path: Path) -> list[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    texts: list[str] = []
    if b"\x00" in data[:2000] or b't\x00o\x00k\x00e\x00n\x00s\x00U\x00s\x00e\x00d\x00' in data:
        texts.append(data.decode("utf-16le", errors="ignore"))
    texts.append(data.decode("utf-8", errors="ignore"))
    return texts


def parse_chatbox_usage_dict(usage: dict[str, Any]) -> dict[str, int]:
    input_tokens = int(
        usage.get("inputTokens")
        or usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or 0
    )
    output_tokens = int(
        usage.get("outputTokens")
        or usage.get("output_tokens")
        or usage.get("completion_tokens")
        or 0
    )
    cached_tokens = int(
        usage.get("cachedInputTokens") or usage.get("cached_input_tokens") or 0
    )
    input_details = usage.get("inputTokenDetails") or usage.get("input_tokens_details")
    if isinstance(input_details, dict):
        cached_tokens = max(
            cached_tokens,
            int(
                input_details.get("cacheReadTokens")
                or input_details.get("cached_tokens")
                or 0
            ),
        )
    reasoning_tokens = int(
        usage.get("reasoningTokens") or usage.get("reasoning_output_tokens") or 0
    )
    output_details = usage.get("outputTokenDetails") or usage.get(
        "output_tokens_details"
    )
    if isinstance(output_details, dict):
        reasoning_tokens = max(
            reasoning_tokens,
            int(
                output_details.get("reasoningTokens")
                or output_details.get("reasoning_tokens")
                or 0
            ),
        )
    total_tokens = int(
        usage.get("totalTokens")
        or usage.get("total_tokens")
        or input_tokens + output_tokens
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_tokens,
        "reasoning_output_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def read_chatbox_usage(chatbox_home: Path) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    files_scanned = 0
    files_skipped = 0
    indexeddb = chatbox_home / "IndexedDB"
    scan_roots = [
        indexeddb / "file__0.indexeddb.blob",
        indexeddb / "file__0.indexeddb.leveldb",
    ]

    for base in scan_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.stat().st_size > 20_000_000:
                continue
            texts = chatbox_file_texts(path)
            if not texts:
                files_skipped += 1
                continue
            files_scanned += 1
            for text in texts:
                for match in CHATBOX_TOKENS_USED_RE.finditer(text):
                    pos = match.start()
                    tokens_used = int(match.group(1))
                    left = text[max(0, pos - 8000) : pos]
                    right = text[pos : min(len(text), pos + 5000)]
                    id_matches = list(CHATBOX_MESSAGE_ID_RE.finditer(left))
                    if id_matches:
                        message_id = id_matches[-1].group(1)
                        id_start = id_matches[-1].start() + max(0, pos - 8000)
                    else:
                        message_id = f"{path}:{pos}"
                        id_start = max(0, pos - 1000)
                    role_area = text[id_start : pos + 1000]
                    if not CHATBOX_ASSISTANT_ROLE_RE.search(role_area):
                        continue

                    usage_obj = None
                    usage_idx = right.find('"usage"')
                    if usage_idx >= 0:
                        raw_usage = balanced_json_object(right, usage_idx)
                        if raw_usage:
                            try:
                                parsed_usage = json.loads(raw_usage)
                            except json.JSONDecodeError:
                                parsed_usage = None
                            if isinstance(parsed_usage, dict):
                                usage_obj = parse_chatbox_usage_dict(parsed_usage)

                    model_matches = list(CHATBOX_MODEL_RE.finditer(left + right[:1000]))
                    model = model_matches[-1].group(1) if model_matches else "unknown"

                    current = records.get(message_id)
                    if current is not None and tokens_used < int(
                        current.get("total_tokens") or 0
                    ):
                        continue

                    if usage_obj is None:
                        usage_obj = {
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "cached_input_tokens": 0,
                            "reasoning_output_tokens": 0,
                            "total_tokens": tokens_used,
                        }
                        has_usage = False
                    else:
                        if usage_obj["total_tokens"] <= 0:
                            usage_obj["total_tokens"] = tokens_used
                        has_usage = True
                    usage_obj["model"] = model
                    usage_obj["has_usage"] = has_usage
                    records[message_id] = usage_obj

    breakdown = empty_breakdown()
    by_model: dict[str, dict[str, int]] = defaultdict(
        lambda: {"messages": 0, "tokens": 0}
    )
    for item in records.values():
        total_tokens = int(item.get("total_tokens") or 0)
        if item.get("has_usage"):
            breakdown["input_tokens"] += int(item.get("input_tokens") or 0)
            breakdown["output_tokens"] += int(item.get("output_tokens") or 0)
            breakdown["cached_input_tokens"] += int(
                item.get("cached_input_tokens") or 0
            )
            breakdown["cache_read_input_tokens"] += int(
                item.get("cached_input_tokens") or 0
            )
            breakdown["reasoning_output_tokens"] += int(
                item.get("reasoning_output_tokens") or 0
            )
            breakdown["chatbox_messages_with_usage"] += 1
        else:
            breakdown["unclassified_total_tokens"] += total_tokens
            breakdown["chatbox_messages_without_usage"] += 1
        breakdown["total_tokens_from_rollouts"] += total_tokens

        model = by_model[str(item.get("model") or "unknown")]
        model["messages"] += 1
        model["tokens"] += total_tokens

    return {
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "chatbox_home": str(chatbox_home),
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "message_count": len(records),
        "message_count_with_usage": int(breakdown["chatbox_messages_with_usage"]),
        "message_count_without_usage": int(
            breakdown["chatbox_messages_without_usage"]
        ),
        "total_tokens": int(breakdown["total_tokens_from_rollouts"]),
        "token_usage_breakdown": breakdown,
        "by_model": dict(
            sorted(by_model.items(), key=lambda item: item[1]["tokens"], reverse=True)
        ),
    }


def combined_usage(
    codex: dict[str, Any], zcode: dict[str, Any], chatbox: dict[str, Any]
) -> dict[str, Any]:
    breakdown = empty_breakdown()
    add_breakdown(breakdown, codex.get("token_usage_breakdown") or {})
    add_breakdown(breakdown, zcode.get("token_usage_breakdown") or {})
    add_breakdown(breakdown, chatbox.get("token_usage_breakdown") or {})
    total_tokens = int(codex.get("total_tokens") or 0) + int(
        zcode.get("total_tokens") or 0
    ) + int(chatbox.get("total_tokens") or 0)

    combined = dict(codex)
    combined.update(
        {
            "generated_at": datetime.now()
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S %z"),
            "source_label": "Codex+ZCode+Chatbox",
            "sources": ["codex", "zcode", "chatbox"],
            "total_tokens": total_tokens,
            "token_usage_breakdown": breakdown,
            "codex_total_tokens": int(codex.get("total_tokens") or 0),
            "zcode_total_tokens": int(zcode.get("total_tokens") or 0),
            "chatbox_total_tokens": int(chatbox.get("total_tokens") or 0),
            "zcode_request_count": int(zcode.get("request_count") or 0),
            "chatbox_message_count": int(chatbox.get("message_count") or 0),
            "chatbox_message_count_with_usage": int(
                chatbox.get("message_count_with_usage") or 0
            ),
            "chatbox_message_count_without_usage": int(
                chatbox.get("message_count_without_usage") or 0
            ),
            "codex": codex,
            "zcode": zcode,
            "chatbox": chatbox,
        }
    )
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update Codex token usage summary for the research dashboard."
    )
    parser.add_argument(
        "--codex-home",
        default=str(DEFAULT_CODEX_HOME),
        help="Path to Codex home. Defaults to the current user's .codex directory.",
    )
    parser.add_argument(
        "--zcode-home",
        default=str(DEFAULT_ZCODE_HOME),
        help="Path to ZCode home. Defaults to the current user's .zcode directory.",
    )
    parser.add_argument(
        "--chatbox-home",
        default=str(DEFAULT_CHATBOX_HOME),
        help="Path to Chatbox app data. Defaults to the current user's Chatbox data directory.",
    )
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser().resolve()
    zcode_home = Path(args.zcode_home).expanduser().resolve()
    chatbox_home = Path(args.chatbox_home).expanduser().resolve()
    codex_summary = read_usage(codex_home)
    zcode_summary = read_zcode_usage(zcode_home)
    chatbox_summary = read_chatbox_usage(chatbox_home)
    summary = combined_usage(codex_summary, zcode_summary, chatbox_summary)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Updated {SUMMARY_JSON}")
    print(f"Codex tokens: {fmt_int(summary['codex_total_tokens'])}")
    print(f"ZCode tokens: {fmt_int(summary['zcode_total_tokens'])}")
    print(f"Chatbox tokens: {fmt_int(summary['chatbox_total_tokens'])}")
    print(f"Combined tokens: {fmt_int(summary['total_tokens'])}")


if __name__ == "__main__":
    main()
