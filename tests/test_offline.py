"""Offline unit tests — no network, no venv, no third-party deps.

Run from anywhere:  python3 -m unittest discover -s tests -p "test_offline.py" -v
(CI runs exactly this.)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import dse  # noqa: E402
import _common as C  # noqa: E402


class TestCommonHelpers(unittest.TestCase):
    def test_parse_symbols_normalizes(self):
        self.assertEqual(C.parse_symbols(" gp , squrpharma ,"), ["GP", "SQURPHARMA"])
        self.assertEqual(C.parse_symbols(""), [])

    def test_resolve_bars_periods(self):
        self.assertEqual(C.resolve_bars("1y", None), 252)
        self.assertEqual(C.resolve_bars("6M", None), 126)   # case-insensitive
        self.assertEqual(C.resolve_bars(None, None), 252)   # default period

    def test_resolve_bars_rejects_unknown_period(self):
        with self.assertRaises(SystemExit):
            C.resolve_bars("17y", None)

    def test_resolve_bars_rejects_out_of_range(self):
        for bad in (0, -5, 5001):
            with self.assertRaises(SystemExit):
                C.resolve_bars(None, bad)

    def test_period_map_monotonic(self):
        vals = [v for k, v in C.PERIOD_BARS.items() if k != "max"]  # max is an alias
        self.assertEqual(vals, sorted(vals))

    def test_md_table_shape(self):
        t = C.md_table(["a", "b"], [["1", "2"]])
        lines = t.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("| a | b |"))
        self.assertTrue(lines[1].startswith("| --- | --- |"))


class TestDseModule(unittest.TestCase):
    def test_version_defined(self):
        self.assertRegex(dse.__version__, r"^\d+\.\d+\.\d+$")

    def test_cache_roundtrip(self):
        key = "unit_test_key"
        dse.cache_put(key, '{"ok": true}')
        got = dse.cache_get(key, ttl=60)
        self.assertEqual(json.loads(got), {"ok": True})
        # expired cache misses
        old = os.path.join(dse.CACHE_DIR, key + ".json")
        os.utime(old, (0, 0))
        self.assertIsNone(dse.cache_get(key, ttl=60))
        os.remove(old)

    def test_cache_write_is_atomic_no_tmp_leftover(self):
        dse.cache_put("atomic_test", "x")
        files = os.listdir(dse.CACHE_DIR)
        self.assertIn("atomic_test.json", files)
        self.assertNotIn("atomic_test.json.tmp", files)
        os.remove(os.path.join(dse.CACHE_DIR, "atomic_test.json"))


class TestCliGuardsOffline(unittest.TestCase):
    """CLI input validation must fail BEFORE any network call."""

    def run_cli(self, *argv):
        return subprocess.run([sys.executable, os.path.join(REPO, "dse.py"), *argv],
                              capture_output=True, text=True, timeout=30)

    def test_bars_upper_bound(self):
        r = self.run_cli("history", "GP", "--bars", "99999")
        self.assertEqual(r.returncode, 1)
        self.assertIn("1-5000", r.stderr)
        self.assertEqual(r.stdout, "")  # stdout stays clean

    def test_bars_lower_bound(self):
        r = self.run_cli("history", "GP", "--bars", "0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--bars must be", r.stderr)

    def test_top_bound(self):
        r = self.run_cli("snapshot", "--top", "999")
        self.assertEqual(r.returncode, 1)
        self.assertIn("1-350", r.stderr)

    def test_bad_interval_rejected_before_network(self):
        r = self.run_cli("history", "GP", "--interval", "9z")
        self.assertEqual(r.returncode, 1)
        self.assertIn("interval must be one of", r.stderr)

    def test_version_flag(self):
        r = self.run_cli("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn(dse.__version__, r.stdout)


class TestSetupScriptPipBootstrap(unittest.TestCase):
    """setup.sh must bootstrap pip into a venv that was created without it.

    Ubuntu without python3-venv: `python3 -m venv` exits 0 but the venv has no
    pip and no ensurepip, so the dependency install died with 'No module named
    pip'. The fix detects a pip-less venv and bootstraps pip (ensurepip, then
    get-pip.py). This test simulates the broken distro state deterministically
    with `--without-pip` and stays offline: requirements are replaced with a
    comment-only file so the dependency install is a no-op (only the bootstrap
    is under test; the real smoke test fails harmlessly without pandas).
    """

    def test_bootstraps_pip_into_pipless_venv(self):
        # venv module itself must be available to simulate the broken state
        probe = subprocess.run([sys.executable, "-m", "venv", "--help"],
                               capture_output=True)
        if probe.returncode != 0:
            self.skipTest("venv module unavailable")

        with tempfile.TemporaryDirectory() as td:
            scratch = os.path.join(td, "repo")
            os.makedirs(scratch)
            SKIP = {".venv", ".git", ".github", "cache", "data", "__pycache__"}
            for name in os.listdir(REPO):
                if name in SKIP:
                    continue
                src = os.path.join(REPO, name)
                dst = os.path.join(scratch, name)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            # Simulate the broken distro: venv that "succeeded" without pip
            subprocess.run([sys.executable, "-m", "venv", "--without-pip",
                            os.path.join(scratch, ".venv")], check=True)
            self.assertFalse(os.path.exists(os.path.join(scratch, ".venv", "bin", "pip")))

            # Keep the test offline: comment-only requirements = no-op install
            note = "# deps intentionally omitted: this test exercises pip bootstrap only\n"
            for req in ("requirements.txt", "requirements-lock.txt"):
                with open(os.path.join(scratch, req), "w") as f:
                    f.write(note)

            r = subprocess.run(["bash", os.path.join(scratch, "setup.sh")],
                               capture_output=True, text=True, timeout=120,
                               env={**os.environ, "PYTHON": sys.executable})
            self.assertEqual(
                r.returncode, 0,
                "setup.sh failed on a pip-less venv:\n" + r.stdout + r.stderr)

            q = subprocess.run([os.path.join(scratch, ".venv", "bin", "python"),
                                "-m", "pip", "--version"],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(q.returncode, 0,
                             "pip still missing after setup.sh:\n" + q.stderr)

    def test_existing_healthy_venv_untouched(self):
        """Regression guard: a venv that already has pip must not be recreated."""
        with tempfile.TemporaryDirectory() as td:
            scratch = os.path.join(td, "repo")
            os.makedirs(scratch)
            SKIP = {".venv", ".git", ".github", "cache", "data", "__pycache__"}
            for name in os.listdir(REPO):
                if name in SKIP:
                    continue
                src = os.path.join(REPO, name)
                dst = os.path.join(scratch, name)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            subprocess.run([sys.executable, "-m", "venv",
                            os.path.join(scratch, ".venv")], check=True)
            marker = os.path.join(scratch, ".venv", "bin", "pip")
            self.assertTrue(os.path.exists(marker))

            note = "# deps intentionally omitted\n"
            for req in ("requirements.txt", "requirements-lock.txt"):
                with open(os.path.join(scratch, req), "w") as f:
                    f.write(note)

            r = subprocess.run(["bash", os.path.join(scratch, "setup.sh")],
                               capture_output=True, text=True, timeout=120,
                               env={**os.environ, "PYTHON": sys.executable})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(marker),
                            "setup.sh recreated a venv that already had pip")


if __name__ == "__main__":
    unittest.main()
