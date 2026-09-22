# Codex Daydream

Turn the shape of a day's Codex work into a playful cartoon-poster prompt without publishing the underlying work log.

> 将当天或上次总结之后的 Codex 工作抽象成一个卡通隐喻，并输出可直接交给图像模型的竖版海报提示词。它不是精确工时报告，也不会在海报中复述项目名、代码、路径或对话原文。

## Use · 使用

Invoke **Codex Daydream** from any Codex task, or mention `$codex-daydream`, then ask:

```text
把我从上次总结以来的工作变成今天的卡通海报提示词。
```

The default scope starts at the latest successful Daydream checkpoint on the same local day. If none exists, it starts at local midnight. Ask for “仅总结当前任务” to avoid scanning other local tasks.

> 默认从当天最近一次成功生成的 Daydream 检查点开始；若当天没有检查点，则从本地零点开始。也可以要求“仅总结当前任务”。

## Privacy model · 隐私模型

- Source sessions are read locally and never modified.
- The collector omits system/developer instructions, subagent tasks, reasoning, tool payloads, and commentary.
- Paths, links, emails, secrets, IDs, code blocks, and other high-risk strings are redacted before excerpts reach the poster workflow.
- The final prompt must generalize project names, people, technologies, numbers, and operational details into visual metaphors.
- No extra transcript database or automatic schedule is created.

This is privacy minimization, not a formal anonymization guarantee. Review the generated prompt before sharing it publicly.

## Output · 输出

The skill produces a title, a compact metaphor explanation, a 4:5 image-generation prompt, and a negative prompt. It deliberately avoids dashboards, exhaustive timelines, and precise productivity claims.

The poster remains concrete enough to recognize the day's work: it selects two to four generalized work anchors and gives each one a visible counterpart. Every package also includes the local work date, `Xingyu Wang`, the repository address, and a short instruction telling vision-capable AI assistants to read the repository README when their user asks to install. No QR code is required; the exact URL is emitted separately:

<https://github.com/wxy/WXY-Codex-Plugins>
