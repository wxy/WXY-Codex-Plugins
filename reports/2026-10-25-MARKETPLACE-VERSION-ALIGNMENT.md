# 本地市场版本对齐验证

日期：2026-10-25（Asia/Shanghai）。用户授权本地市场中的 Footprint 同步到 0.4.7，保留简洁标题规则；没有授权自动合入 PR。

## 来源与范围

- 市场实际来源保持 `/Volumes/MacSSD/develop/WXY-Codex-Plugins`，不是 Git 市场的临时克隆。
- 原开发分支 `codex/compact-title-badges` 的 Footprint 为 0.4.3；其中已验收的简洁标题修复仍未进入远程主分支。原分支保留原样。
- 新分支 `codex/marketplace-version-alignment` 以远程 main `78ea5b3ea7e94a02547f9f16576c735db2ff1992` 为基础，直接采用已经合入的完整 Footprint 0.4.7。其插件目录与该 main 逐文件一致，不是仅改版本号，也不重新实现监测功能。
- 仅恢复 `f07700c` 中的标题脚本、清单、README 和既有回归源码；没有带入该历史提交的测试过程 JSON。标题最多一个时间符号、一个 PR 规模符号，旧重复前缀可清理，AI 概括保留。
- 根 README 同步 0.4.7，并要求安装前核对、保留已注册来源；本地维护使用真实开发仓库。切换注册仓库的分支前必须核对全部插件版本，避免局部升级回退其他插件。

## 验证选择

本轮实际组合了已发布的 Footprint 源码与此前已验证的标题实现。选择直接覆盖标题 Hook、真实 CLI 安装、版本 / 源码一致性及旧入口兼容的端到端路径。Footprint 运行逻辑没有新增变化，不重复此前 0.4.7 的全量 111 场景、浏览器图表、全机扫描或通知验收。没有新建单元测试；原有标题测试文件随修复恢复，但本轮不重复运行隔离测试。

环境：macOS，Codex CLI `0.164.0-alpha.11.1`，Python `3.14.6`。所有验证输入、安装配置、日志和 JSON 均在独立系统临时目录；无模型调用。

| 路径 | 实际结果 |
| --- | --- |
| 既有标题 Hook 黑盒端到端 | 19 / 19 通过。PR 数 0 / 4 / 5 / 7 / 12 / 24 / 25 / 32 / 100 / 10000，时间边界与 AI 改名后旧前缀替换均覆盖，前缀始终至多两个符号 |
| 既有真实 CLI 安全升级端到端 | 3 / 3 通过：缺旧缓存不阻塞、启动异常不阻塞、从旧版升级并转发旧入口 / 更新稳定路径 / 保留无关配置且未启用监测 |
| 实际本地市场 → 临时配置安装 | 两个真实目录入口均正确。Footprint 0.4.7 共 74 个受 Git 管理文件、标题插件 `0.3.0+codex.20260927011134` 共 4 个文件与源码 SHA-256 全部一致；实际 Footprint CLI 返回 0.4.7。未配置时保持 inactive，不创建观察状态 |
| 版本与差异 | Footprint manifest、pyproject 与运行时均为 0.4.7；`git diff origin/main -- plugins/codex-footprint` 为空。命名脚本与此前已验收安装副本一致 |

安装组合目录摘要（按相对路径排序的 SHA-256 映射 JSON 再 SHA-256）：

- Footprint：`22dd00a8a3d937e4c2b568e94c90e1927efef96c1e4ece8aa8513a6f8299bf74`。
- 标题插件：`0351318dd54233b19250e0072e34f7ed487db0194eb7414fdd338663c8c21545`。

## 本机缓存恢复

切回本地来源后，宿主已根据旧分支把 Footprint 安装缓存刷新为 0.4.3；稳定运行时 / worker 仍为 0.4.7。本轮源码对齐后，使用 `codex --no-daemon plugin add codex-footprint@wxy-codex-plugins --json` 恢复缓存，74 个文件与当前来源一致。旧 0.4.3 缓存路径指向 0.4.7，实际旧入口 `--version` 返回 0.4.7。已有稳定 worker 的 PID 未变、仍在运行、版本 0.4.7、无 last_error；没有重启健康服务、修改监测配置或主动扫描。

标题插件保持 `0.3.0+codex.20260927011134`，Daydream 保持 `0.1.0+codex.20260923133500`；市场继续指向 develop 真实仓库。旧聊天兼容入口保留。已经载入内存的旧 MCP 模块不因文件更新而自动重载，需新聊天加载新版；这不影响已运行的 0.4.7 稳定服务。

## 复现

从仓库根目录，先创建独立系统临时 TASK_DIR：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_pr_badge_compaction.py \
  --hook plugins/codex-pr-title-hook/scripts/pr_title_after_pull_request.py \
  --report "$TASK_DIR/title-e2e.json"
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_footprint_safe_upgrade.py \
  --output "$TASK_DIR/safe-upgrade"
git diff --exit-code origin/main -- plugins/codex-footprint
```

市场组合验证使用独立临时 Codex 配置和独立 Footprint 数据目录，调用真实 `codex --no-daemon plugin marketplace add <本仓库真实路径> --json`，然后分别安装两个插件。对 `git ls-files plugins/<插件名>` 的每个普通文件，按相对路径比较来源 / installedPath 文件 SHA-256；检查安装版本、Footprint `--version` 和 `status`。输入为本仓库目录与未配置数据目录，要求 status.enabled=false 且数据目录不存在。退出后删除整个临时配置。此路径不触碰个人安装或启动 worker。

本机状态恢复只用于修正本轮发现的安装缓存回退；重复验证时先读当前状态，不默认重新安装或重启服务。

## 留存与边界

只保留本报告和可复用源码。临时测试配置、完整日志、模拟输入、JSON、报告过程目录均已删除，没有加入 Git。没有合入旧开发分支中的测试过程附件或其他未发布功能。交付通过 PR，远程主分支是否已包含简洁标题修复以该 PR 的合入状态为准；不要把本地同步当成已经远程合入。
