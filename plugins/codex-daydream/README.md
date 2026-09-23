# Codex Daydream

Turn a continuous Codex work period into a cartoon-poster prompt that shows recognizable work and results without publishing the underlying work log.

> 将最近一段连续的 Codex 工作，包括跨午夜的工作，整理成能看出项目用途、投入重点与实际成果的卡通海报提示词。用户可以指定重点、主题、风格和时间范围。

## Use · 使用

Invoke **Codex Daydream** from any Codex task, or mention `$codex-daydream`, then ask:

```text
把最近这段连续工作变成卡通海报提示词。突出今天在存储整理工具上的突破，采用温暖的漫画风格。
```

Every invocation freshly summarizes the full latest continuous work period across tasks. The period can cross midnight; by default a six-hour idle gap separates periods, with a 24-hour maximum span. Earlier poster generations never shorten the scope. Give exact start and end times to override it, or ask for “仅总结当前任务” to use only the current task.

> 每次调用都会重新汇总最近一段完整工作；跨午夜仍可属于同一段。指定明确起止时间可覆盖默认范围。调用插件后补充的“突出什么、用什么风格、可以展示哪些名称或素材”等语句，都会用于这次创作。

## Privacy model · 隐私模型

- Source sessions are read locally and never modified.
- The collector omits system/developer instructions, subagent tasks, reasoning, tool payloads, and commentary.
- Paths, links, emails, secrets, IDs, code blocks, and other high-risk strings are redacted before excerpts reach the poster workflow.
- The final prompt explains project purposes and work outcomes with short labels alongside visual metaphors. It may use a project name, logo, or image when the user provides or approves it for sharing, or when it is clearly public-facing material.
- No extra transcript database or automatic schedule is created.

This is privacy minimization, not a formal anonymization guarantee. Review the generated prompt before sharing it publicly.

## Output · 输出

The skill produces a compact metaphor explanation, a 4:5 image-generation prompt, and a negative prompt. Its default title is **我与 Codex 工作的一天** / **A Day Working with Codex**, making the subject explicit rather than hiding it behind an abstract slogan.

The poster selects one to four work tracks, showing what each project is for, what happened, and which result is supported by the source. The main work gets the largest scene; smaller scenes show secondary work. Project logos or images can be considered from user attachments or bounded local asset candidates. If a separate image model is used, chosen local files must be attached there; a path in a prompt is not enough. The upper 72–78% is the cartoon work scene with short work labels; the lower 22–28% is a dedicated identity panel with `Xingyu Wang`, the work date or overnight date span, `Created with Codex Daydream`, and the repository address.

> 海报上部既有具象的项目隐喻，也有简短的工作标签，能看出主要做了什么、取得什么结果；下部保留独立说明区，写明用户、日期、来源与仓库地址。标题继续直接说明与 Codex 的一天。

The package also includes a short instruction telling vision-capable AI assistants to read the repository README when their user asks to install. No QR code is required; the exact URL is emitted separately:

<https://github.com/wxy/WXY-Codex-Plugins>
