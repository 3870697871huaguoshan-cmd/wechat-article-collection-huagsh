#!/usr/bin/env python3
"""
tests/test_fetch_meta.py — fetch_meta 单元测试

运行:
    python -m pytest tests/test_fetch_meta.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
import json
from unittest.mock import patch, MagicMock
import fetch_meta


SAMPLE_HTML_FULL = """<html>
<meta property="og:title" content="测试文章标题"/>
<meta property="og:description" content="这是文章摘要"/>
<script>var nickname = "测试公众号"</script>
</html>"""

SAMPLE_HTML_NO_NICKNAME = """<html>
<meta property="og:title" content="只有标题的文章"/>
<meta property="og:description" content="没有nickname"/>
</html>"""

SAMPLE_HTML_AUTHOR = """<html>
<meta property="og:title" content="作者兜底文章"/>
<meta property="og:description" content="有 author meta"/>
<meta name="author" content="空格丶"/>
</html>"""

SAMPLE_HTML_EMPTY = "<html><body></body></html>"


class TestFetchMeta:
    """测试 fetch_meta 函数（mock curl）"""

    def test_full_extraction(self):
        """用例 1: curl 成功提取标题、摘要、nickname"""
        with patch.object(fetch_meta, "_curl_once", return_value=SAMPLE_HTML_FULL):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is True
            assert result["title"] == "测试文章标题"
            assert result["description"] == "这是文章摘要"
            assert result["nickname"] == "测试公众号"
            assert result["error"] is None

    def test_no_nickname(self):
        """用例 2: 有标题但无 nickname"""
        with patch.object(fetch_meta, "_curl_once", return_value=SAMPLE_HTML_NO_NICKNAME):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is True
            assert result["title"] == "只有标题的文章"
            assert result["nickname"] is None

    def test_author_meta_extraction(self):
        """用例: 微信短链页常用 meta author 暴露公众号名"""
        with patch.object(fetch_meta, "_curl_once", return_value=SAMPLE_HTML_AUTHOR):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is True
            assert result["nickname"] is None
            assert result["author"] == "空格丶"

    def test_first_ua_fail_second_succeed(self):
        """用例 3: 第一次 UA 返回空，第二次成功"""
        calls = [None, SAMPLE_HTML_FULL]  # first UA fails, second succeeds
        with patch.object(fetch_meta, "_curl_once", side_effect=calls):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is True
            assert result["title"] == "测试文章标题"

    def test_both_uas_fail(self):
        """用例 4: 两次 UA 都失败"""
        with patch.object(fetch_meta, "_curl_once", return_value=None):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is False
            assert result["title"] is None
            assert "两次" in (result["error"] or "")

    def test_html_no_og_title(self):
        """用例 5: HTML 无 og:title → 第一次 None，第二次返回无需 title 的 HTML 也无法提取"""
        with patch.object(fetch_meta, "_curl_once", return_value=SAMPLE_HTML_EMPTY):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is False

    def test_curl_timeout_then_succeed(self):
        """用例 6: 第一次 curl 超时，第二次成功"""
        calls = [None, SAMPLE_HTML_FULL]
        with patch.object(fetch_meta, "_curl_once", side_effect=calls):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["ok"] is True
            assert result["title"] == "测试文章标题"


class TestRegex:
    """测试正则提取"""

    def test_title_with_special_chars(self):
        html = '<meta property="og:title" content="标题包含 &lt;tag&gt; 和 &quot;引号&quot;"/>'
        with patch.object(fetch_meta, "_curl_once", return_value=html):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert "<tag>" in result["title"]
            assert '"引号"' in result["title"]

    def test_nickname_with_spaces(self):
        html = '<script>var nickname = "公众号 名称";</script>'
        html += '<meta property="og:title" content="标题"/>'
        with patch.object(fetch_meta, "_curl_once", return_value=html):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["nickname"] == "公众号 名称"

    def test_nickname_variant_syntax(self):
        """var nickname = 后可有空格"""
        html = '<script>var nickname      =    "多空格公众号"   ;</script>'
        html += '<meta property="og:title" content="标题"/>'
        with patch.object(fetch_meta, "_curl_once", return_value=html):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["nickname"] == "多空格公众号"

    def test_meta_attrs_reversed_and_single_quote_nickname(self):
        """meta 属性顺序变化、nickname 单引号时仍能提取"""
        html = "<meta content='倒序标题' property='og:title'/>"
        html += "<script>var nickname = '单引号公众号';</script>"
        with patch.object(fetch_meta, "_curl_once", return_value=html):
            result = fetch_meta.fetch_meta("https://mp.weixin.qq.com/s/test")
            assert result["title"] == "倒序标题"
            assert result["nickname"] == "单引号公众号"
