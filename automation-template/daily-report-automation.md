# Daily Report Automation Template

Create a daily Codex automation on the receiving machine after the dashboard and SMTP sender have been configured and tested.

Recommended schedule:

```text
Every day at 17:50 local time.
```

Recommended name:

```text
科研 dashboard 日报邮件
```

Workspace:

```text
<RESEARCH_MANAGEMENT_ROOT>
```

Use this prompt, replacing placeholders:

```text
生成科研 dashboard 日报，并发送给用户。

工作区：<RESEARCH_MANAGEMENT_ROOT>。

日报日期使用发送当天的本地日期 YYYY-MM-DD；统计范围为前一天 17:50 到当天 17:50。17:50 之后的工作计入下一天日报。如果前面连续若干日期没有成功发送日报，应检查 research-dashboard/daily-reports/YYYY-MM-DD.md 历史记录，并把缺失日期的 dashboard 进展合并到本次日报。

编码要求：所有 dashboard Markdown、JSON、日报文件一律按 UTF-8 读取和写入。不要根据 PowerShell 或终端中文显示效果判断文件是否乱码。如果项目文件不能按 UTF-8 解码，不要猜测内容，不要发送可能乱码的日报，应停止并说明风险。对话框中打印 Windows 路径时必须包在反引号或代码块中，避免 `\` 被转义或丢失。

发送前固定更新步骤：
1. 在工作区运行 `python .\research-dashboard\tools\update_codex_usage.py`，只读刷新本机可解析的 Codex/ZCode/Chatbox 用量统计。
2. 再运行 `python .\research-dashboard\tools\build_dashboard.py`，让 dashboard 页面和 dashboard-data.json 包含最新统计卡。
3. 这两步属于 dashboard 系统指标维护，不是科研成果；日报正文默认不要展开 token 数字，除非用户明确要求。

日报生成规则：
1. 先以 UTF-8 读取 `research-dashboard/DAILY_REPORT_GUIDE.md`，严格按其中默认邮件格式和写作口径生成日报。
2. 只读取 `research-dashboard/projects/*.md` 和 `research-dashboard/dashboard-data.json`。不要读取 `research-dashboard/tasks/requests/*.json`，除非用户后续明确要求日报包含任务队列。
3. 不 claim pending task，不修改任务 JSON 状态，不启动或恢复自动化服务。
4. 不读取、输出或暴露 token、secret、账号文件、env 文件、登录二维码或账号缓存内容。
5. 不删除文件，不清理缓存，不安装依赖。
6. 日报语言简单，重点写研究推进、结论、限制和下一步原因；不要把 LaTeX 编译、PDF 渲染、脚本运行、页面重建、Codex 用量刷新等工具动作写成研究成果。
7. 不要编造 dashboard 没有记录的进展。

输出格式：
1. 邮件主题必须是“YYYY-MM-DD 科研日报”。
2. 邮件正文不要写标题，不要写统计窗口，不要寒暄，不要附加数据来源、任务队列、工具日志或文件写入说明。
3. 正文第一行写“更新项目数：N”。第二行写“活跃项目数：N”。第三行写“主要内容：...”。
4. 后面写“细则：”，每个项目用 `1：【项目名】摘要内容` 的单段格式，只概括本日进展、得到的结论或限制。项目之间空一行。
5. 不要使用 Markdown 表格、真正编号列表或项目符号列表；开头的 `1：` 只是普通文本。不要在项目段落内部手动换行。
6. 不要写单独的“项目状态”小节，不要单列“下一步”。
7. 正文最后一行写发件人希望保留的署名，例如“科研助手”或真实姓名。
8. 正文源文本只负责内容；邮件 HTML 样式由现有发送脚本负责渲染，不要在正文里手写 HTML。

文件输出：
1. 将同一份正文以 UTF-8 写入 `<RESEARCH_MANAGEMENT_ROOT>\research-dashboard\daily-reports\YYYY-MM-DD.md`。若 daily-reports 目录不存在，可以创建该目录；除此之外不要创建无关文件。
2. 使用当前已配置的本地发送链路发送同一份正文。发送时直接调用 `research-dashboard/tools/send_dashboard_email_smtp.py --date YYYY-MM-DD`，不要临时改模板。
```

Do not copy another user's automation id, target thread id, email address, SMTP secret, local paths, or account configuration.
