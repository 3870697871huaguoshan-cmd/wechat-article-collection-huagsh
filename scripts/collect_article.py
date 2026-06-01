#!/usr/bin/env python3
"""
collect_article.py — 微信公众号文章收藏主入口

用法:
    python collect_article.py <url> [--topic <主题>] [--keywords <关键词>] [--summary]

流程:
    1. fetch_meta       → og:title / og:description / nickname
    2. search_enrich    → 补全公众号名称（nickname 缺失时）
    3. base_records     → 两级查重 (链接 → 标题)
    4. base_records     → 写入 Base
    5. (可选) summary   → extractor → og:description 降级

输出:
    {
      "ok": true,
      "status": "created | duplicate | failed",
      "record_id": "recxxx",
      "title": "...",
      "source": "...",
      "url": "...",
      "data_status": "完整 | 缺公众号名称 | 缺统计数据 | 抓取失败",
      "message": "...",
      "summary": "..." | null
    }
"""

import sys
import json
import os
import subprocess
import re
from urllib.parse import urlparse

# 确保可以导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_meta
import search_enrich
import base_records


def normalize_wechat_url(url: str) -> str:
    """校验并规范化微信文章链接。保留原查询参数，避免破坏文章访问。"""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("链接必须以 http:// 或 https:// 开头")
    if parsed.netloc.lower() != "mp.weixin.qq.com":
        raise ValueError("只支持 mp.weixin.qq.com 微信文章链接")
    if not (parsed.path == "/s" or parsed.path.startswith("/s/")):
        raise ValueError("只支持 /s 或 /s/... 形式的微信文章链接")
    return url


def _extractor_scripts_dir() -> str:
    return os.path.expanduser(
        os.environ.get(
            "WECHAT_ARTICLE_EXTRACTOR_DIR",
            "~/.hermes/hermes-agent/skills/wechat-article-extractor/scripts",
        )
    )


def _compute_data_status(meta_ok: bool, source: str) -> str:
    if not meta_ok:
        return "抓取失败"
    if source == "待补充":
        return "缺公众号名称"
    # 默认都是缺统计数据（主流程不抓 stats）
    return "缺统计数据"


def collect_article(
    url: str,
    topic: str = "",
    keywords: str = "",
    summary: bool = False,
) -> dict:
    """收藏一篇微信文章"""
    try:
        url = normalize_wechat_url(url)
    except ValueError as e:
        return {
            "ok": False,
            "status": "failed",
            "record_id": None,
            "title": None,
            "source": None,
            "url": url,
            "data_status": "抓取失败",
            "message": f"无法收藏：{e}",
            "summary": None,
        }

    # Step 1: 抓元数据
    meta = fetch_meta.fetch_meta(url)
    if not meta["ok"] or not meta["title"]:
        return {
            "ok": False,
            "status": "failed",
            "record_id": None,
            "title": meta.get("title"),
            "source": None,
            "url": url,
            "data_status": "抓取失败",
            "message": f"无法收藏：不能获取文章标题。{meta.get('error', '')}",
            "summary": None,
        }

    # Step 2: 公众号名称补全
    nickname = meta.get("nickname")
    if not nickname:
        enrich = search_enrich.enrich_nickname(meta["title"], url)
        if enrich["ok"]:
            nickname = enrich["source"]
        else:
            nickname = "待补充"

    # Step 3: 查重
    dup = base_records.search_duplicate_by_url(url)
    if dup.get("error"):
        return {
            "ok": False, "status": "failed", "record_id": None,
            "title": meta["title"], "source": nickname, "url": url,
            "data_status": "抓取失败",
            "message": f"查重失败，已停止写入以避免重复收藏：{dup['error']}",
            "summary": None,
        }
    if dup["found"]:
        return {
            "ok": True, "status": "duplicate", "record_id": dup.get("record_id"),
            "title": meta["title"], "source": nickname, "url": url,
            "data_status": None,
            "message": f"这篇文章已收藏过，无需重复写入。\n匹配字段：文章链接",
            "summary": None,
        }

    dup = base_records.search_duplicate_by_title(meta["title"])
    if dup.get("error"):
        return {
            "ok": False, "status": "failed", "record_id": None,
            "title": meta["title"], "source": nickname, "url": url,
            "data_status": "抓取失败",
            "message": f"查重失败，已停止写入以避免重复收藏：{dup['error']}",
            "summary": None,
        }
    if dup["found"]:
        return {
            "ok": True, "status": "duplicate", "record_id": dup.get("record_id"),
            "title": meta["title"], "source": nickname, "url": url,
            "data_status": None,
            "message": f"这篇文章已收藏过，无需重复写入。\n匹配字段：文章标题",
            "summary": None,
        }

    # Step 4: 写入
    data_status = _compute_data_status(True, nickname)
    fields = {
        "文章标题": meta["title"],
        "公众号名称": nickname,
        "文章链接": url,
        "主题关键词": topic,
        "文章关键词": keywords,
        "阅读数": 0,
        "点赞数": 0,
        "转发数": 0,
        "统计来源": "none",
        "数据状态": data_status,
    }
    result = base_records.create_record(fields)
    if not result["ok"]:
        return {
            "ok": False, "status": "failed", "record_id": None,
            "title": meta["title"], "source": nickname, "url": url,
            "data_status": _compute_data_status(True, nickname),
            "message": f"写入飞书 Base 失败：{result.get('error', '未知错误')}",
            "summary": None,
        }

    # 构建消息
    msg = f"已收藏：{meta['title']}\n公众号：{nickname}\n链接：{url}"
    if nickname == "待补充":
        msg += "\n注意：公众号名称未能自动获取，已写为\"待补充\"，可在表格中手动补全。"
    msg += "\n\n阅读数/点赞数/转发数默认填 0。可通过 stats_provider 补录统计数据。"

    output = {
        "ok": True,
        "status": "created",
        "record_id": result.get("record_id"),
        "title": meta["title"],
        "source": nickname,
        "url": url,
        "data_status": data_status,
        "message": msg,
        "summary": None,
    }

    # Step 5: Summary Mode (可选)
    if summary:
        output["summary"] = _generate_summary(url, meta)

    return output


def _generate_summary(url: str, meta: dict) -> str | None:
    """尝试生成摘要，失败不阻塞"""
    # 尝试 extractor
    try:
        r = subprocess.run(
            ["node", "extract_wechat.js", url],
            cwd=_extractor_scripts_dir(),
            capture_output=True,
            text=True,
            timeout=20,
            encoding="utf-8",
            errors="replace",
        )
        data = json.loads(r.stdout)
        if data.get("code") == 0 and data.get("msg_content"):
            text = re.sub(r'<[^>]+>', '', data["msg_content"])
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) >= 800:
                # 返回原文，由 AI 调用方按模板生成摘要
                return text
    except Exception:
        pass

    # 降级：og:description
    desc = meta.get("description") or meta.get("desc")
    if desc:
        return f"微信正文提取失败（通常需要登录态）。以下是基于页面摘要的降级总结：\n\n{desc}"

    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="收藏微信公众号文章")
    parser.add_argument("url", help="mp.weixin.qq.com 文章链接")
    parser.add_argument("--topic", default="", help="主题关键词")
    parser.add_argument("--keywords", default="", help="文章关键词")
    parser.add_argument("--summary", action="store_true", help="同时生成摘要")
    args = parser.parse_args()

    result = collect_article(args.url, args.topic, args.keywords, args.summary)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
