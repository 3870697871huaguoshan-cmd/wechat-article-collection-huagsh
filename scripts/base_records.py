#!/usr/bin/env python3
"""
base_records.py — 飞书 Base 操作封装

封装:
    search_duplicate_by_url(url)          → {"found": bool, "record_id": str|None}
    search_duplicate_by_title(title)      → {"found": bool, "record_id": str|None}
    create_record(fields)                 → {"ok": bool, "record_id": str|None, "error": str|None}
    update_stats(record_id, stats)        → {"ok": bool, "error": str|None}

规则:
    - 查重用 lark-cli base +record-search --format json
    - 写入用 lark-cli base +record-upsert
    - URL 字段传字符串，不传 {link,text}
    - 500/502/503/timeout 指数退避重试 3 次 (2s/4s/8s)
    - 字段类型/字段名/权限错误不重试
"""

import json
import os
import shutil
import subprocess
import time
import sys
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

BASE_TOKEN = "HmeubVX2UazS5RsUyK9ciK3DnJG"
TABLE_ID = "tble8OJWkYYfuKZ5"

RETRYABLE_CODES = {"500", "502", "503", "Gateway Time-out", "Bad Gateway", "Service Unavailable"}
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]
SEARCH_KEYWORD_LIMIT = 50
LARK_CLI_BIN = None


# ── helpers ──────────────────────────────────────────────

@dataclass
class LarkResult:
    stdout: str
    stderr: str
    returncode: int


def _run_lark(argv: list[str], timeout: int = 15) -> subprocess.CompletedProcess | LarkResult:
    global LARK_CLI_BIN
    if LARK_CLI_BIN is None:
        candidates = [
            os.environ.get("LARK_CLI_BIN"),
            shutil.which("lark-cli.cmd"),
            shutil.which("lark-cli.exe"),
            shutil.which("lark-cli"),
        ]
        LARK_CLI_BIN = next((c for c in candidates if c), None)

    if not LARK_CLI_BIN:
        return LarkResult(
            stdout="",
            stderr="lark-cli not found in PATH; set LARK_CLI_BIN to the full path",
            returncode=127,
        )

    try:
        return subprocess.run(
            [LARK_CLI_BIN] + argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        return LarkResult(
            stdout=e.stdout or "",
            stderr=f"timeout: lark-cli exceeded {timeout}s",
            returncode=124,
        )


def _is_retryable(output: str) -> bool:
    for code in RETRYABLE_CODES:
        if code in output:
            return True
    return "timeout" in output.lower()


def _is_field_error(output: str) -> bool:
    field_errors = [
        "URLFieldConvFail", "field type", "field not found",
        "invalid field", "permission", "Unauthorized",
        "AccessDenied", "no permission",
    ]
    combined = output.lower()
    return any(e.lower() in combined for e in field_errors)


def _parse_record_search(stdout: str) -> dict:
    """解析 +record-search 返回，提取 records / record_id_list"""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "records": [], "record_id_list": [], "error": "invalid_json"}

    if isinstance(data, dict) and data.get("ok") is False:
        return {
            "ok": False,
            "records": [],
            "record_id_list": [],
            "error": data.get("error") or data.get("message") or "record_search_failed",
        }

    inner = data.get("data", data)
    records = inner.get("records", inner.get("data", []))
    record_ids = inner.get("record_id_list", [])

    return {"ok": True, "records": records, "record_id_list": record_ids}


def _is_empty_result(parsed: dict) -> bool:
    return len(parsed.get("records", [])) == 0 and len(parsed.get("record_id_list", [])) == 0


def _first_record_id(parsed: dict) -> str | None:
    record_ids = parsed.get("record_id_list") or []
    if record_ids:
        return record_ids[0]

    records = parsed.get("records") or []
    if not records:
        return None
    first = records[0]
    if isinstance(first, dict):
        return first.get("record_id") or first.get("id")
    return None


def _search_duplicate(field_name: str, keyword: str) -> dict:
    if not keyword:
        return {"found": False, "record_id": None, "error": "empty_keyword"}

    r = _run_lark([
        "base", "+record-search", "--as", "user",
        "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
        "--format", "json",
        "--json", json.dumps({
            "keyword": keyword,
            "search_fields": [field_name],
            "select_fields": ["文章标题", "公众号名称", "文章链接"],
            "limit": 1,
        }, ensure_ascii=False),
    ])

    combined = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        return {"found": False, "record_id": None, "error": combined[:500] or "record_search_failed"}

    parsed = _parse_record_search(r.stdout)
    if not parsed.get("ok", False):
        return {"found": False, "record_id": None, "error": str(parsed.get("error"))[:500]}
    if _is_empty_result(parsed):
        return {"found": False, "record_id": None, "error": None}
    return {"found": True, "record_id": _first_record_id(parsed), "error": None}


def _truncate_search_keyword(value: str) -> str:
    return (value or "").strip()[:SEARCH_KEYWORD_LIMIT]


def _url_search_keyword(url: str) -> str | None:
    """record-search keyword 最长 50 字符，微信 URL 查重需提取短文章标识。"""
    parsed = urlparse(url)
    if parsed.path.startswith("/s/"):
        article_id = parsed.path.removeprefix("/s/").strip("/")
        if article_id:
            return _truncate_search_keyword(article_id)

    qs = parse_qs(parsed.query)
    for key in ("sn", "mid", "__biz"):
        values = qs.get(key) or []
        if values and values[0]:
            return _truncate_search_keyword(values[0])

    return None


def _extract_record_id(data: dict) -> str | None:
    inner = data.get("data", {})
    if not isinstance(inner, dict):
        return None
    record = inner.get("record")
    if isinstance(record, dict):
        return record.get("record_id") or record.get("id")
    return inner.get("record_id") or inner.get("id")


# ── public API ───────────────────────────────────────────

def search_duplicate_by_url(url: str) -> dict:
    """按文章链接查重"""
    keyword = _url_search_keyword(url)
    if not keyword:
        return {"found": False, "record_id": None, "error": "unable_to_extract_url_keyword"}
    return _search_duplicate("文章链接", keyword)


def search_duplicate_by_title(title: str) -> dict:
    """按文章标题查重"""
    return _search_duplicate("文章标题", _truncate_search_keyword(title))


def create_record(fields: dict) -> dict:
    """写入记录到飞书 Base，带重试"""
    for attempt in range(MAX_RETRIES):
        r = _run_lark([
            "base", "+record-upsert", "--as", "user",
            "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
            "--json", json.dumps(fields, ensure_ascii=False),
        ])

        try:
            data = json.loads(r.stdout)
            if r.returncode == 0 and data.get("ok"):
                return {
                    "ok": True,
                    "record_id": _extract_record_id(data),
                    "error": None,
                }
        except json.JSONDecodeError:
            pass

        combined = r.stdout + r.stderr

        # 不可重试错误 → 立即返回
        if _is_field_error(combined):
            return {"ok": False, "record_id": None, "error": combined[:500]}

        # 可重试且还有重试次数 → 等待后继续
        if _is_retryable(combined) and attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAYS[attempt])
            continue

        # 非可重试 → 直接返回
        if not _is_retryable(combined):
            return {"ok": False, "record_id": None, "error": combined[:500]}

    return {"ok": False, "record_id": None, "error": "retry_exhausted: 3 attempts all failed"}


def update_stats(record_id: str, stats: dict) -> dict:
    """更新记录的统计数据"""
    # 只更新 stats 相关字段，不覆盖元数据
    fields = {}
    for key in ("阅读数", "点赞数", "转发数", "统计来源", "统计更新时间", "数据状态"):
        if key in stats:
            fields[key] = stats[key]

    if not fields:
        return {"ok": False, "error": "no stats fields to update"}

    for attempt in range(MAX_RETRIES):
        r = _run_lark([
            "base", "+record-upsert", "--as", "user",
            "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
            "--record-id", record_id,
            "--json", json.dumps(fields, ensure_ascii=False),
        ])

        try:
            data = json.loads(r.stdout)
            if r.returncode == 0 and data.get("ok"):
                return {"ok": True, "error": None}
        except json.JSONDecodeError:
            pass

        combined = r.stdout + r.stderr
        if _is_field_error(combined):
            return {"ok": False, "error": combined[:500]}
        if _is_retryable(combined) and attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAYS[attempt])
            continue
        if not _is_retryable(combined):
            return {"ok": False, "error": combined[:500]}

    return {"ok": False, "error": "retry_exhausted: 3 attempts all failed"}


def get_field_list() -> list[dict]:
    """获取当前表字段结构"""
    r = _run_lark([
        "base", "+field-list", "--as", "user",
        "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
    ])
    try:
        data = json.loads(r.stdout)
        return data.get("data", {}).get("fields", [])
    except json.JSONDecodeError:
        return []


# ── CLI ──────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="飞书 Base 记录操作")
    sub = parser.add_subparsers(dest="command")

    dup_url = sub.add_parser("check-url", help="按链接查重")
    dup_url.add_argument("url")

    dup_title = sub.add_parser("check-title", help="按标题查重")
    dup_title.add_argument("title")

    create = sub.add_parser("create", help="创建记录")
    create.add_argument("--json", required=True, help="字段 JSON")

    up_stats = sub.add_parser("update-stats", help="更新统计数据")
    up_stats.add_argument("--record-id", required=True)
    up_stats.add_argument("--json", required=True, help="统计数据 JSON")

    sub.add_parser("fields", help="列出字段")

    args = parser.parse_args()

    if args.command == "check-url":
        result = search_duplicate_by_url(args.url)
    elif args.command == "check-title":
        result = search_duplicate_by_title(args.title)
    elif args.command == "create":
        result = create_record(json.loads(args.json))
    elif args.command == "update-stats":
        result = update_stats(args.record_id, json.loads(args.json))
    elif args.command == "fields":
        result = get_field_list()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
