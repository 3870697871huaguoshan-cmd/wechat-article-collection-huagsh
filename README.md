# wechat-article-collection

微信公众号文章收藏工作流。给定 `mp.weixin.qq.com` 文章链接后，脚本会抓取元数据、补全公众号名称、查重并写入飞书多维表格。

## Features

- 主入口：`scripts/collect_article.py`
- 两级查重：文章链接 -> 文章标题
- 飞书 Base 写入：`lark-cli base +record-upsert`
- 统计数据 provider 框架：`none` / `official` / `wechat_session` / `third_party`
- Summary Mode：先收藏，再尝试摘要；摘要失败不阻塞收藏
- 回归测试：`tests/`

## Prerequisites

- Python 3.10+
- `pytest`
- `curl`
- `lark-cli` 已安装并完成 `auth login --domain base`
- 已有飞书多维表格与目标数据表

## Configuration

复制 `.env.example` 并按本机环境设置变量。不要把 `.env` 提交到 public 仓库。

必需环境变量：

| 变量 | 说明 |
|---|---|
| `WECHAT_COLLECTION_BASE_TOKEN` | 飞书 Base token |
| `WECHAT_COLLECTION_TABLE_ID` | 飞书数据表 ID |

可选环境变量：

| 变量 | 说明 |
|---|---|
| `LARK_CLI_BIN` | 指定 `lark-cli` 可执行文件路径 |
| `WECHAT_ARTICLE_EXTRACTOR_DIR` | Summary Mode 的 extractor 脚本目录 |
| `WECHAT_SESSION_COOKIE` | 仅在显式使用 `wechat_session` provider 时临时提供 |
| `WECHAT_WXTOKEN` | 微信 `getappmsgext` 的 wxtoken，默认 `777` |

PowerShell 示例：

```powershell
$env:WECHAT_COLLECTION_BASE_TOKEN="your_feishu_base_token"
$env:WECHAT_COLLECTION_TABLE_ID="your_feishu_table_id"
```

## Usage

收藏文章：

```bash
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --topic "AI" --keywords "Agent"
```

收藏并尝试摘要：

```bash
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --summary
```

查询统计 provider：

```bash
python scripts/fetch_stats.py --url "https://mp.weixin.qq.com/s/..." --provider none
```

运行测试：

```bash
python -m pytest tests/ -q
```

## File Layout

- `SKILL.md`：技能入口说明，面向 agent 调用
- `remote-skill/SKILL.md`：早期远程技能说明留档，发布时请以根目录 `SKILL.md` 和脚本为准
- `scripts/`：可执行实现
- `tests/`：回归测试
- `diagnosis_claude_vscode_domestic_models.md`：Claude Code 与国产模型兼容性诊断记录，和收藏功能本身无直接依赖

## Security Notes

- 阅读数、点赞数、转发数不能从普通 HTML 稳定抓取。
- `wechat_session` provider 只从环境变量读取临时 Cookie/session 信息，不保存、不打印。
- public 仓库中不要提交 `.env`、真实 Cookie、API Key 或账号密码。

## License

MIT
