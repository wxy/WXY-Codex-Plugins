# WXY Codex Plugins

A single development home and repository marketplace for Codex plugins created by WXY.

> WXY 创作的 Codex 插件统一开发仓库与 repository marketplace。每个插件保持独立安装、独立版本和独立测试。

## Plugins · 插件

| Plugin | Status | Description |
| --- | --- | --- |
| [Codex PR Title Hook](plugins/codex-pr-title-hook/README.md) | Available | Keeps Codex task titles aligned with attached pull requests and compact workflow signals. |
| [Codex Daydream](plugins/codex-daydream/README.md) | Available | Turns work since the previous checkpoint into a privacy-preserving cartoon-poster prompt. |

## Install · 安装

Add this repository as a marketplace:

```sh
codex plugin marketplace add wxy/WXY-Codex-Plugins
```

Install an available plugin:

```sh
codex plugin add codex-pr-title-hook@wxy-codex-plugins
codex plugin add codex-daydream@wxy-codex-plugins
```

Start a new Codex task after installation. Plugins that include lifecycle hooks must also be reviewed and trusted before those hooks run.

> 安装后请新建 Codex 任务。带有生命周期 Hook 的插件还需要先检查并信任其 Hook 定义。

## Repository layout · 仓库结构

```text
WXY-Codex-Plugins/
├── .agents/plugins/marketplace.json
├── plugins/
│   └── <plugin-name>/
├── tests/
└── README.md
```

The repository marketplace is the catalog. Each directory under `plugins/` is an independently installable package with its own manifest, version, resources, and documentation.

> 根目录 marketplace 只负责目录索引；`plugins/` 下的每个目录都是可独立安装和发布的插件包。

## Verify · 验证

Run the current test suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

Validate each plugin package before publishing or reinstalling it.

## Versioning · 版本

Plugins version independently. Release tags should include the plugin name, for example:

```text
codex-pr-title-hook/v0.4.0
codex-daydream/v0.1.0
```
