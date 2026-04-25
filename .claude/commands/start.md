## Auto-run at every session start

Run this automatically before responding to anything else.

Execute these steps in order with no user input:

1. Read docs/inbox.md in full
   - If it contains content: merge into claude_memory.md and any relevant docs, then overwrite docs/inbox.md with empty content, commit: git add docs/inbox.md docs/claude_memory.md && git commit -m "chore: merge inbox into memory" && git push origin HEAD -y
   - If empty: continue

2. Read these files in full:
   - docs/claude_memory.md
   - docs/decisions_log.md
   - docs/design/asset_board_ui.md
   - CLAUDE.md

3. Check docs/design/ for any spec files not yet read — read any that exist

4. Report in one line: "Context loaded. Inbox: [empty/merged X items]. Current task: [task name from memory]. Ready."
