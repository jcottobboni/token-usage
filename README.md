# token-usage

**English** · [Português](README.pt-BR.md)

A local dashboard that shows how many tokens you spent on terminal AI coding agents and how much of each plan's quota is left.

- **A single Python file**, standard library only. No `pip install`, no build step. The optional tray icon needs two packages.
- **100% local**: it reads the files the tools already write to your disk. The server listens only on `127.0.0.1`, and the page loads nothing from the internet.
- **Shows only what you use**: tools that are not installed do not appear in the UI.

## Supported tools

| Tool | Token history | Remaining quota |
|---|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` | Claude Code OAuth API (fallback: cache in `~/.claude.json`) |
| GitHub Copilot CLI | `~/.copilot/session-store.db` | GitHub API via `gh auth token` (fallback: `~/.copilot/session-state`) |
| OpenAI Codex CLI | `~/.codex/sessions/**/rollout-*.jsonl` (honors `CODEX_HOME`) | ChatGPT API used by `/status` (fallback: last `rate_limits` saved in the rollouts) |
| Gemini CLI | `~/.gemini/tmp/*/chats/*.json` and `*.jsonl` | — |
| Google Antigravity | Antigravity CLI (`agy`): `~/.gemini/antigravity-cli/conversations/*.db`. The app does not store conversations in a readable format | Antigravity's local language server, only while the app is open (`agy` keeps its token in memory, so no quota for the CLI) |

What the dashboard shows:

- **Remaining quota** for each window (5-hour session, weekly, monthly premium requests, per-model Antigravity quota), with time until reset.
- **Usage** per day, model, tool and project (working directory), split into fresh input, output, cache read and cache write.

## Requirements

- Python 3.10+
- Linux, macOS or Windows. The Antigravity quota relies on `/proc` and `ss`, so it works on Linux only.
- Optional: an authenticated [`gh`](https://cli.github.com/) for the live Copilot quota.
- On macOS, Claude Code stores its token in the Keychain. In that case, the Claude quota comes from the last value saved in `~/.claude.json`.

## Usage

```bash
git clone https://github.com/leoalmeidasa/token-usage.git
cd token-usage
python3 server.py --open
```

It opens at <http://127.0.0.1:8777/>. To use another port: `TOKEN_USAGE_PORT=9000 python3 server.py`.

The page refreshes by itself every 60 s (quotas every 30 s).

On Windows, run `py server.py --open` in PowerShell. The `~/.claude`, `~/.copilot` etc. folders live in `%USERPROFILE%`.

### Run as a service (systemd, user)

```bash
mkdir -p ~/.config/systemd/user
cp contrib/token-usage.service ~/.config/systemd/user/
# edit ExecStart if the repository is not at ~/token-usage
systemctl --user daemon-reload
systemctl --user enable --now token-usage
```

### Start with Windows

Create a shortcut in the startup folder (`Win+R` → `shell:startup`) with the target below. `pythonw` runs without opening a window.

```
pythonw.exe C:\path\to\token-usage\server.py
```

### Top bar / system tray icon (optional)

`tray.py` adds an icon to the top bar (GNOME, KDE), the Windows notification area or the macOS menu bar. The ring shows the lowest remaining quota across all tools. Clicking it opens a menu with each quota, today's and this month's tokens per tool, and **Open detailed dashboard**. If `server.py` is not running, the icon starts it in the same process.

It needs `pystray` and Pillow. On Linux it also needs PyGObject with AppIndicator; on GNOME, enable the AppIndicator extension (already on by default in Ubuntu).

```bash
# Linux (Ubuntu/Debian)
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-tray.txt
.venv/bin/python tray.py

# start with the session
cp contrib/token-usage-tray.desktop ~/.config/autostart/
```

On Windows and macOS: `pip install -r requirements-tray.txt` and run `pythonw tray.py` (Windows) or `python3 tray.py` (macOS). On Windows, right-click the icon for the menu; left-click opens the dashboard.

## How the numbers are computed

- **Fresh input** excludes cache. Copilot, Codex and Gemini report input with cache included; the dashboard subtracts it so the numbers match Claude's.
- **Output** for Gemini adds the reasoning tokens (`thoughts`). In Codex, `output_tokens` already includes reasoning.
- **Duplicates** are removed: Claude Code writes several lines per response, resumed sessions repeat messages, and Codex repeats `token_count` events.
- **Copilot premium** counts only user-initiated turns in Copilot CLI. The monthly quota also includes IDE and web usage.

## Privacy and security

- No usage data leaves your machine. The only outbound requests are the quota checks. They go to the same endpoints each tool already uses, with the credentials the tool already stored:
  - `api.anthropic.com` (Claude Code)
  - `api.github.com` (Copilot)
  - `chatgpt.com` (Codex)

  The dashboard only queries tools that are installed.
- Credentials are read on each check. They are never copied, logged or returned by the local API.
- The server:
  - listens only on `127.0.0.1` and rejects requests whose `Host` is not `127.0.0.1`/`localhost` (DNS rebinding protection);
  - sends a strict `Content-Security-Policy`, `X-Frame-Options: DENY` and `nosniff`;
  - escapes all text that comes from disk or network before putting it into the HTML.
- Any local process running as your user can read `/api/usage`, which includes project paths. Do not expose the port to the network (for example, through a reverse proxy or `ssh -R`).
- The quota endpoints are **not documented public APIs**. They can change without notice; if they do, the dashboard falls back to the last value saved locally. Use at your own risk and check each service's terms of use.

## Limitations

- Codex, Gemini and Antigravity support is based on the known file formats of those tools. If a new version changes the format, open an issue with an anonymized snippet of the file.
- macOS and Windows support follows the tools' default paths, but it was tested on Linux only.
- Older Gemini CLI versions store only a hash of the project path; such projects show up as `gemini:<hash>`.
- The Antigravity app does not store tokens in a readable format, so only its quota is shown. The Antigravity CLI (`agy`) stores one protobuf per response in SQLite; the dashboard decodes the usage fields without a schema (same `ModelUsageStats` layout as the Windsurf/Codeium language server), so a new `agy` version may break it. The project comes from `history.jsonl`; conversations not listed there show up as `antigravity:<agy project>`.

## License

[MIT](LICENSE). Chart.js 4.4.1 (MIT) is bundled in `vendor/`. See `vendor/LICENSE-chartjs.md`.
