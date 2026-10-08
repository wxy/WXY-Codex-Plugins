# Historical marketplace assessment — 2026-10-08

**Archived decision context.** The user subsequently chose complete personal local use and removed official-marketplace distribution from the current scope. The proposals and release guard below describe an earlier assessment; they are not active requirements. No reduced candidate or public release was produced. Current distribution is documented in `../distribution.md`.

# Official marketplace feasibility and release gate

Checked against official OpenAI documentation on **2026-10-08 (Asia/Shanghai)**. These rules are current evidence, not a permanent platform guarantee. Recheck before a distribution decision.

## Decision

The desired product is a Codex-specific **Development Storage Growth Monitor** with automatic task baselines, local storage observation and meaningful task-window history. Public marketplace distribution is an explicit product goal.

The current complete local architecture cannot be submitted as-is. A skills-only scan-on-demand package would remove automatic task coverage and is not an equivalent official version. The repository therefore builds only the complete local package and deliberately blocks `package --profile marketplace`. This is a product/platform gate, not a packaging defect that can be fixed by hiding hook files.

## Verified constraints

| Constraint | Official source | Effect on Codex Footprint |
| --- | --- | --- |
| Lifecycle hooks supported for manually installed Codex Desktop plugins; hook-containing plugins are ineligible for the public directory | [Package your plugin — bundled hooks](https://developers.openai.com/plugins/build/plugins) | Blocks the core automatic lifecycle adapter in a public ZIP |
| Public MCP submission uses a remote HTTPS endpoint; local MCP authors unable to deploy remotely are directed to contact OpenAI | [Package your plugin — bundled MCP](https://developers.openai.com/plugins/build/plugins) | Our local stdio MCP is not an established public submission path |
| ZIPs containing app references or lifecycle hooks cannot currently be submitted | [Upload and submit your plugin](https://developers.openai.com/plugins/deploy/submission) | Cannot bypass the rule using a manifest variant |
| Plugin hooks require review/trust; enabling/installing does not trust them automatically | [Hooks](https://learn.chatgpt.com/docs/hooks) | Even local installation needs host trust and real lifecycle acceptance |
| Listing icons, identity and review metadata have separate requirements | [Submission field reference](https://developers.openai.com/plugins/deploy/submission) | Local scaffold metadata alone does not establish review readiness |

An engineering fact follows: a remote HTTPS server has no access to arbitrary user-local filesystem paths. It needs a supported local agent/execution channel, permissions and a delivery model. Deploying this Python observer to a cloud URL does not solve local observation. Whether an external companion is acceptable for this use case is **unconfirmed**, not an approved workaround.

## Questions requiring an official answer

1. Is there a supported public-directory exception or planned route for a read-only storage observer using lifecycle hooks? If so, what is the actual review/permission model?
2. Can a public Codex-specific plugin bundle or depend on a local stdio MCP? The docs direct authors to an OpenAI contact, but do not promise approval.
3. Is an independently installed, local-only companion allowed for an official listing? How is installation, update, uninstall and user consent reviewed, and how does Codex provide authenticated lifecycle events to it?
4. If only remote MCP is eligible, is there an approved local bridge that preserves local data and automatic task baselines? A custom cloud-sync service would introduce authentication and data exposure that require a new product decision.

Do not send these questions or contact anyone automatically. No support message, dashboard submission or public publication has been made.

## Paths and their status

- **Complete manual local plugin:** technically implemented in V1, with black-box tests; real Desktop hook delivery still needs acceptance. This is the product validation path, not official distribution.
- **Official local/hook support:** best fit if confirmed by OpenAI. Currently unresolved; retain the complete architecture pending an answer.
- **Official plugin + companion:** possible research direction only. Not implemented and not claimed eligible. Requires official confirmation and a deliberate installation/privacy design.
- **Remote MCP alone:** does not meet local automatic observation requirements.
- **Skills-only replacement:** rejected as an equivalent product. It can manually inspect accessible storage, but cannot promise automatic hook-level task history.

## Release gates

Before calling this an official-market candidate: obtain a documented supported distribution path that preserves core behavior; validate it with a real Codex lifecycle session; review the data/permission/update model; then complete publisher verification, final identity/assets, listing fields, applicable policies and review evidence. No invented URLs, credentials or official affiliation belong in the manifest. The name currently states independent development and uses a separate storage/trend icon; final brand review remains open.

**V1 outcome:** local research/validation scaffold only. Official marketplace feasibility remains blocked by current documented capabilities; no public candidate ZIP is produced.
