#!/usr/bin/env python3
"""
tests/test_collect_article.py — collect_article 端到端测试

运行:
    python -m pytest tests/test_collect_article.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from unittest.mock import patch, MagicMock
import json
import collect_article


class TestCollectArticle:
    """端到端测试主收藏流程"""

    URL = "https://mp.weixin.qq.com/s/test123"

    def _mock_meta(self, title="测试文章", desc="摘要", nickname="测试公众号"):
        return {
            "ok": True,
            "title": title,
            "description": desc,
            "nickname": nickname,
            "error": None,
        }

    def _mock_dup_not_found(self):
        return {"found": False, "record_id": None, "error": None}

    def _mock_dup_found_url(self):
        return {"found": True, "record_id": "recDUP001", "error": None}

    def _mock_dup_found_title(self):
        return {"found": True, "record_id": "recDUP002", "error": None}

    def _mock_create_success(self):
        return {"ok": True, "record_id": "recNEW001", "error": None}

    def test_collect_success(self):
        """用例: 完整收藏成功 — 有 nickname"""
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()):
            result = collect_article.collect_article(self.URL, topic="AI", keywords="Agent")
            assert result["ok"] is True
            assert result["status"] == "created"
            assert result["title"] == "测试文章"
            assert result["source"] == "测试公众号"
            assert result["record_id"] == "recNEW001"
            assert "已收藏" in result["message"]

    def test_collect_no_nickname_enrich_succeeds(self):
        """用例: 无 nickname，search 补全成功"""
        meta = self._mock_meta(nickname=None)
        enrich_result = {"ok": True, "source": "搜狗公众号", "candidates": ["搜狗公众号"], "method": "single"}
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=meta), \
             patch.object(collect_article.search_enrich, "enrich_nickname", return_value=enrich_result), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()):
            result = collect_article.collect_article(self.URL)
            assert result["ok"] is True
            assert result["source"] == "搜狗公众号"

    def test_collect_no_nickname_enrich_fails(self):
        """用例: 无 nickname，search 补全也失败"""
        meta = self._mock_meta(nickname=None)
        enrich_result = {"ok": False, "source": None, "candidates": [], "method": "no_results"}
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=meta), \
             patch.object(collect_article.search_enrich, "enrich_nickname", return_value=enrich_result), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()):
            result = collect_article.collect_article(self.URL)
            assert result["ok"] is True
            assert result["source"] == "待补充"
            assert result["data_status"] == "缺公众号名称"

    def test_duplicate_by_url(self):
        """用例: 链接查重命中"""
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_found_url()):
            result = collect_article.collect_article(self.URL)
            assert result["status"] == "duplicate"
            assert result["data_status"] is None
            assert "已收藏过" in result["message"]

    def test_duplicate_by_title(self):
        """用例: 链接未命中，标题查重命中"""
        # 链接未命中，标题命中
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_found_title()):
            result = collect_article.collect_article(self.URL)
            assert result["status"] == "duplicate"
            assert result["data_status"] is None

    def test_meta_fetch_failed(self):
        """用例: curl 完全失败 → status=failed"""
        meta = {"ok": False, "title": None, "description": None, "nickname": None, "error": "无法获取"}
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=meta):
            result = collect_article.collect_article(self.URL)
            assert result["ok"] is False
            assert result["status"] == "failed"
            assert result["data_status"] == "抓取失败"

    def test_invalid_url_rejected_before_fetch(self):
        """用例: 非微信文章链接直接拒绝"""
        result = collect_article.collect_article("https://example.com/article")
        assert result["ok"] is False
        assert result["status"] == "failed"
        assert "只支持" in result["message"]

    def test_duplicate_search_error_stops_write(self):
        """用例: 查重失败时停止写入，避免重复收藏"""
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value={"found": False, "record_id": None, "error": "search failed"}), \
             patch.object(collect_article.base_records, "create_record") as create_mock:
            result = collect_article.collect_article(self.URL)
            assert result["ok"] is False
            assert "查重失败" in result["message"]
            create_mock.assert_not_called()

    def test_create_record_failed(self):
        """用例: 写入飞书失败"""
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value={"ok": False, "error": "502"}):
            result = collect_article.collect_article(self.URL)
            assert result["ok"] is False
            assert result["status"] == "failed"


class TestSummaryFallback:
    """Summary 降级测试"""

    def test_extractor_1005_fallback_to_og_desc(self):
        """用例: extractor 1005 → 降级到 og:description"""
        url = "https://mp.weixin.qq.com/s/test"
        meta = {"description": "这是 og:description 降级摘要", "desc": "这是 og:description 降级摘要"}
        with patch.object(collect_article.subprocess, "run", side_effect=Exception("extractor failed")):
            result = collect_article._generate_summary(url, meta)
            assert result is not None
            assert "降级总结" in result
            assert "og:description 降级摘要" in result

    def test_extractor_fail_and_no_og_desc(self):
        """用例: extractor 失败 + 无 og:description → None"""
        with patch.object(collect_article.subprocess, "run", side_effect=Exception("extractor failed")):
            result = collect_article._generate_summary("url", {"description": None, "desc": None})
            assert result is None

    def test_extractor_dir_env_override(self):
        """用例: extractor 路径支持环境变量覆盖"""
        meta = {"description": None, "desc": None}
        fake_result = type("MockProc", (), {"stdout": '{"code":1005}'})()
        with patch.dict("os.environ", {"WECHAT_ARTICLE_EXTRACTOR_DIR": "C:/custom/extractor"}, clear=False), \
             patch.object(collect_article.subprocess, "run", return_value=fake_result) as run_mock:
            collect_article._generate_summary("https://mp.weixin.qq.com/s/test", meta)
            assert run_mock.call_args.kwargs["cwd"] == "C:/custom/extractor"


class TestDataStatus:
    """数据状态计算"""

    def test_catch_failed(self):
        assert collect_article._compute_data_status(False, "待补充") == "抓取失败"

    def test_missing_nickname(self):
        assert collect_article._compute_data_status(True, "待补充") == "缺公众号名称"

    def test_default(self):
        assert collect_article._compute_data_status(True, "公众号X") == "缺统计数据"
