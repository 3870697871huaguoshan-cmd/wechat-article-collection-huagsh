"""
official.py — 微信公众号官方图文统计接口

适用范围:
    仅适用于用户自己拥有统计权限的公众号文章。

环境变量:
    WECHAT_OFFICIAL_ACCESS_TOKEN  可选，优先使用。
    WECHAT_OFFICIAL_APPID / WECHAT_OFFICIAL_SECRET  可选，用于换取 access_token。
    WECHAT_OFFICIAL_BEGIN_DATE / WECHAT_OFFICIAL_END_DATE  可选，YYYY-MM-DD。

说明:
    官方图文分析接口通常提供阅读/分享数据，不稳定提供点赞数，因此
    like_count 置 0 且 partial=True。
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _empty(error: str) -> dict:
    return {
        "ok": False,
        "provider": "official",
        "read_count": 0,
        "like_count": 0,
        "share_count": 0,
        "confidence": "none",
        "partial": True,
        "error": error,
    }


def _ok(read_count: int, share_count: int, confidence: str) -> dict:
    return {
        "ok": True,
        "provider": "official",
        "read_count": read_count,
        "like_count": 0,
        "share_count": share_count,
        "confidence": confidence,
        "partial": True,
        "error": None,
    }


def _as_int(value) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _http_json_get(url: str) -> dict:
    with urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_json_post(url: str, body: dict) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _access_token() -> str | None:
    token = os.environ.get("WECHAT_OFFICIAL_ACCESS_TOKEN")
    if token:
        return token
    appid = os.environ.get("WECHAT_OFFICIAL_APPID")
    secret = os.environ.get("WECHAT_OFFICIAL_SECRET")
    if not appid or not secret:
        return None
    query = urlencode({"grant_type": "client_credential", "appid": appid, "secret": secret})
    data = _http_json_get("https://api.weixin.qq.com/cgi-bin/token?" + query)
    return data.get("access_token")


def _date_range() -> tuple[str, str]:
    yesterday = date.today() - timedelta(days=1)
    begin = os.environ.get("WECHAT_OFFICIAL_BEGIN_DATE") or yesterday.isoformat()
    end = os.environ.get("WECHAT_OFFICIAL_END_DATE") or begin
    return begin, end


def _article_title(url: str) -> str | None:
    explicit = os.environ.get("WECHAT_OFFICIAL_ARTICLE_TITLE")
    if explicit:
        return explicit
    try:
        import fetch_meta

        meta = fetch_meta.fetch_meta(url)
        return meta.get("title") if meta.get("ok") else None
    except Exception:
        return None


def _best_detail(item: dict) -> dict:
    details = item.get("details") or []
    if isinstance(details, list) and details:
        return details[-1]
    return item


def fetch(url: str) -> dict:
    try:
        token = _access_token()
    except Exception as e:
        return _empty(f"token_failed: {type(e).__name__}")
    if not token:
        return _empty("not_configured: WECHAT_OFFICIAL_ACCESS_TOKEN or WECHAT_OFFICIAL_APPID/SECRET not set")

    begin, end = _date_range()
    try:
        data = _http_json_post(
            "https://api.weixin.qq.com/datacube/getarticletotal?access_token=" + token,
            {"begin_date": begin, "end_date": end},
        )
    except Exception as e:
        return _empty(f"official_failed: {type(e).__name__}")

    if data.get("errcode"):
        return _empty(f"official_error: {data.get('errcode')} {data.get('errmsg', '')}".strip())

    items = data.get("list") or data.get("data") or []
    if not isinstance(items, list) or not items:
        return _empty("no_article_stats")

    title = _article_title(url)
    chosen = None
    confidence = "medium"
    if title:
        for item in items:
            if str(item.get("title") or "").strip() == title.strip():
                chosen = item
                confidence = "high"
                break
    if chosen is None and len(items) == 1:
        chosen = items[0]
    if chosen is None:
        return _empty("article_not_found_in_official_stats")

    detail = _best_detail(chosen)
    read_count = _as_int(
        detail.get("int_page_read_count")
        or detail.get("ori_page_read_count")
        or detail.get("read_count")
    )
    share_count = _as_int(detail.get("share_count") or detail.get("share_user"))
    return _ok(read_count, share_count, confidence)
