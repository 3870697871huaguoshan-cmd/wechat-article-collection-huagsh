#!/usr/bin/env python3
"""
tests/test_base_records.py — base_records 单元测试

运行:
    python -m pytest tests/test_base_records.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
import json
from unittest.mock import patch
import base_records


# ── helpers ──────────────────────────────────────────────

def _mock_run(stdout: str, returncode: int = 0) -> dict:
    """创建模拟的 subprocess.CompletedProcess"""
    return type("MockProc", (), {
        "stdout": stdout, "stderr": "",
        "returncode": returncode,
    })()


def _search_response(record_ids: list[str]) -> str:
    """生成 +record-search 的 JSON 响应"""
    return json.dumps({
        "ok": True,
        "data": {
            "records": [["title", None, "url"]] if record_ids else [],
            "record_id_list": record_ids,
            "fields": ["文章标题", "公众号名称", "文章链接"],
            "has_more": False,
        }
    }, ensure_ascii=False)


def _upsert_response(record_id: str = "recxxx") -> str:
    return json.dumps({
        "ok": True,
        "data": {"record_id": record_id},
    })


class TestSearchDuplicate:
    """查重测试"""

    def test_search_url_found(self):
        """用例: 链接查重命中 → found=True, 有 record_id"""
        stdout = _search_response(["recABC123"])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)) as run_mock:
            result = base_records.search_duplicate_by_url("https://mp.weixin.qq.com/s/test")
            assert result["found"] is True
            assert result["record_id"] == "recABC123"
            payload = json.loads(run_mock.call_args.args[0][-1])
            assert payload["keyword"] == "test"

    def test_search_url_long_link_uses_short_article_id(self):
        """用例: 长 URL 查重时不超过 record-search 的 50 字符 keyword 限制"""
        long_url = "https://mp.weixin.qq.com/s/abcdefghijklmnopqrstuvwxyz1234567890?chksm=long-tracking"
        stdout = _search_response([])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)) as run_mock:
            result = base_records.search_duplicate_by_url(long_url)
            payload = json.loads(run_mock.call_args.args[0][-1])
            assert result["found"] is False
            assert payload["keyword"] == "abcdefghijklmnopqrstuvwxyz1234567890"
            assert len(payload["keyword"]) <= 50

    def test_search_url_query_sn_variant(self):
        """用例: /s?sn=xxx 形式用 sn 查重"""
        stdout = _search_response([])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)) as run_mock:
            result = base_records.search_duplicate_by_url("https://mp.weixin.qq.com/s?sn=sn123&mid=mid999")
            payload = json.loads(run_mock.call_args.args[0][-1])
            assert result["error"] is None
            assert payload["keyword"] == "sn123"

    def test_search_url_query_biz_variant(self):
        """用例: /s/?__biz=xxx 形式用 __biz 兜底查重"""
        stdout = _search_response([])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)) as run_mock:
            result = base_records.search_duplicate_by_url("https://mp.weixin.qq.com/s/?__biz=biz123")
            payload = json.loads(run_mock.call_args.args[0][-1])
            assert result["error"] is None
            assert payload["keyword"] == "biz123"

    def test_search_url_path_id_wins_over_query(self):
        """用例: /s/abc?sn=yyy 优先使用路径文章 ID"""
        stdout = _search_response([])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)) as run_mock:
            result = base_records.search_duplicate_by_url("https://mp.weixin.qq.com/s/abc?sn=yyy")
            payload = json.loads(run_mock.call_args.args[0][-1])
            assert result["error"] is None
            assert payload["keyword"] == "abc"

    def test_search_url_empty_identifier_returns_error(self):
        """用例: 裸 /s/ 且无 query 标识时不做无意义查重"""
        with patch.object(base_records, "_run_lark") as run_mock:
            result = base_records.search_duplicate_by_url("https://mp.weixin.qq.com/s/")
            assert result["found"] is False
            assert result["error"] == "unable_to_extract_url_keyword"
            run_mock.assert_not_called()

    def test_search_url_not_found(self):
        """用例: 链接查重未命中"""
        stdout = _search_response([])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)):
            result = base_records.search_duplicate_by_url("https://mp.weixin.qq.com/s/test")
            assert result["found"] is False
            assert result["record_id"] is None

    def test_search_title_found(self):
        """用例: 标题查重命中"""
        stdout = _search_response(["recXYZ789"])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)):
            result = base_records.search_duplicate_by_title("某篇文章标题")
            assert result["found"] is True
            assert result["record_id"] == "recXYZ789"

    def test_search_title_truncated_to_keyword_limit(self):
        """用例: 长标题查重不超过 record-search 的 50 字符限制"""
        long_title = "题" * 80
        stdout = _search_response([])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)) as run_mock:
            result = base_records.search_duplicate_by_title(long_title)
            payload = json.loads(run_mock.call_args.args[0][-1])
            assert result["error"] is None
            assert payload["keyword"] == "题" * 50

    def test_search_title_not_found(self):
        """用例: 标题查重未命中"""
        stdout = _search_response([])
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)):
            result = base_records.search_duplicate_by_title("全新文章标题")
            assert result["found"] is False

    def test_search_failure_returns_error(self):
        """用例: 查重命令失败时返回 error，调用方不能继续写入"""
        with patch.object(base_records, "_run_lark", return_value=_mock_run("permission denied", returncode=1)):
            result = base_records.search_duplicate_by_url("https://mp.weixin.qq.com/s/test")
            assert result["found"] is False
            assert result["error"]


class TestCreateRecord:
    """写入测试"""

    def test_create_success(self):
        """用例: 写入成功"""
        stdout = _upsert_response("recNEW001")
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)):
            result = base_records.create_record({
                "文章标题": "测试", "公众号名称": "公众号",
                "文章链接": "https://mp.weixin.qq.com/s/test",
                "阅读数": 0, "点赞数": 0, "转发数": 0,
            })
            assert result["ok"] is True
            assert result["record_id"] == "recNEW001"

    def test_create_retry_502_then_succeed(self):
        """用例: 第一次 502，第二次成功"""
        fail_stdout = '{"ok":false,"error":"502 Bad Gateway"}'
        success_stdout = _upsert_response("recRETRY001")
        calls = [
            _mock_run(fail_stdout, returncode=1),
            _mock_run(success_stdout),
        ]
        with patch.object(base_records, "_run_lark", side_effect=calls):
            with patch("time.sleep", return_value=None):  # 跳过 sleep
                result = base_records.create_record({"文章标题": "重试测试"})
                assert result["ok"] is True

    def test_create_field_type_error_no_retry(self):
        """用例: 字段类型错误 → 不重试，直接返回"""
        error_stdout = '{"ok":false,"error":"URLFieldConvFail: invalid field value"}'
        with patch.object(base_records, "_run_lark", return_value=_mock_run(error_stdout, returncode=1)):
            result = base_records.create_record({"文章标题": "测试"})
            assert result["ok"] is False
            assert "URLFieldConvFail" in (result["error"] or "")

    def test_create_permission_error_no_retry(self):
        """用例: 权限错误 → 不重试"""
        error_stdout = '{"ok":false,"error":"AccessDenied: no permission"}'
        with patch.object(base_records, "_run_lark", return_value=_mock_run(error_stdout, returncode=1)):
            result = base_records.create_record({"文章标题": "测试"})
            assert result["ok"] is False

    def test_create_non_retryable_error_no_retry(self):
        """用例: 非可重试错误不应先 sleep 重试"""
        error_stdout = '{"ok":false,"error":"bad request"}'
        with patch.object(base_records, "_run_lark", return_value=_mock_run(error_stdout, returncode=1)) as run_mock:
            result = base_records.create_record({"文章标题": "测试"})
            assert result["ok"] is False
            assert run_mock.call_count == 1

    def test_create_retry_exhausted(self):
        """用例: 连续 3 次 502 → retry_exhausted"""
        fail_stdout = '{"ok":false,"error":"502 Bad Gateway"}'
        calls = [_mock_run(fail_stdout, returncode=1)] * 3
        with patch.object(base_records, "_run_lark", side_effect=calls):
            with patch("time.sleep", return_value=None):
                result = base_records.create_record({"文章标题": "测试"})
                assert result["ok"] is False
                assert "retry_exhausted" in result["error"]


class TestUpdateStats:
    """统计字段更新测试"""

    def test_update_stats_success(self):
        """用例: 更新统计字段成功"""
        stdout = _upsert_response("rec001")
        with patch.object(base_records, "_run_lark", return_value=_mock_run(stdout)) as run_mock:
            result = base_records.update_stats("rec001", {
                "阅读数": 100,
                "点赞数": 9,
                "转发数": 3,
                "统计来源": "wechat_session",
                "ignored": "不会写入",
            })
            payload = json.loads(run_mock.call_args.args[0][-1])
            assert result["ok"] is True
            assert payload == {
                "阅读数": 100,
                "点赞数": 9,
                "转发数": 3,
                "统计来源": "wechat_session",
            }

    def test_update_stats_empty_fields(self):
        """用例: 无可更新字段时直接失败"""
        result = base_records.update_stats("rec001", {"ignored": "x"})
        assert result["ok"] is False
        assert result["error"] == "no stats fields to update"

    def test_update_stats_retry_502_then_succeed(self):
        """用例: 第一次 502，第二次成功"""
        calls = [
            _mock_run('{"ok":false,"error":"502 Bad Gateway"}', returncode=1),
            _mock_run(_upsert_response("rec001")),
        ]
        with patch.object(base_records, "_run_lark", side_effect=calls):
            with patch("time.sleep", return_value=None):
                result = base_records.update_stats("rec001", {"阅读数": 100})
                assert result["ok"] is True
