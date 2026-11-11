# rcoi

Run AI agents (Claude Code, Codex) in [Coi](https://github.com/coipond/coi)
containers on a remote agent host, from your laptop, over plain SSH. Three
small bash scripts:

- **`rcoi`** (your machine): runs `coi` (or `coi-task`) on the agent host,
  with Coi's own command syntax: `rcoi list`, `rcoi attach <ct>`, `rcoi task new …`.
- **`git agent`** (`git-agent`, your machine): moves code between your local
  repo and the agent host over SSH. You push `main` there, agents commit to
  `agent/<task>` branches, you fetch those back and review them locally. The
  agent host needs no GitHub (or other forge) credentials.
- **`coi-task`** (agent host): one git worktree + branch + Coi session per
  task. It starts agents in the background, types prompts in, and cleans up.

```bash
git agent init                                   # once per repo: send it to the agent host
rcoi task new myrepo fix-login --bg -p 'fix the login bug, commit when done'
rcoi task peek myrepo fix-login                  # what is it doing?
git agent diff fix-login                         # what did it change?
```

Each task gets its own worktree (`~/src/<repo>-<task>`), branch
(`agent/<task>`) and Coi container. You review and merge on the laptop.

Coi has no remote mode. It has to run on the machine that runs Incus, because
it mounts host folders into containers, sets immutable flags on the host and
runs its `coi supervise` monitor there. `rcoi` runs it there for you:
- each argument reaches the remote `coi` exactly as you typed it, including
  spaces, quotes and `$`;
- you get a terminal when you need one (`attach`, interactive `shell`);
- output stays a clean pipe otherwise (`rcoi list | grep …`).

## Contents

1. [Requirements](#requirements)
2. [Install](#install)
3. [Quick start](#quick-start)
4. [Task lifecycle](#task-lifecycle)
5. [Models, profiles and Codex](#models-profiles-and-codex)
6. [Recipes](#recipes)
7. [Command reference](#command-reference)
8. [Settings](#settings)
9. [Troubleshooting](#troubleshooting)
10. [Things to know](#things-to-know)
11. [Security](#security)

## Requirements

- **Your machine (Linux or macOS):** bash 3.2 or newer (macOS's built-in
  `/bin/bash` is fine, also when your shell is zsh), OpenSSH client, git.
- **Agent host (Linux):**
  - Coi + Incus, working for the user you log in as (`coi shell` works there);
    tested with Coi v0.16.0;
  - git, jq and flock (util-linux);
  - SSH login as that user, with a key, and bash as its login shell.

## Install

Get this folder onto both machines (`git clone`, or `scp -r`).

### 1. Agent host

```bash
./install.sh --agent-host
```

This installs `coi-task` into `/usr/local/bin` (using sudo if needed). That
directory is on the PATH of non-interactive SSH sessions, which is how rcoi
calls it. It then checks that coi, incus, git, jq and flock are there.

Configure Coi so agents can work on their own. Minimal `~/.coi/config.toml`:

```toml
[tool]
name = "claude"
permission_mode = "bypass"     # the agent edits and commits without asking (it's in a container)

[defaults.env_commands]
# Claude's login token, read when a session starts.
# Create one with `claude setup-token`, store it with mode 0600.
CLAUDE_CODE_OAUTH_TOKEN = "cat /home/you/.config/coi-secrets/claude_token"
```

Without `permission_mode = "bypass"`, an agent started in the background asks
before each write, and nobody is there to answer. Network limits, memory
limits, protected branches and so on are up to you. See Coi's docs.

### 2. Your machine

```bash
./install.sh --host you@agent-host
```

It installs `rcoi` and `git-agent` into `~/.local/bin` (no sudo) and writes
the host into `~/.config/rcoi/host`. It then checks:
- that `~/.local/bin` is on your PATH, and prints the line to add if it isn't;
- that SSH logs in without a password, and suggests `ssh-copy-id` if it doesn't;
- that `coi` and `coi-task` are found on the agent host.

On **macOS**, `~/.local/bin` isn't on the PATH by default. Add it to
`~/.zshrc` and open a new terminal:

```zsh
export PATH="$HOME/.local/bin:$PATH"
```

Check it works:

```bash
rcoi version          # Coi's version, from the agent host
rcoi task list        # task worktrees on the agent host
git agent help
```

| install.sh | |
|---|---|
| `./install.sh` | update the scripts, keep the host setting |
| `--host user@host` | set (or change) the agent host |
| `--agent-host` | install `coi-task` instead (run on the agent host) |
| `--prefix DIR` | install somewhere else |
| `--uninstall` | remove the scripts; `~/.config/rcoi/host` stays |

To update: get the new version of this folder and run `./install.sh` again
(on each machine, with `--agent-host` there).

## Quick start

Run everything on your machine, inside your repo (here `~/code/myrepo`, task
`sum`). The task name is what you use in every later command.

```bash
cd ~/code/myrepo
git agent init                 # once per repo: creates ~/src/myrepo on the host, adds the 'agentvm' remote, pushes main

rcoi task new myrepo sum --bg -p 'summarize the project into sum.md, then commit'
rcoi task peek myrepo sum      # the agent's screen right now

git agent diff sum             # read what changed
git agent merge sum            # merge agent/sum into main (--no-ff)
rcoi task done myrepo sum      # stop the session, remove worktree + branch on the host
```

## Task lifecycle

**1. Send the repo to the agent host**
```bash
git agent init        # once per repo
git agent sync        # after each new commit on main, so new tasks start from it
```
> A task starts from whatever `main` is **on the agent host**. If you forget
> `git agent sync`, the agent works on stale code.

**2. Start an agent with a prompt**
```bash
rcoi task new myrepo sum --bg -p 'summarize the project into sum.md, then commit'
rcoi task new myrepo sum --profile codex --bg -p '…'   # the same with Codex (see Profiles)
```
This creates the worktree `~/src/myrepo-sum` on branch `agent/sum`, starts the
agent in a background session, and types the prompt in once it's ready. In an
existing task, use `shell` instead of `new`.

Modes for `new` / `shell`:

| Mode | What runs | Can you attach? |
|---|---|---|
| (none) | interactive `coi shell` (reattaches if the task's session is running) | you're in it |
| `--bg` | background session; `send` the prompt later | yes |
| `--bg -p "…"` | background session, prompt typed in (**Claude and Codex**) | yes |
| `-p "…"` | headless `coi run --prompt`, prints the result when it ends (**Claude only**) | no |
| `-- cmd…` | plain `coi run -- cmd` (no agent settings: **no write permission** for an agent started this way) | no |

**3. See progress**
```bash
rcoi task list                 # tasks, whether their session is running, their profile
rcoi task peek myrepo sum      # the agent's screen (add a number for more lines: peek myrepo sum 100)
git agent list                 # agent branches and their latest commit
```

**4. Follow up or take over**
```bash
rcoi task send myrepo sum 'also add a section about the CLI options'
rcoi task attach myrepo sum    # interactive; detach with Ctrl+B, release, then d
```

**5. Review on your machine**
```bash
git agent diff sum             # or: git agent log sum
git agent try sum              # check it out as review/sum, to run or test it
                               # (this runs the agent's code: read the diff first)
```

**6a. Keep it**
```bash
git switch main
git agent merge sum
git push origin main && git agent sync
rcoi task done myrepo sum      # merged work only
git branch -D review/sum       # if you used try
```

**6b. Discard it**
```bash
rcoi task drop myrepo sum      # asks first; -y skips the question
git switch main && git branch -D review/sum    # only if you used try
git agent list                 # drops agentvm/agent/sum locally too
```

**Pause and resume:** `rcoi task stop myrepo sum` ends the session but keeps
the worktree and commits. Start it again with
`rcoi task shell myrepo sum --bg -p "Continue where you left off."`

The task remembers its profile, so `shell` and `send` don't need `--profile`.

## Models, profiles and Codex

A **profile** is one file on the agent host,
`~/.coi/profiles/<name>/config.toml`, layered over the global config. The
directory name is the profile name. Settings are layered, later wins:

```
global ~/.coi/config.toml  <  repo .coi/config.toml  <  --profile <name>
```

Pick one per task with `--profile`. coi-task remembers it, and
`rcoi task list` shows it.

### Claude models and effort

Coi picks the model from config (`[tool.claude] model = …`, passed to Claude
Code as `ANTHROPIC_MODEL`). There is **no `--model` flag**.

- **Model values:** aliases follow the newest release (`opus`, `sonnet`,
  `haiku`); full IDs pin a version (`claude-opus-5-5`, `claude-sonnet-5-5`,
  `claude-haiku-5-5`).
- **Effort values:** `low`, `medium`, `high`, `xhigh`, `max`, `auto`. When
  `effort_level` is set in config, Coi injects it into every session; when
  it's unset, you choose it in the session.
- **To change the default for every session**, set `[tool.claude]` in the
  global `~/.coi/config.toml` instead of adding a profile.

Three ways to pick a model:
```bash
rcoi task new <repo> <task> --bg -p "..."                      # a) the default from config
rcoi task new <repo> <task> --profile sonnet --bg -p "..."     # b) a profile, for the whole task
rcoi task attach <repo> <task>                                 # c) mid-session: use Claude's /model, detach Ctrl+B, d
```
Check which model a session uses: `rcoi task peek <repo> <task> 10` (the
header shows e.g. "Opus 5.5 · Claude API").

### Example profiles

```toml
# ~/.coi/profiles/sonnet/config.toml
[tool.claude]
model = "sonnet"

# ~/.coi/profiles/opus-max/config.toml
[tool.claude]
model = "opus"
effort_level = "max"

# ~/.coi/profiles/haiku/config.toml
[tool.claude]
model = "haiku"

# ~/.coi/profiles/codex/config.toml
[tool]
name = "codex"
permission_mode = "bypass"

# ~/.coi/profiles/codex-high/config.toml
[tool]
name = "codex"
permission_mode = "bypass"
[tool.codex]
reasoning_effort = "high"      # minimal | low | medium | high
# model = "<codex model id>"   # -> codex -m <model>

# ~/.coi/profiles/claude2/config.toml   (a second Claude account)
[defaults.env_commands]
CLAUDE_CODE_OAUTH_TOKEN = "cat ~/.config/coi-secrets/claude_token_2"
```

Create one from your laptop, then use it:
```bash
ssh "$(rcoi host)" 'mkdir -p -m 700 ~/.coi/profiles/opus-max && cat > ~/.coi/profiles/opus-max/config.toml' <<'EOF'
[tool.claude]
model = "opus"
effort_level = "max"
EOF
rcoi task new <repo> <task> --profile opus-max --bg -p "..."
```

Rules:
- A Claude profile needs only `[tool.claude]`; it inherits `name = "claude"`
  from the global config.
- A Codex profile **must** set `[tool] name = "codex"`. Without it, the
  profile runs Claude.
- The Claude account is chosen when a session starts. To switch a running
  task, `stop` it and start it again with the other profile.

### Codex

Codex must be in the image: `[container.build] agents = ["claude", "codex"]`.
Then use it through a `codex` profile (above):

```bash
rcoi task new myrepo fix --profile codex --bg -p 'fix the failing test, then commit'
```

| Item | State |
|---|---|
| Login | `~/.codex/auth.json` on the agent host (mode 0600); Coi copies it into every session. |
| Permissions | `bypass` (`--dangerously-bypass-approvals-and-sandbox`). The Incus container is the sandbox. |
| Folder trust | `coi-task` adds `[projects."~/src/<repo>"] trust_level = "trusted"` to the host's `~/.codex/config.toml`, so no dialog blocks `--bg -p`. |
| Monitoring | Codex writes about 500 MB at startup, so set the monitor's write-rate limit to 500 MB/s, or the container freezes. |
| Model / reasoning | Codex's defaults; see `codex-high` above. |

To log in: run `codex login` (`--device-auth` on a machine without a browser,
or `--with-api-key`), then copy `auth.json` to the host's `~/.codex/auth.json`
with `chmod 600`. The browser login flow doesn't work inside a container.
Without the file, `--bg -p` stops with "Codex is not logged in".

Limits:
- **No headless mode.** `-p` without `--bg` is refused; use `--bg -p`.
- `coi list` doesn't show Codex workspaces. Use `rcoi task list`, which reads
  from Incus.
- The footer warning "could not find bubblewrap" is harmless: Codex's own
  sandbox is off in bypass mode.

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
stop   <repo> <task>                         end the session, keep the worktree
done   <repo> <task>                         stop + remove worktree + branch (merged only)
drop   <repo> <task> [-y]                    the same, discarding unmerged work
list   [<repo>]                              tasks, sessions, profiles
```

**`git agent`**
```
git agent init          create ~/src/<repo> on the agent host, add the 'agentvm' remote, push main
git agent sync          push main to the agent host (never forced)
git agent list          fetch and list the agent branches (newest first)
git agent diff <task>   what the agent changed since it branched off main
git agent log  <task>   the same, commit by commit
git agent try  <task>   check it out as review/<task>
git agent merge <task>  merge it into main
```

Your repo only fetches `agent/*` branches from the agent host
(`+refs/heads/agent/*:refs/remotes/agentvm/agent/*`). So an agent can't replace
your `main` or tags, and nothing is pushed anywhere but the agent host. `sync`
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

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `rcoi list` shows **Frozen** | The security monitor paused it. Check `~/.coi/audit/<ct>.jsonl` (or `rcoi audit` / `rcoi logs <ct>`) for `threats`. If it's a false positive: `rcoi unfreeze <ct>`, then raise the limit under `[monitoring]` in `~/.coi/config.toml`. |
| `--bg -p` says "asking to trust the folder" | Trust was not pre-set. Attach and answer it (`rcoi task attach`). For Codex, check the host's `~/.codex/config.toml` has the repo root. |
| "Codex is not logged in" | `~/.codex/auth.json` is missing or expired on the host. See [Codex](#codex). |
| "agent not ready after 180s" | Look with `rcoi task attach`. `COI_TASK_READY_TIMEOUT` raises the wait. |
| The agent worked on old code | You forgot `git agent sync` before `task new`. |
| `task done` refuses | The branch isn't merged. Merge it (`git agent merge`) or use `drop`. |
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

## Security

Agents run with Coi's isolation, and with whatever access you give them in
`~/.coi/config.toml` (network mode, env vars, mounted secrets). `bypass` only
means they don't ask before acting inside their container.

`rcoi` adds no access of its own. It's an SSH login as the Coi user plus one
command. Whoever can run `rcoi` against a host can already SSH to it. There's
no Incus API exposed to the network (`incus remote` would make the laptop an
Incus admin of the host, which is root-equivalent there).
