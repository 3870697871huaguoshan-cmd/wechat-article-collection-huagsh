#!/usr/bin/env python3
"""
Self-owned WeChat article statistics capture.

This provider uses a locally stored WeChat web/session authorization to fetch
real article statistics from mp.weixin.qq.com. It does not require third-party
APIs and does not require users to export CSV files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from ._wechat_http import http_get, http_post_json, js_var


PROVIDER = "wechat_stats_capture"
DEFAULT_SESSION_FILES = [
    Path.home() / ".hermes" / "wechat_stats_session.json",
    Path(__file__).resolve().parents[2] / ".runtime" / "wechat_stats_session.json",
]

def _empty(error: str) -> dict:
    return {
        "ok": False,
        "provider": PROVIDER,
        "read_count": 0,
        "like_count": 0,
        "share_count": 0,
        "confidence": "none",
        "partial": False,
        "error": error,
    }


def _ok(read_count: int, like_count: int, share_count: int) -> dict:
    return {
        "ok": True,
        "provider": PROVIDER,
        "read_count": read_count,
        "like_count": like_count,
        "share_count": share_count,
        "confidence": "high",
        "partial": False,
        "error": None,
    }


def _session_file_candidates() -> list[Path]:
    explicit = os.environ.get("WECHAT_STATS_SESSION_FILE")
    if explicit:
        return [Path(explicit).expanduser()]
    return DEFAULT_SESSION_FILES


def _load_session() -> dict:
    session = {
        "cookie": os.environ.get("WECHAT_SESSION_COOKIE") or "",
        "appmsg_token": os.environ.get("WECHAT_APPMSG_TOKEN") or "",
        "pass_ticket": os.environ.get("WECHAT_PASS_TICKET") or "",
        "uin": os.environ.get("WECHAT_UIN") or "",
        "key": os.environ.get("WECHAT_KEY") or "",
        "wxtoken": os.environ.get("WECHAT_WXTOKEN") or "777",
    }
    for path in _session_file_candidates():
        if not path.exists() or not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key, value in data.items():
                if value and not session.get(key):
                    session[key] = str(value)
    return session


def _extract_params(url: str, html: str, session: dict) -> dict[str, str]:
    qs = parse_qs(urlparse(url).query)
    params = {
        "__biz": (qs.get("__biz") or [None])[0] or js_var(html, "biz", "__biz"),
        "mid": (qs.get("mid") or [None])[0] or js_var(html, "mid", "appmsgid"),
        "idx": (qs.get("idx") or [None])[0] or js_var(html, "idx", "itemidx") or "1",
        "sn": (qs.get("sn") or [None])[0] or js_var(html, "sn"),
        "appmsg_token": (
            (qs.get("appmsg_token") or [None])[0]
            or session.get("appmsg_token")
            or js_var(html, "appmsg_token")
        ),
        "pass_ticket": (qs.get("pass_ticket") or [None])[0] or session.get("pass_ticket") or "",
        "uin": session.get("uin") or "",
        "key": session.get("key") or "",
    }
    return {k: v for k, v in params.items() if v}


def _pick_int(data: dict, *keys: str) -> int | None:
    for key in keys:
        if key in data and data.get(key) is not None:
            try:
                return int(data.get(key) or 0)
            except (TypeError, ValueError):
                return None
    return None


def fetch(url: str) -> dict:
    session = _load_session()
    cookie = session.get("cookie") or ""
    if not cookie:
        return _empty(
            "authorization_required: initialize local WeChat statistics authorization "
            "with scripts/init_wechat_stats_capture.py"
        )

    try:
        html = http_get(url, cookie)
        params = _extract_params(url, html, session)
        required = ["__biz", "mid", "idx", "sn", "appmsg_token"]
        missing = [key for key in required if not params.get(key)]
        if missing:
            return _empty(f"authorization_incomplete: missing {','.join(missing)}")

        query = {
            "__biz": params["__biz"],
            "mid": params["mid"],
            "idx": params["idx"],
            "sn": params["sn"],
            "appmsg_token": params["appmsg_token"],
            "pass_ticket": params.get("pass_ticket", ""),
            "uin": params.get("uin", ""),
            "key": params.get("key", ""),
            "wxtoken": session.get("wxtoken") or "777",
            "f": "json",
        }
        ext_url = "https://mp.weixin.qq.com/mp/getappmsgext?" + urlencode(query)
        data = http_post_json(
            ext_url,
            {"is_only_read": "1", "is_temp_url": "0", "appmsg_type": "9", "reward_uin_count": "0"},
            cookie,
            url,
        )
        if data.get("base_resp", {}).get("ret") not in (None, 0):
            return _empty("authorization_expired_or_rejected")

        stat = data.get("appmsgstat") or {}
        read_count = _pick_int(stat, "read_num", "read_count")
        like_count = _pick_int(stat, "like_num", "old_like_num", "like_count")
        share_count = _pick_int(stat, "share_num", "share_count", "share_count_num")
        missing_stats = []
        if read_count is None:
            missing_stats.append("read_count")
        if like_count is None:
            missing_stats.append("like_count")
        if share_count is None:
            missing_stats.append("share_count")
        if missing_stats:
            available = ",".join(sorted(stat.keys())) or "none"
            return _empty(f"stats_incomplete: missing {','.join(missing_stats)}; available_keys={available}")
        return _ok(read_count, like_count, share_count)
    except Exception as exc:
        return _empty(f"wechat_stats_capture_failed: {type(exc).__name__}")
