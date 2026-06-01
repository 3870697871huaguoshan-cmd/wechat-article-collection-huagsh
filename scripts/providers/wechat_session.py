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

import json
import os
import re
from html import unescape
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


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


def _js_var(html: str, *names: str) -> str | None:
    for name in names:
        patterns = [
            rf'var\s+{re.escape(name)}\s*=\s*["\']([^"\']+)["\']',
            rf'{re.escape(name)}\s*:\s*["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return unescape(m.group(1)).strip()
    return None


def _extract_params(url: str, html: str) -> dict[str, str]:
    qs = parse_qs(urlparse(url).query)
    params = {
        "__biz": (qs.get("__biz") or [None])[0] or _js_var(html, "biz", "__biz"),
        "mid": (qs.get("mid") or [None])[0] or _js_var(html, "mid", "appmsgid"),
        "idx": (qs.get("idx") or [None])[0] or _js_var(html, "idx", "itemidx") or "1",
        "sn": (qs.get("sn") or [None])[0] or _js_var(html, "sn"),
        "appmsg_token": (
            (qs.get("appmsg_token") or [None])[0]
            or os.environ.get("WECHAT_APPMSG_TOKEN")
            or _js_var(html, "appmsg_token")
        ),
        "pass_ticket": (qs.get("pass_ticket") or [None])[0] or os.environ.get("WECHAT_PASS_TICKET") or "",
        "uin": os.environ.get("WECHAT_UIN") or "",
        "key": os.environ.get("WECHAT_KEY") or "",
    }
    return {k: v for k, v in params.items() if v}


def _http_get(url: str, cookie: str) -> str:
    req = Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://mp.weixin.qq.com/",
        "Cookie": cookie,
    })
    with urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_post_json(url: str, body: dict[str, str], cookie: str, referer: str) -> dict:
    data = urlencode(body).encode("utf-8")
    req = Request(url, data=data, headers={
        "User-Agent": UA,
        "Referer": referer,
        "Cookie": cookie,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    })
    with urlopen(req, timeout=12) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return json.loads(text)


def fetch(url: str) -> dict:
    cookie = os.environ.get("WECHAT_SESSION_COOKIE")
    if not cookie:
        return _empty("not_configured: WECHAT_SESSION_COOKIE not set")

    try:
        html = _http_get(url, cookie)
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
        data = _http_post_json(
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
