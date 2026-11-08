# rcoi

Run AI agents in [Coi](https://github.com/coipond/coi) containers on a remote
agent host, from your laptop, over plain SSH. Two small bash scripts:

- **`rcoi`**: runs `coi` (or `coi-task`) on the agent host, with Coi's own
  command syntax: `rcoi list`, `rcoi attach <ct>`, `rcoi task new …`.
- **`git agent`** (`git-agent`): moves code between your local repo and the
  agent host over SSH. You push `main` there, agents commit to `agent/<task>`
  branches, you fetch those back and review them locally. The agent host
  needs no GitHub (or other forge) credentials.

```bash
git agent init                                   # once per repo: send it to the agent host
rcoi task new myrepo fix-login --bg -p 'fix the login bug, commit when done'
rcoi task peek myrepo fix-login                  # what is it doing?
git agent diff fix-login                         # what did it change?
```

Coi has no remote mode. It has to run on the machine that runs Incus,
because it mounts host folders into containers, sets immutable flags on the
host and runs its `coi supervise` monitor there. `rcoi` runs it there for you:
- each argument reaches the remote `coi` exactly as you typed it, including
  spaces, quotes and `$`;
- you get a terminal when you need one (`attach`, interactive `shell`);
- output stays a clean pipe otherwise (`rcoi list | grep …`).

## Requirements

- **Your machine (Linux or macOS):** bash 3.2 or newer (macOS's built-in
  `/bin/bash` is fine, also when your shell is zsh), OpenSSH client, git.
- **Agent host:**
  - Coi + Incus;
  - SSH login as the Coi user, with bash as its login shell;
  - `coi` and `coi-task` on the PATH of a non-interactive SSH session
    (`/usr/local/bin` is).
- **coi-task** is the worktree-per-task helper behind `rcoi task` and
  `git agent init`. It comes from homelab_ansible
  (`roles/coi-agent-host/files/coi-task`, installed by the `coi-agent-host`
  role). Plain `rcoi <coi command>` only needs Coi.

## Install

From this folder (copy it to the machine first, e.g. `scp -r` or `git clone`):

```bash
./install.sh --host sisio@agents-vm01.home.kolsut.net
```

It installs `rcoi` and `git-agent` into `~/.local/bin` (no sudo) and writes
the host into `~/.config/rcoi/host`. It then checks:
- that `~/.local/bin` is on your PATH, and prints the line to add if it isn't;
- that SSH logs in without a password, and suggests `ssh-copy-id` if it doesn't;
- that `coi` and `coi-task` are found on the host.

On **macOS**, `~/.local/bin` isn't on the PATH by default. Add it to
`~/.zshrc` (install.sh prints the exact line) and open a new terminal:

```zsh
export PATH="$HOME/.local/bin:$PATH"
```

Then:

```bash
rcoi version          # Coi's version, from the host
rcoi task list        # task worktrees on the host
git agent help
```

| install.sh | |
|---|---|
| `./install.sh` | update the scripts, keep the host setting |
| `--host user@host` | set (or change) the agent host |
| `--prefix DIR` | install somewhere else, e.g. `/usr/local/bin` (needs write access there) |
| `--uninstall` | remove the scripts; `~/.config/rcoi/host` stays |

To update later: replace this folder with the new version and run `./install.sh` again.

### Settings

| What | How |
|---|---|
| Agent host | `RCOI_HOST=user@host`, else the first line of `~/.config/rcoi/host` (`git agent` also takes `AGENTVM_HOST`) |
| Extra SSH options for rcoi | `RCOI_SSH_OPTS="-p 2222 -i ~/.ssh/agent"` (word-split) |
| git agent's remote name | `AGENTVM_REMOTE` (default `agentvm`) |
| Branch agents start from | `AGENTVM_BASE` (default `main`) |

SSH keys or Kerberos must log in **without a password prompt**, because
`git agent` and pipes need that. Interactive `rcoi` works either way. SSH
options for `git agent` go into `~/.ssh/config` (a `Host` entry), since git
calls ssh itself.

## Workflow

Run everything on your machine, inside your repo (here `~/Projects/myrepo`,
task `sum`). The task name is what you use in every later command.

**1. Send the repo to the agent host (once per repo)**
```bash
cd ~/Projects/myrepo
git agent init        # creates ~/src/myrepo on the host, adds the 'agentvm' remote, pushes main
git agent sync        # later: push your new main there, so new tasks start from it
```

**2. Start an agent with a prompt**
```bash
rcoi task new myrepo sum --bg -p 'summarize the project into sum.md, then commit'
```
This creates the worktree `~/src/myrepo-sum` on branch `agent/sum` and starts
Claude in a background session, then types the prompt in once it's ready. In an
existing task, use `shell` instead of `new`.

**3. See progress**
```bash
rcoi task list                 # tasks and whether their session is running
rcoi task peek myrepo sum      # the agent's screen right now (rcoi task peek myrepo sum 100: more lines)
git agent list                 # agent branches and their latest commit
```

**4. Follow up with the agent**
```bash
rcoi task send myrepo sum 'also add a section about the CLI options'
```

**5. Interact with the agent**
```bash
rcoi task attach myrepo sum
```
To leave, press **Ctrl+B**, let go, then **d**. The agent keeps running.

**6. Get the changes into a local branch**
```bash
git agent diff sum             # read what changed first
git agent try sum              # check it out as review/sum, to run or test it
```
To keep it:
```bash
git switch main
git agent merge sum            # merges agent/sum into main (--no-ff)
git push origin main && git agent sync
rcoi task done myrepo sum      # stops the session, removes the worktree + branch on the host
git branch -D review/sum       # if you used try
```

**7. Discard the changes and delete the Coi container**
```bash
rcoi task drop myrepo sum      # asks first; -y skips the question
git switch main && git branch -D review/sum    # only if you used try
git agent list                 # drops agentvm/agent/sum locally too
```
To stop only the container and keep the work, run `rcoi task stop myrepo sum`.
Start it again later with `rcoi task shell myrepo sum --bg`.

## git agent

```
git agent init          create ~/src/<repo> on the agent host, add the 'agentvm' remote, push main
git agent sync          push main to the agent host (never forced)
git agent list          fetch and list the agent branches (newest first)
git agent diff <task>   what the agent changed since it branched off main
git agent log  <task>   the same, commit by commit
git agent try  <task>   check it out as review/<task> (this runs the agent's code: read the diff first)
git agent merge <task>  merge it into main
```

Your repo only fetches `agent/*` branches from the agent host
(`+refs/heads/agent/*:refs/remotes/agentvm/agent/*`). So an agent can't
replace your `main` or tags, and nothing is pushed anywhere but the agent host.
`sync` never forces: if it's rejected, `main` on the host was changed there,
so look before you overwrite it.

## rcoi usage


```
rcoi <coi args...>     coi <coi args...> on the host
rcoi task <args...>    coi-task <args...> on the host
rcoi host              print the configured host
rcoi help              rcoi's help (rcoi --help is Coi's own help)
```

Paths you pass to Coi are **host** paths. Arguments arrive literally, so the
remote side never expands `~` or `$VARS`, while your local shell expands an
unquoted `~` to your **laptop** home. That only works if both homes match. So pass
absolute host paths (`rcoi shell -w /home/sisio/src/myrepo-fix --background`),
or use `rcoi task`, which works with repo and task names instead of paths.

### Background agents you can watch and take over

The usual loop with `coi-task`:

```bash
# start: worktree ~/src/myrepo-fix-login on branch agent/fix-login,
# Claude in a background tmux session, prompt typed in once it's ready
rcoi task new myrepo fix-login --bg -p "fix the login bug, run the tests, commit"

rcoi task list                       # worktrees + their sessions (running / frozen)
rcoi task peek myrepo fix-login      # its screen right now (last 40 lines)
rcoi task send myrepo fix-login "also update the changelog"
rcoi task attach myrepo fix-login    # interactive; Ctrl+B, then d detaches, the agent keeps going
rcoi task stop myrepo fix-login      # shut the session down, keep the worktree

rcoi task shell myrepo fix-login --bg -p "follow-up..."   # new session on the same worktree
rcoi task done myrepo fix-login      # after merging: stop, remove worktree + branch
rcoi task drop myrepo fix-login      # or discard unmerged work (asks; -y to skip)
```

Other modes of `new` / `shell`:

| Mode | What runs | Can you attach? |
|---|---|---|
| (none) | interactive `coi shell` (reattaches if the task's session is running) | you're in it |
| `--bg [-p "…"]` | `coi shell --background`, prompt typed into it | yes |
| `-p "…"` | headless `coi run --prompt`, prints the result when it ends | no |
| `-- cmd…` | plain `coi run -- cmd` (no agent settings: **no write permission** for an agent started this way) | no |

The same names work with plain Coi too: `rcoi task list` shows the container
name, so `rcoi attach <ct>`, `rcoi tmux capture <ct>`, `rcoi shutdown <ct>` do
the same as the task commands.

## Things to know

- **The SSH connection can drop:** a background agent keeps running in tmux on the
  host. Just `attach` again.
- **Detaching is two keys:** press Ctrl+B, let go, then press `d`. Ctrl+B on its
  own does nothing visible. Don't use Ctrl+C or Ctrl+D to leave: those go to
  Claude, and Ctrl+D twice ends Claude and then the session's shell, which ends
  the session. If you're stuck, type Enter `~` `.` to drop the SSH connection.
  The agent keeps running.
- **tmux inside tmux:** if you use tmux on the laptop, `Ctrl+B` goes to your
  tmux first. Press Ctrl+B twice, then `d`, to detach the agent's session, or change
  one of the prefixes.
- **Sessions don't end on their own:** the background session stays up
  after Claude finishes, so you can attach and ask follow-ups. `stop`, `done`
  or `drop` it, or `rcoi list` to see what's still running.
- **Claude's first-run screens:** each Coi container is fresh, so Claude would
  stop at its theme picker and the "trust this folder" dialog, and nobody
  answers those in a background session. coi-task seeds the host's
  `~/.claude.json`, which Coi copies into every session: it records onboarding
  as done and accepts trust for that exact worktree path. `done`/`drop` remove
  the trust entry again. If an agent still waits on a dialog, `--bg` says so and
  `attach` lets you answer it.
- **Prompts are sent literally:** `coi tmux send` (Coi v0.16.0) puts the
  text inside a double-quoted shell string in the container, so `$(…)` or
  backticks in it would be executed. coi-task's `send` and `--bg -p` use
  `tmux send-keys -l` through `incus exec` instead, which passes the text as an
  argument with no shell involved. Newlines become spaces (Enter would
  submit early). Prefer them over `rcoi tmux send`.
- **zsh (macOS default) and other shells:** quote prompts. zsh refuses an
  unquoted word with `?` or `*` that matches no file ("no matches found").
  Use single quotes when a prompt contains `!` or `$`, because inside double
  quotes your shell expands them before rcoi sees them.
- **Terminals:** kitty, Ghostty and the like send a `TERM` the host may not
  know. Attaching works anyway (Coi maps it), and coi-task types prompts in
  without a terminal.
- **Coi's monitor:** it may pause (freeze) a session on suspicious activity:
  `rcoi task list` shows `frozen`. See `rcoi audit` / `rcoi logs <ct>`.

## Security

`rcoi` adds no access of its own. It's an SSH login as the Coi user plus one
command. Whoever can run `rcoi` against a host can already SSH to it.
There's no Incus API exposed to the network (`incus remote` would make
the laptop an Incus admin of the host, which is root-equivalent there).
