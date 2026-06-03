#!/usr/bin/env python3
"""runtime_env tests."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from runtime_env import load_env_files


def test_load_env_files_does_not_override_existing(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "WECHAT_COLLECTION_BASE_TOKEN=file_token\n"
        "WECHAT_COLLECTION_TABLE_ID='table_from_file'\n"
        "EMPTY_LINE_SHOULD_SKIP=\n",
        encoding="utf-8",
    )
    old_base = os.environ.get("WECHAT_COLLECTION_BASE_TOKEN")
    old_table = os.environ.get("WECHAT_COLLECTION_TABLE_ID")
    old_empty = os.environ.get("EMPTY_LINE_SHOULD_SKIP")
    try:
        os.environ["WECHAT_COLLECTION_BASE_TOKEN"] = "existing_token"
        os.environ.pop("WECHAT_COLLECTION_TABLE_ID", None)
        os.environ.pop("EMPTY_LINE_SHOULD_SKIP", None)

        loaded = load_env_files([env_file], include_defaults=False)

        assert str(env_file) in loaded
        assert os.environ["WECHAT_COLLECTION_BASE_TOKEN"] == "existing_token"
        assert os.environ["WECHAT_COLLECTION_TABLE_ID"] == "table_from_file"
        assert os.environ["EMPTY_LINE_SHOULD_SKIP"] == ""
    finally:
        if old_base is None:
            os.environ.pop("WECHAT_COLLECTION_BASE_TOKEN", None)
        else:
            os.environ["WECHAT_COLLECTION_BASE_TOKEN"] = old_base
        if old_table is None:
            os.environ.pop("WECHAT_COLLECTION_TABLE_ID", None)
        else:
            os.environ["WECHAT_COLLECTION_TABLE_ID"] = old_table
        if old_empty is None:
            os.environ.pop("EMPTY_LINE_SHOULD_SKIP", None)
        else:
            os.environ["EMPTY_LINE_SHOULD_SKIP"] = old_empty
