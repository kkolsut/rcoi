# Workflow

← [README](../README.md) · [Workflow](workflow.md) · [Profiles](profiles.md) · [Terminal UI](tui.md) · [Reference](reference.md) · [Troubleshooting](troubleshooting.md) · [Security](security.md)

From starting an agent to merging or discarding its work, step by step.

## Task lifecycle

### 1. Send the repo to the agent host
```bash
git agent init        # once per repo
git agent sync        # after each new commit on main, so new tasks start from it
```
> Second machine? The repo is already on the agent host, so use
> `git agent connect` there instead of `init`: it only adds the remote.

> A task starts from whatever `main` is **on the agent host**. If you forget
> `git agent sync`, the agent works on stale code. `git agent new` (below)
> syncs for you.

### 2. Start an agent with a prompt
```bash
git agent new sum --bg -p 'summarize the project into sum.md, then commit'
git agent new sum --profile codex --bg -p '…'   # the same with Codex (see [Profiles](profiles.md))
```
`git agent new <task> ...` is `rcoi task new myrepo <task> ...` with the repo
name taken from the current repo, and it pushes your `main` first when it's
ahead of the host's (a fast-forward only; `--no-sync` skips that, and a `main`
that differs on the host is only warned about). It creates the worktree
`~/src/myrepo-sum` on branch `agent/sum`, starts the agent in a background
session, and types the prompt in once it's ready. In an existing task, use
`rcoi task shell` instead.

Modes for `new` / `shell`:

| Mode | What runs | Can you attach? |
|---|---|---|
| (none) | interactive `coi shell` (reattaches if the task's session is running) | you're in it |
| `--bg` | background session; `send` the prompt later | yes |
| `--bg -p "…"` | background session, prompt typed in (**Claude and Codex**) | yes |
| `-p "…"` | headless `coi run --prompt`, prints the result when it ends (**Claude only**) | no |
| `-- cmd…` | plain `coi run -- cmd` (no agent settings: **no write permission** for an agent started this way) | no |

### 3. See progress
```bash
rcoi task list                 # tasks, their session and profile, what each agent is doing, its work
rcoi task status myrepo sum    # just this one: e.g. "waiting   +4 commits, 3 uncommitted"
rcoi task peek myrepo sum      # the agent's screen (add a number for more lines: peek myrepo sum 100)
git agent list                 # agent branches and their latest commit
rcoi task wait myrepo sum      # block until the agent is idle again (optional timeout
                               # in seconds), e.g.: rcoi task wait myrepo sum && git agent list
```
`rcoi task list` adds `agent: …` for each running session and `work: …` for
each task, e.g.:
```
/home/you/src/myrepo-sum   56205aa [agent/sum]   session: coi-f90e18aa-1 running   agent: waiting   work: +1 commit, clean
```

| agent | meaning |
|---|---|
| `working` | busy (its screen shows "esc to interrupt") |
| `waiting` | its turn ended: it's done, or wants a reply. With `work: …, clean` and commits, it's usually finished |
| `asking` | a question or approval on screen: answer it with `rcoi task attach` |
| `no agent` | the container runs, but the agent's tmux session is gone (it exited, or killed the tmux server): `rcoi task stop`, then start it again |
| `starting` | none of these yet |

It reads the bottom of each agent's screen (Claude and Codex), all sessions at
once, so `list` takes about half a second longer with running sessions. It's
best effort: a new agent version that changes its screen text can confuse it
(`wait` reads the same signs).

`git agent list` (and `try`) flag a task with `nothing new vs main` (the agent hasn't
committed yet, or it's merged already) or `uncommitted changes on the host`
(its worktree has edits that aren't in any commit, so `diff`/`try` can't see
them yet). Either way: let it finish, or look and commit yourself:
```bash
git agent wip sum              # the uncommitted changes, straight from the host's worktree
rcoi task commit myrepo sum    # commit them all there (optional message as 3rd argument)
rcoi task send myrepo sum 'commit your work'    # or let the agent do it
```

### 4. Follow up or take over
```bash
rcoi task send myrepo sum 'also add a section about the CLI options'
rcoi task attach myrepo sum    # interactive; detach with Ctrl+B, release, then d
```

### 5. Review on your machine
```bash
git agent diff sum             # or: git agent log sum
git agent try sum              # check it out as review/sum, to run or test it
                               # (this runs the agent's code: read the diff first)
git agent try sum              # again later: back on review/sum, fast-forwarded to
                               # the agent's new commits (pull if you committed there too)
```

### 5b. Work on it together (both ways, as often as you like)
```bash
git agent pull sum             # the agent's new commits -> review/sum (created if missing;
                               # merged if you have commits of your own there)
git switch review/sum          # fix things yourself, commit
git agent push sum             # your commits -> agent/sum on the host (and its worktree)
rcoi task send myrepo sum 'I pushed commits to your branch, see git log; continue from them'
```
On `review/<task>`, both default to that task (`git agent pull`, `git agent push`).
This also moves work between your machines: push from one, pull on the other.
`push` is never forced. It is refused when the agent committed since your last
`pull` (pull, then push again) and when the agent has uncommitted changes in its
worktree (let it commit or stop it first): your push never overwrites its work.
The agent host needs git 2.35 or newer for this (older git moves the branch
under the worktree without updating its files).

`main` moved on while the task runs? `git agent update sum` brings the agent's
commits into `review/sum`, merges your `main` there and pushes the result, so
the agent continues on top of the newer code (tell it, as after `push`). On a
conflict it stops: resolve it on `review/sum`, commit, then `git agent push sum`.

### 6a. Keep it
```bash
git agent merge sum            # merges review/sum if it has your commits on top of the
                               # agent's (so they aren't left out), else agent/sum
git push origin main
git agent done sum             # pushes main to the host, removes the task there
                               # (session, worktree, agent/sum) and review/sum here
```
`done` refuses unless both `agent/sum` and `review/sum` are merged into `main`.

### 6b. Discard it
```bash
git agent drop sum             # lists what's lost, asks first (-y skips the question);
                               # removes the same things as done
```
(`rcoi task done` / `rcoi task drop` do only the host's part.)

### 7. Remove the repo from the agent host (when you're done with it there)
```bash
git agent remove               # lists its tasks + unmerged branches, asks, then deletes
                               # ~/src/myrepo and its task worktrees, and the 'agentvm' remote
```

**Pause and resume:** `rcoi task stop myrepo sum` ends the session but keeps
the worktree and commits. Start it again with
`rcoi task shell myrepo sum --bg -p "Continue where you left off."`

The task remembers its profile, so `shell` and `send` don't need `--profile`.

## Recipes

**Everyday feature or bugfix (default model)**
```bash
git agent sync
rcoi task new myrepo fix-login --bg -p "Fix the login redirect loop (issue #12). Add a test. Commit when done."
rcoi task peek myrepo fix-login
git agent diff fix-login && git agent merge fix-login
rcoi task done myrepo fix-login
```

**Cheap, mechanical work (renames, typos, dependency bumps): Sonnet**
```bash
rcoi task new myrepo docs-typos --profile sonnet --bg -p "Fix typos in docs/, commit."
```

**Hard problem: Opus at high effort** (needs the `opus-max` profile)
```bash
rcoi task new myrepo race-cond --profile opus-max --bg -p "Find and fix the race in the job scheduler. Explain the root cause in the commit message."
```

**Quick answer, no session: headless Claude**
```bash
rcoi task new myrepo q-arch -p "Summarise how the request pipeline works. Don't change files."
rcoi task drop myrepo q-arch -y
```

**Second opinion: Claude and Codex on the same problem.** Both start from the
same `main`, run in parallel, and produce two branches to compare:
```bash
rcoi task new myrepo parser-claude --bg -p "Rewrite the CSV parser to stream rows. Commit."
rcoi task new myrepo parser-codex  --profile codex --bg -p "Rewrite the CSV parser to stream rows. Commit."
git agent list
git agent diff parser-claude
git agent diff parser-codex
git agent merge parser-claude          # keep the better one
rcoi task done myrepo parser-claude
rcoi task drop myrepo parser-codex -y
```

**Have another agent review the work**
```bash
rcoi task new myrepo feature-x --bg -p "Implement feature X. Commit."
# when it's done, same worktree and profile:
rcoi task shell myrepo feature-x --bg
rcoi task send  myrepo feature-x "Review the last commit critically; list bugs, fix them, commit."
```
For a reviewer on a different model, start a separate task pointed at the branch:
```bash
rcoi task new myrepo review-x --profile codex --bg -p "Review the diff main..agent/feature-x and write findings to REVIEW.md. Commit."
```

**Long job you check on later**
```bash
rcoi task new myrepo big-refactor --bg -p "..."
rcoi task list myrepo
rcoi task peek myrepo big-refactor 60
rcoi task send myrepo big-refactor "Stop after the current module and commit."
```

**Run the tests in the sandbox (no agent)**
```bash
rcoi task new myrepo ci-check -- make test
```
