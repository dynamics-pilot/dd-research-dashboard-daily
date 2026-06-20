# Agent Dashboard Guide

在本工作区做科研任务时，请维护 `research-dashboard`。

如果 `$maintain-research-dashboard` 出现在可用 skills 中，先使用该 skill。它定义了 dashboard 的项目文件接口、开始检查和结束检查。

## 每次开始前

1. 查看 `research-dashboard/index.html` 或对应的 `projects/*.md`。
2. 确认当前任务属于哪个研究项目。
3. 如果没有对应项目，从 `projects/_template.md` 新建一个 Markdown 文件；文件名用简短英文 slug，front matter 的 `title` 用中文研究题目。

## 每次结束前

更新对应项目文件：

- `updated`: 当前日期和分钟，格式为 `YYYY-MM-DD HH:MM`。
- `当前问题`: 还没解决、会阻塞后续工作的事项。
- `已解决`: 已解决事项，写成 `- [x] ~~问题~~ (YYYY-MM-DD)`。
- `下一步计划`: 后续 agent 或用户可以直接执行的动作。
- `维护文件`: 本轮读过、改过、生成或需要继续维护的关键文件。
- `关键记录`: 实验结论、判断依据、失败尝试、重要上下文。

确认项目 Markdown 仍然使用可解析的 front matter：

- 文件保存为 UTF-8 无 BOM。
- 第一行必须只有 `---`。
- 结束 front matter 的 `---` 必须单独占一行。
- `title`、`status`、`priority`、`owner`、`updated`、`tags`、`summary` 等字段必须各占一行。
- 不要写成 `--- title: ... status: ... summary: ... ---` 这一类单行头部。

然后运行：

```powershell
python .\research-dashboard\tools\build_dashboard.py
```

## 约束

- 新建项目和 dashboard 可见标题默认写中文；专业词汇、缩写和软件名可保留英文，例如 UAV、iLQR、MATLAB；文件 slug 和路径仍保持简短英文/ASCII。
- 不要为了让 dashboard 变短而删除历史记录。
- 已解决的问题请划掉或移动到 `已解决`。
- 不确定是否删除时，先问用户。
- 不要删除整个文件夹；如确需删除文件，也必须逐个文件处理并确认必要性。
