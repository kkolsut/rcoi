# Models, profiles and Codex

← [README](../README.md) · [Workflow](workflow.md) · [Profiles](profiles.md) · [Terminal UI](tui.md) · [Reference](reference.md) · [Troubleshooting](troubleshooting.md) · [Security](security.md)

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
