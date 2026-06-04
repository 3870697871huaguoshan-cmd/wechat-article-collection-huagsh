# wechat-article-collection

微信公众号文章收藏工作流。给定 `mp.weixin.qq.com` 文章链接后，脚本会抓取元数据、补全公众号名称、查重、读取真实统计数据并写入飞书多维表格。

## Features

- 主入口：`scripts/collect_article.py`
- 两级查重：文章链接 -> 文章标题
- 飞书 Base 写入：`lark-cli base +record-upsert`
- 固定真实统计路径：自建微信统计采集器
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
| `WECHAT_STATS_SESSION_FILE` | 可选：本地微信统计授权文件路径 |

说明：写入 Base 的 `统计来源` 使用现有选项 `wechat_session`，不要求新增 Base 字段或选项。

PowerShell 示例：

```powershell
$env:WECHAT_COLLECTION_BASE_TOKEN="your_feishu_base_token"
$env:WECHAT_COLLECTION_TABLE_ID="your_feishu_table_id"
```

## Usage

运行前诊断：

```bash
python scripts/collect_article.py --version
python scripts/collect_article.py --diagnose
```

收藏文章：

```bash
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..."
```

收藏并尝试摘要：

```bash
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --summary
```

固定真实统计采集路径：

1. 运行 `python scripts/collect_article.py --diagnose`。
2. 如果统计授权未初始化，运行 `python scripts/init_wechat_stats_capture.py`。
3. 运行 `python scripts/collect_article.py "<文章链接>"`，脚本自动采集统计并写入 Base。

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

- 阅读数、点赞数、转发数不以普通 HTML 作为统计来源；正式收藏必须由自建统计采集器获取真实数据，未命中时不会写入 Base。
- 脚本不调用付费第三方 API，不要求用户导出 CSV，不上传 Cookie、密钥或统计数据。
- public 仓库中不要提交 `.env`、真实 Cookie、API Key 或账号密码。
- 脚本会自动读取 `~/.hermes/.env` 和项目 `.env`，但不会打印敏感值。

## License

MIT
