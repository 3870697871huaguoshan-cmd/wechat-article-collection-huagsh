"""
wechat_session.py — 微信登录态接口

仅在用户显式指定 provider=wechat_session 且通过环境变量临时提供
Cookie/session 参数时调用。不保存 cookie/token，不打印敏感信息。

必需环境变量:
    WECHAT_SESSION_COOKIE

可选环境变量:
    WECHAT_APPMSG_TOKEN
    WECHAT_PASS_TICKET
    WECHAT_UIN
    WECHAT_KEY
    WECHAT_WXTOKEN (默认 777)

接口: mp.weixin.qq.com/mp/getappmsgext
可能返回: read_num, like_num, old_like_num
"""

from __future__ import annotations

import os
from urllib.parse import parse_qs, urlencode, urlparse

from ._wechat_http import http_get, http_post_json, js_var


def _empty(error: str) -> dict:
    return {
        "ok": False,
        "provider": "wechat_session",
        "read_count": 0,
        "like_count": 0,
        "share_count": 0,
        "confidence": "none",
        "partial": False,
        "error": error,
    }


def _ok(read_count: int, like_count: int) -> dict:
    return {
        "ok": True,
        "provider": "wechat_session",
        "read_count": read_count,
        "like_count": like_count,
        "share_count": 0,
        "confidence": "medium",
        "partial": True,
        "error": None,
    }


def _extract_params(url: str, html: str) -> dict[str, str]:
    qs = parse_qs(urlparse(url).query)
    params = {
        "__biz": (qs.get("__biz") or [None])[0] or js_var(html, "biz", "__biz"),
        "mid": (qs.get("mid") or [None])[0] or js_var(html, "mid", "appmsgid"),
        "idx": (qs.get("idx") or [None])[0] or js_var(html, "idx", "itemidx") or "1",
        "sn": (qs.get("sn") or [None])[0] or js_var(html, "sn"),
        "appmsg_token": (
            (qs.get("appmsg_token") or [None])[0]
            or os.environ.get("WECHAT_APPMSG_TOKEN")
            or js_var(html, "appmsg_token")
        ),
        "pass_ticket": (qs.get("pass_ticket") or [None])[0] or os.environ.get("WECHAT_PASS_TICKET") or "",
        "uin": os.environ.get("WECHAT_UIN") or "",
        "key": os.environ.get("WECHAT_KEY") or "",
    }
    return {k: v for k, v in params.items() if v}


def fetch(url: str) -> dict:
    cookie = os.environ.get("WECHAT_SESSION_COOKIE")
    if not cookie:
        return _empty("not_configured: WECHAT_SESSION_COOKIE not set")

    try:
        html = http_get(url, cookie)
        params = _extract_params(url, html)
        required = ["__biz", "mid", "idx", "sn", "appmsg_token"]
        missing = [key for key in required if not params.get(key)]
        if missing:
            return _empty(f"missing_params: {','.join(missing)}")

        query = {
            "__biz": params["__biz"],
            "mid": params["mid"],
            "idx": params["idx"],
            "sn": params["sn"],
            "appmsg_token": params["appmsg_token"],
            "pass_ticket": params.get("pass_ticket", ""),
            "uin": params.get("uin", ""),
            "key": params.get("key", ""),
            "wxtoken": os.environ.get("WECHAT_WXTOKEN", "777"),
            "f": "json",
        }
        ext_url = "https://mp.weixin.qq.com/mp/getappmsgext?" + urlencode(query)
        data = http_post_json(
            ext_url,
            {"is_only_read": "1", "is_temp_url": "0", "appmsg_type": "9", "reward_uin_count": "0"},
            cookie,
            url,
        )

        stat = data.get("appmsgstat") or {}
        read_count = int(stat.get("read_num") or 0)
        like_count = int(stat.get("like_num") or stat.get("old_like_num") or 0)
        if data.get("base_resp", {}).get("ret") not in (None, 0):
            return _empty("session_expired_or_rejected")
        return _ok(read_count, like_count)
    except Exception as e:
        return _empty(f"wechat_session_failed: {type(e).__name__}")
