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
$env:WECHAT_STATS_PROVIDER="none"  # none / official / wechat_session / third_party
$env:WECHAT_STATS_FALLBACK_CHAIN=""
```

## 主入口

```bash
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..."
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --summary
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --stats-provider wechat_session
```

## 字段写入规则

| 字段名 | 写入规则 |
| --- | --- |
| 文章标题 | `og:title`，失败则停止收藏 |
| 公众号名称 | `var nickname` → `meta author / og:article:author` → 搜索补全 → `待补充` |
| 文章链接 | 原始微信文章 URL 字符串 |
| 主题关键词 | 用户指定或脚本自动提取 |
| 文章关键词 | 用户指定或脚本自动提取 |
| 阅读数 | provider 返回值；无 provider 写 0 |
| 点赞数 | provider 返回值；无 provider 写 0 |
| 转发数 | provider 返回值；无 provider 写 0 |
| 收藏时间 | 脚本写当前时间 |
| 统计来源 | `none` / `official` / `wechat_session` / `third_party` |
| 统计更新时间 | 脚本写当前时间 |
| 数据状态 | `完整` / `缺公众号名称` / `缺统计数据` / `抓取失败` / `统计获取失败` |

## 关键规则

- URL 查重使用脚本内精确扫描，不依赖 `record-search` 对 URL 字段的模糊匹配。
- 无统计 provider 时，不得声称阅读数/点赞数/转发数已真实抓取；状态必须是 `缺统计数据`。
- `缺公众号名称` 优先级高于统计失败，避免状态互相覆盖。
- `wechat_session` 只能在用户显式配置 Cookie/session 时调用；不得保存或打印敏感信息。
- Summary Mode 必须先收藏再总结，摘要失败不阻塞收藏。

## 统计 Provider

| Provider | 说明 |
| --- | --- |
| `none` | 不获取统计，写 0，状态为 `缺统计数据` |
| `official` | 微信官方图文统计，仅自有公众号可用，需 access token 或 appid/secret |
| `wechat_session` | 微信登录态接口，需 `WECHAT_SESSION_COOKIE` |
| `third_party` | 通用第三方 HTTP API，需 `WECHAT_STATS_API_URL` |
