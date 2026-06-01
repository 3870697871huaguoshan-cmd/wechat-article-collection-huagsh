"""
third_party.py — 第三方数据 API

读取环境变量 WECHAT_STATS_API_KEY。
未配置时返回 not_configured。
"""


def fetch(url: str) -> dict:
    import os

    api_key = os.environ.get("WECHAT_STATS_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "provider": "third_party",
            "read_count": 0,
            "like_count": 0,
            "share_count": 0,
            "confidence": "none",
            "partial": False,
            "error": "not_configured: WECHAT_STATS_API_KEY not set",
        }

    # 占位 — 实际调用第三方 API
    return {
        "ok": False,
        "provider": "third_party",
        "read_count": 0,
        "like_count": 0,
        "share_count": 0,
        "confidence": "none",
        "partial": False,
        "error": "not_implemented: third_party provider is a stub",
    }
