# Security

← [README](../README.md) · [Workflow](workflow.md) · [Profiles](profiles.md) · [Terminal UI](tui.md) · [Reference](reference.md) · [Troubleshooting](troubleshooting.md) · [Security](security.md)

Agents run with Coi's isolation, and with whatever access you give them in
`~/.coi/config.toml` (network mode, env vars, mounted secrets). `bypass` only
means they don't ask before acting inside their container.

`rcoi` adds no access of its own. It's an SSH login as the Coi user plus one
command. Whoever can run `rcoi` against a host can already SSH to it. There's
no Incus API exposed to the network (`incus remote` would make the laptop an
Incus admin of the host, which is root-equivalent there).
