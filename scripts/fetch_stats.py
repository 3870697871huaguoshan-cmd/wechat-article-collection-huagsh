#!/usr/bin/env python3
"""
fetch_stats.py — 统计数据获取入口

用法:
    python fetch_stats.py <url> <provider> [fallback_chain]
    python fetch_stats.py --url '<url>' --provider official --fallback-chain "official,third_party"

规则:
    - 默认 provider=none
    - 只调用用户显式指定的 provider
    - 不自动跨 provider 降级
    - 只有用户显式配置 fallback_chain 时才尝试链路

输出:
    {"ok": bool, "provider": str, "read_count": int, "like_count": int,
     "share_count": int, "confidence": str, "partial": bool, "error": str|None}
"""

import sys
import json
from providers import provider_none as _provider_none


PROVIDER_MAP = {
    "none": _provider_none,
}


def _lazy_import(name: str):
    """延迟导入 provider 模块（避免未安装依赖报错）"""
    if name in PROVIDER_MAP:
        return PROVIDER_MAP[name]
    try:
        mod = __import__(f"providers.{name}", fromlist=["fetch"])
        PROVIDER_MAP[name] = mod.fetch
        return mod.fetch
    except ImportError:
        def _stub(url: str) -> dict:
            return {
                "ok": False, "provider": name,
                "read_count": 0, "like_count": 0, "share_count": 0,
                "confidence": "none", "partial": False,
                "error": f"provider module not found: {name}",
            }
        PROVIDER_MAP[name] = _stub
        return _stub


def fetch_stats(url: str, provider: str = "none", fallback_chain: str | None = None) -> dict:
    """
    获取文章统计数据。

    Args:
        url: mp.weixin.qq.com 文章链接
        provider: 指定的 provider 名称
        fallback_chain: 逗号分隔的降级链，如 "official,third_party"。
                        仅在用户显式配置时使用。

    Returns:
        标准 StatsResult dict
    """
    provider = (provider or "none").strip()
    if fallback_chain:
        chain = [p.strip() for p in fallback_chain.split(",") if p.strip()]
    else:
        chain = [provider]
    if not chain:
        chain = ["none"]

    last_error = None
    for p in chain:
        if p == "none":
            return PROVIDER_MAP["none"](url)

        fn = _lazy_import(p)
        try:
            result = fn(url)
        except Exception as e:
            result = {
                "ok": False, "provider": p,
                "read_count": 0, "like_count": 0, "share_count": 0,
                "confidence": "none", "partial": False,
                "error": str(e),
            }

        if result["ok"]:
            return result

        last_error = result

        # 没有 fallback_chain → 不继续尝试
        if not fallback_chain:
            break

    if last_error:
        return last_error

    return PROVIDER_MAP["none"](url)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="获取微信文章统计数据")
    parser.add_argument("positional", nargs="*", help="兼容位置参数: <url> <provider> [fallback_chain]")
    parser.add_argument("--url", default=None, help="文章 URL")
    parser.add_argument("--provider", default="none", help="provider 名称")
    parser.add_argument("--fallback-chain", default=None, help="降级链 (逗号分隔)")
    args = parser.parse_args()

    url = args.url
    provider = args.provider
    fallback_chain = args.fallback_chain
    if args.positional:
        url = args.positional[0]
    if len(args.positional) >= 2:
        provider = args.positional[1]
    if len(args.positional) >= 3:
        fallback_chain = args.positional[2]
    if not url:
        parser.error("需要提供 --url 或位置参数 <url>")

    result = fetch_stats(url, provider, fallback_chain)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
