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
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..."

# 运行前诊断（Hermes 测试必须先做）
python scripts/collect_article.py --version
python scripts/collect_article.py --diagnose

# 收藏并总结
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --summary

# 统计授权初始化（仅在 --diagnose 显示未初始化时执行）
python scripts/init_wechat_stats_capture.py

# 运行测试
python -m pytest tests/ -v
```

## 核心原则

- **先确认版本** — Hermes 测试前先运行 `--version`，必须看到 `2026-06-04.1` 或更新
- **脚本自加载环境** — 自动读取 `~/.hermes/.env`、项目 `.env`，不依赖外层 shell 注入
- **不重复收藏** — 写入前两级查重（链接 → 标题）
- **URL 字段格式正确** — `lark-cli base +record-upsert` 传字符串，不混用 `{link,text}`
- **统计数据不误判** — 未获取到真实阅读/点赞/转发数时停止写入，不用 `0` 冒充成功
- **字段不缺失** — 公众号名称补不到时停止写入，不写 `"待补充"`
- **失败有明确原因** — 返回结构化错误，调用方按提示完成一次性统计授权初始化

永久限制：
- 阅读数、点赞数、转发数不以普通 HTML 作为统计来源；正式流程固定调用本技能自建的微信统计采集器。
- 正文内容不稳定。`wechat-article-extractor` 常因登录态返回 `1005`，仅用于 Summary Mode。
- 公众号名称优先从 `var nickname` 获取；短链页常见兜底是 `<meta name="author">` / `og:article:author`；仍失败才走搜索补全；补不到则不写入。

## 飞书 Base 配置

通过环境变量或 `~/.hermes/.env` 配置目标 Base，不要在 public 仓库中硬编码真实资源标识：

- `WECHAT_COLLECTION_BASE_TOKEN`
- `WECHAT_COLLECTION_TABLE_ID`

PowerShell 示例：

```powershell
$env:WECHAT_COLLECTION_BASE_TOKEN="your_feishu_base_token"
$env:WECHAT_COLLECTION_TABLE_ID="your_feishu_table_id"
```

Hermes `.env` 示例：

```text
WECHAT_COLLECTION_BASE_TOKEN=your_feishu_base_token
WECHAT_COLLECTION_TABLE_ID=your_feishu_table_id
```

配置后运行 `python scripts/collect_article.py --diagnose`，确认：

- `base_token_configured: true`
- `table_id_configured: true`
- `stats_authorization_configured: true`

## 脚本清单

| 脚本 | 用途 | 调用时机 |
|------|------|----------|
| `scripts/collect_article.py` | **主入口** — 收藏文章 | 用户给链接时直接调用 |
| `scripts/fetch_meta.py` | curl 抓 og:title/description/nickname/author | collect_article 内部调用 |
| `scripts/search_enrich.py` | wechat-article-search 补公众号名称 | nickname 缺失时 collect_article 内部调用 |
| `scripts/base_records.py` | 飞书 Base 查重/写入/更新 | collect_article 内部调用 |
| `scripts/fetch_stats.py` | 统计数据获取入口 | collect_article 内部调用 |
| `scripts/providers/wechat_stats_capture.py` | 自建微信统计采集器 | collect_article 默认调用 |
| `scripts/init_wechat_stats_capture.py` | 一次性统计授权初始化 | 仅在诊断显示未初始化时调用 |

## 主流程

```
用户给链接
  → python scripts/collect_article.py --version / --diagnose
  → python scripts/collect_article.py <url> [--summary]
     ├─ fetch_meta: curl ×2 (换UA, 10s超时，nickname/author 兜底)
     ├─ search_enrich: nickname 缺失时搜狗补全
     ├─ base_records: 两级查重 (链接精确扫描→标题精确扫描)
     ├─ fetch_stats: 调用自建微信统计采集器
     ├─ base_records: +record-upsert 写入
     └─ --summary: extractor → og:description 降级
```

## 查重

写入前必须查重。当前实现使用 `lark-cli base +record-list --format json` 拉取必要字段，并在脚本内做精确匹配，避免 URL 字段被飞书返回成 Markdown 链接时 `record-search` 漏判：

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
| 公众号名称 | 文本 | nickname → meta author / og:article:author → search source；仍失败则停止写入 |
| 文章链接 | 文本(URL) | 用户提供的链接，传字符串 |
| 主题关键词 | 文本 | 用户指定或自动提取 |
| 文章关键词 | 文本 | 用户指定或自动提取 |
| 阅读数 | 数字 | 自建统计采集器返回真实值；未命中则停止写入 |
| 点赞数 | 数字 | 自建统计采集器返回真实值；未命中则停止写入 |
| 转发数 | 数字 | 自建统计采集器返回真实值；未命中则停止写入 |
| 收藏时间 | 日期 | 脚本写当前时间 |
| 统计来源 | 单选 | 写入现有选项 `wechat_session` |
| 统计更新时间 | 日期 | 脚本每次写入统计字段时写当前时间 |
| 数据状态 | 单选 | 成功写入时为 `完整`；失败时不写入 Base，仅在脚本输出中返回 `缺公众号名称` / `抓取失败` / `统计获取失败` |

## 真实统计固定采集路径

不要给用户选择题。Hermes 只执行这一条路径：

1. 运行 `python scripts/collect_article.py --diagnose`。
2. 如果 `stats_authorization_configured=false`，运行 `python scripts/init_wechat_stats_capture.py` 完成一次性统计授权初始化。
3. 运行 `python scripts/collect_article.py "<文章链接>"`。
4. 脚本自动提取文章参数，调用 `wechat_stats_capture` 获取 `read_num` / `like_num` / `share_num`，再写入 Base。

合规与风控：只使用用户本机授权态；不调用付费第三方 API；不上传 Cookie、密钥或统计数据；不无限循环采集；一次只处理当前用户请求的文章。

## 公众号名称补全

多 source 不一致时不盲取第一个：
1. 标题精确匹配 → 确认
2. URL 文章 ID 匹配 → 确认
3. 无法确认 → 停止写入，返回缺公众号名称

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
  "source": "公众号名称",
  "url": "https://mp.weixin.qq.com/s/...",
  "data_status": "完整 | 缺公众号名称 | 统计获取失败 | 抓取失败 | null(重复记录)",
  "message": "已收藏：...",
  "summary": null
}
```

## 依赖技能

- `wechat-article-search` — 搜狗微信搜索与真实链接解析
- `wechat-article-extractor` — 可选正文提取，仅用于 Summary Mode
