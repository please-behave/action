"""Offline tests of the public Action installer and its execution command."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.path_file = self.root / "github-path"
        self.env = dict(os.environ, PATH=str(self.tools) + os.pathsep + os.environ["PATH"],
                        RUNNER_TEMP=str(self.root), RUNNER_OS="Linux", RUNNER_ARCH="X64",
                        PLEASE_VERSION="v1.2.3", PLEASE_RUN="false", GITHUB_PATH=str(self.path_file),
                        ASSETS=str(self.assets), DOWNLOADS=str(self.root / "downloads"),
                        INVOCATION=str(self.root / "invocation"))
        curl = self.tools / "curl"
        curl.write_text('#!/bin/bash\nset -eu\nurl="${@: -3:1}"\nprintf "%s\\n" "$url" >> "$DOWNLOADS"\ncp "$ASSETS/${url##*/}" "${@: -1}"\n')
        curl.chmod(0o755)
        self.archive("x86_64-unknown-linux-gnu")

    def archive(self, target, version="v1.2.3", member="please", kind=tarfile.REGTYPE):
        name = f"please-{version}-{target}"
        data = b'#!/bin/sh\nprintf "%s\\n" "$@" > "$INVOCATION"\nexit "${RESULT:-0}"\n'
        with tarfile.open(self.assets / f"{name}.tar.gz", "w:gz") as archive:
            info = tarfile.TarInfo(f"{name}/{member}")
            info.type = kind
            if kind == tarfile.SYMTYPE:
                info.linkname = "missing"
            info.size = len(data)
            info.mode = 0o755
            archive.addfile(info, io.BytesIO(data))
        digest = hashlib.sha256((self.assets / f"{name}.tar.gz").read_bytes()).hexdigest()
        (self.assets / "SHA256SUMS").write_text(f"{digest}  {name}.tar.gz\n")

    def install(self, **env):
        return subprocess.run(["bash", str(ROOT / "scripts/install.sh")],
                              env=dict(self.env, **env), capture_output=True, text=True)

    def test_install_only_exports_path_without_execution(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = Path(self.path_file.read_text().strip()) / "please"
        self.assertTrue(os.access(installed, os.X_OK))
        self.assertFalse((self.root / "invocation").exists())
        self.assertFalse(list(self.root.glob("please-download.*")))
        # A new process consumes GITHUB_PATH, as a subsequent workflow step does.
        result = subprocess.run(["bash", "-c", "command -v please"],
                                env=dict(self.env, PATH=str(installed.parent) + os.pathsep + self.env["PATH"]),
                                capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), str(installed))

    def test_execution_point_is_one_argument_and_status_is_preserved(self):
        self.assertEqual(self.install().returncode, 0)
        metadata = (ROOT / "action.yml").read_text()
        self.assertIn("if: inputs.run == 'true'", metadata)
        command = metadata.split("      run: ")[-1].strip()
        for point, status in (("check", 0), ("custom", 0),
                              ("check", 1), ("custom", 2), ("custom", 7),
                              ('custom point; $(touch unexpected)', 2)):
            with self.subTest(point=point, status=status):
                invocation = self.root / "invocation"
                result = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", command],
                                        env=dict(self.env, PATH=self.path_file.read_text().strip() + os.pathsep + self.env["PATH"],
                                                 PLEASE_EXECUTION_POINT_INPUT=point, RESULT=str(status)),
                                        cwd=self.root, capture_output=True, text=True)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(invocation.read_text().splitlines(), ["run", "--at", point])
                self.assertFalse((self.root / "unexpected").exists())

    def test_arm64_archive(self):
        self.archive("aarch64-unknown-linux-gnu")
        self.assertEqual(self.install(RUNNER_ARCH="ARM64").returncode, 0)

    def test_exact_version_selects_cli_release_urls(self):
        self.archive("x86_64-unknown-linux-gnu", version="v2.3.4")
        result = self.install(PLEASE_VERSION="v2.3.4", PLEASE_RUN="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        base = "https://github.com/please-behave/cli/releases/download/v2.3.4"
        self.assertEqual((self.root / "downloads").read_text().splitlines(), [
            f"{base}/please-v2.3.4-x86_64-unknown-linux-gnu.tar.gz", f"{base}/SHA256SUMS"])
        self.assertFalse((self.root / "invocation").exists())

    def test_missing_or_symlink_executable_is_rejected(self):
        for member, kind in (("wrong-name", tarfile.REGTYPE), ("please", tarfile.SYMTYPE)):
            with self.subTest(member=member, kind=kind):
                self.archive("x86_64-unknown-linux-gnu", member=member, kind=kind)
                result = self.install()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.path_file.exists())
                self.assertFalse(list(self.root.glob("please-download.*")))

    def test_corrupt_archive_is_rejected_after_checksum_verification(self):
        archive = next(self.assets.glob("*.tar.gz"))
        archive.write_bytes(b"not a gzip archive")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (self.assets / "SHA256SUMS").write_text(f"{digest}  {archive.name}\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.path_file.exists())
        self.assertFalse(list(self.root.glob("please-download.*")))

    def test_invalid_inputs_and_platforms_fail_before_installation(self):
        for env in ({"PLEASE_VERSION": ""}, {"PLEASE_VERSION": "latest"},
                    {"PLEASE_VERSION": "v1.2.3;echo injected"},
                    {"PLEASE_VERSION": "v01.2.3"}, {"PLEASE_VERSION": "v1.2.3-rc.1"}, {"PLEASE_RUN": "yes"},
                    {"RUNNER_OS": "macOS"}, {"RUNNER_ARCH": "other"}):
            with self.subTest(env=env):
                result = self.install(**env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("::error::", result.stderr)
                self.assertFalse(self.path_file.exists())
                self.assertFalse((self.root / "downloads").exists())

    def test_download_and_checksum_failures_do_not_export_path(self):
        valid = (self.assets / "SHA256SUMS").read_text()
        for sums in ("", valid * 2, valid.replace("x86_64", "wrong"),
                     "0" * 64 + "  please-v1.2.3-x86_64-unknown-linux-gnu.tar.gz\n"):
            (self.assets / "SHA256SUMS").write_text(sums)
            result = self.install()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Please Behave installation failed", result.stderr)
            self.assertFalse(self.path_file.exists())
        (self.assets / "SHA256SUMS").write_text(valid)
        next(self.assets.glob("*.tar.gz")).unlink()
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse(self.path_file.exists())
        self.archive("x86_64-unknown-linux-gnu")
        (self.assets / "SHA256SUMS").unlink()
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse(self.path_file.exists())


if __name__ == "__main__":
    unittest.main()
