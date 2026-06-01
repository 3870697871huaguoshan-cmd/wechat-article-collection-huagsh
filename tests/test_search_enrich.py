#!/usr/bin/env python3
"""
tests/test_search_enrich.py — search_enrich 单元测试

运行:
    python -m pytest tests/test_search_enrich.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from unittest.mock import patch
import search_enrich


class TestCandidateKeywords:
    """搜索关键词生成测试"""

    def test_candidate_keywords_empty_title(self):
        assert search_enrich._candidate_keywords("   ") == []

    def test_candidate_keywords_short_title(self):
        assert search_enrich._candidate_keywords("短标题") == ["短标题"]

    def test_candidate_keywords_long_title_deduplicated(self):
        result = search_enrich._candidate_keywords("这是 一个很长 的标题")
        assert result[0] == "这是 一个很长 的标题"
        assert result[1:] == ["这是一个很长的标", "这是一个很长", "这是一个"]


class TestEnrichNickname:
    """测试 enrich_nickname"""

    def test_empty_title(self):
        result = search_enrich.enrich_nickname("", "")
        assert result["ok"] is False
        assert result["method"] == "no_title"

    def test_no_search_results(self):
        with patch.object(search_enrich, "_run_search", return_value=[]):
            result = search_enrich.enrich_nickname("某篇文章标题")
            assert result["ok"] is False
            assert result["method"] == "no_results"

    def test_full_title_then_short_keyword_retry(self):
        """用例: 完整标题 0 结果时，用短关键词补搜"""
        calls = [
            [],
            [{"title": "短词命中", "source": "补搜公众号", "url": "https://mp.weixin.qq.com/s/abc"}],
        ]
        with patch.object(search_enrich, "_run_search", side_effect=calls) as run_mock:
            result = search_enrich.enrich_nickname("这是一个很长的微信公众号文章标题")
            assert result["ok"] is True
            assert result["source"] == "补搜公众号"
            assert run_mock.call_count == 2

    def test_all_source_empty(self):
        """用例: search source 全部为空"""
        items = [
            {"title": "某篇", "source": "", "url": "https://mp.weixin.qq.com/s/abc"},
            {"title": "某篇2", "source": "", "url": "https://mp.weixin.qq.com/s/def"},
        ]
        with patch.object(search_enrich, "_run_search", return_value=items):
            result = search_enrich.enrich_nickname("某篇文章标题")
            assert result["ok"] is False
            assert result["method"] == "all_source_empty"

    def test_single_source(self):
        """用例: 唯一 source 直接返回"""
        items = [
            {"title": "某篇", "source": "唯一公众号", "url": "https://mp.weixin.qq.com/s/abc"},
        ]
        with patch.object(search_enrich, "_run_search", return_value=items):
            result = search_enrich.enrich_nickname("某篇文章标题")
            assert result["ok"] is True
            assert result["source"] == "唯一公众号"
            assert result["method"] == "single"

    def test_multiple_same_source(self):
        """用例: 多个结果 source 相同 → 视为 single"""
        items = [
            {"title": "A", "source": "同一公众号", "url": "https://mp.weixin.qq.com/s/a"},
            {"title": "B", "source": "同一公众号", "url": "https://mp.weixin.qq.com/s/b"},
        ]
        with patch.object(search_enrich, "_run_search", return_value=items):
            result = search_enrich.enrich_nickname("标题")
            assert result["ok"] is True
            assert result["method"] == "single"

    def test_multi_source_exact_match(self):
        """用例: 多 source 不一致，标题精确匹配确认"""
        items = [
            {"title": "需要匹配的精确标题", "source": "正确公众号", "url": "https://mp.weixin.qq.com/s/abc"},
            {"title": "其他文章", "source": "错误公众号", "url": "https://mp.weixin.qq.com/s/def"},
        ]
        with patch.object(search_enrich, "_run_search", return_value=items):
            result = search_enrich.enrich_nickname("需要匹配的精确标题")
            assert result["ok"] is True
            assert result["source"] == "正确公众号"
            assert result["method"] == "exact_match"

    def test_multi_source_url_match(self):
        """用例: 标题不精确匹配，URL 文章 ID 匹配"""
        items = [
            {"title": "文章A", "source": "候选1", "url": "https://mp.weixin.qq.com/s/abc123"},
            {"title": "文章B", "source": "候选2", "url": "https://mp.weixin.qq.com/s/def456"},
        ]
        article_url = "https://mp.weixin.qq.com/s/def456?chksm=xxx"
        with patch.object(search_enrich, "_run_search", return_value=items):
            result = search_enrich.enrich_nickname("模糊标题", article_url)
            assert result["ok"] is True
            assert result["source"] == "候选2"
            assert result["method"] == "url_match"

    def test_multi_source_cannot_confirm(self):
        """用例: 多 source 不一致，无法确认 → 返回 pending + 候选"""
        items = [
            {"title": "文章A", "source": "公众号X", "url": "https://mp.weixin.qq.com/s/111"},
            {"title": "文章B", "source": "公众号Y", "url": "https://mp.weixin.qq.com/s/222"},
        ]
        article_url = "https://mp.weixin.qq.com/s/333"  # 不匹配任何 URL
        with patch.object(search_enrich, "_run_search", return_value=items):
            result = search_enrich.enrich_nickname("一个模糊的标题", article_url)
            assert result["ok"] is False
            assert result["source"] is None
            assert result["method"] == "pending"
            assert len(result["candidates"]) == 2
            assert "公众号X" in result["candidates"]
            assert "公众号Y" in result["candidates"]
