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
$env:WECHAT_STATS_PROVIDER="wechat_downloader_csv"  # wechat_downloader_csv / official / wechat_session / third_party
$env:WECHAT_DOWNLOADER_CSV="D:/path/to/export.csv"
$env:WECHAT_STATS_FALLBACK_CHAIN=""
```

## 主入口

```bash
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --stats-provider wechat_downloader_csv
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --stats-provider wechat_downloader_csv --summary
```

## 字段写入规则

| 字段名 | 写入规则 |
| --- | --- |
| 文章标题 | `og:title`，失败则停止收藏 |
| 公众号名称 | `var nickname` → `meta author / og:article:author` → 搜索补全；仍失败则停止写入 |
| 文章链接 | 原始微信文章 URL 字符串 |
| 主题关键词 | 用户指定或脚本自动提取 |
| 文章关键词 | 用户指定或脚本自动提取 |
| 阅读数 | provider 返回真实值；未命中则停止写入 |
| 点赞数 | provider 返回真实值；未命中则停止写入 |
| 转发数 | provider 返回真实值；未命中则停止写入 |
| 收藏时间 | 脚本写当前时间 |
| 统计来源 | 使用现有选项：`official` / `wechat_session` / `third_party`；`wechat_downloader_csv` 写入时映射为 `wechat_session` |
| 统计更新时间 | 脚本写当前时间 |
| 数据状态 | 成功写入时为 `完整`；失败时不写入 Base |

## 关键规则

- URL 查重使用脚本内精确扫描，不依赖 `record-search` 对 URL 字段的模糊匹配。
- 无统计 provider 时停止写入，不用 `0` 冒充真实数据。
- 公众号名称补不到时停止写入，不写 `待补充`。
- `wechat_session` 只能在用户显式配置 Cookie/session 时调用；不得保存或打印敏感信息。
- Summary Mode 必须先收藏再总结，摘要失败不阻塞收藏。

## 统计 Provider

| Provider | 说明 |
| --- | --- |
| `wechat_downloader_csv` | 读取微信公众号批量下载工具导出的本地 CSV，当前首选；Base 统计来源写 `wechat_session` |
| `none` | 仅诊断，不允许正式写入 |
| `official` | 微信官方图文统计，仅自有公众号可用，需 access token 或 appid/secret |
| `wechat_session` | 微信登录态接口，需 `WECHAT_SESSION_COOKIE` |
| `third_party` | 通用第三方 HTTP API，需 `WECHAT_STATS_API_URL` |
