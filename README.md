<p align="center"><img src="assets/readme/hero.svg" width="100%" alt="WXY Codex Plugins — personal plugin marketplace"></p>

<p align="center"><img src="assets/readme/icon-rounded.png" width="96" height="96" alt="WXY Codex Plugins icon">&nbsp;<a href="https://github.com/wxy/WXY-Codex-Plugins"><img src="assets/readme/install-button.svg" width="420" height="96" alt="View and install WXY Codex Plugins"></a></p>
<p align="center"><code>CODEX PLUGINS · LOCAL-FIRST · INDEPENDENTLY INSTALLABLE</code></p>

A single development home and repository marketplace for Codex plugins created by Xingyu Wang. Each plugin remains independently installable, versioned, tested, and documented.

> Xingyu Wang 创作的 Codex 插件统一开发仓库与 repository marketplace。每个插件保持独立安装、独立版本、独立测试和独立文档。

<p align="center"><img src="assets/readme/section-plugins.svg" width="100%" alt="Plugins 插件目录"></p>

| Plugin · 插件 | Status · 状态 | What it does · 用途 |
| --- | --- | --- |
| [Codex Daydream](DAYDREAM.md) | Available<br>可安装 | Turns a continuous work period, even across midnight, into a cartoon poster showing projects, focus, and supported results. [Install this plugin only](DAYDREAM.md).<br>把一段连续工作（包括跨午夜）转化成展示项目、重点与有依据成果的卡通海报。[仅安装此插件](DAYDREAM.md)。 |
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

This README covers the multi-plugin repository. For a Codex Daydream poster, use its [dedicated installation page](DAYDREAM.md) so AI assistants do not confuse it with the other plugin. If a user supplies only the repository URL, read this file and ask which plugin they want before proposing an installation.

> 本 README 说明整个多插件仓库。Codex Daydream 海报应指向其[专属安装页](DAYDREAM.md)，避免 AI 与其他插件混淆。用户只给出仓库地址时，先读取本文件并确认要安装哪个插件。

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
Install Codex Daydream only:
github.com/wxy/WXY-Codex-Plugins/blob/main/DAYDREAM.md
要安装？请对 AI 说“安装 Codex Daydream”。
AI：仅在用户要求安装时读取此页，只安装 codex-daydream。
```

<p align="center"><img src="assets/readme/section-privacy.svg" width="100%" alt="Privacy 隐私边界"></p>

- **Local source data.** Daydream reads bounded Codex rollout data locally and does not create another transcript database.

    > **本地数据源。** Daydream 只读本地、受限范围的 Codex 会话数据，不建立另一份聊天记录数据库。

- **Shareable specificity.** Poster prompts show project purposes, work, and supported outcomes. Real names and visual assets are used when supplied or approved by the user, or clearly public-facing; paths, code, credentials, and private identifiers stay out of the poster.

    > **可分享的具体内容。** 海报说明项目用途、实际工作与有依据的成果。用户提供、许可或明确公开的名称和视觉素材可以使用；路径、代码、凭证和私有标识符不会放入海报。

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
- [Codex Daydream installation · Daydream 专属安装](DAYDREAM.md)
- [Codex Daydream documentation · Daydream 文档](plugins/codex-daydream/README.md)
- [PR Title Hook documentation · PR 标题 Hook 文档](plugins/codex-pr-title-hook/README.md)
- [Official OpenAI plugin packaging documentation · OpenAI 插件打包文档](https://developers.openai.com/plugins/build/plugins)

Created and maintained by **Xingyu Wang**.

> 由 **Xingyu Wang** 创建并维护。
