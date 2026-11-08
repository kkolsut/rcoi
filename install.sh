#!/usr/bin/env bash
# install.sh - install rcoi (Linux, macOS).
#
# On your machine (laptop/workstation):
#   ./install.sh --host user@agent-host     rcoi + git-agent into ~/.local/bin, set the agent host
#   ./install.sh                            update them, keep the host setting
#   ./install.sh --uninstall                remove them (the host setting stays)
#
# On the agent host (the machine running Coi + Incus):
#   ./install.sh --agent-host               coi-task into /usr/local/bin (uses sudo if needed)
#   ./install.sh --agent-host --uninstall
#
#   --prefix DIR   install somewhere else
set -euo pipefail

usage() { sed -n '2,13s/^# \{0,1\}//p' "$0"; }
say() { echo "install: $*"; }
die() { echo "install: $*" >&2; exit 1; }

here=$(cd "$(dirname "$0")" && pwd)
prefix=""
host=""
uninstall=0
side=client

while [[ $# -gt 0 ]]; do
  case $1 in
    --host) [[ $# -ge 2 && -n $2 ]] || die "--host needs user@host"; host=$2; shift 2 ;;
    --prefix) [[ $# -ge 2 && -n $2 ]] || die "--prefix needs a directory"; prefix=$2; shift 2 ;;
    --agent-host) side=agent; shift ;;
    --uninstall) uninstall=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[[ -z $host || $host =~ ^[A-Za-z0-9._@-]+$ ]] || die "odd host '$host' (expected user@host)"
[[ $side == client || -z $host ]] || die "--host is for your machine, not for --agent-host"

if [[ $side == agent ]]; then
  tools="coi-task"
  prefix=${prefix:-/usr/local/bin}   # on the PATH of non-interactive SSH sessions
else
  tools="rcoi git-agent"
  prefix=${prefix:-$HOME/.local/bin}
fi

# Use sudo only when we can't write the target directory (or, if it doesn't
# exist yet, the nearest parent that does).
writable() {
  local d=$prefix
  while [[ ! -e $d ]]; do d=$(dirname "$d"); done
  [[ -w $d ]]
}
run() { if writable; then "$@"; else sudo "$@"; fi; }

if ((uninstall)); then
  for t in $tools; do
    if [[ -e $prefix/$t ]]; then run rm -f "$prefix/$t"; say "removed $prefix/$t"; fi
  done
  [[ $side == agent ]] || say "kept ${XDG_CONFIG_HOME:-$HOME/.config}/rcoi/host (delete it yourself if you like)"
  exit 0
fi

writable || say "$prefix is not writable for you, using sudo"
run mkdir -p "$prefix"
for t in $tools; do
  [[ -f $here/$t ]] || die "$here/$t is missing - run install.sh from the rcoi folder"
  run install -m 0755 "$here/$t" "$prefix/$t"
  say "installed $prefix/$t"
done

# ---------------------------------------------------------------- agent host
if [[ $side == agent ]]; then
  missing=""
  for c in coi incus git jq flock; do
    command -v "$c" >/dev/null || missing="$missing $c"
  done
  if [[ -n $missing ]]; then
    say "coi-task also needs:$missing (jq and flock (util-linux) come with your distro)"
  else
    say "coi, incus, git, jq and flock found - coi-task is ready (coi-task help)"
  fi
  [[ ${SHELL##*/} == bash ]] || say "note: rcoi expects bash as this user's login shell (it is ${SHELL##*/})"
  exit 0
fi

# ------------------------------------------------------------- your machine
conf="${XDG_CONFIG_HOME:-$HOME/.config}/rcoi/host"
if [[ -n $host ]]; then
  mkdir -p "$(dirname "$conf")"
  echo "$host" >"$conf"
  say "agent host: $host ($conf)"
elif [[ -r $conf ]]; then
  read -r host <"$conf" || true
  say "agent host: ${host:-<empty>} (kept, from $conf)"
else
  say "no agent host yet: rerun with --host user@host (or set RCOI_HOST)"
fi

# PATH: the scripts must be found by name (git finds git-agent as `git agent`)
case ":$PATH:" in
  *":$prefix:"*) ;;
  *)
    case ${SHELL##*/} in
      zsh) rc="~/.zshrc" ;;
      bash) if [[ $(uname -s) == Darwin ]]; then rc="~/.bash_profile"; else rc="~/.bashrc"; fi ;;
      *) rc="your shell's startup file" ;;
    esac
    say "$prefix is not on your PATH; add this line to $rc and open a new terminal:"
    echo "    export PATH=\"$prefix:\$PATH\""
    ;;
esac

# Can we reach the host without a password? (git agent and pipes need that)
[[ -n $host ]] || exit 0
if ssh -o BatchMode=yes -o ConnectTimeout=5 -o LogLevel=ERROR "$host" true 2>/dev/null; then
  missing=$(ssh -o BatchMode=yes -o LogLevel=ERROR "$host" \
    'for c in coi coi-task; do command -v "$c" >/dev/null || printf "%s " "$c"; done' 2>/dev/null || true)
  if [[ -z $missing ]]; then
    say "ssh to $host works, coi and coi-task found there - try: rcoi task list"
  else
    say "ssh to $host works, but not on its PATH there: $missing"
    say "(copy this folder there and run: ./install.sh --agent-host)"
  fi
else
  say "can't log in to $host without a password yet; set up a key, e.g.:"
  echo "    ssh-copy-id $host"
fi
