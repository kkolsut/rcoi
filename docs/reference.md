# Reference

← [README](../README.md) · [Workflow](workflow.md) · [Profiles](profiles.md) · [Terminal UI](tui.md) · [Reference](reference.md) · [Troubleshooting](troubleshooting.md) · [Security](security.md)

## Command reference

```
rcoi <coi args...>     coi <coi args...> on the host
rcoi task <args...>    coi-task <args...> on the host
rcoi host              print the configured host
rcoi help              rcoi's help (rcoi --help is Coi's own help)
```

**`rcoi task`** (coi-task)
```
new    <repo> <task> [--profile P] [mode]   new worktree agent/<task> + start the agent
shell  <repo> <task> [--profile P] [mode]   start the agent in an existing task worktree
         modes: (none) | --bg [-p "prompt"] | -p "prompt" (Claude) | -- cmd...
attach <repo> <task>                         live session (detach: Ctrl+B, d)
peek   <repo> <task> [lines]                 print the screen (default 40 lines)
send   <repo> <task> "text"                  type text + Enter
wait   <repo> <task> [secs]                  until the agent is idle or asks you (default: no timeout)
status <repo> <task>                         what the agent is doing, commits, uncommitted files
wip    <repo> <task> [--color]               uncommitted changes in the worktree (git agent wip)
commit <repo> <task> ["msg"]                 commit everything in the worktree (git add -A)
stop   <repo> <task>                         end the session, keep the worktree
done   <repo> <task>                         stop + remove worktree + branch (merged only)
drop   <repo> <task> [-y]                    the same, discarding unmerged work
list   [<repo>]                              tasks, sessions, profiles, agent state, work
remove <repo> [-y]                           drop every task, delete ~/src/<repo> (git agent remove)
```

**`git agent`**
```
git agent init          create ~/src/<repo> on the agent host, add the 'agentvm' remote, push main
git agent connect       only add the 'agentvm' remote (repo already on the host, e.g. init from another machine)
git agent remove [-y]   delete ~/src/<repo> + its tasks on the host, then the 'agentvm' remote (asks first)
git agent sync          push main to the agent host (never forced)
git agent new <task> [--no-sync] [--profile P] [mode]
                        rcoi task new <this repo> <task> ..., syncing main first if it's ahead
git agent list          fetch and list the agent branches (newest first), flag unfinished ones
git agent wip  [task]   the agent's uncommitted changes on the host
git agent diff <task>   what the agent changed since it branched off main
git agent log  <task>   the same, commit by commit
git agent try  <task>   check it out as review/<task> (again: fast-forward it)
git agent pull [task]   agent's new commits -> review/<task> (merge; creates it if missing)
git agent push [task]   review/<task> -> agent/<task> on the host (never forced)
git agent update [task] merge main into review/<task>, then push it
git agent merge <task>  merge review/<task> (if it has your commits) or agent/<task> into main
git agent done [task]   sync main, remove the task on the host and review/<task> (merged only)
git agent drop [task] [-y]  the same for unmerged work: discards it (asks first)
```
`[task]` defaults to the task of the current `review/<task>` branch.

Your repo only fetches `agent/*` branches from the agent host
(`+refs/heads/agent/*:refs/remotes/agentvm/agent/*`). So an agent can't replace
your `main` or tags, and nothing is pushed anywhere but the agent host. `push`
only updates an existing `agent/<task>` branch. `sync`
never forces: if it's rejected, `main` on the host was changed there, so look
before you overwrite it.

**Plain Coi works too.** `rcoi task list` shows the container name, so
`rcoi attach <ct>`, `rcoi tmux capture <ct>`, `rcoi shutdown <ct>` do the same
as the task commands.

**Paths you pass to Coi are host paths.** Arguments arrive literally, so the
remote side never expands `~` or `$VARS`, while your local shell expands an
unquoted `~` to your **laptop** home. Pass absolute host paths
(`rcoi shell -w /home/you/src/myrepo-fix --background`), or use `rcoi task`,
which works with repo and task names instead of paths.

## Settings

| What | How |
|---|---|
| Agent host | `RCOI_HOST=user@host`, else the first line of `~/.config/rcoi/host` (`git agent` also takes `AGENTVM_HOST`) |
| Extra SSH options for rcoi | `RCOI_SSH_OPTS="-p 2222 -i ~/.ssh/agent"` (word-split) |
| git agent's remote name | `AGENTVM_REMOTE` (default `agentvm`) |
| Branch agents start from | `AGENTVM_BASE` (default `main`) |
| Where repos live on the agent host | `COI_TASK_SRC` (default `~/src`; `git agent init` assumes `~/src`) |
| How long `--bg -p` waits for the agent | `COI_TASK_READY_TIMEOUT` seconds (default 180) |

SSH must log in **without a password prompt** (key or Kerberos), because
`git agent` and pipes need that. Interactive `rcoi` works either way. SSH
options for `git agent` go into `~/.ssh/config` (a `Host` entry), since git
calls ssh itself.
