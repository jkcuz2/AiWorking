"""Remote MCP server for coordinating two AI game developers.

Deploy this service on a web host and connect both Codex clients to /mcp.
Data lives in Supabase; credentials are supplied as environment variables.
"""

import os
from datetime import datetime, timezone
from typing import Literal

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from supabase import Client, create_client
from starlette.requests import Request
from starlette.responses import JSONResponse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
MCP_ACCESS_TOKEN = os.environ["MCP_ACCESS_TOKEN"]
PORT = int(os.environ.get("PORT", "8000"))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

auth = StaticTokenVerifier(
    tokens={
        MCP_ACCESS_TOKEN: {
            "client_id": "ai-game-studio",
            "scopes": ["studio:read", "studio:write"],
        }
    },
    required_scopes=["studio:read", "studio:write"],
)

mcp = FastMCP("AI Game Studio Coordinator", auth=auth, stateless_http=True)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "ai-game-studio-coordinator"})


VALID_STATUSES = {"open", "in_progress", "blocked", "done", "cancelled"}
VALID_PRIORITIES = {"low", "normal", "high", "critical"}


def _rows(response):
    return response.data or []


@mcp.tool

def ping() -> dict:
    """Check that the shared coordination server and database are reachable."""
    supabase.table("studio_tasks").select("id").limit(1).execute()
    return {"ok": True, "service": "ai-game-studio", "time_utc": datetime.now(timezone.utc).isoformat()}


@mcp.tool

def create_task(
    title: str,
    description: str,
    created_by: str,
    assigned_to: str = "unassigned",
    priority: str = "normal",
) -> dict:
    """Create a shared task for one of the developers. Priority: low, normal, high, critical."""
    if not title.strip() or not description.strip():
        raise ValueError("title and description cannot be empty")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
    payload = {
        "title": title.strip(),
        "description": description.strip(),
        "created_by": created_by.strip(),
        "assigned_to": assigned_to.strip() or "unassigned",
        "priority": priority,
        "status": "open",
    }
    rows = _rows(supabase.table("studio_tasks").insert(payload).execute())
    return rows[0] if rows else {"ok": True, "message": "Task created; refresh task list."}


@mcp.tool

def list_tasks(status: str = "open", assigned_to: str = "all", limit: int = 50) -> list[dict]:
    """List shared tasks. Use status='all' or assigned_to='all' to remove that filter."""
    if status != "all" and status not in VALID_STATUSES:
        raise ValueError(f"status must be 'all' or one of {sorted(VALID_STATUSES)}")
    limit = max(1, min(int(limit), 100))
    query = supabase.table("studio_tasks").select("*")
    if status != "all":
        query = query.eq("status", status)
    if assigned_to != "all":
        query = query.eq("assigned_to", assigned_to)
    result = query.order("created_at", desc=True).limit(limit).execute()
    return _rows(result)


@mcp.tool

def claim_task(task_id: str, agent_name: str) -> dict:
    """Claim an open task. Only one agent should succeed; work on your own branch after claiming."""
    now = datetime.now(timezone.utc).isoformat()
    result = supabase.table("studio_tasks").update({
        "status": "in_progress",
        "claimed_by": agent_name,
        "updated_at": now,
    }).eq("id", task_id).eq("status", "open").in_("assigned_to", ["unassigned", agent_name]).execute()
    rows = _rows(result)
    if not rows:
        return {"ok": False, "message": "Task was not open, does not exist, or is assigned to the other agent. Run list_tasks."}
    return {"ok": True, "task": rows[0]}


@mcp.tool

def update_task(
    task_id: str,
    agent_name: str,
    status: str,
    result: str,
) -> dict:
    """Update a task status and append a concise completion/blocker report in result."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    existing = _rows(supabase.table("studio_tasks").select("*").eq("id", task_id).limit(1).execute())
    if not existing:
        return {"ok": False, "message": "No task with that ID."}
    task = existing[0]
    if agent_name not in {task.get("claimed_by"), task.get("assigned_to"), "director"}:
        return {"ok": False, "message": "This task is assigned to another agent. Ask the director to reassign it."}
    now = datetime.now(timezone.utc).isoformat()
    updated = _rows(supabase.table("studio_tasks").update({
        "status": status,
        "result": result,
        "updated_at": now,
    }).eq("id", task_id).execute())
    return {"ok": True, "task": updated[0] if updated else {"id": task_id, "status": status}}


@mcp.tool

def send_message(sender: str, recipient: str, body: str, task_id: str = "") -> dict:
    """Send a message to another agent. Use recipient='all' for a team-wide message."""
    if not sender.strip() or not recipient.strip() or not body.strip():
        raise ValueError("sender, recipient, and body cannot be empty")
    payload = {
        "sender": sender.strip(),
        "recipient": recipient.strip(),
        "body": body.strip(),
    }
    if task_id.strip():
        payload["task_id"] = task_id.strip()
    rows = _rows(supabase.table("studio_messages").insert(payload).execute())
    return rows[0] if rows else {"ok": True, "message": "Message sent."}


@mcp.tool

def read_messages(agent_name: str, after_id: int = 0, limit: int = 50) -> list[dict]:
    """Read team-wide messages and messages sent directly to you, oldest first. Save the largest id for later."""
    limit = max(1, min(int(limit), 100))
    query = (
        supabase.table("studio_messages")
        .select("*")
        .gt("id", max(0, int(after_id)))
        .in_("recipient", ["all", agent_name])
        .order("id", desc=False)
        .limit(limit)
    )
    return _rows(query.execute())


@mcp.tool

def studio_status() -> dict:
    """Get a high-level status report with recent tasks and messages."""
    open_tasks = _rows(
        supabase.table("studio_tasks").select("id,title,assigned_to,status,priority,updated_at")
        .in_("status", ["open", "in_progress", "blocked"]).order("created_at", desc=True).limit(30).execute()
    )
    recent_messages = _rows(
        supabase.table("studio_messages").select("id,sender,recipient,task_id,body,created_at")
        .order("id", desc=True).limit(15).execute()
    )
    return {"active_tasks": open_tasks, "recent_messages": list(reversed(recent_messages))}


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=PORT, path="/mcp")
