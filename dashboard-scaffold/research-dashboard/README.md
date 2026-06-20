# Research Dashboard

这个目录用于管理多个科研任务的进展。核心原则是：每个研究任务维护一个 Markdown 文件，网页 `index.html` 由脚本自动汇总生成。

本机已创建全局 skill：

```text
%USERPROFILE%\.codex\skills\maintain-research-dashboard
```

后续 agent 做科研任务前后应使用 `$maintain-research-dashboard`，按该 skill 的开始/结束协议读取和更新本 dashboard。

## 快速使用

打开网页：

```text
D:\ResearchManagement\research-dashboard\index.html
```

重新生成网页：

```powershell
python .\research-dashboard\tools\build_dashboard.py
```

生成脚本会同时写入 `index.html` 和 `dashboard-data.json`。网页会每 5 秒尝试读取 `dashboard-data.json`，只更新变化的项目卡片；发生变化的卡片会显示浅色提示。点击卡片后，当前浏览器会把该项目标记为已读并清除提示色。

## 新建研究任务

1. 复制模板 `projects/_template.md`。
2. 改名为简短英文 slug，例如 `uav-task-allocation.md`。
3. 填写 front matter，`title` 默认使用中文研究题目，专业英文术语可以保留：

   ```yaml
   ---
   title: 中文研究题目
   status: active
   priority: medium
   owner: DD + Codex
   order:
   updated: 2026-05-15 16:58
   tags: [UAV, planning]
   summary: 一句话说明这个研究正在解决什么。
   ---
   ```

4. 填写各章节：当前问题、已解决、下一步计划、维护文件、关键记录。
5. 运行生成脚本。

## 推荐维护习惯

- 新建项目、任务和 dashboard 可见标题默认用中文；专业词汇、缩写和软件名可保留英文，例如 UAV、iLQR、MATLAB；文件 slug、路径和任务 ID 仍保持简短英文/ASCII。
- 当前仍然阻塞研究的问题放在 `当前问题`。
- `updated` 精确到分钟，推荐格式为 `YYYY-MM-DD HH:MM`。
- 解决掉的问题移动或复制到 `已解决`，并写成 `- [x] ~~问题~~ (YYYY-MM-DD)`。
- 下一步计划只保留可执行动作，避免写成泛泛的愿望。
- 维护文件记录 agent 实际改动或重点阅读的文件，便于后续接手。
- 关键记录保留研究判断、实验结论、失败尝试和重要分歧，不要只记录代码动作。
- 网页的 `排列方式` 默认使用 `自定义顺序`，可直接拖拽项目改变顺序，结果保存在当前浏览器；新增项目会追加到后面。也可以临时切换到 `按更新时间`，查看最近更新的项目。若要让生成脚本的默认顺序永久生效，在项目 front matter 写 `order: 10`、`order: 20` 这类数字。
- 不确定是否删除时，不删。过期任务可以把 `status` 改为 `paused` 或 `archived`。

## 文件结构

```text
research-dashboard/
  index.html                  # 自动生成的可视化网页
  dashboard-data.json         # 自动生成的页面增量刷新数据
  README.md                   # 使用说明
  AGENT_DASHBOARD_GUIDE.md    # 给后续 agent 的简短维护约定
  projects/
    _template.md              # 新研究模板
    *.md                      # 每个研究一个文件
  tools/
    build_dashboard.py        # 静态网页生成脚本
```

## 状态字段

- `active`: 正在推进。
- `paused`: 暂停，但未来可能继续。
- `waiting`: 等待外部信息、实验结果或人工确认。
- `archived`: 已归档，不再主动推进。
