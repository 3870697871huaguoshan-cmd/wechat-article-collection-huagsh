---
name: wechat-article-collection
description: 微信公众号文章收藏工作流。用于收藏 mp.weixin.qq.com 文章、按关键词搜索公众号文章、补全文章元数据、写入飞书多维表格「瑶哥的公众号文章收藏录」，以及在用户要求时生成摘要。
---

# 微信公众号文章收藏工作流

## 核心原则

这个技能只做可靠收藏，不承诺绕过微信平台限制。

永久限制：
- 阅读数、点赞数、转发数无法自动抓取。微信要求登录态且数据动态渲染，写入时固定为 `0`，不要告诉用户这些字段已真实抓取。
- 正文内容不稳定。`wechat-article-extractor` 常因微信登录态或脚本解析失败返回 `1005`，只能作为摘要模式的可选来源。
- 公众号名称是最高失败率字段。优先从 HTML `var nickname` 取；失败后用搜狗微信搜索结果的 `source` 补全；仍失败则写 `待补充` 并在回复里说明。

必须优先保证：
- 不重复收藏。
- URL 字段格式正确。
- 已知不可抓取字段不伪造。
- 失败时有明确降级路径。

## 飞书 Base 信息

- base_token: `HmeubVX2UazS5RsUyK9ciK3DnJG`
- table_id: `tble8OJWkYYfuKZ5`
- Base URL: `https://my.feishu.cn/base/HmeubVX2UazS5RsUyK9ciK3DnJG`

字段映射：

| 字段名 | 类型 | 写入规则 |
| --- | --- | --- |
| 文章标题 | 文本 | 优先用 `og:title`，其次搜索结果标题，最后 `待补充` |
| 公众号名称 | 文本 | 优先 `var nickname`，其次搜索结果 `source`，最后 `待补充` |
| 文章链接 | URL | 用真实 `mp.weixin.qq.com` 链接 |
| 主题关键词 | 文本 | 用户指定优先；否则可从标题提取 |
| 文章关键词 | 文本 | 用户指定优先；否则可从标题提取 |
| 阅读数 | 数字 | 固定写 `0`，不可声称已抓取 |
| 点赞数 | 数字 | 固定写 `0`，不可声称已抓取 |
| 转发数 | 数字 | 固定写 `0`，不可声称已抓取 |
| 收藏时间 | 日期 | 表格自动填充时不要手写 |

写入 Base 前先读字段结构：

```bash
lark-cli base +field-list --as user --base-token HmeubVX2UazS5RsUyK9ciK3DnJG --table-id tble8OJWkYYfuKZ5
```

## 标准收藏流程

### 场景 A：用户给微信文章链接

必须按这个顺序执行，不要先跑 extractor。

1. 规范化链接
   - 只接受 `https://mp.weixin.qq.com/s/...`、`https://mp.weixin.qq.com/s?...` 等微信文章链接。
   - 去掉明显的分享追踪参数不影响文章访问时可以保留原链接；不要把搜狗跳转页写入表格。

2. curl 抓元数据，最多尝试 2 次
   - 第一次用移动端 UA。
   - 失败或核心字段为空时换桌面 UA 重试一次。
   - 每次超时 10 秒左右，不要让单次抓取卡 20 秒以上。

```bash
curl -s -L --max-time 10 \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" \
  -H "Referer: https://mp.weixin.qq.com/" \
  "https://mp.weixin.qq.com/s/..."
```

从 HTML 中提取：
- 标题：`<meta property="og:title" content="...">`
- 摘要：`<meta property="og:description" content="...">`
- 公众号名称：`var nickname = "..."`

3. 搜索补全公众号名称
   - 只有在标题可用但公众号名称为空时搜索。
   - 先用完整标题搜；0 结果时切 4-8 个连续中文关键词重搜。
   - `source` 为空字符串时视为无效，不要写空字符串到表格。

```bash
cd ~/.hermes/hermes-agent/skills/wechat-article-search
node scripts/search_wechat.js "文章标题或关键词" -n 5 -r
```

结果字段：
- `title`: 文章标题
- `url`: 已解析的真实 `mp.weixin.qq.com` 链接
- `source`: 公众号名称，可能为空，必须判空
- `summary`: 摘要
- `datetime` / `date_text`: 发布时间

4. 查重
   - 写入前必须查重。
   - 先按文章链接查；如果链接查不到，再按文章标题查。
   - 发现重复时不要新增记录，回复用户“已收藏过”，并说明匹配到的标题或链接。

```bash
lark-cli base +record-search --as user \
  --base-token HmeubVX2UazS5RsUyK9ciK3DnJG \
  --table-id tble8OJWkYYfuKZ5 \
  --format json \
  --json '{"keyword":"https://mp.weixin.qq.com/s/...","search_fields":["文章链接"],"select_fields":["文章标题","公众号名称","文章链接"],"limit":10}'
```

5. 写入
   - 使用 `lark-cli base +record-upsert`。
   - URL 字段用当前 lark-cli 的 Base CellValue：直接传 URL 字符串。
   - 如果绕过 lark-cli 调原始 bitable API，URL 字段必须是 `{"link":"...","text":"..."}`；不要把原始 API 的格式混到 lark-cli 命令里。

```bash
lark-cli base +record-upsert --as user \
  --base-token HmeubVX2UazS5RsUyK9ciK3DnJG \
  --table-id tble8OJWkYYfuKZ5 \
  --json '{
    "文章标题": "文章标题",
    "公众号名称": "公众号名称或待补充",
    "文章链接": "https://mp.weixin.qq.com/s/...",
    "主题关键词": "用户指定主题或自动关键词",
    "文章关键词": "关键词",
    "阅读数": 0,
    "点赞数": 0,
    "转发数": 0
  }'
```

6. 写入失败重试
   - 飞书 API 或 lark-cli 返回 500/502/503、超时、临时网络错误时，指数退避重试 3 次：2 秒、4 秒、8 秒。
   - 字段类型错误、权限错误、`URLFieldConvFail`、字段名不存在时不要盲目重试，先修正 payload。

### 场景 B：用户给关键词，让你搜索后收藏

1. 用 `wechat-article-search` 搜索，返回候选结果给用户选择，除非用户明确说“选最相关的一篇”。

```bash
cd ~/.hermes/hermes-agent/skills/wechat-article-search
node scripts/search_wechat.js "关键词" -n 10 -r
```

2. 用户选中后，进入场景 A 的查重和写入步骤。
3. 搜索结果的 `source` 为空时不要直接写空值，改写 `待补充`。

### 场景 C：用户要求“收藏并总结”

先收藏，再尝试总结。摘要失败不能阻塞收藏。

1. 先按场景 A/B 完成收藏。
2. 再调用 `wechat-article-extractor` 尝试获取 `msg_content`。
3. 如果 extractor 返回 `1005` 或正文为空：
   - 用 curl 拿到的 `og:description` 生成降级摘要。
   - 如果 `og:description` 也为空，告诉用户“已收藏，但当前链接无法稳定提取正文，暂不能总结”。
4. 摘要只在回复里输出，不写入当前 Base。

摘要格式：

```markdown
## 文章概要
- 一句话核心结论

## 关键要点
- 要点 1
- 要点 2
- 要点 3

## 思考与启发
- 1-2 句可执行启发
```

## 数据完整性规则

生成待写入记录前，必须做这个归一化：

```text
title = og:title || search.title || "待补充"
source = nickname || non_empty(search.source) || "待补充"
url = normalized_mp_weixin_url || search.url
read_count = 0
like_count = 0
share_count = 0
```

如果 `title` 或 `url` 都不可用，不要写表格，先向用户说明无法收藏并给出失败原因。

如果 `source == "待补充"`，收藏仍然可以继续，但回复里必须提示用户后续可手动补全公众号名称。

## 已知失败模式

### wechat-article-extractor

| 错误码 | 含义 | 处理 |
| --- | --- | --- |
| 1005 | 脚本解析失败，通常需要微信登录态 | 不重试，不阻塞收藏；摘要模式降级到 `og:description` |
| 1004 | 访问过于频繁 | 等待后最多重试 1 次 |
| 1001 | 缺少标题或发布时间 | 用 curl/search 结果兜底 |
| 2003 | 内容涉嫌侵权被删除 | 告知用户，停止收藏 |
| 2006 | 内容违规无法查看 | 告知用户，停止收藏 |
| 2009 | 不支持的链接格式 | 要求用户提供微信文章链接 |
| 2015 | 账号迁移中 | 告知用户，必要时让用户提供新链接 |

### wechat-article-search

- 完整长标题经常 0 结果，必须切关键词重搜。
- 搜狗可能反爬或验证码，失败时不要无限重试。
- 同一标题可能被多个账号转载；如果结果不唯一且用户没有授权自动选择，返回候选让用户选。
- `source` 可能为空，必须判空。

### curl

- 成功率不稳定，尤其是 `var nickname`。
- 对无 UA 请求可能返回空内容。
- 失败时换 UA 重试一次即可，不要循环请求。

## 回复模板

收藏成功：

```text
已收藏：<文章标题>
公众号：<公众号名称或待补充>
链接：<文章链接>

阅读数/点赞数/转发数受微信限制无法自动抓取，已按 0 写入。
```

已重复：

```text
这篇文章已经收藏过了，没有重复写入。
匹配依据：<文章链接或文章标题>
```

部分成功：

```text
已收藏：<文章标题>
公众号名称这次没有稳定识别到，已写为“待补充”。
阅读数/点赞数/转发数受微信限制无法自动抓取，已按 0 写入。
```

收藏并总结但正文提取失败：

```text
已收藏文章，但微信正文提取失败（通常需要登录态）。下面是基于页面摘要的降级总结：
...
```

## 依赖技能

- `wechat-article-search`：搜狗微信搜索与真实链接解析。
- `wechat-article-extractor`：可选正文提取，仅用于 summary mode。
- `lark-base`：字段读取、查重、记录写入。
