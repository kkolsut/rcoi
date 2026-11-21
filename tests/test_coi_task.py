"""Tests for coi-task's agent status: python3 -m unittest discover tests

coi-task runs against a fake `incus` (and `coi`) on the PATH: `incus list`
reports one running container for the task's worktree, and `incus exec ...
tmux capture-pane` prints a prepared screen (or fails like a missing tmux
session does).
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COI_TASK = os.path.join(ROOT, "coi-task")

FAKE_INCUS = r"""#!/usr/bin/env bash
case $1 in
  list) cat "$FAKE_DIR/incus.json" ;;
  exec)
    if [[ -e $FAKE_DIR/no-tmux ]]; then
      echo "can't find session: coi-coi-x-1" >&2; exit 1
    fi
    cat "$FAKE_DIR/screen" ;;
esac
"""

# Screens as the agents draw them (bottom part; trailing blank lines like tmux pads).
CLAUDE_WORKING = """\
● Reading the test suite
✻ Pondering… (12s · ↑ 1.2k tokens · esc to interrupt)

╭────────────────────────────────────────────╮
│ >                                          │
╰────────────────────────────────────────────╯
  ⏵⏵ bypass permissions on (shift+tab to cycle)



"""
CLAUDE_WAITING = """\
● Done: the tests pass and the fix is committed (a1b2c3d).

────────────────────────────────────────────────
❯
────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle)
"""
CLAUDE_ASKING = """\
 Bash command
   rm -rf build/
 Do you want to proceed?
 ❯ 1. Yes
   2. No, and tell Claude what to do differently (esc)
"""
CLAUDE_QUESTION = """\
 Which database should I use?
 ❯ 1. SQLite
   2. Postgres
 Enter to select · ↑/↓ to navigate · Esc to cancel
"""
CODEX_WORKING = """\
• Working (8s • esc to interrupt)

▌ Ask Codex to do anything
  ⏎ send   ⌃J newline   ⌃T transcript   ⌃C quit   98% context left
"""
CODEX_WAITING = """\
• I updated the parser and added tests.

▌ Ask Codex to do anything
  ⏎ send   ⌃J newline   ⌃T transcript   ⌃C quit   97% context left
"""
# "esc to interrupt" further up, in the conversation: only the bottom counts.
OLD_TEXT_ABOVE = "> why does it say esc to interrupt?\n" + "\n".join("line %d" % i for i in range(20)) + "\n" + CLAUDE_WAITING


class AgentStateTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="coi-task-test-")
        self.addCleanup(shutil.rmtree, self.d, True)
        bin_ = os.path.join(self.d, "bin")
        os.mkdir(bin_)
        for name, body in (("incus", FAKE_INCUS), ("coi", "#!/bin/sh\nexit 0\n")):
            p = os.path.join(bin_, name)
            with open(p, "w") as f:
                f.write(body)
            os.chmod(p, 0o755)
        src = os.path.join(self.d, "src")
        repo = os.path.join(src, "demo")
        g = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                                       "-c", "init.defaultBranch=main"] + list(a),
                                      check=True, capture_output=True)
        os.makedirs(repo)
        g("-C", repo, "init", "-q")
        g("-C", repo, "commit", "-q", "--allow-empty", "-m", "base")
        self.wt = os.path.join(src, "demo-fix")
        g("-C", repo, "worktree", "add", "-q", "-b", "agent/fix", self.wt)
        g("-C", self.wt, "commit", "-q", "--allow-empty", "-m", "one")
        g("-C", self.wt, "commit", "-q", "--allow-empty", "-m", "two")
        with open(os.path.join(self.wt, "new.txt"), "w") as f:
            f.write("x")
        self.running(True)
        self.env = dict(os.environ, PATH=bin_ + ":" + os.environ["PATH"], HOME=self.d,
                        COI_TASK_SRC=src, FAKE_DIR=self.d)

    def running(self, up):
        cts = [{"name": "coi-x-1", "status": "Running" if up else "Stopped",
                "devices": {"workspace": {"source": self.wt}}}]
        with open(os.path.join(self.d, "incus.json"), "w") as f:
            json.dump(cts, f)

    def screen(self, text):
        with open(os.path.join(self.d, "screen"), "w") as f:
            f.write(text)

    def coi_task(self, *args):
        p = subprocess.run([COI_TASK] + list(args), env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def state(self, text):
        self.screen(text)
        return self.coi_task("status", "demo", "fix").split("  ")[0].strip()

    def test_states(self):
        for name, text, want in [
            ("claude working", CLAUDE_WORKING, "working"),
            ("claude waiting", CLAUDE_WAITING, "waiting"),
            ("claude permission", CLAUDE_ASKING, "asking"),
            ("claude question", CLAUDE_QUESTION, "asking"),
            ("codex working", CODEX_WORKING, "working"),
            ("codex waiting", CODEX_WAITING, "waiting"),
            ("old text above", OLD_TEXT_ABOVE, "waiting"),
            ("blank screen", "\n\n\n", "starting"),
        ]:
            with self.subTest(name):
                self.assertEqual(self.state(text), want)

    def test_no_agent(self):
        open(os.path.join(self.d, "no-tmux"), "w").close()
        self.assertEqual(self.coi_task("status", "demo", "fix").split("  ")[0].strip(), "no agent")

    def test_stopped_and_work(self):
        self.running(False)
        self.assertEqual(self.coi_task("status", "demo", "fix").split(), ["stopped", "+2", "commits,", "1", "uncommitted"])

    def test_list(self):
        self.screen(CLAUDE_WAITING)
        out = self.coi_task("list")
        line = next(l for l in out.splitlines() if "[agent/fix]" in l)
        self.assertIn("session: coi-x-1 running", line)
        self.assertIn("agent: waiting", line)
        self.assertIn("work: +2 commits, 1 uncommitted", line)
        main = next(l for l in out.splitlines() if "[main]" in l)
        self.assertNotIn("agent:", main)
        self.assertNotIn("work:", main)


if __name__ == "__main__":
    unittest.main()
