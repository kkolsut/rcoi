# rcoi

Run AI agents (Claude Code, Codex) in [Coi](https://github.com/coipond/coi)
containers on a remote agent host, from your laptop, over plain SSH. Three
small bash scripts, and a terminal UI on top of them:

- **`rcoi`** (your machine): runs `coi` (or `coi-task`) on the agent host,
  with Coi's own command syntax: `rcoi list`, `rcoi attach <ct>`, `rcoi task new …`.
- **`git agent`** (`git-agent`, your machine): moves code between your local
  repo and the agent host over SSH. You push `main` there, agents commit to
  `agent/<task>` branches, you fetch those back and review them locally. The
  agent host needs no GitHub (or other forge) credentials.
- **`coi-task`** (agent host): one git worktree + branch + Coi session per
  task. It starts agents in the background, types prompts in, and cleans up.
- **`rcoi-tui`** (your machine, optional): one screen for a repo's tasks, their
  branches and each agent's live screen, with keys for the commands above.
  See [docs/tui.md](docs/tui.md).

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

## Requirements

- **Your machine (Linux or macOS):** bash 3.2 or newer (macOS's built-in
  `/bin/bash` is fine, also when your shell is zsh), OpenSSH client, git;
  Python 3.8+ for `rcoi-tui` (standard library only).
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

It installs `rcoi`, `git-agent` and `rcoi-tui` into `~/.local/bin` (no sudo) and writes
the host into `~/.config/rcoi/host`. It then checks:
- that `~/.local/bin` is on your PATH, and prints the line to add if it isn't;
- that SSH logs in without a password, and suggests `ssh-copy-id` if it doesn't;
- that `coi` is found on the agent host;
- that `coi-task` there is the same as this folder's. If it's missing or
  differs, it asks whether to install it there: it copies it over SSH and
  runs `install` (with `sudo` if the folder isn't writable, so sudo may ask
  for your password on the host).

So after `git pull` here, one `./install.sh` updates both machines.
`--update-host` installs without asking (e.g. from a script), `--no-host`
skips the host. Installing on the host directly (`./install.sh --agent-host`
there) still works.

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
| `--update-host` / `--no-host` | update `coi-task` on the agent host without asking / don't check it |
| `--agent-host` | install `coi-task` instead (run on the agent host) |
| `--prefix DIR` | install somewhere else |
| `--uninstall` | remove the scripts; `~/.config/rcoi/host` stays |

To update: get the new version of this folder (`git pull`) and run
`./install.sh` again. It offers to update `coi-task` on the agent host too.

## Basic usage

Run everything on your machine, inside your repo (here `~/code/myrepo`). The
task name (`fix`) is what you use in every later command.

```bash
cd ~/code/myrepo
git agent init                 # once per repo: creates ~/src/myrepo on the host, adds the 'agentvm' remote, pushes main

git agent new fix --bg -p 'fix the login bug, add a test, commit when done'
                               # new task: worktree + branch agent/fix + agent (pushes main first)
rcoi task list                 # every task: is its agent working, waiting or asking; commits, uncommitted files
rcoi task peek myrepo fix      # the agent's screen right now
rcoi task send myrepo fix 'also update the docs'
rcoi task attach myrepo fix    # talk to it yourself; detach with Ctrl+B, release, then d

git agent diff fix             # what it changed
git agent try fix              # check it out as review/fix to run and test it (read the diff first)
git agent merge fix            # merge it into main
git push origin main
git agent done fix             # remove the task: session, worktree, agent/fix and review/fix
git agent drop fix             # ...or discard it instead (asks first)
```

Or all of it on one screen: `rcoi-tui` (see [docs/tui.md](docs/tui.md)).

## More documentation

| | |
|---|---|
| [Workflow](docs/workflow.md) | the task lifecycle step by step: progress, follow-ups, reviewing and working on a task together, keeping or discarding it; recipes |
| [Models, profiles and Codex](docs/profiles.md) | picking a model or effort, profiles, a second Claude account, Codex |
| [Terminal UI](docs/tui.md) | `rcoi-tui`: keys, repos and local clones, agent states |
| [Reference](docs/reference.md) | every `rcoi task` and `git agent` command; settings |
| [Troubleshooting](docs/troubleshooting.md) | common problems; things to know (detaching, tmux, prompts, quoting) |
| [Security](docs/security.md) | what agents can access, what rcoi adds |
