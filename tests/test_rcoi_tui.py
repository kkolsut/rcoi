"""Tests for rcoi-tui: python3 -m unittest discover tests

The end-to-end tests run the real UI in a pseudo-terminal, against fake rcoi
and git-agent scripts placed next to a copy of rcoi-tui (it prefers those over
the PATH), so nothing talks to an agent host.
"""
import importlib.machinery
import importlib.util
import os
import pty
import select
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "rcoi-tui")


def load():
    loader = importlib.machinery.SourceFileLoader("rcoi_tui", SCRIPT)
    spec = importlib.util.spec_from_loader("rcoi_tui", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


tui = load()

LIST = textwrap.dedent("""\
    /home/u/src/demo                             620f572 [main]
    /home/u/src/demo-tui                         620f572 [agent/tui]   session: coi-966d85eb-1 running
    /home/u/src/demo-red-giant                   643b721 [agent/red-giant]   profile: research   session: coi-b4-1 frozen, coi-b4-2 stopped
    /home/u/src/demo-new-ui                      643b721 [agent/new-ui]   profile: codex
    """)


class ParseTest(unittest.TestCase):
    def test_task_list(self):
        tasks, repos = tui.parse_task_list(LIST)
        self.assertEqual(repos, ["demo"])
        self.assertEqual(sorted(tasks), [("demo", "new-ui"), ("demo", "red-giant"), ("demo", "tui")])
        t = tasks[("demo", "tui")]
        self.assertEqual((t.worktree, t.profile, t.session), ("/home/u/src/demo-tui", "", ("coi-966d85eb-1", "running")))
        r = tasks[("demo", "red-giant")]
        self.assertEqual((r.profile, r.state), ("research", "frozen"))
        self.assertEqual(len(r.sessions), 2)
        self.assertEqual(tasks[("demo", "new-ui")].state, "stopped")

    def test_gone(self):
        tasks, _ = tui.parse_task_list(LIST)
        t = tasks[("demo", "tui")]
        t.gone = True
        self.assertEqual(t.state, "no agent")

    def test_no_tmux_message(self):
        # What coi printed when an agent had killed its own tmux server.
        out = "can't find session: coi-coi-966d85eb-1\n\nNo tmux session found in container.\n"
        self.assertTrue(tui.NO_TMUX_RE.search(out))
        self.assertFalse(tui.NO_TMUX_RE.search("╭ Claude Code ╮\n> \n  bypass permissions on\n"))

    def test_clean(self):
        self.assertEqual(tui.clean("\x1b[31mred\x1b[0m\tx\r\n"), "red    x")

    def test_find_clones(self):
        d = tempfile.mkdtemp(prefix="rcoi-tui-clones-")
        self.addCleanup(shutil.rmtree, d, True)
        def repo(path, url=None):
            os.makedirs(path)
            subprocess.run(["git", "init", "-q", path], check=True)
            if url:
                subprocess.run(["git", "-C", path, "remote", "add", "agentvm", url], check=True)
        repo(os.path.join(d, "a"), "me@host:src/alpha")
        repo(os.path.join(d, "group", "b"), "me@host:src/beta.git")
        repo(os.path.join(d, "c"))                              # no agentvm remote
        repo(os.path.join(d, "dup"), "me@host:src/alpha")
        found = tui.find_clones([d])
        self.assertEqual(found, {"alpha": os.path.join(d, "a"), "beta": os.path.join(d, "group", "b")})
        # The repo we're in wins over another clone of the same host repo.
        self.assertEqual(tui.find_clones([d], os.path.join(d, "dup"))["alpha"], os.path.join(d, "dup"))

    def test_valid_name(self):
        self.assertTrue(tui.valid_name("red-giant_2.x"))
        for bad in ("", ".hidden", "a b", "a/b", "$(x)"):
            self.assertFalse(tui.valid_name(bad), bad)


FAKE_RCOI = r"""#!/usr/bin/env bash
printf '%s\n' "rcoi $*" >>"$FAKE_LOG"
case "$1 $2" in
  "task list") cat "$FAKE_DIR/list" ;;
  "task peek")
    if [[ $4 == dead ]]; then
      echo "can't find session: coi-coi-dead-1" >&2; echo "No tmux session found in container." >&2; exit 1
    fi
    echo "AGENT SCREEN OF $4"; echo "  bypass permissions on" ;;
  "task wip") echo " M file.txt"; echo "+WIP LINE" ;;
esac
exit 0
"""

FAKE_GIT_AGENT = r"""#!/usr/bin/env bash
printf '%s\n' "git agent $*" >>"$FAKE_LOG"
printf '%s @ %s\n' "git agent $*" "${PWD##*/}" >>"$FAKE_LOG.cwd"
echo "fake git agent $1: ok"
"""


class TuiTest(unittest.TestCase):
    """The UI in a pty, driven by keystrokes."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="rcoi-tui-test-")
        bin_ = os.path.join(self.d, "bin")
        os.mkdir(bin_)
        shutil.copy(SCRIPT, bin_)
        for name, body in (("rcoi", FAKE_RCOI), ("git-agent", FAKE_GIT_AGENT)):
            p = os.path.join(bin_, name)
            with open(p, "w") as f:
                f.write(body)
            os.chmod(p, 0o755)
        self.log = os.path.join(self.d, "calls")
        open(self.log, "w").close()

        # The "host": a repo with main and agent/work, agent/dead, as git agent would fetch.
        host = os.path.join(self.d, "src", "demo")
        g = lambda *a, cwd=host: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                                                 "-c", "init.defaultBranch=main"] + list(a), cwd=cwd,
                                                check=True, capture_output=True)
        os.makedirs(host)
        g("init", "-q")
        g("commit", "-q", "--allow-empty", "-m", "base")
        for task in ("work", "dead"):
            g("branch", "agent/" + task)
            g("switch", "-q", "agent/" + task)
            g("commit", "-q", "--allow-empty", "-m", "agent commit on " + task)
            g("switch", "-q", "main")
        # The laptop's clone, named differently: the repo name comes from the remote.
        self.repo = os.path.join(self.d, "laptop", "laptop-clone")
        os.makedirs(os.path.dirname(self.repo))
        g("clone", "-q", "-o", "agentvm", host, self.repo, cwd=self.d)
        g("branch", "review/work", "agentvm/agent/work", cwd=self.repo)

        # A second repo with a clone one level deeper (laptop/group/other-clone),
        # and a third one with no clone at all.
        other = os.path.join(self.d, "src", "other")
        os.makedirs(other)
        g("init", "-q", cwd=other)
        g("commit", "-q", "--allow-empty", "-m", "base", cwd=other)
        g("branch", "agent/feat", cwd=other)
        g("clone", "-q", "-o", "agentvm", other, os.path.join(self.d, "laptop", "group", "other-clone"), cwd=self.d)
        lone = os.path.join(self.d, "src", "lone")

        with open(os.path.join(self.d, "list"), "w") as f:
            f.write("%s 1 [main]\n" % host)
            f.write("%s-work 1 [agent/work]   session: coi-work-1 running\n" % host)
            f.write("%s-dead 1 [agent/dead]   session: coi-dead-1 running\n" % host)
            f.write("%s 1 [main]\n" % other)
            f.write("%s-feat 1 [agent/feat]   session: coi-feat-1 running\n" % other)
            f.write("%s 1 [main]\n" % lone)
            f.write("%s-solo 1 [agent/solo]\n" % lone)
        self.bin = bin_

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def calls(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def start(self, *args):
        env = dict(os.environ, RCOI_HOST="fake@host", FAKE_LOG=self.log, FAKE_DIR=self.d,
                   RCOI_TUI_ROOTS=os.path.join(self.d, "laptop"), RCOI_TUI_STATUS_SECS="1",
                   TERM="xterm-256color", LINES="40", COLUMNS="140", ESCDELAY="25")
        env.pop("RCOI_SSH_OPTS", None)
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(self.repo)
            os.execve(os.path.join(self.bin, "rcoi-tui"), ["rcoi-tui", "--no-mux", "--interval", "0.5"] + list(args), env)
        self.pid, self.fd, self.out = pid, fd, b""
        import fcntl, struct, termios
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))
        self.addCleanup(self.stop)

    def read(self, secs=0.3):
        end = time.time() + secs
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if r:
                try:
                    self.out += os.read(self.fd, 65536)
                except OSError:
                    return

    def wait_for(self, text, secs=10):
        end = time.time() + secs
        while time.time() < end:
            self.read(0.1)
            if text.encode() in self.out:
                return
        self.fail("never saw %r; got tail:\n%s" % (text, self.out[-2000:].decode("utf-8", "replace")))

    def ready(self):
        """Tasks sort by name (dead, work); "dead" is selected first."""
        self.wait_for("tmux session is gone")

    def wait_call(self, call, secs=10):
        end = time.time() + secs
        while time.time() < end:
            self.read(0.1)
            if call in self.calls():
                return
        self.fail("%r not called; calls: %s" % (call, self.calls()))

    def key(self, s):
        os.write(self.fd, s.encode())
        self.read(0.3)

    def stop(self):
        if self.fd is None:
            return
        try:
            os.write(self.fd, b"q")
        except OSError:
            pass
        for _ in range(50):
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.exit = os.waitstatus_to_exitcode(status)
                break
            self.read(0.1)
        else:
            os.kill(self.pid, 9)
            os.waitpid(self.pid, 0)
            self.exit = None
        os.close(self.fd)
        self.fd = None

    def test_shows_tasks_screen_and_quits(self):
        self.start()
        self.wait_for("repo: demo")             # named after the remote, not the folder
        self.ready()
        self.key("j")
        self.wait_for("AGENT SCREEN OF work")
        self.assertIn("rcoi task list", self.calls())
        self.assertNotIn(b"AGENT SCREEN OF feat", self.out)     # other repos stay hidden
        self.stop()
        self.assertEqual(self.exit, 0)

    def test_dead_agent_is_flagged_and_restarted(self):
        self.start()
        self.ready()
        self.wait_for("no agent")
        self.key("u")
        self.wait_for("restart it? [y/N]")
        self.key("y\r")
        self.wait_call("rcoi task shell demo dead --bg")
        calls = self.calls()
        self.assertLess(calls.index("rcoi task stop demo dead"), calls.index("rcoi task shell demo dead --bg"))

    def test_git_agent_actions_for_local_repo(self):
        self.start()
        self.ready()
        self.key("j")                           # work
        self.wait_for("AGENT SCREEN OF work")
        self.key("p")
        self.wait_call("git agent pull work")
        self.wait_for("pull work: done")
        self.key("P")
        self.wait_for("[y/N]")
        self.key("y\r")
        self.wait_call("git agent push work")
        self.wait_for("push work: done")
        self.key("X")
        self.wait_for("and review/work in laptop-clone?")
        self.key("y\r")
        self.wait_call("git agent drop work -y")
        self.assertNotIn("rcoi task drop demo work -y", self.calls())

    def test_new_task_goes_through_git_agent(self):
        self.start()
        self.ready()
        self.key("n")
        self.wait_for("name:")
        self.key("fresh\r")
        self.wait_for("the default")            # curses redraws only what changed: match the tails
        self.key("codex\r")
        self.wait_for("just start it")
        self.key("fix $(rm -rf ~) and `x`\r")   # passed as one argument, never through a shell
        self.wait_call("git agent new fresh --profile codex --bg -p fix $(rm -rf ~) and `x`")

    def test_wip_view(self):
        self.start()
        self.ready()
        self.key("j")
        self.key("w")
        self.wait_for("+WIP LINE")
        self.assertIn("rcoi task wip demo work", self.calls())
        self.key("q")
        self.wait_for("AGENT SCREEN OF work")

    def cwd_calls(self):
        try:
            with open(self.log + ".cwd") as f:
                return f.read().splitlines()
        except FileNotFoundError:
            return []

    def test_pick_another_repo_and_act_in_its_clone(self):
        self.start()
        self.ready()
        self.key("R")
        self.wait_for("show the tasks of")
        self.wait_for("other-clone")            # the chooser shows where each clone is
        self.wait_for("(no local clone)")       # lone
        self.key("o\r")                         # jump to "other"
        self.wait_for("repo: other")
        self.wait_for("AGENT SCREEN OF feat")
        self.key("p")
        self.wait_call("git agent pull feat")
        self.assertIn("git agent pull feat @ other-clone", self.cwd_calls())

    def test_R_then_enter_shows_all_repos(self):
        self.start()
        self.ready()
        self.assertNotIn(b"feat", self.out)
        self.key("R")
        self.wait_for("(shown now)")            # demo, the current view
        self.key("\r")                          # starts on "(all repos)"
        self.wait_for("all repos")
        self.wait_for("feat")
        self.wait_for("solo")
        self.wait_for("one repo")               # the menu says what A does next

    def test_status_clears_and_keys_stay(self):
        self.start()
        self.ready()
        self.key("j")
        self.key("p")
        self.wait_for("pull work: done")
        self.out = b""
        self.read(2.5)                          # RCOI_TUI_STATUS_SECS=1
        self.assertIn("─" * 20, self.out.decode("utf-8", "replace"))   # the rule is back
        self.key("A")
        self.wait_for("all repos")

    def test_all_repos_and_a_repo_without_clone(self):
        self.start()
        self.ready()
        self.key("A")
        self.wait_for("all repos")
        self.wait_for("solo")
        self.key("G")                           # sorted: demo first (we're in it), then lone, other
        self.key("k")                           # lone/solo
        self.wait_for("lone: no local clone found")
        self.key("d")
        self.wait_for("no local clone of lone found")
        self.key("X")
        self.wait_for("[y/N]")
        self.key("y\r")
        self.wait_call("rcoi task drop lone solo -y")   # without a clone: rcoi task, not git agent
        self.key("A")
        self.wait_for("repo: lone")             # A from all: the selected task's repo

    def test_cancel_drop_runs_nothing(self):
        self.start()
        self.ready()
        self.key("X")
        self.wait_for("[y/N]")
        self.key("\r")
        self.read(1)
        self.assertFalse([c for c in self.calls() if "drop" in c])


if __name__ == "__main__":
    unittest.main()
