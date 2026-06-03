"""
third_party.py — 第三方数据 API

环境变量:
    WECHAT_STATS_API_URL  必需。接收 POST JSON {"url": "..."} 的接口。
    WECHAT_STATS_API_KEY  可选。存在时以 Bearer token 传入。

兼容响应字段:
    read_count / read_num / read
    like_count / like_num / old_like_num / like
    share_count / share_num / share
"""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


def _empty(error: str) -> dict:
    return {
        "ok": False,
        "provider": "third_party",
        "read_count": 0,
        "like_count": 0,
        "share_count": 0,
        "confidence": "none",
        "partial": False,
        "error": error,
    }


def _as_int(value) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _pick(data: dict, *keys: str):
    for key in keys:
        if key in data:
            return data[key]
    return None


def fetch(url: str) -> dict:
    endpoint = os.environ.get("WECHAT_STATS_API_URL")
    api_key = os.environ.get("WECHAT_STATS_API_KEY")
    if not endpoint:
        return _empty("not_configured: WECHAT_STATS_API_URL not set")

    body = json.dumps({"url": url}, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = Request(endpoint, data=body, headers=headers)
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except Exception as e:
        return _empty(f"third_party_failed: {type(e).__name__}")

    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return _empty("invalid_response: expected JSON object")

    ok = payload.get("ok", True) if isinstance(payload, dict) else False
    if ok is False:
        return _empty(str(payload.get("error") or "third_party_error"))

    return {
        "ok": True,
        "provider": "third_party",
        "read_count": _as_int(_pick(data, "read_count", "read_num", "read")),
        "like_count": _as_int(_pick(data, "like_count", "like_num", "old_like_num", "like")),
        "share_count": _as_int(_pick(data, "share_count", "share_num", "share")),
        "confidence": str(data.get("confidence") or payload.get("confidence") or "medium"),
        "partial": bool(data.get("partial", payload.get("partial", False))),
        "error": None,
    }
