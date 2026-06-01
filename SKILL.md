---
name: wechat-article-collection
description: 微信公众号文章收藏工作流。用于收藏 mp.weixin.qq.com 文章、按关键词搜索公众号文章、补全文章元数据、写入飞书多维表格「瑶哥的公众号文章收藏录」，以及在用户要求时生成摘要。
---

# 微信公众号文章收藏工作流

> **优先调用 `scripts/collect_article.py`，不要让模型手写完整流程。**

## 快速开始

```bash
# 收藏文章
cd diagnosis/wechat-article-collection-project
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --topic "AI" --keywords "Agent"

# 收藏并总结
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --summary

# 运行测试
python -m pytest tests/ -v
```

## 核心原则

- **不重复收藏** — 写入前两级查重（链接 → 标题）
- **URL 字段格式正确** — `lark-cli base +record-upsert` 传字符串，不混用 `{link,text}`
- **已知不可抓取字段不伪造** — 阅读/点赞/转发数默认填 `0`
- **失败有明确降级路径** — 不阻塞收藏

永久限制：
- 阅读数、点赞数、转发数不能从普通 HTML 抓取。需通过 stats_provider 补录。
- 正文内容不稳定。`wechat-article-extractor` 常因登录态返回 `1005`，仅用于 Summary Mode。
- 公众号名称是最高失败率字段（`var nickname` 命中率 ~40%）。

## 飞书 Base 配置

通过环境变量配置目标 Base，不要在 public 仓库中硬编码真实资源标识：

- `WECHAT_COLLECTION_BASE_TOKEN`
- `WECHAT_COLLECTION_TABLE_ID`

PowerShell 示例：

```powershell
$env:WECHAT_COLLECTION_BASE_TOKEN="your_feishu_base_token"
$env:WECHAT_COLLECTION_TABLE_ID="your_feishu_table_id"
```

## 脚本清单

| 脚本 | 用途 | 调用时机 |
|------|------|----------|
| `scripts/collect_article.py` | **主入口** — 收藏文章 | 用户给链接时直接调用 |
| `scripts/fetch_meta.py` | curl 抓 og:title/description/nickname | collect_article 内部调用 |
| `scripts/search_enrich.py` | wechat-article-search 补公众号名称 | nickname 缺失时 collect_article 内部调用 |
| `scripts/base_records.py` | 飞书 Base 查重/写入/更新 | collect_article 内部调用 |
| `scripts/fetch_stats.py` | 统计数据获取入口 | 用户显式请求时独立调用 |
| `scripts/providers/official.py` | 微信公众号官方数据接口 | 占位，需配置 WECHAT_OFFICIAL_APPID/SECRET |
| `scripts/providers/wechat_session.py` | 微信登录态接口 | 可用框架，需显式提供临时 `WECHAT_SESSION_COOKIE` 等环境变量，不保存 cookie/token |
| `scripts/providers/third_party.py` | 第三方数据 API | 占位，需配置 WECHAT_STATS_API_KEY |

## 主流程

```
用户给链接
  → python scripts/collect_article.py <url> [--summary]
     ├─ fetch_meta: curl ×2 (换UA, 10s超时)
     ├─ search_enrich: nickname 缺失时搜狗补全
     ├─ base_records: 两级查重 (链接→标题)
     ├─ base_records: +record-upsert 写入
     └─ --summary: extractor → og:description 降级
```

## 查重

写入前必须查重，使用 `lark-cli base +record-search --format json`：

```bash
# 按链接
python scripts/base_records.py check-url "https://mp.weixin.qq.com/s/..."

# 按标题
python scripts/base_records.py check-title "文章标题"
```

命中重复 → 返回 `status=duplicate`，不写入。

## 字段映射

写入前用 `python scripts/base_records.py fields` 确认字段结构。

| 字段名 | 类型 | 写入规则 |
|--------|------|----------|
| 文章标题 | 文本 | og:title → search.title → 终止 |
| 公众号名称 | 文本 | nickname → search source → "待补充" |
| 文章链接 | 文本(URL) | 用户提供的链接，传字符串 |
| 主题关键词 | 文本 | 用户指定或自动提取 |
| 文章关键词 | 文本 | 用户指定或自动提取 |
| 阅读数 | 数字 | 默认 0，由 stats_provider 更新 |
| 点赞数 | 数字 | 默认 0，由 stats_provider 更新 |
| 转发数 | 数字 | 默认 0，由 stats_provider 更新 |
| 收藏时间 | 日期 | 飞书自动填充 |
| 统计来源 | 单选 | 主流程写 `none`，由 stats_provider 更新为 `official` / `wechat_session` / `third_party` |
| 统计更新时间 | 日期 | 仅统计数据更新时写入 |
| 数据状态 | 单选 | 主流程写 `缺统计数据` / `缺公众号名称` / `抓取失败`，统计更新后可改为 `完整` |

## 统计数据获取

**不支持从普通 HTML 抓取。** 通过可插拔 provider 获取：

```bash
# 默认 none（不获取）
python scripts/fetch_stats.py --url "<链接>" --provider none

# 显式指定 provider
python scripts/fetch_stats.py --url "<链接>" --provider official

# 配置 fallback_chain 时才允许链路
python scripts/fetch_stats.py --url "<链接>" --provider official --fallback-chain "official,third_party,none"
```

### Provider 安全规则

- 默认 `none`，不自动抓取
- 用户必须显式指定 provider
- provider 失败时直接返回该 provider 的结构化错误，**不自动跨 provider 跳转**；只有用户显式配置 `fallback_chain` 且链路中包含 `none` 时才降级到 `none`
- `wechat_session` 涉及 cookie/token → 不能无感知触发
- `third_party` 涉及 API key/费用 → 不能无感知触发
- 只有用户显式配置 `fallback_chain` 时才按链路尝试

### Provider 类型

| Provider | 数据来源 | 状态 | 可用字段 |
|----------|----------|------|----------|
| `none` | 不获取 | 可用 | 全 0 |
| `official` | 微信公众平台图文分析 | 占位 | read_count, share_count（like_count 为 partial） |
| `wechat_session` | 微信登录态接口 | 可用框架 | read_num, like_num（需 session；share_count 默认为 0/partial） |
| `third_party` | 第三方 API | 占位 | 取决于具体 API |

### fetch_stats 返回结构

```json
{
  "ok": true,
  "provider": "official",
  "read_count": 12345,
  "like_count": 0,
  "share_count": 45,
  "confidence": "high | medium | low | none",
  "partial": true,
  "error": null
}
```

## 公众号名称补全

多 source 不一致时不盲取第一个：
1. 标题精确匹配 → 确认
2. URL 文章 ID 匹配 → 确认
3. 无法确认 → "待补充"，返回候选列表

## Summary Mode

先收藏，再总结。总结失败不阻塞收藏：

```
extractor 成功 → 结构化摘要
extractor 1005 → 降级 og:description
两者都失败 → "已收藏，无法获取正文用于总结"
```

## 错误处理

| 错误类型 | 策略 |
|----------|------|
| HTTP 500/502/503/timeout | 指数退避 2s/4s/8s，最多 3 次 |
| 字段类型/字段名/权限错误 | 不重试，直接返回结构化错误 |
| `URLFieldConvFail` | 不重试，检查字段名 |
| curl 首次无 og:title | 换 UA 重试 1 次 |
| extractor 1005 | 不重试，降级到 og:description |
| 搜狗验证码 | 等 5 秒重试 1 次 |

## 输出结构 (collect_article.py)

```json
{
  "ok": true,
  "status": "created | duplicate | failed",
  "record_id": "recxxx",
  "title": "文章标题",
  "source": "公众号名称或待补充",
  "url": "https://mp.weixin.qq.com/s/...",
  "data_status": "完整 | 缺公众号名称 | 缺统计数据 | 抓取失败 | null(重复记录)",
  "message": "已收藏：...",
  "summary": null
}
```

## 依赖技能

- `wechat-article-search` — 搜狗微信搜索与真实链接解析
- `wechat-article-extractor` — 可选正文提取，仅用于 Summary Mode
