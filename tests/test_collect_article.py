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
            "author": None,
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

    def _mock_stats_success(self, provider="wechat_downloader_csv"):
        return {
            "ok": True,
            "provider": provider,
            "read_count": 123,
            "like_count": 9,
            "share_count": 2,
            "confidence": "high",
            "partial": False,
            "error": None,
        }

    def test_collect_success(self):
        """用例: 完整收藏成功 — 有 nickname + 真实统计数据"""
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.fetch_stats, "fetch_stats", return_value=self._mock_stats_success()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()) as create_mock:
            result = collect_article.collect_article(self.URL, topic="AI", keywords="Agent", stats_provider="wechat_downloader_csv")
            assert result["ok"] is True
            assert result["status"] == "created"
            assert result["title"] == "测试文章"
            assert result["source"] == "测试公众号"
            assert result["record_id"] == "recNEW001"
            assert "已收藏" in result["message"]
            fields = create_mock.call_args.args[0]
            assert fields["收藏时间"]
            assert fields["统计更新时间"]
            assert fields["统计来源"] == "wechat_session"
            assert fields["数据状态"] == "完整"
            assert fields["阅读数"] == 123

    def test_collect_uses_author_as_source(self):
        """用例: 无 nickname 时使用 meta author 作为公众号名称"""
        meta = self._mock_meta(nickname=None)
        meta["author"] = "作者公众号"
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=meta), \
             patch.object(collect_article.fetch_stats, "fetch_stats", return_value=self._mock_stats_success()), \
             patch.object(collect_article.search_enrich, "enrich_nickname") as enrich_mock, \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()):
            result = collect_article.collect_article(self.URL, stats_provider="wechat_downloader_csv")
            assert result["ok"] is True
            assert result["source"] == "作者公众号"
            enrich_mock.assert_not_called()

    def test_collect_stats_provider_success_writes_counts(self):
        """用例: stats provider 成功时写入统计字段并返回 stats"""
        stats = {
            "ok": True,
            "provider": "wechat_session",
            "read_count": 123,
            "like_count": 9,
            "share_count": 2,
            "confidence": "medium",
            "partial": False,
            "error": None,
        }
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.fetch_stats, "fetch_stats", return_value=stats), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()) as create_mock:
            result = collect_article.collect_article(self.URL, stats_provider="wechat_session")
            fields = create_mock.call_args.args[0]
            assert result["stats"] == stats
            assert result["data_status"] == "完整"
            assert fields["阅读数"] == 123
            assert fields["点赞数"] == 9
            assert fields["转发数"] == 2
            assert fields["统计来源"] == "wechat_session"
            assert fields["数据状态"] == "完整"

    def test_collect_missing_source_stops_write(self):
        """用例: 缺公众号名称时停止写入，不写待补充"""
        meta = self._mock_meta(nickname=None)
        enrich_result = {"ok": False, "source": None, "candidates": [], "method": "no_results"}
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=meta), \
             patch.object(collect_article.search_enrich, "enrich_nickname", return_value=enrich_result), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record") as create_mock:
            result = collect_article.collect_article(self.URL, stats_provider="wechat_downloader_csv")
            assert result["ok"] is False
            assert result["data_status"] == "缺公众号名称"
            create_mock.assert_not_called()

    def test_collect_no_nickname_enrich_succeeds(self):
        """用例: 无 nickname，search 补全成功"""
        meta = self._mock_meta(nickname=None)
        enrich_result = {"ok": True, "source": "搜狗公众号", "candidates": ["搜狗公众号"], "method": "single"}
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=meta), \
             patch.object(collect_article.fetch_stats, "fetch_stats", return_value=self._mock_stats_success()), \
             patch.object(collect_article.search_enrich, "enrich_nickname", return_value=enrich_result), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()):
            result = collect_article.collect_article(self.URL, stats_provider="wechat_downloader_csv")
            assert result["ok"] is True
            assert result["source"] == "搜狗公众号"

    def test_collect_no_nickname_enrich_fails(self):
        """用例: 无 nickname，search 补全也失败 → 停止写入"""
        meta = self._mock_meta(nickname=None)
        enrich_result = {"ok": False, "source": None, "candidates": [], "method": "no_results"}
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=meta), \
             patch.object(collect_article.search_enrich, "enrich_nickname", return_value=enrich_result), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record") as create_mock:
            result = collect_article.collect_article(self.URL, stats_provider="wechat_downloader_csv")
            assert result["ok"] is False
            assert result["data_status"] == "缺公众号名称"
            create_mock.assert_not_called()

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
             patch.object(collect_article.fetch_stats, "fetch_stats", return_value=self._mock_stats_success()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value={"ok": False, "error": "502"}):
            result = collect_article.collect_article(self.URL, stats_provider="wechat_downloader_csv")
            assert result["ok"] is False
            assert result["status"] == "failed"

    def test_missing_stats_provider_stops_write(self):
        """用例: 未准备统计 CSV → 停止写入，不写 0，并给出操作路径"""
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record") as create_mock:
            with patch.dict("os.environ", {}, clear=True):
                result = collect_article.collect_article(self.URL)
            assert result["ok"] is False
            assert result["data_status"] == "统计获取失败"
            assert "微信公众号批量下载工具3.9" in result["message"]
            assert "--stats-csv" in result["message"]
            create_mock.assert_not_called()

    def test_stats_csv_argument_sets_env_and_collects(self):
        """用例: stats_csv 参数会配置 CSV 路径并完成写入"""
        with patch.object(collect_article.fetch_meta, "fetch_meta", return_value=self._mock_meta()), \
             patch.object(collect_article.fetch_stats, "fetch_stats", return_value=self._mock_stats_success()) as stats_mock, \
             patch.object(collect_article.base_records, "search_duplicate_by_url", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "search_duplicate_by_title", return_value=self._mock_dup_not_found()), \
             patch.object(collect_article.base_records, "create_record", return_value=self._mock_create_success()):
            with patch.dict("os.environ", {}, clear=True):
                result = collect_article.collect_article(self.URL, stats_csv="D:/export.csv")
                assert result["ok"] is True
                assert os.environ["WECHAT_DOWNLOADER_CSV"] == "D:/export.csv"
                assert stats_mock.call_args.kwargs["provider"] == "wechat_downloader_csv"


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
        assert collect_article._compute_data_status(True, "公众号X") == "完整"
