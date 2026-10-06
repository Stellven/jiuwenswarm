# Run the accepted Codex subscription browser demo

This guide describes the Windows demo accepted by Xiaoyang on 2026-09-28. It covers personal sign-in, ordinary text chat, streaming, stop, and saved application history. Advanced tools, teams, memory/retrieval, and media are still being integrated; this is not whole-project acceptance.

## 1. On Xiaoyang's already configured computer

If http://localhost:5173 is already open and working, use that instance. Do not start a second copy.

Otherwise, open PowerShell and run:

```powershell
Set-Location 'D:\research\ai_for_research\jiuwenswarm'
.\Start-Codex.cmd
```

Keep the terminal open. After startup, open **http://localhost:5173** in your browser. The equivalent command, from the repository root, is:

```powershell
.\.venv\Scripts\python.exe -m jiuwenswarm.codex_start all
```

## 2. First setup on another Windows computer

Prerequisites: Git with Git LFS, Python 3.11, Node.js 22 with npm, uv, and your own account with working Codex subscription access. The verified versions are Python 3.11.3, Node 22.23.3, npm 10.9.9 and setup uv 0.12.19. See [environment evidence](../../../governance/ENVIRONMENT.md). Spec Kit is for development and is not required merely to run the demo.

From a parent directory that does not already contain a `jiuwenswarm` folder:

```powershell
git lfs install
git clone --branch ai4r_main_branch https://github.com/Stellven/jiuwenswarm.git
Set-Location jiuwenswarm
git lfs pull
uv sync --locked --python 3.11 --extra codex --group test
Push-Location jiuwenswarm/channels/web/frontend
npm.cmd ci --no-audit --no-fund
npm.cmd run build
Pop-Location
.\Start-Codex.cmd
```

Run each command successfully before continuing. This launcher serves the built frontend, so **the frontend build is required**. Running only `npm run dev` does not start the application backend. The locked `codex` extra supplies the application's Codex runtime; a separately installed IDE Codex does not replace it.

For an existing clean checkout, first switch to `ai4r_main_branch` (or your assigned `ai4r_xiaoyang`, `ai4r_saurav`, `ai4r_ramika`, or `ai4r_muk` branch), run `git pull --ff-only`, then repeat the dependency/build steps. Preserve any local edits before switching. Do not use a hard reset to update a working checkout.

## 3. Browser demonstration

1. Open **http://localhost:5173** and locate the Codex subscription panel.
2. Click **Sign in with ChatGPT / 使用 ChatGPT 登录**, open the provided sign-in link, and finish signing in with your own account. Return to the app and wait for the ready state. Do not enter a model-provider API key.
3. Create a new conversation, choose an available model if requested, and send: `Reply with exactly: Subscription chat works.` Confirm that the response appears.
4. Send: `Write 200 short numbered sentences about gardening.` While the response is streaming, press **Stop**. Confirm that output stops and the partial response remains visible. If it finishes too quickly, request a longer response and repeat.
5. Refresh the browser, open the same conversation, and confirm that the previous messages remain visible.
6. Create a separate conversation for a new conversation context. Another message in the same conversation continues its Codex thread.

## 4. Stopping, restarting, and local data

- Stop the services with **Ctrl+C in the launcher terminal**. Closing the browser alone does not stop the backend.
- Start again with `Start-Codex.cmd`. The application uses `%USERPROFILE%\.jiuwenswarm-ai4r` for this preview. It does not import your previous installation's profile.
- Each person signs in locally. Do not share or commit that profile, authentication files, or sign-in links.
- Browser refresh preserves application history. A full backend restart or account switch currently requires a **new conversation for further generation**; old history remains available. This restart-continuation limitation is tracked in AI4R-001.

## 5. Troubleshooting

| Symptom | Action |
| --- | --- |
| Browser cannot connect | Keep the launcher terminal open, inspect its startup errors, and use the printed Web UI URL. Default ports are 5173 (Web), 19000 (Gateway WebSocket), 19001 (Gateway HTTP), and 18092 (AgentServer). |
| Port already in use / profile ownership error | Reuse the existing running instance or stop its launcher before starting another. Do not delete profile files to bypass ownership. |
| Old interface or no subscription panel | Stop the app, run `npm.cmd run build` in the frontend directory, restart with the subscription launcher, and refresh the browser. |
| Login not ready or subscription unavailable | Complete the login flow on this computer and check the displayed account/network error. No API-key fallback is used. |
| `NEW_SESSION_REQUIRED` after restarting or changing accounts | Create a new conversation. Existing history is retained. |
| `.venv` or Codex runtime missing | Repeat `uv sync --locked --python 3.11 --extra codex --group test` from the repository root. |
| Native Node 20 test/setup problems | Use the verified Node 22 environment described in ENVIRONMENT. |

Verification and remaining scope: [TEST_REPORT](TEST_REPORT.md), [handoff](HANDOFF.md), and [current status](../../../governance/CURRENT_STATUS.md).
