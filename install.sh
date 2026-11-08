#!/usr/bin/env bash
# install.sh - install rcoi and git-agent for the current user (Linux, macOS).
#
#   ./install.sh --host user@agent-host     install + set the agent host
#   ./install.sh                            install/update, keep the host setting
#   ./install.sh --prefix /usr/local/bin    somewhere else than ~/.local/bin
#   ./install.sh --uninstall                remove the scripts (the host setting stays)
#
# Only copies two scripts and writes ~/.config/rcoi/host. No sudo needed
# unless --prefix points at a system directory.
set -euo pipefail

usage() { sed -n '2,10s/^# \{0,1\}//p' "$0"; }
say() { echo "install: $*"; }
die() { echo "install: $*" >&2; exit 1; }

here=$(cd "$(dirname "$0")" && pwd)
prefix="$HOME/.local/bin"
host=""
uninstall=0
tools="rcoi git-agent"

while [[ $# -gt 0 ]]; do
  case $1 in
    --host) [[ $# -ge 2 && -n $2 ]] || die "--host needs user@host"; host=$2; shift 2 ;;
    --prefix) [[ $# -ge 2 && -n $2 ]] || die "--prefix needs a directory"; prefix=$2; shift 2 ;;
    --uninstall) uninstall=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[[ -z $host || $host =~ ^[A-Za-z0-9._@-]+$ ]] || die "odd host '$host' (expected user@host)"
conf="${XDG_CONFIG_HOME:-$HOME/.config}/rcoi/host"

if ((uninstall)); then
  for t in $tools; do
    if [[ -e $prefix/$t ]]; then rm -f "$prefix/$t"; say "removed $prefix/$t"; fi
  done
  say "kept $conf (delete it yourself if you like)"
  exit 0
fi

# Scripts
mkdir -p "$prefix"
for t in $tools; do
  [[ -f $here/$t ]] || die "$here/$t is missing - run install.sh from the rcoi folder"
  install -m 0755 "$here/$t" "$prefix/$t"
  say "installed $prefix/$t"
done

# Host setting, shared by rcoi and git agent
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

# Can we reach the host without a password? (scripts and pipes need that)
[[ -n $host ]] || exit 0
if ssh -o BatchMode=yes -o ConnectTimeout=5 -o LogLevel=ERROR "$host" true 2>/dev/null; then
  missing=$(ssh -o BatchMode=yes -o LogLevel=ERROR "$host" \
    'for c in coi coi-task; do command -v "$c" >/dev/null || printf "%s " "$c"; done' 2>/dev/null || true)
  if [[ -z $missing ]]; then
    say "ssh to $host works, coi and coi-task found there - try: rcoi list"
  else
    say "ssh to $host works, but not on its PATH there: $missing"
  fi
else
  say "can't log in to $host without a password yet; set up a key, e.g.:"
  echo "    ssh-copy-id $host"
fi
