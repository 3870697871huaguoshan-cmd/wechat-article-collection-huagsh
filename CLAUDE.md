# wechat-article-collection — 技能维护

维护 `wechat-article-collection` 技能（微信公众号文章收藏工作流），修复已知缺陷。

## 技能来源
- 飞书 Drive 文件夹：https://my.feishu.cn/drive/folder/E63dfuPk7l0UWgdXdTzcKYCgneq
- 缺陷分析文档：https://my.feishu.cn/docx/NEfEdx53Go8aUUxsWeicP2JZn0g

## 规则
- 修改前先通过 `drive +pull` 同步飞书上的最新版本
- 修改后通过 `drive +push` 同步回飞书
- SKILL.md 是技能说明入口；scripts/ 和 tests/ 是主流程的可执行实现与回归测试，也需要一起维护
- 按缺陷分析报告的优先级（P0 → P1 → P2）依次修复
- 每次修改后验证 lark-cli 仍然可以正确加载该技能
