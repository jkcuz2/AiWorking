"""Run a one-shot, API-managed Codex-harness agent connected to the shared studio MCP.

Usage:
  python api_agent.py director "Create a sprint plan for the game's first prototype"
  python api_agent.py critic "Review all open tasks and message the director with risks"

This agent can coordinate through the shared store. It does NOT automatically share a
local PC's filesystem. Use GitHub or a configured self-hosted environment for code work.
"""

import os
import sys
from openai import OpenAI

MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
MCP_URL = os.environ["STUDIO_MCP_URL"]
MCP_TOKEN = os.environ["STUDIO_MCP_TOKEN"]

ROLE_INSTRUCTIONS = {
    "director": """You are the API Studio Director. Use the game_studio MCP tools first:
inspect studio_status and messages, then turn the user's goal into small tasks with clear acceptance criteria.
Assign independent tasks to the developers named Daan and friend. Use create_task and send_message to record your work.
Do not claim any game code has been changed or tested. Your role is coordination and planning unless a code environment is explicitly provided.""",
    "critic": """You are the Independent API Critic. Use game_studio MCP tools to inspect current tasks and messages.
Find risks, missing acceptance criteria, overlapping files, and likely bugs. Send specific recommendations to director and, when relevant, team-wide.
Create a separate review task only if it is useful. Do not claim game files were edited or tests were run.""",
    "planner": """You are the Sprint Planner. Use game_studio MCP tools to inspect the current queue and messages.
Break the user's goal into small, non-overlapping tasks, assign them to Daan or friend, and send each assignee the exact task ID and acceptance criteria.
Do not claim game files were edited or tests were run.""",
}


def main() -> int:
    if len(sys.argv) < 3:
        print('Usage: python api_agent.py director|critic|planner "your task"')
        return 2

    role = sys.argv[1].strip().lower()
    prompt = " ".join(sys.argv[2:]).strip()
    if role not in ROLE_INSTRUCTIONS:
        print(f"Unknown role: {role}. Choose director, critic, or planner.")
        return 2

    client = OpenAI()
    agent_config = {
        "model": MODEL,
        "instructions": ROLE_INSTRUCTIONS[role],
        "tools": [
            {
                "type": "mcp",
                "server_label": "game_studio",
                "transport": {
                    "type": "http",
                    "server_url": MCP_URL,
                    "authorization": f"Bearer {MCP_TOKEN}",
                },
                "required": True,
            }
        ],
        "multi_agent": {"enabled": True, "max_concurrent_subagents": 2},
    }

    print(f"Starting {role} API agent using model {MODEL}...")
    with client.beta.agents.sessions.create(
        agent=agent_config,
        environment={"type": "openai_hosted"},
        input=prompt,
        stream=True,
    ).with_result_collection() as stream:
        for event in stream:
            # Show event types, not raw payloads that might contain sensitive data.
            event_type = getattr(event, "type", "event")
            print(f"[{event_type}]", flush=True)
        result = stream.get_final_result()

    print("\nAGENT RESULT\n")
    print(result.output_text)
    print(f"\nSession ID: {result.session_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
