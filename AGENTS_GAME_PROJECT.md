# AI Game Studio Collaboration Rules

Both Codex developers must follow this protocol when working in the game repository.

## Before starting a task
1. Call `game_studio.ping` and `game_studio.studio_status`.
2. Read shared messages using `game_studio.read_messages` with your consistent agent name (`Daan` or `friend`).
3. List open tasks. Claim one with `game_studio.claim_task` before coding.
4. Check the task description for files reserved by the other agent. If there is overlap, message the director and wait for reassignment.
5. Work on your own Git branch.

## While working
- Do not edit files assigned to the other agent.
- Send a short message when starting, when blocked, and when a significant milestone is finished.
- Keep task descriptions, acceptance criteria, and filenames accurate.
- Do not assume that a message sent by the other agent means their code is already merged.

## When finishing
1. Run available tests/builds and report the exact commands and results.
2. Commit and push your own branch; open a pull request rather than editing the main branch directly.
3. Call `game_studio.update_task` with `done` or `blocked` and a factual summary.
4. Send the other agent a message with the branch/PR, changed files, tests, and remaining concerns.
5. Check new messages before beginning the next task.

The coordination server shares task/message state only. GitHub is the source of truth for code. Never claim a build, test, merge, or deployment succeeded unless you verified it.
