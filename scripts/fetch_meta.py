#!/usr/bin/env python3
"""
fetch_meta.py — 抓取微信文章元数据（og:title / og:description / var nickname）

用法:
    python fetch_meta.py <mp.weixin.qq.com URL>
    python fetch_meta.py --json '<url>'

输出 (JSON):
    {"ok": true, "title": "...", "description": "...", "nickname": "...", "author": "...", "error": null}
"""

import subprocess
import re
import sys
import json
import time
from html import unescape
from html.parser import HTMLParser


UAS = [
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
]

NICKNAME_RE = re.compile(r"""var nickname\s*=\s*['"]([^'"]+)['"]""")


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attr_map = {k.lower(): v for k, v in attrs if v is not None}
        prop = attr_map.get("property") or attr_map.get("name")
        content = attr_map.get("content")
        if prop and content:
            self.og[prop] = unescape(content).strip()


def _re_first(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    return unescape(m.group(1)).strip() if m else None


def _extract_og(html: str) -> dict[str, str]:
    parser = _MetaParser()
    parser.feed(html)
    return parser.og


def _curl_once(url: str, ua: str) -> str | None:
    """单次 curl，返回 HTML 或 None"""
    try:
        r = subprocess.run(
            [
                "curl", "-s", "-L", "--max-time", "10",
                "-H", f"User-Agent: {ua}",
                "-H", "Referer: https://mp.weixin.qq.com/",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=12,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
    except (subprocess.TimeoutExpired, Exception):
        pass
    return None


def fetch_meta(url: str) -> dict:
    """抓取微信文章元数据，最多 2 次尝试（换 UA）"""
    for i, ua in enumerate(UAS):
        if i > 0:
            time.sleep(2)
        html = _curl_once(url, ua)
        if not html:
            continue

        og = _extract_og(html)
        title = og.get("og:title")
        if title:
            return {
                "ok": True,
                "title": title,
                "description": og.get("og:description"),
                "nickname": _re_first(NICKNAME_RE, html),
                "author": og.get("author") or og.get("og:article:author"),
                "error": None,
            }

    return {
        "ok": False,
        "title": None,
        "description": None,
        "nickname": None,
        "author": None,
        "error": "无法获取文章标题：两次 curl 均未能提取 og:title",
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "用法: fetch_meta.py <url>"}, ensure_ascii=False))
        sys.exit(1)

    url = sys.argv[1]
    result = fetch_meta(url)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
