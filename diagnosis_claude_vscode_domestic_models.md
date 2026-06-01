# Claude Code for VS Code 使用国产模型兼容性诊断报告

生成日期：2026-05-29  
涉及模型：MiniMax-M2.7、DeepSeek-v4-pro  
涉及客户端：Claude Code for VS Code / Claude Code CLI v2.1.156  
目标：诊断 Claude Code 在 VS Code 窗口模式和 VS Code 集成终端中使用国产 Anthropic 兼容接口时报错的问题，并给出可执行整改建议。

## 一、结论摘要

本次问题的核心不是模型本身不能用，也不是单纯的 API Key、Base URL 或 Claude Code 版本问题，而是 Claude Code for VS Code 集成路径与国产 Anthropic 兼容接口之间存在协议兼容性冲突。

在 VS Code 的 Claude Code 插件环境中，请求会通过 `claude-vscode` / SDK 集成路径发送，并在 `messages` 数组中夹带 `role: "system"` 类型的消息。MiniMax、DeepSeek 等国产 Anthropic 兼容接口当前只接受 `user` / `assistant` 作为 `messages[].role`，因此直接返回 400。

典型报错如下：

```text
API Error: 400 Failed to deserialize the JSON body into the target type:
messages[1].role: unknown variant system, expected user or assistant
```

```text
API Error: 400 invalid params, chat content has invalid message role: system (2013)
```

因此，该问题本质上是“Claude Code VS Code 集成请求格式”与“第三方 Anthropic 兼容接口接收格式”不一致导致的。

## 二、环境与已观察现象

### 1. 使用环境

- 操作系统：Windows
- Claude Code 版本：v2.1.156
- 使用入口：
  - VS Code Claude Code 窗口模式
  - VS Code 内置终端中的 Claude Code
  - 独立 Windows PowerShell 中的 Claude Code
- 测试模型：
  - MiniMax-M2.7
  - DeepSeek-v4-pro
- 接入方式：通过 Anthropic 兼容接口配置 `ANTHROPIC_BASE_URL` 等环境变量

### 2. 失败场景

以下场景均出现同类错误：

| 场景 | 模型 | 结果 | 典型错误 |
|---|---|---|---|
| VS Code Claude Code 窗口模式 | MiniMax-M2.7 | 失败 | `invalid message role: system (2013)` |
| VS Code Claude Code 窗口模式 | DeepSeek-v4-pro | 失败 | `messages[1].role: unknown variant system` |
| VS Code 插件管理的终端模式 | MiniMax-M2.7 | 失败 | `invalid message role: system (2013)` |
| VS Code 插件管理的终端模式 | DeepSeek-v4-pro | 失败 | `messages[1].role: unknown variant system` |
| VS Code 普通终端中启动 Claude | MiniMax-M2.7 | 失败 | `invalid message role: system (2013)` |

### 3. 成功或部分成功场景

独立 Windows PowerShell 中直接运行 `claude`，使用 MiniMax-M2.7 时曾成功返回正常回复。这说明：

- MiniMax-M2.7 接口本身并非完全不可用；
- Claude Code v2.1.156 也并非在所有入口下都必然失败；
- 失败更集中地出现在 VS Code 插件集成环境或被 VS Code 注入上下文的运行路径中。

仍建议补充一个对照测试：在独立 PowerShell 中切换到同一项目目录后运行 `claude`，确认是否仍然成功。该测试可进一步区分“项目上下文触发”与“VS Code 集成触发”。

## 三、关键证据

### 1. 错误信息直接指向 `messages[].role`

DeepSeek 报错：

```text
messages[1].role: unknown variant system, expected user or assistant
```

MiniMax 报错：

```text
chat content has invalid message role: system (2013)
```

两个服务商的错误虽然表述不同，但都明确指向同一问题：请求体中的 `messages` 数组出现了 `role: "system"`。

### 2. VS Code 集成路径会注入额外上下文

排查日志中可见 VS Code 相关入口信息，例如：

```text
cc_entrypoint=claude-vscode
```

以及：

```text
[API REQUEST] /anthropic/v1/messages source=sdk
Sending 38 skills via attachment
```

这说明 VS Code 插件并不只是简单调用普通命令行模式，而是通过 Claude Code 的 IDE / SDK 集成路径发送请求，并附带了文件、技能、上下文等额外信息。

这些 IDE 上下文很可能被组织为 system 类型消息插入到 `messages` 数组中，从而触发国产兼容接口的校验失败。

### 3. 更换模型不能解决

MiniMax-M2.7 和 DeepSeek-v4-pro 均失败，说明这不是某一个模型能力不足，而是多个国产 Anthropic 兼容接口共同存在的协议适配问题。

### 4. 版本和 wrapper 不是根因

曾尝试通过 VS Code 设置 `claudeProcessWrapper` 强制调用全局 Claude Code 可执行文件，并确认 wrapper 生效。但错误仍然存在。

这说明问题不是“VS Code 插件调用了错误版本的 Claude Code”这么简单，而是 VS Code 集成路径在发送请求时仍然采用了不被国产兼容接口接受的消息格式。

### 5. `CLAUDE_CODE_SIMPLE=1` 未解决本环境问题

曾在 Claude Code 配置环境变量中加入：

```text
CLAUDE_CODE_SIMPLE=1
```

但 VS Code / SDK 集成路径下仍然报 `system role` 错误。因此，在当前环境中，该变量无法可靠阻止 VS Code 集成请求携带 `messages[].role = system`。

## 四、对豆包反馈的审阅

豆包反馈中有一部分判断是有价值的：

- 国产 Anthropic 兼容接口通常不接受 `messages` 中出现 `role: "system"`；
- 问题与新版 Claude Code 发送的 system 类型上下文有关；
- 通过简化请求或代理改写请求，是合理方向。

但也有几处需要谨慎看待：

1. “官方 API messages 里可以有 `role: "system"`”这一说法需要核实。Anthropic Messages API 的常规格式是顶层 `system` 字段加 `messages` 中的 `user` / `assistant`，并不建议把 system 作为 messages role 直接放入。

2. `simple_mode: true` 没有在当前 Claude Code 配置中被证实为有效字段。若配置文件 schema 不支持，该字段可能会被忽略。

3. `providers` 数组配置也未在当前本地 Claude Code 配置 schema 中被确认有效。当前更可靠的方式仍是通过 `env` 设置 `ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、模型名等。

4. `CLAUDE_CODE_SIMPLE=1` 在独立 CLI 某些路径下可能有效，但本次实测无法解决 VS Code 插件集成路径的问题。

## 五、根因分析

### 1. 请求格式冲突

Claude Code VS Code 集成路径可能构造了类似下面的请求：

```json
{
  "system": "全局系统提示",
  "messages": [
    {
      "role": "system",
      "content": "IDE 或动态上下文"
    },
    {
      "role": "user",
      "content": "你好"
    }
  ]
}
```

但 MiniMax、DeepSeek 的 Anthropic 兼容接口期望的是：

```json
{
  "system": "全局系统提示和动态系统提示",
  "messages": [
    {
      "role": "user",
      "content": "你好"
    }
  ]
}
```

也就是说，system 信息可以存在，但应当放在顶层 `system` 字段，而不是作为 `messages` 数组中的一条消息。

### 2. VS Code 插件比普通 CLI 更容易触发该问题

VS Code 插件为了实现编辑器感知、文件上下文、选区上下文、技能注入、自动编辑等能力，会向 Claude Code 注入更多系统级上下文。

这些上下文在请求中更容易表现为 system 类型消息，因此比独立 PowerShell 中的普通 CLI 更容易触发第三方接口的兼容问题。

### 3. 国产兼容接口校验更严格

MiniMax、DeepSeek 虽然提供 Anthropic 兼容入口，但并不等于完全兼容 Claude Code 所有内部请求形态。它们当前至少没有兼容 `messages[].role = system` 这种请求格式。

## 六、已经尝试过的处理措施

1. 新建 Claude Code 会话，问题仍然存在。

2. 更换模型：
   - MiniMax-M2.7 失败；
   - DeepSeek-v4-pro 失败。

3. 切换 VS Code 的 Claude Code 使用方式：
   - 窗口模式失败；
   - 插件终端模式失败；
   - VS Code 普通终端中运行也失败。

4. 修改 VS Code 配置，尝试使用 `claudeCode.useTerminal`，未解决根因。

5. 创建 `claudeProcessWrapper` 强制走全局 Claude Code，可执行文件生效但请求仍失败。

6. 添加 `CLAUDE_CODE_SIMPLE=1`，仍未阻止 VS Code 集成路径发送 system role 消息。

## 七、整改建议

### 方案 A：VS Code 窗口模式使用官方 Anthropic 接入

这是最稳妥方案。如果希望继续使用 VS Code 图形化窗口模式、编辑器上下文、自动改文件、技能注入等完整 Claude Code 能力，建议使用官方 Anthropic 支持的接入方式。

优点：

- 与 Claude Code VS Code 插件兼容性最好；
- 不需要维护代理；
- 出错概率最低。

缺点：

- 成本和账号体系需要接受官方 Anthropic 方案。

### 方案 B：国产模型只在独立 PowerShell / Windows Terminal 中使用

如果 MiniMax-M2.7 在独立 PowerShell 中稳定可用，则可以将国产模型作为命令行工作模式使用，避免 VS Code 插件集成路径。

建议进一步测试：

```powershell
cd "C:\Users\Eric8\03-claude code\diagnosis\wechat-article-collection-project"
claude
```

如果在独立 PowerShell 的同一项目目录中仍然可用，说明问题基本可以锁定在 VS Code 注入环境，而不是项目目录本身。

优点：

- 实施成本低；
- 不需要开发额外组件；
- 可以继续使用 MiniMax / DeepSeek。

缺点：

- 不能获得完整 VS Code 窗口式交互体验；
- 编辑器集成能力弱于插件窗口模式。

### 方案 C：编写本地兼容代理，改写请求

如果必须同时满足：

- 使用 VS Code 窗口模式；
- 使用 MiniMax / DeepSeek；
- 保留 Claude Code 插件交互体验；

那么更现实的技术方案是增加一个本地代理服务。

代理工作方式：

1. VS Code Claude Code 不再直接请求 MiniMax / DeepSeek；
2. `ANTHROPIC_BASE_URL` 指向本地代理，例如：

```text
http://127.0.0.1:8787/anthropic
```

3. 本地代理接收 Claude Code 请求；
4. 代理扫描请求体中的 `messages`；
5. 如果发现 `role: "system"`：
   - 将其内容合并到顶层 `system` 字段；
   - 从 `messages` 数组中删除该 system 消息；
6. 代理再把改写后的请求转发给 MiniMax 或 DeepSeek；
7. 对流式 SSE 响应保持透传。

代理改写前：

```json
{
  "system": "A",
  "messages": [
    {
      "role": "system",
      "content": "B"
    },
    {
      "role": "user",
      "content": "你好"
    }
  ]
}
```

代理改写后：

```json
{
  "system": "A\n\nB",
  "messages": [
    {
      "role": "user",
      "content": "你好"
    }
  ]
}
```

代理还需要注意：

- 不能记录 API Token；
- 需要支持 streaming；
- 需要保留 `x-api-key`、`authorization`、`anthropic-version` 等必要请求头；
- 需要正确透传错误；
- 需要将日志做脱敏；
- 最好先只支持本机 `127.0.0.1`，避免暴露到公网。

该方案是目前在“国产模型 + VS Code 窗口模式”之间做兼容的最可控路线。

### 方案 D：等待服务商兼容

也可以向 MiniMax / DeepSeek 反馈，要求其 Anthropic 兼容接口支持或自动转换 `messages[].role = system`。

但该方案不可控，无法保证时间。

### 方案 E：不建议直接修改 VS Code 插件源码

直接改 Claude Code VS Code 插件内部代码不推荐：

- 插件更新会覆盖修改；
- 内部实现不稳定；
- 调试成本高；
- 容易造成新的不可预期问题。

## 八、当前本机配置变更记录

排查过程中曾做过以下实验性改动：

1. VS Code 用户配置中设置过：

```json
{
  "claudeCode.useTerminal": false,
  "claudeCode.claudeProcessWrapper": "C:\\Users\\Eric8\\.claude\\claude-vscode-wrapper.exe"
}
```

2. 曾创建 wrapper 文件：

```text
C:\Users\Eric8\.claude\claude-vscode-wrapper.exe
```

3. 曾在 Claude Code 配置环境变量中加入：

```text
CLAUDE_CODE_SIMPLE=1
```

这些改动均未解决当前根因。若后续采用官方 Anthropic 或本地代理方案，建议清理无效 wrapper 配置，避免后续排查被干扰。

注意：本报告不记录任何 API Token。若排查过程中曾将配置文件或日志完整发送给第三方，应考虑轮换相关密钥。

## 九、建议下一步动作

优先级建议如下：

1. 先确认独立 PowerShell 在同一项目目录下运行 `claude` 是否稳定可用。

2. 如果只需要国产模型工作流，优先使用独立 PowerShell / Windows Terminal。

3. 如果必须使用 VS Code 窗口模式，优先改用官方 Anthropic 接入。

4. 如果必须使用 VS Code 窗口模式加国产模型，则开发本地兼容代理，将 `messages[].role = system` 改写到顶层 `system` 字段。

5. 向 MiniMax / DeepSeek 提交兼容性反馈，请求其 Anthropic 兼容接口支持 Claude Code VS Code 插件产生的 system role 请求。

## 十、给 Claude / 服务商的简短问题描述

可以直接复制下面这段给 Claude Code、MiniMax 或 DeepSeek 技术支持：

```text
我在 Windows + VS Code 中使用 Claude Code v2.1.156，通过 Anthropic 兼容接口接入 MiniMax-M2.7 / DeepSeek-v4-pro。

在独立 PowerShell 中 MiniMax-M2.7 曾可以正常回复，但在 VS Code Claude Code 窗口模式、VS Code 插件终端模式、VS Code 普通终端中均失败。

错误分别为：
- DeepSeek: messages[1].role: unknown variant system, expected user or assistant
- MiniMax: invalid params, chat content has invalid message role: system (2013)

排查日志显示 VS Code 集成路径包含 cc_entrypoint=claude-vscode，并通过 /anthropic/v1/messages source=sdk 发起请求，且会发送 IDE/skills 上下文。

我的判断是：VS Code Claude Code 集成路径会在 messages 数组中插入 role=system 的消息，而 MiniMax/DeepSeek 的 Anthropic 兼容接口只接受 user/assistant，导致 400。

请确认：
1. Claude Code VS Code 集成是否会发送 messages[].role=system？
2. 是否有官方配置可以强制将 system 消息合并到顶层 system 字段？
3. MiniMax/DeepSeek 是否可以兼容或自动转换 messages[].role=system？
4. 如果不能，是否建议通过本地代理改写请求体？
```

