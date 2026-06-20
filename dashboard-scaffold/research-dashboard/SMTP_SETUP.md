# SMTP 邮件发送本地配置

这套配置用于让日报邮件改走本地 SMTP，而不是 Gmail connector。

## 文件

- `research-dashboard/config/smtp-mail.local.json`
- `research-dashboard/config/smtp-mail.secret`
- `research-dashboard/tools/set_smtp_secret.py`
- `research-dashboard/tools/send_dashboard_email_smtp.py`
- `research-dashboard/tools/smtp_secret_dpapi.py`

## 安全模式

这里不再把 SMTP 授权码以明文写进配置文件。

改用 Windows 当前用户的 `DPAPI` 做本机加密：

- 磁盘上保存的是密文
- 只有当前 Windows 用户可解密
- 发信脚本只在内存中解密
- 不打印、不回写、不记录明文

## 初始化

1. 检查 `smtp-mail.local.json` 里的邮箱地址、收件人和服务器参数。
2. 运行：

```powershell
python .\research-dashboard\tools\set_smtp_secret.py --secret-file .\research-dashboard\config\smtp-mail.secret
```

3. 按提示输入新的 SMTP 授权码两次。
4. 把 `smtp-mail.local.json` 里的 `enabled` 改成 `true`。

## 更换授权码

再次运行同一个命令即可覆盖密文文件：

```powershell
python .\research-dashboard\tools\set_smtp_secret.py --secret-file .\research-dashboard\config\smtp-mail.secret
```

## 发送方式

发送脚本会构造标准 MIME 邮件：

- `text/plain`
- `text/html`

这样三星邮箱会把它当作真正的 HTML 邮件渲染，而不是把 HTML 源码显示出来。

## 备注

- 当前默认服务器按 163 SSL 配置写成 `smtp.163.com:465`。
- 如果后续改成其他邮箱，只需要修改 `smtp-mail.local.json`。
- `smtp-mail.secret` 不建议进压缩包、模板包或版本管理。
