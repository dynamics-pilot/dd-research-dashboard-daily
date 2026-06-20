# Research Dashboard Interface

Use this reference when maintaining:

```text
D:\ResearchManagement\research-dashboard
```

## Files

```text
research-dashboard/
  index.html
  dashboard-data.json
  projects/
    _template.md
    <project-slug>.md
  tools/
    build_dashboard.py
```

Do not hand-edit `index.html` except for emergency repair. Treat `projects/*.md` as source data and regenerate the page with:

```powershell
python .\research-dashboard\tools\build_dashboard.py
```

The build command also writes `dashboard-data.json`. The browser polls it about every 5 seconds and updates changed project cards without a full page reload. Changed cards get a pale highlight until DD clicks the card in that browser. This acknowledgement is stored in browser localStorage, so another agent cannot directly clear DD's browser-local highlight except by producing new dashboard data for the page to process.

The dashboard URL is:

```text
file:///D:/matlabDrive/ResearchManagement/research-dashboard/index.html
```

The page also shows browser-local system time, supports custom drag ordering, supports temporary updated-time ordering, and separates `active` projects from `waiting`/`paused`/`archived` projects.

Run the command from:

```text
D:\ResearchManagement
```

## Default Recording Rule

- Default assumption: if DD work creates reusable project memory, it belongs in the dashboard unless DD explicitly says not to record it.
- This includes research, papers, figures, simulations, experiments, reviewer responses, proposals, translation workflows, recurring engineering work, and multi-agent handoffs that DD may revisit.
- Do not skip dashboard maintenance just because DD did not explicitly remind the current agent.
- Default exceptions: personal privacy matters, medical matters, secrets/accounts/tokens/logins, or other sensitive non-research items; and one-off trivial actions with no future memory value.
- If unsure, prefer a short update in the closest existing project rather than leaving the work unrecorded.
- If DD has already required several agents to co-maintain one merged topic, all related work must continue in that same project file unless DD later asks to split it.

## Naming and Language

- Dashboard-visible names should be Chinese by default: project `title`, card names, section headings, summaries, and handoff labels.
- Professional English terms, acronyms, software names, model names, and method names may stay in English when that is clearer, e.g. UAV, iLQR, CFD, BEM, MATLAB, CodexBridge.
- File slugs, paths, command names, and code identifiers should stay as short ASCII/English identifiers, e.g. `payload-vector-birotor-ilqr.md`.
- Avoid English-only generated titles unless DD explicitly asks for English or a Chinese title would be misleading.

## Project File Schema

Each project file must use this front matter:

```yaml
---
title: 中文研究题目（专业英文术语可保留）
status: active
priority: medium
owner: DD + Codex
order:
updated: YYYY-MM-DD HH:MM
tags: [tag1, tag2]
summary: 用中文一句话说明这个研究正在解决什么。
---
```

Parsing rules are strict:

- Save project Markdown as UTF-8 without BOM.
- The opening `---` must be the first visible characters in the file and must be alone on line 1.
- The closing `---` must also be alone on its own line.
- Each metadata field must be on its own line.
- Do not write front matter as one line, e.g. `--- title: ... status: ... summary: ... ---`.
- Do not put checklist items or section headings above the opening `---`.

If the generated card title is the filename slug, `updated` is shown as unknown, or the card summary begins with `--- title:`, the front matter was not parsed. Fix the project Markdown source and rebuild.

Valid `status` values:

- `active`: 正在推进。
- `waiting`: 等待用户、实验、数据、审稿意见、外部信息或人工确认。
- `paused`: 暂停，但未来可能继续。
- `archived`: 已归档，不再主动推进。

Recommended `priority` values: `high`, `medium`, `low`.

Optional `order`: lower numbers appear earlier in the generated dashboard. Browser drag-and-drop order is stored in localStorage for DD's current browser under the default custom sort mode; new projects are appended to that custom order. The dashboard also has an updated-time sort mode for temporary review. Use `order` when the default generated order should be permanent across agents and regenerations.

Use minute precision for `updated`, e.g. `2026-05-15 16:58`. This makes updated-time sorting useful when several agents edit the dashboard on the same day.

Required sections:

```markdown
## 当前问题

- [ ] 当前还没有解决、会影响继续推进的问题。

## 已解决

- [x] ~~已经解决的问题。~~ (YYYY-MM-DD)

## 下一步计划

- [ ] 后续 agent 或用户可以直接执行的动作。

## 维护文件

- `path/to/file` - 文件用途、本轮改动或后续注意点。

## 关键记录

- YYYY-MM-DD: 关键判断、实验结论、失败尝试或交接上下文。
```

## Start Checklist

Use this checklist before research work:

- List or inspect `research-dashboard/projects/*.md`.
- Read the matching project file fully.
- If the project is missing, create `projects/<short-english-slug>.md` from `_template.md` and use a Chinese project `title`.
- Before creating a new project, check whether DD has already merged this work into an existing shared topic. If yes, update that existing project instead.
- Confirm the active blocker from `当前问题`.
- Confirm the next executable step from `下一步计划`.
- Confirm relevant source, manuscript, data, figure, or output files from `维护文件`.

## End Checklist

Use this checklist after meaningful research work:

- Update `updated` to the current local date and minute.
- Add new blockers to `当前问题`.
- Mark solved blockers in `已解决` with strike-through and date.
- Replace vague next steps with concrete actions.
- Add touched or important files to `维护文件`.
- Append dated context to `关键记录`.
- Confirm the file still begins with a valid multi-line `---` front matter block and is saved as UTF-8 without BOM.
- Rebuild `index.html`.
- In the final response, say which project entry was updated.

## Minimal New Project Example

```markdown
---
title: 多无人机任务分配鲁棒性实验
status: active
priority: high
owner: DD + Codex
updated: 2026-05-15 16:58
tags: [UAV, task-allocation, simulation]
summary: 梳理并验证多无人机任务分配算法在扰动和通信约束下的鲁棒性。
---

## 当前问题

- [ ] 需要明确鲁棒性指标和随机扰动设置。

## 已解决

- [x] ~~建立 dashboard 项目记录。~~ (2026-05-15)

## 下一步计划

- [ ] 检查现有 MATLAB 仿真入口和参数配置文件。
- [ ] 设计 3-5 组可复现实验。

## 维护文件

- `path/to/simulation.m` - 待确认的仿真入口。

## 关键记录

- 2026-05-15: 本项目需要把算法表现和实验设置分开记录，避免后续 agent 混淆结论与待验证假设。
```

## Update Style

Prefer compact, dated records. Preserve important failed attempts because future agents often need to know what not to repeat.

Do not fabricate experiments, conclusions, paper line numbers, or file changes. If a result is only inferred, label it as an inference.
