# wechat-article-collection

微信公众号文章收藏工作流。给定 `mp.weixin.qq.com` 文章链接后，脚本会抓取元数据、补全公众号名称、查重、读取真实统计数据并写入飞书多维表格。

## Features

- 主入口：`scripts/collect_article.py`
- 两级查重：文章链接 -> 文章标题
- 飞书 Base 写入：`lark-cli base +record-upsert`
- 固定真实统计路径：读取本地导出的文章数据 CSV
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
| `WECHAT_DOWNLOADER_CSV` | 微信公众号批量下载工具导出的 CSV 文件 |
| `WECHAT_DOWNLOADER_CSV_DIR` | CSV 导出目录；未设置 `WECHAT_DOWNLOADER_CSV` 时读取最新 CSV |

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

用户导出 CSV 后重跑：

```powershell
python scripts/collect_article.py "https://mp.weixin.qq.com/s/..." --stats-csv "D:/path/to/export.csv"
```

固定真实统计采集路径：

1. 打开“微信公众号批量下载工具3.9”。
2. 将目标文章链接粘贴到工具，点击“1.获取公众号id”。
3. 按工具提示在微信桌面客户端内打开生成链接，等待“获取密钥成功”。
4. 点击“2.批量下载文章”或“2.导出文章数据”，导出文章数据 CSV。
5. 使用 `--stats-csv` 带 CSV 路径重跑收藏。

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

- 阅读数、点赞数、转发数不能从普通 HTML 稳定抓取；正式收藏必须从本地 CSV 命中真实统计，未命中时不会写入 Base。
- 脚本只读取本地 CSV，不运行 exe，不上传数据。CSV 命中行如果三项统计全为 `0`，会被视为无效导出。
- public 仓库中不要提交 `.env`、真实 Cookie、API Key 或账号密码。
- 脚本会自动读取 `~/.hermes/.env` 和项目 `.env`，但不会打印敏感值。

## License

MIT
