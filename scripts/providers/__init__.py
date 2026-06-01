#!/usr/bin/env python3
"""
providers/ — stats_provider 接口实现

每个 provider 模块实现:
    fetch(url: str) -> dict

返回结构:
    {"ok": bool, "provider": str, "read_count": int, "like_count": int,
     "share_count": int, "confidence": str, "partial": bool, "error": str|None}
"""


def provider_none(url: str) -> dict:
    """默认 provider — 不获取统计数据"""
    return {
        "ok": True,
        "provider": "none",
        "read_count": 0,
        "like_count": 0,
        "share_count": 0,
        "confidence": "none",
        "partial": False,
        "error": None,
    }
