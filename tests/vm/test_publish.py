# SPDX-License-Identifier: Apache-2.0
"""scripts/ci-publish.sh: the VM jobs of one ISO publish to ci-screens at once, and none is lost."""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci-publish.sh"


def git(*args: str, cwd: pathlib.Path | None = None, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout


@unittest.skipUnless(shutil.which("git"), "needs git")
class PublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.remote = self.tmp / "remote.git"
        git("init", "-q", "--bare", "-b", "ci-screens", str(self.remote))
        # like GitHub's runners: no git identity anywhere, and none guessed from the host name
        config = self.tmp / "gitconfig"
        config.write_text("[user]\n\tuseConfigOnly = true\n")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "EMAIL"))}
        self.env.update(GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM="1", CI_PUBLISH_URL=self.remote.as_uri())
        self.publish("uefi")          # the first publish creates the branch

    def publish(self, name: str, env: dict | None = None) -> str:
        src = self.tmp / "out" / name
        src.mkdir(parents=True, exist_ok=True)
        (src / "README.md").write_text(f"{name}\n")
        r = subprocess.run(["bash", str(SCRIPT), str(src), f"runs/1/{name}", f"screens: run 1 ({name})"],
                           env=env or self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("did not reach", r.stdout)
        return r.stdout

    def published(self) -> list[str]:
        return sorted(git("ls-tree", "-r", "--name-only", "ci-screens", cwd=self.remote).split())

    def test_a_job_that_loses_the_race_still_lands(self):
        # ISO #11: another job pushed between this job's clone and its push; the rebase had no
        # committer, stopped on the other commit, and pushing that commit "succeeded".
        other = self.tmp / "other"
        git("clone", "-q", self.remote.as_uri(), str(other), env=self.env)
        (other / "runs/1/uefi-sb").mkdir(parents=True)
        (other / "runs/1/uefi-sb/README.md").write_text("uefi-sb\n")
        git("add", "-A", cwd=other, env=self.env)
        git("-c", "user.name=other", "-c", "user.email=other@example.org", "commit", "-q", "-m",
            "screens: run 1 (uefi-sb)", cwd=other, env=self.env)
        # the other job pushes right after this job's clone (a hook of the clone stands in for it)
        hooks = self.tmp / "templates/hooks"
        hooks.mkdir(parents=True)
        (hooks / "post-checkout").write_text(
            "#!/bin/sh\n"
            f"[ -e '{self.tmp}/raced' ] && exit 0\n"
            f"touch '{self.tmp}/raced'\n"
            "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE\n"
            f"git -C '{other}' push -q origin HEAD:ci-screens\n")
        (hooks / "post-checkout").chmod(0o755)
        out = self.publish("safe-graphics-uefi", env={**self.env, "GIT_TEMPLATE_DIR": str(self.tmp / "templates")})
        self.assertTrue((self.tmp / "raced").exists())
        self.assertIn("runs/1/safe-graphics-uefi → ci-screens", out)
        self.assertEqual(self.published(), ["runs/1/safe-graphics-uefi/README.md", "runs/1/uefi-sb/README.md",
                                            "runs/1/uefi/README.md"])
        subjects = git("log", "--format=%s", "ci-screens", cwd=self.remote).splitlines()
        self.assertEqual(subjects, ["screens: run 1 (safe-graphics-uefi)", "screens: run 1 (uefi-sb)",
                                    "screens: run 1 (uefi)"])

    def test_nothing_new_is_not_an_error(self):
        self.assertIn("nothing new", self.publish("uefi"))
        self.assertEqual(self.published(), ["runs/1/uefi/README.md"])


if __name__ == "__main__":
    unittest.main()
