#!/usr/bin/env bash
# install.sh - install rcoi (Linux, macOS).
#
# On your machine (laptop/workstation):
#   ./install.sh --host user@agent-host     rcoi, git-agent, rcoi-tui into ~/.local/bin, set the agent host
#   ./install.sh                            update them, keep the host setting
#   ./install.sh --uninstall                remove them (the host setting stays)
#   Then it checks coi-task on the agent host and, if it's missing or differs
#   from this folder's, offers to install it there (over SSH, sudo asks there):
#     --update-host  without asking        --no-host  don't check the host
#
# On the agent host (the machine running Coi + Incus):
#   ./install.sh --agent-host               coi-task into /usr/local/bin (uses sudo if needed)
#   ./install.sh --agent-host --uninstall
#
#   --prefix DIR   install somewhere else
set -euo pipefail

usage() { sed -n '2,16s/^# \{0,1\}//p' "$0"; }
say() { echo "install: $*"; }
die() { echo "install: $*" >&2; exit 1; }

here=$(cd "$(dirname "$0")" && pwd)
prefix=""
host=""
uninstall=0
side=client
host_mode=ask   # ask | yes | no: update coi-task on the agent host

while [[ $# -gt 0 ]]; do
  case $1 in
    --host) [[ $# -ge 2 && -n $2 ]] || die "--host needs user@host"; host=$2; shift 2 ;;
    --prefix) [[ $# -ge 2 && -n $2 ]] || die "--prefix needs a directory"; prefix=$2; shift 2 ;;
    --agent-host) side=agent; shift ;;
    --uninstall) uninstall=1; shift ;;
    --update-host) host_mode=yes; shift ;;
    --no-host) host_mode=no; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[[ -z $host || $host =~ ^[A-Za-z0-9._@-]+$ ]] || die "odd host '$host' (expected user@host)"
[[ $side == client || -z $host ]] || die "--host is for your machine, not for --agent-host"
[[ $side == client || $host_mode == ask ]] || die "--update-host/--no-host are for your machine, not for --agent-host"

if [[ $side == agent ]]; then
  tools="coi-task"
  prefix=${prefix:-/usr/local/bin}   # on the PATH of non-interactive SSH sessions
else
  tools="rcoi git-agent rcoi-tui"
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
command -v python3 >/dev/null || say "note: rcoi-tui needs python3 (the other tools don't)"
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
[[ -n $host && $host_mode != no ]] || exit 0
SSH=(ssh -o LogLevel=ERROR)
if ! "${SSH[@]}" -o BatchMode=yes -o ConnectTimeout=5 "$host" true 2>/dev/null; then
  say "can't log in to $host without a password yet; set up a key, e.g.:"
  echo "    ssh-copy-id $host"
  exit 0
fi
"${SSH[@]}" -o BatchMode=yes "$host" 'command -v coi >/dev/null' \
  || say "note: coi is not on the PATH on $host (install Coi there first)"

# ------------------------------------------------- coi-task on the agent host
# Same file as this folder's? Compared by checksum; the host is Linux.
sum() { if command -v sha256sum >/dev/null; then sha256sum; else shasum -a 256; fi | cut -d' ' -f1; }
mine=$(sum <"$here/coi-task")
# One line from the host: "<path> <checksum>", or nothing if coi-task isn't there.
info=$("${SSH[@]}" -o BatchMode=yes "$host" \
  'p=$(command -v coi-task) && printf "%s %s\n" "$p" "$(sha256sum <"$p" | cut -d" " -f1)"' 2>/dev/null || true)
remote_path=${info%% *} theirs=${info#* }
if [[ -n $info && $theirs == "$mine" ]]; then
  say "coi-task on $host is up to date ($remote_path) - try: rcoi task list"
  exit 0
fi
# Where to put it: where it is now, else /usr/local/bin (on the PATH of
# non-interactive SSH sessions, which is how rcoi runs it).
dest=${remote_path:-/usr/local/bin/coi-task}
[[ -n $info ]] || remote_path=""
[[ $dest =~ ^/[A-Za-z0-9._/-]+$ ]] || die "odd coi-task path on $host: '$dest'"
if [[ -n $remote_path ]]; then
  say "coi-task on $host ($dest) differs from this folder's"
else
  say "coi-task is not installed on $host"
fi

case $host_mode in
  yes) ;;
  ask)
    if [[ ! -t 0 ]]; then
      say "not a terminal, so not asking: update it with ./install.sh --update-host"
      exit 0
    fi
    read -r -p "install: install it to $host:$dest now (sudo may ask for your password there)? [Y/n] " ans
    if [[ $ans == [nN]* ]]; then
      say "left as it is; later: ./install.sh --update-host"
      exit 0
    fi
    ;;
esac

# Copy to a temp file there, then install it with sudo only if the folder
# isn't writable. -t gives sudo a terminal for its password prompt.
tmp=$("${SSH[@]}" -o BatchMode=yes "$host" 'mktemp "${TMPDIR:-/tmp}/coi-task.XXXXXX"') \
  || die "can't create a temp file on $host"
[[ $tmp =~ ^/[A-Za-z0-9._/-]+$ ]] || die "odd temp file on $host: '$tmp'"
scp -q -o LogLevel=ERROR "$here/coi-task" "$host:$tmp" || die "copying coi-task to $host failed"
tty=-T; [[ -t 0 && -t 1 ]] && tty=-t
# shellcheck disable=SC2029  # expands here on purpose; $dest and $tmp are checked above
if ! "${SSH[@]}" "$tty" "$host" "d=\$(dirname $dest); mkdir -p \"\$d\" 2>/dev/null; \
    if [ -w \"\$d\" ]; then install -m 0755 $tmp $dest; else sudo install -m 0755 $tmp $dest; fi; \
    rc=\$?; rm -f $tmp; exit \$rc"; then
  die "installing coi-task on $host failed (above)"
fi
now=$("${SSH[@]}" -o BatchMode=yes "$host" "sha256sum <$dest | cut -d' ' -f1" 2>/dev/null || true)
[[ $now == "$mine" ]] || die "coi-task on $host still differs after installing - check $host:$dest"
say "installed coi-task on $host ($dest) - try: rcoi task list"
