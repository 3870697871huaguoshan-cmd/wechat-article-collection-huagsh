"""
official.py — 微信公众号官方数据接口

接口占位 + 参数校验。
实际实现需:
    1. 微信公众平台获取 access_token
    2. 调用图文分析接口
    3. 解析 read_count / share_count

注意: like_count 官方图文分析接口不一定提供，应标为 partial/optional。
"""


def fetch(url: str) -> dict:
    """
    微信公众号官方数据接口 — 占位实现。
    需要用户配置微信公众平台 appid/appsecret。
    """
    import os

    appid = os.environ.get("WECHAT_OFFICIAL_APPID")
    secret = os.environ.get("WECHAT_OFFICIAL_SECRET")

    if not appid or not secret:
        return {
            "ok": False,
            "provider": "official",
            "read_count": 0,
            "like_count": 0,
            "share_count": 0,
            "confidence": "none",
            "partial": True,
            "error": "not_configured: WECHAT_OFFICIAL_APPID / WECHAT_OFFICIAL_SECRET not set",
        }

    # 占位 — 实际调用微信公众平台 API
    # TODO: 实现 access_token 获取 + 图文分析接口调用
    return {
        "ok": False,
        "provider": "official",
        "read_count": 0,
        "like_count": 0,       # like_count 在官方接口中不一定可用
        "share_count": 0,
        "confidence": "none",
        "partial": True,
        "error": "not_implemented: official provider is a stub",
    }
