from __future__ import annotations

import argparse
import json
import re
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from smtp_secret_dpapi import unprotect_text

WORKSPACE_ROOT = Path(r"D:\ResearchManagement")
DASHBOARD_ROOT = WORKSPACE_ROOT / "research-dashboard"
CONFIG_PATH = DASHBOARD_ROOT / "config" / "smtp-mail.local.json"


def load_config() -> dict:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not config.get("enabled", False):
        raise RuntimeError(
            f"SMTP config is disabled in {CONFIG_PATH}. "
            "Set enabled=true after replacing placeholder credentials."
        )
    secret_path = Path(config["secret_file"])
    if not secret_path.exists():
        raise RuntimeError(
            f"Encrypted SMTP secret file not found: {secret_path}. "
            "Create it first with set_smtp_secret.py."
        )
    config["smtp_password"] = unprotect_text(secret_path.read_text(encoding="ascii").strip())
    return config


def read_report(report_date: str) -> str:
    report_path = DASHBOARD_ROOT / "daily-reports" / f"{report_date}.md"
    return report_path.read_text(encoding="utf-8")


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def compact_display_title(title: str, max_units: int = 18) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    units = 0
    kept: list[str] = []
    for char in title:
        units += 1 if ord(char) < 128 else 2
        if units > max_units:
            return "".join(kept).rstrip(" ，,、-") + "..."
        kept.append(char)
    return title


def parse_report(body_text: str) -> dict:
    lines = [line.strip() for line in body_text.splitlines()]
    nonempty = [line for line in lines if line]
    if len(nonempty) < 4:
        raise RuntimeError("Report body is too short to render as dashboard email.")

    project_items: list[tuple[str, str]] = []
    signature = nonempty[-1]
    detail_started = False

    for line in nonempty[3:-1]:
        if line == "细则：":
            detail_started = True
            continue
        if not detail_started:
            continue
        matched = re.match(r"^(\d+)：\s*【(.+?)】\s*(.+)$", line)
        if matched:
            _idx, title, content = matched.groups()
            project_items.append((title, content))

    return {
        "update_count": nonempty[0],
        "active_count": nonempty[1],
        "main_summary": nonempty[2],
        "items": project_items,
        "signature": signature,
    }


def build_focus_block(summary: str) -> str:
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="background:#fffdf9;border:1px solid #e7ddd0;">'
        "<tr>"
        '<td style="padding:16px 20px 6px 20px;font-family:Arial,'
        '\'Microsoft YaHei\',sans-serif;font-size:12px;line-height:1.4;'
        'letter-spacing:1px;text-transform:uppercase;color:#8f6b32;">'
        "Main Focus</td>"
        "</tr>"
        "<tr>"
        '<td style="padding:0 20px 18px 20px;font-family:Arial,'
        '\'Microsoft YaHei\',sans-serif;font-size:18px;line-height:1.95;'
        'color:#26313d;word-break:normal;overflow-wrap:normal;line-break:strict;">'
        f"{escape_html(summary)}</td>"
        "</tr>"
        "</table>"
    )


def build_project_card(index: int, title: str, content: str, accent: str) -> str:
    display_title = compact_display_title(title)
    return f"""
      <tr>
        <td style="padding:0 0 18px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
            style="background:#ffffff;border:1px solid #e7ddd0;border-collapse:separate;">
            <tr>
              <td style="width:7px;background:{accent};font-size:0;line-height:0;">&nbsp;</td>
              <td style="padding:18px 20px 6px 20px;font-family:Georgia,'Times New Roman',serif;font-size:26px;line-height:1.18;color:#18212b;font-weight:700;">
                {index}：{escape_html(f"【{display_title}】")}
              </td>
            </tr>
            <tr>
              <td style="width:7px;background:{accent};font-size:0;line-height:0;">&nbsp;</td>
              <td style="padding:0 20px 20px 20px;font-family:Arial,'Microsoft YaHei',sans-serif;font-size:16px;line-height:2.0;color:#475467;word-break:normal;overflow-wrap:normal;line-break:strict;">
                {escape_html(content)}
              </td>
            </tr>
          </table>
        </td>
      </tr>"""


def build_html(subject: str, body_text: str) -> str:
    report = parse_report(body_text)
    update_value = report["update_count"].split("：", 1)[-1]
    main_summary = report["main_summary"].split("：", 1)[-1].strip()
    signature = report["signature"]
    body_signature = "" if signature == "邸伟承" else signature
    signature_row = ""
    if body_signature:
        signature_row = (
            '<tr><td style="padding:4px 30px 30px 30px;'
            "font-family:Arial,'Microsoft YaHei',sans-serif;"
            'font-size:22px;line-height:1.5;color:#18212b;">'
            f"{escape_html(body_signature)}</td></tr>"
        )

    accents = ["#1f4b8f", "#c96f1a", "#0f766e", "#b42318"]
    item_blocks = []
    for idx, (title, content) in enumerate(report["items"], start=1):
        item_blocks.append(build_project_card(idx, title, content, accents[(idx - 1) % len(accents)]))

    items_html = "\n".join(item_blocks)

    return f"""<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#efe7db;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#efe7db;">
      <tr>
        <td align="center" style="padding:28px 10px 40px 10px;">
          <table role="presentation" width="760" cellspacing="0" cellpadding="0" style="width:760px;max-width:760px;background:#f7f2ea;border:1px solid #ddcfbf;">
            <tr>
              <td style="background:#173f73;padding:0;">
                <div style="height:10px;background:#d9852f;font-size:0;line-height:0;">&nbsp;</div>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="padding:24px 34px 22px 34px;">
                      <div style="font-family:Arial,'Microsoft YaHei',sans-serif;font-size:12px;line-height:1.4;letter-spacing:1.6px;text-transform:uppercase;color:#d7e6fb;">Research Dashboard</div>
                      <div style="padding-top:8px;font-family:Georgia,'Times New Roman',serif;font-size:46px;line-height:1.04;color:#ffffff;font-weight:700;">科研管理</div>
                    </td>
                    <td style="padding:24px 34px 22px 0;vertical-align:top;text-align:right;">
                      <div style="display:inline-block;background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.22);padding:10px 14px 9px 14px;">
                        <div style="font-family:Arial,'Microsoft YaHei',sans-serif;font-size:11px;line-height:1.2;letter-spacing:1.2px;text-transform:uppercase;color:#dbeafe;">Updated</div>
                        <div style="padding-top:6px;font-family:Georgia,'Times New Roman',serif;font-size:30px;line-height:1;color:#ffffff;">{escape_html(update_value)}</div>
                      </div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 30px 6px 30px;">
                {build_focus_block(main_summary)}
              </td>
            </tr>
            <tr>
              <td style="padding:22px 30px 0 30px;font-family:Georgia,'Times New Roman',serif;font-size:34px;line-height:1.1;color:#18212b;font-weight:700;">
                细则
              </td>
            </tr>
            <tr>
              <td style="padding:18px 30px 8px 30px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                  {items_html}
                </table>
              </td>
            </tr>
            {signature_row}
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_email(report_date: str) -> None:
    config = load_config()
    body_text = read_report(report_date)
    subject = f'{config.get("subject_prefix", "")}{report_date} 科研日报'
    html = build_html(subject, body_text)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = formataddr((str(Header(config["from_name"], "utf-8")), config["from_email"]))
    msg["To"] = config["to_email"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=config["from_email"].split("@", 1)[-1])
    if config.get("reply_to"):
        msg["Reply-To"] = config["reply_to"]
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    security = config.get("smtp_security", "ssl").lower()
    if security == "ssl":
        with smtplib.SMTP_SSL(
            config["smtp_host"], int(config["smtp_port"]), timeout=30
        ) as server:
            server.login(config["smtp_user"], config["smtp_password"])
            server.sendmail(config["from_email"], [config["to_email"]], msg.as_string())
    elif security == "starttls":
        with smtplib.SMTP(
            config["smtp_host"], int(config["smtp_port"]), timeout=30
        ) as server:
            server.starttls()
            server.login(config["smtp_user"], config["smtp_password"])
            server.sendmail(config["from_email"], [config["to_email"]], msg.as_string())
    else:
        raise RuntimeError(f"Unsupported smtp_security: {security}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD")
    args = parser.parse_args()
    send_email(args.date)


if __name__ == "__main__":
    main()
