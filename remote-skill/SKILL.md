---
name: wechat-article-collection
description: 微信公众号文章收藏工作流。优先调用脚本收藏 mp.weixin.qq.com 文章，补全元数据、查重、获取可配置统计数据并写入飞书多维表格。
---

# 微信公众号文章收藏工作流

> 远程安装时也必须优先调用 `scripts/collect_article.py`，不要让模型手写完整流程。

## 必需配置

```powershell
$env:WECHAT_COLLECTION_BASE_TOKEN="your_feishu_base_token"
$env:WECHAT_COLLECTION_TABLE_ID="your_feishu_table_id"
```

可选统计配置：

```powershell
$env:WECHAT_DOWNLOADER_CSV="D:/path/to/export.csv"
```

## 主入口

```bash
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..."
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --summary
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --stats-csv "D:/path/to/export.csv"
```

## 字段写入规则

| 字段名 | 写入规则 |
| --- | --- |
| 文章标题 | `og:title`，失败则停止收藏 |
| 公众号名称 | `var nickname` → `meta author / og:article:author` → 搜索补全；仍失败则停止写入 |
| 文章链接 | 原始微信文章 URL 字符串 |
| 主题关键词 | 用户指定或脚本自动提取 |
| 文章关键词 | 用户指定或脚本自动提取 |
| 阅读数 | 本地统计 CSV 返回真实值；未命中则停止写入 |
| 点赞数 | 本地统计 CSV 返回真实值；未命中则停止写入 |
| 转发数 | 本地统计 CSV 返回真实值；未命中则停止写入 |
| 收藏时间 | 脚本写当前时间 |
| 统计来源 | 写入现有选项 `wechat_session` |
| 统计更新时间 | 脚本写当前时间 |
| 数据状态 | 成功写入时为 `完整`；失败时不写入 Base |

## 关键规则

- URL 查重使用脚本内精确扫描，不依赖 `record-search` 对 URL 字段的模糊匹配。
- 无本地真实统计 CSV 时停止写入，不用 `0` 冒充真实数据。
- 公众号名称补不到时停止写入，不写 `待补充`。
- 脚本只读取用户本机导出的 CSV；不保存或打印敏感信息。
- Summary Mode 必须先收藏再总结，摘要失败不阻塞收藏。

## 真实统计固定采集路径

1. 先运行收藏脚本。
2. 如果返回 `统计获取失败`，按脚本 message 提示用户打开“微信公众号批量下载工具3.9”。
3. 用户获取公众号 id、在微信桌面客户端打开生成链接、等待“获取密钥成功”。
4. 用户导出文章数据 CSV。
5. 用 `--stats-csv "<CSV路径>"` 重跑收藏。
