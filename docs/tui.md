# rcoi-tui: the terminal UI

← [README](../README.md) · [Workflow](workflow.md) · [Profiles](profiles.md) · [Terminal UI](tui.md) · [Reference](reference.md) · [Troubleshooting](troubleshooting.md) · [Security](security.md)

```bash
cd myrepo && rcoi-tui        # starts with this repo's tasks; R: another repo, A: all repos
rcoi-tui --all               # every repo's tasks (also the default outside a repo)
```

```
 rcoi-tui   host: you@agent-host   repo: myrepo
 main in sync
 TASK               AGENT     WIP  PROFILE    +/-     REVIEW UPDATED          LAST COMMIT
 check              waiting        -          +3      yes    5 minutes ago    add star catalogue check
 parser             working   4    codex      +1             1 minute ago     split the lexer
 tui                no agent       -          +7             2 hours ago      curses front end
 new-ui             stopped        codex      +0             3 days ago       start
── screen: check (coi-f90e18aa-1, waiting) ───────────────────────── Tab: changes ──
 (the agent's screen, refreshed every 2 seconds)
```

It is a front end only: every key runs `rcoi` or `git agent`, and `o` shows
the commands it ran and their output.

`git agent` needs a local clone, so rcoi-tui looks for yours: every repo with
an `agentvm` remote one or two levels below `~/Projects`, `~/src`, `~/code`
and the folder holding the repo you started in (set `RCOI_TUI_ROOTS`,
colon-separated, to look elsewhere). Each repo's `git agent` commands run in
its own clone (`new` pushes main first, `done`/`drop` also delete
`review/<task>` there). For a repo without a clone the git keys are off and
`new`/`done`/`drop` use `rcoi task`. `R` lists the repos with their clones.

| Key | Does | Key | Does |
|---|---|---|---|
| `R` | pick a repo | `A` | one repo / all repos |
| `Enter`, `a` | attach (detach: Ctrl+B, d) | `n` | new task (`--bg`, optional prompt) |
| `s` | send text to the agent | `u` | start a session (restarts a dead one) |
| `x` | stop the session | `w` | the agent's uncommitted changes |
| `c` | commit them on the host | `d` / `l` | diff / log in your pager |
| `t` | try (`review/<task>`) | `p` / `P` | pull / push `review/<task>` |
| `U` | update `review/<task>` with main | `m` | merge into main |
| `D` | done (merged only) | `X` | drop (asks first) |
| `y` | sync main to the host | `Tab` | preview: screen / changes |
| `r` | refresh | `?` | help |

AGENT is what the agent is doing, from `rcoi task list` (see
[See progress](workflow.md#3-see-progress)): **waiting** (bold) and **asking** are your
turn; Enter attaches to answer. WIP is the number of uncommitted files in its
worktree (`w` shows them, `c` commits them). **no agent** means the container
still runs but the agent's tmux session is gone: the agent exited, or killed
the tmux server in its container (e.g. `tmux kill-server` while testing a
terminal app). `u` restarts it (stop + start; worktree and commits stay).
With an older `coi-task` on the host, AGENT only says `running`: update it
with `./install.sh`.

Options: `--all` (start with every repo), `--interval SECONDS` (screen refresh, default 2),
`--no-mux` (by default it shares one SSH connection between its commands).
Tests: `python3 -m unittest discover tests` (fake `rcoi`/`git-agent`, no host needed).
