# AI Game Studio Coordination Hub

This starter makes a shared, authenticated MCP server that gives two Codex sessions (or API-managed Codex agents) shared tools for task assignment, inbox messages, and status tracking. Game files are still shared through GitHub; the hub does not synchronize source files itself.

## Architecture

- Supabase Postgres stores tasks and messages.
- Render hosts this remote MCP server at `https://YOUR-SERVICE.onrender.com/mcp/`.
- Both Codex clients connect to that one MCP endpoint.
- GitHub branches/pull requests keep code changes separate and mergeable.
- OpenAI Agents API sessions can use the same MCP endpoint with an API key (optional advanced step).

## 1. Create the database

1. Create a project at https://supabase.com/.
2. Open **SQL Editor** in that project.
3. Create a new query, paste all of `schema.sql`, and click **Run**.
4. Open **Project Settings → API** (or **Data API**, depending on the current dashboard layout). Copy the Project URL and the `service_role` / secret API key. The service-role key bypasses row-level security, so it must only be stored as a secret in Render. Never put it in GitHub, Codex config, or this project's files.

## 2. Create a private GitHub repo and deploy the server

1. Create a **private** GitHub repository named `ai-game-studio-coordinator`.
2. Add this folder's files to that repository and push them.
3. In Render, choose **New → Web Service**, connect the private repository, and select the branch.
4. Use these settings:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `python server.py`
   - Health check path: `/health` (if Render asks for one)
5. Add these Environment Variables in Render:
   - `SUPABASE_URL` = the Supabase Project URL
   - `SUPABASE_SERVICE_ROLE_KEY` = the Supabase service-role/secret key
   - `MCP_ACCESS_TOKEN` = a long random secret (generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
6. Deploy. Save the Render HTTPS service URL, e.g. `https://ai-game-studio-coordinator.onrender.com`.
7. Open `https://YOUR-SERVICE.onrender.com/health` to confirm the server is running. The MCP endpoint is `https://YOUR-SERVICE.onrender.com/mcp/`.

Keep Render and Supabase secrets private. Anyone with the MCP token can read and write the shared studio tasks and messages. Render's free service may sleep when inactive; its first request after inactivity can take longer. Supabase holds the actual persistent data.

## 3. Connect your Codex app to the shared MCP server

Codex uses a TOML config. On Windows, the user-level file is normally `%USERPROFILE%\.codex\config.toml`.

1. In Windows, open Start and search for **Environment Variables**.
2. Open **Edit environment variables for your account**.
3. Under User variables, click **New**:
   - Name: `GAME_STUDIO_MCP_TOKEN`
   - Value: the same long token you set for `MCP_ACCESS_TOKEN` in Render
4. Save and completely restart Codex.
5. Open `%USERPROFILE%\.codex\config.toml` in Notepad (create it if it does not exist). Add:

```toml
[mcp_servers.game_studio]
url = "https://YOUR-SERVICE.onrender.com/mcp/"
bearer_token_env_var = "GAME_STUDIO_MCP_TOKEN"
required = false
```

Replace the sample URL with your real Render URL. Keep any existing config contents; do not replace the whole file.

If you have the Codex CLI installed, you can register the same connection from PowerShell after setting the environment variable:

```powershell
codex mcp add game_studio --url https://YOUR-SERVICE.onrender.com/mcp/ --bearer-token-env-var GAME_STUDIO_MCP_TOKEN
codex mcp list
```

6. Restart Codex. Open the MCP/server settings in Codex if available and verify `game_studio` is connected. If your Codex build doesn't accept remote URL entries in `config.toml`, use the Codex MCP settings/UI or check the current MCP setup guide: https://developers.openai.com/resources/docs-mcp . The config schema can change across Codex versions.
7. Ask Codex: `Use the game_studio MCP server to call ping and studio_status. Do not edit files yet.`

## 4. Connect your friend's Codex

Repeat the same process on your friend's PC. Use the same Render URL and the same value for `GAME_STUDIO_MCP_TOKEN`. In their environment, name their agent in prompts as `friend` (or choose a unique name and consistently use it).

For a small private project this shared-token approach is simple, but both people effectively have the same permissions. If you later need different permissions, use OAuth or separate per-user tokens and authorization.

## 5. Use the shared tools in Codex

The MCP server exposes these tools:

- `ping()` — verify connectivity.
- `create_task(title, description, created_by, assigned_to, priority)` — create a work item.
- `list_tasks(status, assigned_to, limit)` — inspect the queue.
- `claim_task(task_id, agent_name)` — claim an open task.
- `update_task(task_id, agent_name, status, result)` — finish or block a task.
- `send_message(sender, recipient, body, task_id)` — send a message.
- `read_messages(agent_name, after_id, limit)` — read messages for the agent and team-wide messages.
- `studio_status()` — see active work and recent messages.

Try these in your Codex chat:

**In your Codex (director):**

> Use game_studio. Call ping. Create a task called "Prototype core movement" assigned to Daan, with clear acceptance criteria. Send a team-wide message telling the other developer what you are doing. Then inspect the actual game repository and implement the task on your own Git branch. Before editing, list tasks and messages so you don't duplicate work.

**In your friend's Codex (developer/reviewer):**

> You are friend. Use game_studio to read the task list and your inbox. Claim an unassigned task or ask the director through send_message for one. Work on a separate Git branch. Do not edit files that Daan is actively changing. When finished, run the available tests, update the task to done or blocked, and send a concise summary to Daan.

## 6. Set up the codebase collaboration separately

The MCP hub stores coordination data; it does not sync game files. Create a separate private GitHub repository for the actual game. Each developer should:

1. Clone the game repository.
2. Make a feature branch, e.g. `agent/daan-movement` or `agent/friend-ui`.
3. Commit and push their changes.
4. Open a pull request.
5. Review and merge after tests pass.

Do not have both agents edit the same files at once. Ask them to reserve files in the shared task description and report filenames in their progress messages. Copy `AGENTS_GAME_PROJECT.md` into the actual game repository as `AGENTS.md` so Codex is reminded to use the coordination tools.

## 7. Optional: run an API-managed Codex-harness agent

The included `api_agent.py` connects an OpenAI-managed Codex-harness session to the same MCP message store. It can plan tasks, create queue items, and message your local Codex sessions. This is separate from ChatGPT subscriptions and is billed by API usage. Current official guides: [Agents API quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart) and [MCP connections](https://developers.openai.com/api/docs/guides/agents-api/tools/mcp).

1. Create an OpenAI API key at https://platform.openai.com/api-keys and make sure your project has access to the Agents API. The current quickstart requires Agents read/write and Responses write permissions.
2. In Command Prompt, from this folder, install the SDK: `py -m pip install openai`.
3. Set environment variables in that same Command Prompt session (replace values):

```bat
set "OPENAI_API_KEY=your_openai_api_key"
set "STUDIO_MCP_URL=https://YOUR-SERVICE.onrender.com/mcp/"
set "STUDIO_MCP_TOKEN=your_MCP_ACCESS_TOKEN"
set "OPENAI_MODEL=gpt-6-astra"
```

4. Run a manager agent: `py api_agent.py director "Create the first prototype sprint tasks and assign separate tasks to Daan and friend."`
5. Or run a separate review agent: `py api_agent.py critic "Review all active tasks and send the director the five biggest risks."`

This API-managed agent can use the shared task/message tools, but it does not share the live filesystem of either local Codex app. Its default hosted environment is separate. Use the local Codex apps for game-file edits, with GitHub branches for integration. For agents that themselves modify files in a persistent workspace, configure a self-hosted execution environment or an explicit GitHub-based workflow.

## Troubleshooting

- **401 / unauthorized:** check the Render `MCP_ACCESS_TOKEN` and the Windows `GAME_STUDIO_MCP_TOKEN` values match exactly, then restart Codex.
- **Cannot connect:** visit the Render service root first and check the deploy logs. Make sure you used the HTTPS URL and `/mcp/`.
- **MCP tool isn't visible:** restart Codex and open a new chat. Check the MCP configuration syntax for your installed version.
- **Database error:** re-run `schema.sql`; confirm `SUPABASE_URL` and the service-role key in Render are correct.
- **API key versus subscription:** using the local Codex app uses your Codex sign-in/metering; API-managed sessions use separate API billing.
- **One agent doesn't check messages:** the tool makes shared messages available, but it doesn't force an already-running chat to check continuously. Add an instruction to check `studio_status` and `read_messages` before each task and after each milestone.
