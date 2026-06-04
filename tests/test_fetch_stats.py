#!/usr/bin/env python3
"""
tests/test_fetch_stats.py — fetch_stats 单元测试

运行:
    python -m pytest tests/test_fetch_stats.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from unittest.mock import patch
import fetch_stats
from providers import official, third_party, wechat_session, wechat_stats_capture


class TestFetchStats:
    """统计数据获取测试"""

    URL = "https://mp.weixin.qq.com/s/test"

    def test_default_none(self):
        """用例: 默认 provider=none → 全 0"""
        result = fetch_stats.fetch_stats(self.URL)
        assert result["ok"] is True
        assert result["provider"] == "none"
        assert result["read_count"] == 0
        assert result["confidence"] == "none"

    def test_none_explicit(self):
        result = fetch_stats.fetch_stats(self.URL, provider="none")
        assert result["ok"] is True
        assert result["provider"] == "none"

    def test_official_not_configured(self):
        """用例: 指定 official 但未配置 → ok=False, error=not_configured"""
        with patch.dict("os.environ", {}, clear=True):
            result = fetch_stats.fetch_stats(self.URL, provider="official")
            assert result["ok"] is False
            assert result["provider"] == "official"
            assert "not_configured" in (result.get("error") or "")

    def test_third_party_not_configured(self):
        """用例: third_party 未配置 API key"""
        with patch.dict("os.environ", {}, clear=True):
            result = fetch_stats.fetch_stats(self.URL, provider="third_party")
            assert result["ok"] is False
            assert "not_configured" in (result.get("error") or "")

    def test_no_auto_fallback_without_chain(self):
        """用例: 不传 fallback_chain → 不会自动跨 provider"""
        with patch.dict("os.environ", {}, clear=True):
            result = fetch_stats.fetch_stats(self.URL, provider="official")
            assert result["provider"] == "official"
            assert result["ok"] is False  # 不会自动尝试 other providers

    def test_fallback_chain_respected(self):
        """用例: 显式配置 fallback_chain 时按链路尝试"""
        with patch.dict("os.environ", {}, clear=True):
            result = fetch_stats.fetch_stats(
                self.URL,
                provider="official",
                fallback_chain="official,third_party,none",
            )
            # official 失败 → third_party 失败（未配置） → none 兜底
            assert result["provider"] == "none"
            assert result["ok"] is True
            assert result["confidence"] == "none"

    def test_none_in_chain_returns_immediately(self):
        """用例: fallback_chain 中含 none → 在 none 处返回全 0"""
        with patch.dict("os.environ", {}, clear=True):
            result = fetch_stats.fetch_stats(
                self.URL,
                provider="official",
                fallback_chain="none",
            )
            assert result["provider"] == "none"
            assert result["ok"] is True

    def test_unknown_provider(self):
        """用例: 未知 provider → 返回错误"""
        result = fetch_stats.fetch_stats(self.URL, provider="unknown_provider")
        assert result["ok"] is False
        assert "not found" in (result.get("error") or "")

    def test_blank_provider_defaults_none(self):
        """用例: 空 provider 不触发未定义变量，降级为 none"""
        result = fetch_stats.fetch_stats(self.URL, provider="")
        assert result["ok"] is True
        assert result["provider"] == "none"

    def test_third_party_success_with_mock_http(self):
        """用例: third_party 调用配置的 HTTP API 并解析统计字段"""
        response = type("MockResp", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: None,
            "read": lambda self: b'{"ok":true,"data":{"read_num":321,"like_num":8,"share_num":5}}',
        })()
        with patch.dict("os.environ", {"WECHAT_STATS_API_URL": "https://stats.example/api"}, clear=True), \
             patch.object(third_party, "urlopen", return_value=response):
            result = third_party.fetch(self.URL)
            assert result["ok"] is True
            assert result["read_count"] == 321
            assert result["like_count"] == 8
            assert result["share_count"] == 5

    def test_official_success_with_mock_api(self):
        """用例: official 通过标题匹配官方图文统计"""
        article_total = {
            "list": [{
                "title": "测试文章",
                "details": [{"int_page_read_count": 456, "share_count": 12}],
            }]
        }
        with patch.dict("os.environ", {"WECHAT_OFFICIAL_ACCESS_TOKEN": "token"}, clear=True), \
             patch.object(official, "_http_json_post", return_value=article_total), \
             patch.object(official, "_article_title", return_value="测试文章"):
            result = official.fetch(self.URL)
            assert result["ok"] is True
            assert result["read_count"] == 456
            assert result["share_count"] == 12
            assert result["like_count"] == 0
            assert result["partial"] is True


class TestWechatSessionProvider:
    """微信登录态 provider 测试"""

    def test_wechat_session_not_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            result = wechat_session.fetch("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is False
            assert "WECHAT_SESSION_COOKIE" in result["error"]

    def test_wechat_session_success_with_mock_http(self):
        html = """
        <script>
        var biz = "MzA123";
        var appmsgid = "10001";
        var itemidx = "1";
        var sn = "abcdef";
        var appmsg_token = "token123";
        </script>
        """
        response = {"base_resp": {"ret": 0}, "appmsgstat": {"read_num": 123, "like_num": 9}}
        with patch.dict("os.environ", {"WECHAT_SESSION_COOKIE": "cookie=value"}, clear=True), \
             patch.object(wechat_session, "http_get", return_value=html), \
             patch.object(wechat_session, "http_post_json", return_value=response):
            result = wechat_session.fetch("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is True
            assert result["provider"] == "wechat_session"
            assert result["read_count"] == 123
            assert result["like_count"] == 9
            assert result["partial"] is True

    def test_wechat_session_custom_wxtoken(self):
        """用例: WECHAT_WXTOKEN 可覆盖默认 wxtoken"""
        html = """
        <script>
        var biz = "MzA123";
        var appmsgid = "10001";
        var itemidx = "1";
        var sn = "abcdef";
        var appmsg_token = "token123";
        </script>
        """
        response = {"base_resp": {"ret": 0}, "appmsgstat": {"read_num": 1, "like_num": 0}}
        with patch.dict("os.environ", {"WECHAT_SESSION_COOKIE": "cookie=value", "WECHAT_WXTOKEN": "custom777"}, clear=True), \
             patch.object(wechat_session, "http_get", return_value=html), \
             patch.object(wechat_session, "http_post_json", return_value=response) as post_mock:
            wechat_session.fetch("https://mp.weixin.qq.com/s/test")
            assert "wxtoken=custom777" in post_mock.call_args.args[0]


class TestWechatStatsCaptureProvider:
    """自建微信统计采集器测试"""

    def test_stats_capture_not_authorized(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(wechat_stats_capture, "DEFAULT_SESSION_FILES", []):
            result = wechat_stats_capture.fetch("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is False
            assert "authorization_required" in result["error"]

    def test_stats_capture_success_with_mock_http(self):
        html = """
        <script>
        var biz = "MzA123";
        var appmsgid = "10001";
        var itemidx = "1";
        var sn = "abcdef";
        var appmsg_token = "token123";
        </script>
        """
        response = {
            "base_resp": {"ret": 0},
            "appmsgstat": {"read_num": 123, "like_num": 9, "share_num": 2},
        }
        with patch.dict("os.environ", {"WECHAT_SESSION_COOKIE": "cookie=value"}, clear=True), \
             patch.object(wechat_stats_capture, "http_get", return_value=html), \
             patch.object(wechat_stats_capture, "http_post_json", return_value=response):
            result = wechat_stats_capture.fetch("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is True
            assert result["provider"] == "wechat_stats_capture"
            assert result["read_count"] == 123
            assert result["like_count"] == 9
            assert result["share_count"] == 2
            assert result["partial"] is False

    def test_stats_capture_rejects_missing_share_count(self):
        html = """
        <script>
        var biz = "MzA123";
        var appmsgid = "10001";
        var itemidx = "1";
        var sn = "abcdef";
        var appmsg_token = "token123";
        </script>
        """
        response = {"base_resp": {"ret": 0}, "appmsgstat": {"read_num": 123, "like_num": 9}}
        with patch.dict("os.environ", {"WECHAT_SESSION_COOKIE": "cookie=value"}, clear=True), \
             patch.object(wechat_stats_capture, "http_get", return_value=html), \
             patch.object(wechat_stats_capture, "http_post_json", return_value=response):
            result = wechat_stats_capture.fetch("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is False
            assert "share_count" in result["error"]
