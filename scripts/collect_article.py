#!/usr/bin/env python3
"""
collect_article.py — 微信公众号文章收藏主入口

用法:
    python collect_article.py <url> [--topic <主题>] [--keywords <关键词>] [--summary] [--stats-csv <CSV路径>]

流程:
    1. fetch_meta       → og:title / og:description / nickname
    2. search_enrich    → 补全公众号名称（nickname 缺失时）
    3. base_records     → 两级查重 (链接 → 标题)
    4. fetch_stats      → 获取真实阅读/点赞/转发数据
    5. base_records     → 写入 Base
    6. (可选) summary   → extractor → og:description 降级

输出:
    {
      "ok": true,
      "status": "created | duplicate | failed",
      "record_id": "recxxx",
      "title": "...",
      "source": "...",
      "url": "...",
      "data_status": "完整 | 缺公众号名称 | 统计获取失败 | 抓取失败",
      "message": "...",
      "summary": "..." | null
    }
"""

import sys
import json
import os
import subprocess
import re
from datetime import datetime
from urllib.parse import urlparse

# 确保可以导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runtime_env import load_env_files
import fetch_meta
import search_enrich
import base_records
import fetch_stats

SKILL_VERSION = "2026-06-03.3"
LOADED_ENV_FILES = load_env_files()


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
    return "完整"


def _now_lark_datetime() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _auto_topic(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    rules = [
        ("AI", ["ai", "codex", "claude", "agent", "openai", "人工智能", "大模型"]),
        ("编程", ["代码", "编程", "开发", "github", "python", "javascript"]),
        ("效率工具", ["效率", "工具", "工作流", "自动化", "hermes"]),
        ("产品", ["产品", "案例", "使用案例", "use cases"]),
    ]
    hits = [name for name, keywords in rules if any(k in text for k in keywords)]
    return " / ".join(dict.fromkeys(hits[:3]))


def _auto_keywords(title: str, description: str = "") -> str:
    text = f"{title} {description}"
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}|[\u4e00-\u9fff]{2,6}", text)
    stop = {"官方提供", "最佳使用", "使用案例", "最近我在", "发现它", "专门有"}
    seen = []
    for item in candidates:
        if item in stop:
            continue
        if item.lower() not in {x.lower() for x in seen}:
            seen.append(item)
        if len(seen) >= 8:
            break
    return " / ".join(seen)


def _stats_error_message(error: str | None) -> str:
    details = error or "unknown"
    return (
        "无法收藏：未获取到真实阅读/点赞/转发数据，已停止写入。\n"
        "下一步请按固定采集路径处理：\n"
        "1. 打开“微信公众号批量下载工具3.9”。\n"
        "2. 将目标文章链接粘贴到工具，点击“1.获取公众号id”。\n"
        "3. 按工具提示在微信桌面客户端内打开生成链接，等待“获取密钥成功”。\n"
        "4. 点击“2.批量下载文章”或“2.导出文章数据”，导出包含 read_num/like_num/share_num 的 CSV。\n"
        "5. 重新运行本脚本，并传入 --stats-csv <CSV路径>。\n"
        f"当前错误：{details}"
    )


def diagnose_runtime() -> dict:
    csv_path = os.environ.get("WECHAT_DOWNLOADER_CSV")
    csv_dir = os.environ.get("WECHAT_DOWNLOADER_CSV_DIR")
    return {
        "ok": True,
        "skill_version": SKILL_VERSION,
        "loaded_env_files": LOADED_ENV_FILES,
        "base_token_configured": bool(os.environ.get("WECHAT_COLLECTION_BASE_TOKEN")),
        "table_id_configured": bool(os.environ.get("WECHAT_COLLECTION_TABLE_ID")),
        "stats_csv_configured": bool(csv_path),
        "stats_csv_exists": bool(csv_path and os.path.isfile(os.path.expanduser(csv_path))),
        "stats_csv_dir_configured": bool(csv_dir),
        "stats_csv_dir_exists": bool(csv_dir and os.path.isdir(os.path.expanduser(csv_dir))),
        "default_stats_flow": "local_csv",
    }


def _stats_fields(url: str, provider: str, fallback_chain: str | None = None) -> tuple[dict, dict | None]:
    timestamp = _now_lark_datetime()
    if provider == "none":
        return {}, {
            "ok": False,
            "provider": "none",
            "read_count": 0,
            "like_count": 0,
            "share_count": 0,
            "confidence": "none",
            "partial": False,
            "error": "stats_csv_required",
        }

    stats = fetch_stats.fetch_stats(url, provider=provider, fallback_chain=fallback_chain)
    if not stats.get("ok") or stats.get("partial"):
        return {}, stats

    stats_source = stats.get("provider") or provider
    if stats_source == "wechat_downloader_csv":
        # The Base field is an existing single-select. Keep using the existing
        # wechat_session option because the CSV is produced from a WeChat
        # desktop-session credential flow.
        stats_source = "wechat_session"

    fields = {
        "阅读数": int(stats.get("read_count") or 0),
        "点赞数": int(stats.get("like_count") or 0),
        "转发数": int(stats.get("share_count") or 0),
        "统计来源": stats_source,
        "统计更新时间": timestamp,
    }
    fields["数据状态"] = "完整"
    return fields, stats


def collect_article(
    url: str,
    topic: str = "",
    keywords: str = "",
    summary: bool = False,
    stats_provider: str | None = None,
    fallback_chain: str | None = None,
    stats_csv: str | None = None,
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
    nickname = meta.get("nickname") or meta.get("author")
    if not nickname:
        enrich = search_enrich.enrich_nickname(meta["title"], url)
        if enrich["ok"]:
            nickname = enrich["source"]
        else:
            return {
                "ok": False,
                "status": "failed",
                "record_id": None,
                "title": meta["title"],
                "source": None,
                "url": url,
                "data_status": "缺公众号名称",
                "message": "无法收藏：不能获取真实公众号名称，已停止写入以避免字段缺失。",
                "summary": None,
            }

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
    if stats_csv:
        os.environ["WECHAT_DOWNLOADER_CSV"] = stats_csv
    stats_provider = stats_provider or os.environ.get("WECHAT_STATS_PROVIDER", "wechat_downloader_csv")
    fallback_chain = fallback_chain or os.environ.get("WECHAT_STATS_FALLBACK_CHAIN")
    topic = topic or _auto_topic(meta["title"], meta.get("description") or "")
    keywords = keywords or _auto_keywords(meta["title"], meta.get("description") or "")
    data_status = _compute_data_status(True, nickname)
    stat_fields, stats_result = _stats_fields(url, stats_provider, fallback_chain)
    if not stats_result or not stats_result.get("ok") or stats_result.get("partial"):
        return {
            "ok": False,
            "status": "failed",
            "record_id": None,
            "title": meta["title"],
            "source": nickname,
            "url": url,
            "data_status": "统计获取失败",
            "message": _stats_error_message((stats_result or {}).get("error")),
            "summary": None,
            "stats": stats_result,
        }
    if stat_fields.get("数据状态"):
        data_status = stat_fields["数据状态"]
    fields = {
        "文章标题": meta["title"],
        "公众号名称": nickname,
        "文章链接": url,
        "主题关键词": topic,
        "文章关键词": keywords,
        "收藏时间": _now_lark_datetime(),
    }
    fields.update(stat_fields)
    fields["数据状态"] = data_status
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
    msg += (
        f"\n阅读数：{stat_fields['阅读数']}"
        f"\n点赞数：{stat_fields['点赞数']}"
        f"\n转发数：{stat_fields['转发数']}"
        f"\n统计来源：{stat_fields['统计来源']}"
    )

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
    if stats_result is not None:
        output["stats"] = stats_result

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
    parser.add_argument("url", nargs="?", help="mp.weixin.qq.com 文章链接")
    parser.add_argument("--topic", default="", help="主题关键词")
    parser.add_argument("--keywords", default="", help="文章关键词")
    parser.add_argument("--summary", action="store_true", help="同时生成摘要")
    parser.add_argument("--stats-csv", default=None, help="本地下载工具导出的文章数据 CSV 路径")
    parser.add_argument("--version", action="store_true", help="输出技能版本")
    parser.add_argument("--diagnose", action="store_true", help="输出运行环境诊断")
    parser.add_argument("--stats-provider", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--fallback-chain", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.version:
        print(SKILL_VERSION)
        return
    if args.diagnose:
        print(json.dumps(diagnose_runtime(), ensure_ascii=False, indent=2))
        return
    if not args.url:
        parser.error("需要提供 mp.weixin.qq.com 文章链接，或使用 --version/--diagnose")

    result = collect_article(
        args.url,
        args.topic,
        args.keywords,
        args.summary,
        args.stats_provider,
        args.fallback_chain,
        args.stats_csv,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
