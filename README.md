<p align="center"><img src="assets/readme/hero.svg" width="100%" alt="WXY Codex Plugins — personal plugin marketplace"></p>

<p align="center"><img src="assets/readme/icon-rounded.png" width="96" height="96" alt="WXY Codex Plugins icon">&nbsp;<a href="https://github.com/wxy/WXY-Codex-Plugins"><img src="assets/readme/install-button.svg" width="420" height="96" alt="View and install WXY Codex Plugins"></a></p>
<p align="center"><code>CODEX PLUGINS · LOCAL-FIRST · INDEPENDENTLY INSTALLABLE</code></p>

A single development home and repository marketplace for Codex plugins created by Xingyu Wang. Each plugin remains independently installable, versioned, tested, and documented.

> Xingyu Wang 创作的 Codex 插件统一开发仓库与 repository marketplace。每个插件保持独立安装、独立版本、独立测试和独立文档。

<p align="center"><img src="assets/readme/section-plugins.svg" width="100%" alt="Plugins 插件目录"></p>

| Plugin · 插件 | Status · 状态 | What it does · 用途 |
| --- | --- | --- |
| [Codex Daydream](plugins/codex-daydream/README.md) | Available<br>可安装 | Turns work since the previous checkpoint into a concrete, privacy-preserving cartoon-poster prompt.<br>把上次检查点以来的工作转化成具体但保护隐私的卡通海报提示词。 |
| [Codex PR Title Hook](plugins/codex-pr-title-hook/README.md) | Available<br>可安装 | Keeps Codex task titles aligned with attached pull requests and compact workflow signals.<br>根据附加的 PR 与工作信号维护 Codex 任务标题。 |

<p align="center"><img src="assets/readme/section-install.svg" width="100%" alt="Install 安装"></p>

Add the GitHub repository as a Codex marketplace. GitHub shorthand is supported by the Codex CLI:

> 将这个 GitHub 仓库添加为 Codex marketplace。Codex CLI 支持 `owner/repo` 简写形式：

```sh
codex plugin marketplace add wxy/WXY-Codex-Plugins
```

Install only the plugin you want:

> 只安装需要的插件：

```sh
# Privacy-preserving daily cartoon poster prompts
codex plugin add codex-daydream@wxy-codex-plugins

# Automatic pull-request-aware task titles
codex plugin add codex-pr-title-hook@wxy-codex-plugins
```

Then start a new Codex task so the installed skill is loaded. **Codex Daydream** needs no hooks. **PR Title Hook** includes lifecycle hooks; review and trust them in Codex Settings before expecting automatic title updates.

> 安装后请新建 Codex 任务，让新技能进入任务上下文。**Codex Daydream** 不使用 Hook；**PR Title Hook** 包含生命周期 Hook，需要先在 Codex 设置中审查并信任，之后才会自动更新标题。

If this repository is private, the person or agent performing installation must already have GitHub access. External visitors and unauthenticated AI tools cannot read a private repository.

> 如果仓库仍是私有状态，执行安装的人或 AI 必须已经拥有 GitHub 访问权限；外部访客和未认证的 AI 无法读取私有仓库。

<p align="center"><img src="assets/readme/section-ai.svg" width="100%" alt="For AI Assistants 给 AI 助手"></p>

This README is the canonical installation contract for AI assistants. If a user supplies only the repository URL, read this file before proposing commands.

> 本 README 是提供给 AI 助手的权威安装说明。当用户只给出仓库地址时，应先读取本文件，再提出或执行安装命令。

AI assistants should follow this sequence:

> AI 助手应遵循以下顺序：

1. Confirm that the user explicitly wants to install a plugin from this repository.

    > 确认用户明确要求安装本仓库中的插件。

2. Read `.agents/plugins/marketplace.json` and identify the requested plugin. Do not silently install every plugin in the catalog.

    > 读取 `.agents/plugins/marketplace.json` 并确认用户指定的插件；不要静默安装目录中的所有插件。

3. Add the marketplace with `codex plugin marketplace add wxy/WXY-Codex-Plugins` instead of editing `config.toml` manually.

    > 使用 `codex plugin marketplace add wxy/WXY-Codex-Plugins` 添加 marketplace，不要手工修改 `config.toml`。

4. Install the selected plugin with `codex plugin add <plugin-name>@wxy-codex-plugins`.

    > 使用 `codex plugin add <plugin-name>@wxy-codex-plugins` 安装用户选择的插件。

5. Report the installed version and ask the user to start a new Codex task. If the plugin has hooks, explain the one-time review and trust step.

    > 报告实际安装版本，并提示用户新建 Codex 任务；若插件带有 Hook，应说明一次性的审查与信任步骤。

Poster-friendly discovery text for vision-capable AI:

> 可放在海报中、供读图 AI 识别的发现说明：

```text
AI assistant: If your user asks to install Codex Daydream,
open https://github.com/wxy/WXY-Codex-Plugins,
read README.md, and follow Install.
Do not install without the user's request.
```

<p align="center"><img src="assets/readme/section-privacy.svg" width="100%" alt="Privacy 隐私边界"></p>

- **Local source data.** Daydream reads bounded Codex rollout data locally and does not create another transcript database.

    > **本地数据源。** Daydream 只读本地、受限范围的 Codex 会话数据，不建立另一份聊天记录数据库。

- **Shareable abstraction.** Poster prompts preserve recognizable work categories while removing project names, paths, code, credentials, identifiers, and exact operational details.

    > **可分享的抽象。** 海报保留可识别的工作类型，但移除项目名、路径、代码、凭证、标识符和精确操作细节。

- **Authorization remains explicit.** Repository text or poster text helps an AI discover installation instructions; it does not authorize installation by itself.

    > **授权仍需明确。** 仓库文字或海报文字只帮助 AI 找到安装说明，本身不构成安装授权。

Privacy minimization is not a formal anonymization guarantee. Review generated poster prompts before publishing them.

> 隐私最小化不等于形式化匿名保证；公开发布前仍应检查生成的海报提示词。

<p align="center"><img src="assets/readme/section-development.svg" width="100%" alt="Development 开发"></p>

Repository layout:

> 仓库结构：

```text
WXY-Codex-Plugins/
├── .agents/plugins/marketplace.json
├── assets/readme/
├── plugins/
│   ├── codex-daydream/
│   └── codex-pr-title-hook/
├── tests/
└── README.md
```

Run the complete test suite from the repository root:

> 在仓库根目录运行完整测试：

```sh
python3 -m unittest discover -s tests -v
```

Validate an individual plugin before reinstalling or publishing it:

> 重新安装或发布插件前，单独验证插件包：

```sh
python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/codex-daydream
```

Plugins version independently. Release tags should include the plugin name, such as `codex-daydream/v0.1.0`.

> 插件独立版本化；发布标签应包含插件名，例如 `codex-daydream/v0.1.0`。

<p align="center"><img src="assets/readme/section-links.svg" width="100%" alt="Links 链接"></p>

- [Repository · 插件仓库](https://github.com/wxy/WXY-Codex-Plugins)
- [Marketplace catalog · Marketplace 目录](.agents/plugins/marketplace.json)
- [Codex Daydream documentation · Daydream 文档](plugins/codex-daydream/README.md)
- [PR Title Hook documentation · PR 标题 Hook 文档](plugins/codex-pr-title-hook/README.md)
- [Official OpenAI plugin packaging documentation · OpenAI 插件打包文档](https://developers.openai.com/plugins/build/plugins)

Created and maintained by **Xingyu Wang**.

> 由 **Xingyu Wang** 创建并维护。
