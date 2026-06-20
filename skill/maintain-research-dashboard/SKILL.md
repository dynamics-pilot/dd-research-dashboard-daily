---
name: maintain-research-dashboard
description: Maintain DD's research progress dashboard before and after scientific work. Use when Codex starts, resumes, hands off, or finishes research tasks for DD, especially MATLAB/Python simulation, LaTeX manuscript work, literature review, reviewer response, UAV/MAV/robotics/control/task-allocation projects, or any multi-agent research collaboration that should record current problems, solved items, next steps, maintained files, and historical context in D:\ResearchManagement\research-dashboard.
---

# Maintain Research Dashboard

Use this skill as a research handoff protocol. The dashboard is the shared memory for DD and future agents, so update it whenever research state changes.

Default bias: if work materially changes research understanding, manuscript state, experiment status, simulation evidence, figure status, proposal status, translation workflow, or another continuing DD project context, add or update the dashboard unless DD explicitly says not to record it.

## Core Interface

Default dashboard root:

```text
D:\ResearchManagement\research-dashboard
```

Project files live at:

```text
D:\ResearchManagement\research-dashboard\projects\<project-slug>.md
```

Regenerate the webpage after edits:

```powershell
python .\research-dashboard\tools\build_dashboard.py
```

The build command writes both `index.html` and `dashboard-data.json`. The page polls `dashboard-data.json` about every 5 seconds, updates changed cards without a full page reload, and highlights cards whose content hash changed until DD clicks them in that browser.

Read `references/dashboard-interface.md` when you need the exact project schema, Chinese section names, start/end checklist, or examples.

For daily research summaries, first read:

```text
D:\ResearchManagement\research-dashboard\DAILY_REPORT_GUIDE.md
```

Daily reports should summarize research progress and conclusions in simple language. Do not treat tool actions such as LaTeX compilation, PDF rendering, page rebuilds, dependency installation, cache cleanup, or script success as research results unless they directly changed a deliverable or support a stated research conclusion.

## Naming and Language

User-facing dashboard names should be Chinese by default. When creating or revising project `title`, dashboard-visible names, section headings, summaries, and handoff labels, write the title in Chinese unless DD explicitly asks otherwise.

Professional English terms, acronyms, model names, software names, and file identifiers may stay in English when natural, e.g. UAV, iLQR, CFD, BEM, MATLAB, CodexBridge. File slugs and paths should remain short ASCII/English identifiers such as `payload-vector-birotor-ilqr.md`.

## Default Inclusion Policy

By default, proactively maintain the dashboard for almost all DD work in this workspace. Do not wait for DD to remind you.

Add or update a dashboard project whenever the task affects one of these:

- research ideas, hypotheses, problem framing, or claim boundaries
- manuscripts, reviewer responses, figures, tables, appendices, or submission packaging
- simulations, experiments, datasets, result interpretation, or failure analysis
- proposals, reports, translation workflows, or recurring technical deliverables that DD will likely revisit
- multi-agent handoffs, role splits, merged-topic ownership, or shared project context

Do not create or update dashboard records only in these default exception cases:

- DD explicitly says not to add this work to the dashboard
- the task is mainly personal privacy, medical, account, finance, password, token, secret, login, or other sensitive non-research material
- the task is a one-off low-value action with no continuing project memory benefit

If a task is borderline, prefer a brief dashboard note rather than omitting it. The main failure mode is missing project memory, not over-recording.

If DD has explicitly said several agents must co-maintain one existing topic, do not split it into new parallel project files. Reuse that shared project and follow the merged-topic boundary strictly.

## DD Material Passport Notes

When `dd-research-playbook` asks for a DD Material Passport, record it in the matching project file as a compact key note or handoff block. Keep the dashboard schema unchanged; the passport is a structured note, not a new database.

Include the fields that matter for the current task: research contract, code state, data and runs, artifacts, claim map, quality-gate status, unresolved blockers, next commands, and timestamp. Use explicit labels such as `PROVISIONAL`, `UNVERIFIED`, `AUTHOR_INPUT_NEEDED`, `not checked`, or `not applicable` instead of filling gaps from memory.

## Daily Report Notes

When DD asks for a dashboard daily report, follow `DAILY_REPORT_GUIDE.md`. By default:

- Do not print a Markdown title or statistics window in the email body.
- Start the body directly with `更新项目数：N`, `活跃项目数：N`, and `主要内容：...`.
- Then write `细则：` only. Format each project as a single paragraph shaped like `1：【项目名】摘要内容`, with a blank line between projects.
- Daily report project titles inside `【】` must be compact display titles, not full paper titles. Prefer 4 to 12 Chinese characters or one short mixed Chinese-English phrase; avoid long manuscript titles that wrap on mobile. Put the specific long topic in the paragraph content instead.
- `细则：` 下的项目编号必须按出现顺序连续递增，写成 `1：`、`2：`、`3：`，不要全部重复成 `1：`。
- Save the same plain-text body to `daily-reports/YYYY-MM-DD.md`. The sender may render that body as a styled HTML email, but the source text format stays simple.
- Do not use Markdown tables, numbered lists, or bullet lists in email reports. Mobile mail clients render those poorly and often create hanging indents.
- Do not insert hard line breaks inside a project paragraph; let the mail client wrap naturally.
- Do not write a separate `项目状态` section or explicit `下一步` lines unless DD asks for them.
- Do not print `待处理任务`, `需要 DD 决策`, `明日建议`, or `数据来源` unless DD explicitly asks for those sections.
- Focus on what research, manuscript, figure, experiment, simulation, or proposal content changed, and what conclusion or limitation was recorded.
- Do not foreground numeric results, parameter values, page counts, dimensions, R2/RMSE, percentages, or similar details unless DD explicitly asks for them. Prefer high-level statements of work completed, judgments formed, and remaining limits.
- Use plain, compact Chinese. Avoid inflated wording.
- If a statement is inferred from timestamps or project context rather than explicitly recorded, label it as `推断`.
- Do not expose secret, token, account, env, login, QR-code, or CodexBridge Weixin account details.

## Project File Invariants

Project Markdown files must be UTF-8 without BOM. The YAML front matter must be a real multi-line block: the opening `---` and closing `---` each appear alone on their own line, and every metadata field is on its own line.

Never compress front matter into one line such as `--- title: ... status: ... ---`. If a dashboard card title falls back to the file slug or its summary starts with `--- title:`, the project file front matter was not parsed; fix the Markdown source first, then rebuild the dashboard.

## Start Protocol

Before doing substantive research work:

1. Identify the relevant research project from the user request, current files, or existing dashboard entries.
2. Read `research-dashboard/index.html` for a quick overview, or read the matching `projects/*.md` file for complete context.
3. If no matching project exists, create one from `projects/_template.md` with a short English slug and a Chinese front-matter `title`.
   Exception: if DD has already designated a merged/shared topic for this work, update that existing project instead of creating a new one.
4. Check current problems, next steps, maintained files, and key notes before making research decisions.
5. If starting a new thread of work, add or refine one concise current-problem item so the dashboard reflects why this session exists.

## End Protocol

Before finishing a research turn:

1. Set `updated` to the current local date and minute, formatted as `YYYY-MM-DD HH:MM`.
2. Move or copy solved blockers into the solved section as `- [x] ~~problem~~ (YYYY-MM-DD)`.
3. Keep unresolved blockers in the current-problems section as unchecked items.
4. Rewrite the next-steps section into concrete actions a later agent can execute.
5. Update the maintained-files section with files read, edited, generated, or requiring follow-up.
6. Append the key-notes section with dated research judgments, experiment outcomes, failed attempts, handoff notes, or a compact DD Material Passport when the task touched code, experiments, figures, manuscript claims, or submission packaging. Prefer records that can be reused in a daily report: what changed, what was learned, what remains unsupported, and what should happen next. Keep tool-only details out of key notes unless they affect the research claim or deliverable.
7. Verify the project file still starts with a parseable multi-line front matter block. Do not leave BOM or a one-line `--- title: ... ---` header.
8. Run the build command from `D:\ResearchManagement` so both `index.html` and `dashboard-data.json` are refreshed.
9. Mention in the final response that the dashboard was updated, or explain why it could not be updated.

## Project Selection

Use an existing project file when the topic, paper, experiment, dataset, or codebase clearly matches it. Create a new project only when the work is a distinct research direction or no existing entry can reasonably hold the context.

When DD has previously merged several subtopics, agents, or deliverables into one dashboard theme, treat that merge decision as binding unless DD later changes it. Do not split the topic again just because the current task emphasizes one sub-area.

If unsure whether to create a new project, prefer adding a short note to the closest existing project and ask DD in the final response whether it should be split later.

## Archiving Protocol

When marking a project as `archived`, first inspect `当前问题` and `下一步计划`. Move completed or now-solved items into `已解决` with the date. Remove obsolete, conditional, or out-of-scope future items from active checklists, preserving any useful context as `关键记录` instead. Do not leave unchecked items in an archived project unless they are explicitly documented as an external unresolved blocker; if meaningful work remains, use `paused` rather than `archived`.

## Safety

Do not delete dashboard history to make entries shorter. Mark stale work as `paused` or `archived`, and preserve the reason in key notes.

Do not delete folders. If a generated cache or process file must be removed, delete only that individual file after confirming it is safe and necessary.
