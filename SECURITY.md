# Security Notes

Do not commit local credentials or private dashboard data.

Never publish:

- `smtp-mail.secret`;
- `smtp-mail.local.json` with real account details;
- `.env` files;
- Codex automation ids or thread ids;
- generated daily reports;
- real project Markdown history from a private dashboard;
- account caches, browser profiles, login data, QR codes, or token usage summaries.

Before publishing a fork or derived package, run a conservative secret scan and inspect staged files manually.
