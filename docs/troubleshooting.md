# Troubleshooting

← [README](../README.md) · [Workflow](workflow.md) · [Profiles](profiles.md) · [Terminal UI](tui.md) · [Reference](reference.md) · [Troubleshooting](troubleshooting.md) · [Security](security.md)

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `rcoi list` shows **Frozen** | The security monitor paused it. Check `~/.coi/audit/<ct>.jsonl` (or `rcoi audit` / `rcoi logs <ct>`) for `threats`. If it's a false positive: `rcoi unfreeze <ct>`, then raise the limit under `[monitoring]` in `~/.coi/config.toml`. |
| `--bg -p` says "asking to trust the folder" | Trust was not pre-set. Attach and answer it (`rcoi task attach`). For Codex, check the host's `~/.codex/config.toml` has the repo root. |
| "Codex is not logged in" | `~/.codex/auth.json` is missing or expired on the host. See [Codex](profiles.md#codex). |
| "agent not ready after 180s" | Look with `rcoi task attach`. `COI_TASK_READY_TIMEOUT` raises the wait. |
| `git agent init`: "already exists" | The repo is on the host already (init from another machine). Use `git agent connect`. |
| The agent worked on old code | You forgot `git agent sync` before `rcoi task new` (`git agent new` syncs). Catch up: `git agent update <task>`. |
| `try`/`diff` show no changes | The agent hasn't committed: `git agent wip <task>` shows its work, `rcoi task commit <repo> <task>` commits it. |
| `done` refuses | The branch isn't merged. Merge it (`git agent merge`) or use `drop`. |
| Wrong model | `rcoi task peek <repo> <task> 10` shows it. Check the task's profile in `rcoi task list`. |
| A session is gone but the container is stuck | `rcoi list`, then `rcoi shutdown <ct>` (or `rcoi kill <ct>`). |
| zsh: "no matches found" | Quote your prompts. zsh refuses an unquoted word with `?` or `*` that matches no file. |

## Things to know

- **The SSH connection can drop:** a background agent keeps running in tmux on
  the host. Just `attach` again.
- **Detaching is two keys:** press Ctrl+B, let go, then press `d`. Ctrl+B on
  its own does nothing visible. Don't use Ctrl+C or Ctrl+D to leave: those go
  to the agent, and Ctrl+D twice ends it and then the session's shell, which
  ends the session. If you're stuck, type Enter `~` `.` to drop the SSH
  connection. The agent keeps running.
- **tmux inside tmux:** if you use tmux on the laptop, `Ctrl+B` goes to your
  tmux first. Press Ctrl+B twice, then `d`, or change one of the prefixes.
- **Sessions don't end on their own:** the background session stays up after
  the agent finishes, so you can attach and ask follow-ups. `stop`, `done` or
  `drop` it; `rcoi list` shows what's still running.
- **Claude's first-run screens:** each Coi container is fresh, so Claude would
  stop at its theme picker and the "trust this folder" dialog, and nobody
  answers those in a background session. coi-task seeds the host's
  `~/.claude.json`, which Coi copies into every session: it records onboarding
  as done and accepts trust for that exact worktree path. `done`/`drop` remove
  the trust entry again. If an agent still waits on a dialog, `--bg` says so
  and `attach` lets you answer it.
- **Prompts are sent literally:** `coi tmux send` (Coi v0.16.0) puts the text
  inside a double-quoted shell string in the container, so `$(…)` or backticks
  would be executed. coi-task's `send` and `--bg -p` use `tmux send-keys -l`
  through `incus exec` instead, which passes the text as an argument with no
  shell involved. Newlines become spaces (Enter would submit early). Prefer
  them over `rcoi tmux send`.
- **Quoting:** use single quotes when a prompt contains `!` or `$`, because
  inside double quotes your shell expands them before rcoi sees them.
- **Terminals:** kitty, Ghostty and the like send a `TERM` the host may not
  know. Attaching works anyway (Coi maps it), and coi-task types prompts in
  without a terminal.
- **Coi's monitor:** it may pause (freeze) a session on suspicious activity:
  `rcoi task list` shows `frozen`.
