#!/usr/bin/env python3
"""Shared helpers for WeChat article/session HTTP providers."""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlencode
from urllib.request import Request, urlopen


UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def js_var(html: str, *names: str) -> str | None:
    for name in names:
        patterns = [
            rf'var\s+{re.escape(name)}\s*=\s*["\']([^"\']*)["\']',
            rf'{re.escape(name)}\s*:\s*["\']([^"\']*)["\']',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return unescape(m.group(1)).strip()
    return None


def http_get(url: str, cookie: str) -> str:
    req = Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://mp.weixin.qq.com/",
        "Cookie": cookie,
    })
    with urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_post_json(url: str, body: dict[str, str], cookie: str, referer: str) -> dict:
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
