# Agent Handoff: Research Dashboard and Daily Report

This file is for the receiving Codex agent.

## Goal

Install a local research dashboard, the matching Codex skill, and a daily email-report workflow equivalent in behavior to DD's current setup, but using the receiving machine's paths, sender email account, and automation id.

## Step 1: Install

From PowerShell:

```powershell
cd D:\path\to\dd-dashboard-daily-package-20260617
.\install_dashboard_daily.ps1 -ResearchRoot "D:\ResearchManagement"
```

Use another `-ResearchRoot` if the user wants a different location.

The installer copies:

- skill to `%USERPROFILE%\.codex\skills\maintain-research-dashboard`
- dashboard scaffold to `<ResearchRoot>\research-dashboard`
- SMTP template to `<ResearchRoot>\research-dashboard\config\smtp-mail.local.json` if no local config exists

It also rewrites default paths in installed text files to the selected `ResearchRoot`.

## Step 2: Verify Installation

Check these files:

```text
%USERPROFILE%\.codex\skills\maintain-research-dashboard\SKILL.md
<ResearchRoot>\research-dashboard\README.md
<ResearchRoot>\research-dashboard\DAILY_REPORT_GUIDE.md
<ResearchRoot>\research-dashboard\projects\_template.md
<ResearchRoot>\research-dashboard\tools\build_dashboard.py
<ResearchRoot>\research-dashboard\tools\send_dashboard_email_smtp.py
```

Use UTF-8 when reading and writing Markdown/JSON files. If Chinese display looks wrong in a terminal, do not assume the file is corrupt until it has been read explicitly as UTF-8.

When printing Windows paths in the conversation, wrap them in backticks or fenced code blocks so `\` is not lost or interpreted as an escape character.

## Step 3: Build The Empty Dashboard

```powershell
cd <ResearchRoot>
python .\research-dashboard\tools\build_dashboard.py
```

Expected outputs:

```text
<ResearchRoot>\research-dashboard\index.html
<ResearchRoot>\research-dashboard\dashboard-data.json
```

## Step 4: Configure SMTP

Edit:

```text
<ResearchRoot>\research-dashboard\config\smtp-mail.local.json
```

Set the receiving machine's sender account:

- `smtp_host`
- `smtp_port`
- `smtp_security`
- `smtp_user`
- `from_email`
- `from_name`
- `to_email`
- `secret_file`

The other user should use their own sender email account. If the goal is to send reports to DD, set `to_email` to DD's receiving email. Do not copy DD's SMTP secret.

Create the encrypted secret on the receiving machine:

```powershell
cd <ResearchRoot>
python .\research-dashboard\tools\set_smtp_secret.py --secret-file .\research-dashboard\config\smtp-mail.secret
```

Then set `"enabled": true` in `smtp-mail.local.json`.

Before SMTP is configured, running the sender should stop with `SMTP config is disabled`; that is expected.

## Step 5: Create First Project

Copy:

```text
<ResearchRoot>\research-dashboard\projects\_template.md
```

to a short ASCII slug, for example:

```text
<ResearchRoot>\research-dashboard\projects\my-project.md
```

Keep front matter multi-line and UTF-8. Do not use one-line YAML front matter.

## Step 6: Test Daily Report Manually

Create:

```text
<ResearchRoot>\research-dashboard\daily-reports\YYYY-MM-DD.md
```

with a body matching `DAILY_REPORT_GUIDE.md`, then send:

```powershell
cd <ResearchRoot>
python .\research-dashboard\tools\send_dashboard_email_smtp.py --date YYYY-MM-DD
```

Only enable automation after manual sending works.

## Step 7: Create Daily Automation

Read:

```text
automation-template\daily-report-automation.md
```

Create a local Codex automation:

- name: `科研 dashboard 日报邮件`
- schedule: every day at 17:50 local time
- workspace: `<ResearchRoot>`
- prompt: use the template and replace placeholders

Do not copy another user's automation id, thread id, local paths, email account, or SMTP secret.

## Operational Rules

- Dashboard project files must be UTF-8. Prefer UTF-8 without BOM for generated Markdown/JSON.
- Do not expose tokens, secrets, login files, QR codes, env files, or account caches.
- Do not delete dashboard history.
- Do not delete folders. If cleanup is needed, delete individual generated files only after confirming they are safe to remove.
- Daily reports should summarize research progress, judgments, and limitations, not tool logs.
