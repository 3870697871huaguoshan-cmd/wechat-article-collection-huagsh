#!/usr/bin/env python3
"""
Initialize local WeChat statistics authorization storage.

This script stores authorization material in a local JSON file. It is a
bootstrap helper for the self-owned stats capture flow; collection scripts read
the file automatically afterwards.
"""

from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path


DEFAULT_SESSION_FILE = Path.home() / ".hermes" / "wechat_stats_session.json"


def main():
    parser = argparse.ArgumentParser(description="初始化微信公众号统计采集授权")
    parser.add_argument("--session-file", default=str(DEFAULT_SESSION_FILE), help="授权文件保存路径")
    parser.add_argument("--cookie", default=None, help="微信授权 Cookie；不传则交互输入")
    parser.add_argument("--appmsg-token", default="", help="可选 appmsg_token")
    parser.add_argument("--pass-ticket", default="", help="可选 pass_ticket")
    parser.add_argument("--uin", default="", help="可选 uin")
    parser.add_argument("--key", default="", help="可选 key")
    parser.add_argument("--wxtoken", default="777", help="可选 wxtoken")
    args = parser.parse_args()

    cookie = args.cookie
    if not cookie:
        cookie = getpass.getpass("输入微信授权 Cookie（输入内容不会回显）：").strip()
    if not cookie:
        parser.error("必须提供 Cookie")

    path = Path(args.session_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cookie": cookie,
        "appmsg_token": args.appmsg_token,
        "pass_ticket": args.pass_ticket,
        "uin": args.uin,
        "key": args.key,
        "wxtoken": args.wxtoken,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "session_file": str(path),
        "message": "微信统计采集授权已保存；后续 collect_article.py 会自动读取。",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
