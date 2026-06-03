#!/usr/bin/env python3
"""
Read real article statistics exported by the local WeChat downloader tool.

Supported CSV columns from qiye45/wechatDownload:
    title,url,time,like_num,read_num,share_num,comment_count

Configuration:
    WECHAT_DOWNLOADER_CSV      absolute path to one exported CSV file
    WECHAT_DOWNLOADER_CSV_DIR  directory containing exported CSV files

The provider never launches the third-party executable and never sends data
to a remote endpoint. It only parses local CSV files the user already exported.
"""

from __future__ import annotations

import csv
import html
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PROVIDER = "wechat_downloader_csv"
REQUIRED_COLUMNS = {"title", "url", "like_num", "read_num", "share_num"}


def _error(message: str) -> dict:
    return {
        "ok": False,
        "provider": PROVIDER,
        "read_count": 0,
        "like_count": 0,
        "share_count": 0,
        "confidence": "none",
        "partial": False,
        "error": message,
    }


def _stats(read_count: int, like_count: int, share_count: int, csv_path: Path) -> dict:
    return {
        "ok": True,
        "provider": PROVIDER,
        "read_count": read_count,
        "like_count": like_count,
        "share_count": share_count,
        "confidence": "high",
        "partial": False,
        "error": None,
        "source_file": str(csv_path),
    }


def _candidate_csv_files() -> list[Path]:
    explicit = os.environ.get("WECHAT_DOWNLOADER_CSV")
    if explicit:
        return [Path(explicit).expanduser()]

    csv_dir = os.environ.get("WECHAT_DOWNLOADER_CSV_DIR")
    if not csv_dir:
        return []

    root = Path(csv_dir).expanduser()
    if not root.exists() or not root.is_dir():
        return [root]

    files = [p for p in root.glob("*.csv") if p.is_file()]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not path.is_file():
        raise IsADirectoryError(str(path))

    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return []
                normalized_fields = [name.strip() for name in reader.fieldnames]
                rows = []
                for raw in reader:
                    rows.append({(k or "").strip(): (v or "").strip() for k, v in raw.items()})
                if not REQUIRED_COLUMNS.issubset(set(normalized_fields)):
                    missing = ", ".join(sorted(REQUIRED_COLUMNS - set(normalized_fields)))
                    raise ValueError(f"CSV missing required columns: {missing}")
                return rows
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def _clean_url(url: str) -> str:
    return html.unescape((url or "").strip())


def _article_key(url: str) -> tuple[str, ...]:
    parsed = urlparse(_clean_url(url))
    query = parse_qs(parsed.query)
    if parsed.path.startswith("/s/"):
        slug = parsed.path.rsplit("/", 1)[-1].strip()
        if slug:
            return ("slug", slug)

    parts = []
    for name in ("__biz", "mid", "idx", "sn"):
        value = (query.get(name) or [""])[0]
        if value:
            parts.append(f"{name}={value}")
    if parts:
        return ("query", *parts)

    return ("url", re.sub(r"#.*$", "", _clean_url(url)))


def _url_matches(target_url: str, row_url: str) -> bool:
    target = _clean_url(target_url)
    row = _clean_url(row_url)
    if not target or not row:
        return False
    if target == row:
        return True
    return _article_key(target) == _article_key(row)


def _parse_int(value: str) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not re.fullmatch(r"\d+", text):
        return None
    return int(text)


def _row_to_result(row: dict, csv_path: Path) -> dict:
    read_count = _parse_int(row.get("read_num", ""))
    like_count = _parse_int(row.get("like_num", ""))
    share_count = _parse_int(row.get("share_num", ""))
    if read_count is None or like_count is None or share_count is None:
        return _error("matched row exists, but read_num/like_num/share_num is missing or invalid")
    if read_count <= 0 and like_count <= 0 and share_count <= 0:
        return _error("matched row statistics are all zero; treat as invalid export, not real stats")
    return _stats(read_count, like_count, share_count, csv_path)


def fetch(url: str) -> dict:
    files = _candidate_csv_files()
    if not files:
        return _error(
            "not_configured: set WECHAT_DOWNLOADER_CSV to the exported CSV file, "
            "or WECHAT_DOWNLOADER_CSV_DIR to the export directory"
        )

    errors = []
    for path in files:
        try:
            rows = _read_csv_rows(path)
        except Exception as exc:
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue

        for row in rows:
            if _url_matches(url, row.get("url", "")):
                return _row_to_result(row, path)

    detail = "; ".join(errors[:3])
    suffix = f" Errors: {detail}" if detail else ""
    return _error(f"article_not_found_in_export_csv: {url}.{suffix}")
