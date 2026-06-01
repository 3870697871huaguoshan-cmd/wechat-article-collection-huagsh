#!/usr/bin/env python3
"""
search_enrich.py — 通过 wechat-article-search 补全公众号名称

用法:
    python search_enrich.py '<标题>' '<文章URL>'
    python search_enrich.py --title '<标题>' --url '<文章URL>'

输出 (JSON):
    {"ok": true, "source": "公众号名称", "candidates": [...], "method": "exact_match | url_match | single | pending"}
"""

import subprocess
import json
import sys
import os
import re

SEARCH_SCRIPT_DIR = os.path.expanduser(
    "~/.hermes/hermes-agent/skills/wechat-article-search"
)
SEARCH_SCRIPT = "scripts/search_wechat.js"


def _run_search(keyword: str, n: int = 5) -> list[dict]:
    """调用 wechat-article-search，返回结果列表"""
    try:
        r = subprocess.run(
            ["node", SEARCH_SCRIPT, keyword, "-n", str(n), "-r"],
            cwd=SEARCH_SCRIPT_DIR,
            capture_output=True, text=True, timeout=15,
        )
        items = json.loads(r.stdout)
        if isinstance(items, list):
            return items
    except Exception:
        pass
    return []


def _candidate_keywords(title: str) -> list[str]:
    """先用完整标题，失败后再用较短关键词补搜。"""
    title = (title or "").strip()
    if not title:
        return []

    candidates = [title]
    compact = re.sub(r"\s+", "", title)
    for size in (12, 8, 6, 4):
        if len(compact) >= size:
            candidates.append(compact[:size])
    return list(dict.fromkeys(candidates))


def enrich_nickname(title: str, article_url: str = "") -> dict:
    """
    用标题搜索补全公众号名称。
    返回:
        {"ok": bool, "source": str|None, "candidates": list[str], "method": str}
    """
    if not title:
        return {"ok": False, "source": None, "candidates": [], "method": "no_title"}

    items: list[dict] = []
    for keyword in _candidate_keywords(title):
        items = _run_search(keyword, n=5)
        if items:
            break

    if not items:
        return {"ok": False, "source": None, "candidates": [], "method": "no_results"}

    # 过滤空 source
    valid = [it for it in items if it.get("source")]
    if not valid:
        return {"ok": False, "source": None, "candidates": [], "method": "all_source_empty"}

    # 收集唯一 source
    unique_sources = list(dict.fromkeys(it["source"] for it in valid))
    candidates = unique_sources[:5]  # max 5 candidates

    # 单个 source → 直接返回
    if len(unique_sources) == 1:
        return {
            "ok": True, "source": unique_sources[0],
            "candidates": candidates, "method": "single",
        }

    # 多个不一致 → 标题精确匹配
    for it in valid:
        if it.get("title") == title:
            return {
                "ok": True, "source": it["source"],
                "candidates": candidates, "method": "exact_match",
            }

    # 多 source → URL 文章 ID 匹配
    if article_url:
        aid_match = re.search(r'/s/([a-zA-Z0-9_-]+)', article_url)
        if aid_match:
            aid = aid_match.group(1)
            for it in valid:
                if aid in (it.get("url") or ""):
                    return {
                        "ok": True, "source": it["source"],
                        "candidates": candidates, "method": "url_match",
                    }

    # 无法确认 → 返回 None + 候选列表
    return {
        "ok": False, "source": None,
        "candidates": candidates, "method": "pending",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="补全公众号名称")
    parser.add_argument("--title", required=True, help="文章标题")
    parser.add_argument("--url", default="", help="文章 URL（用于匹配）")
    args = parser.parse_args()

    result = enrich_nickname(args.title, args.url)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    # 支持命令行位置参数
    if len(sys.argv) >= 3 and not sys.argv[1].startswith("--"):
        title, url = sys.argv[1], sys.argv[2]
        result = enrich_nickname(title, url)
        print(json.dumps(result, ensure_ascii=False))
    else:
        main()
