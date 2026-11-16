"""`turpin host-install` and `turpin env` (delphside/programme#117, task T8): what the install
script writes and refuses, and which machine a target names.

Test conditions derive from the design (§6's table, §9 *no mutual removal*, §11 *Root-ops and
the allowlist*) and the test design (R37, R38, S41, S42), not from the code. The script is run
by `bash` against a folder that stands for the machine's root, with a `sudo` that only runs
what it is given; the end-to-end runs through `ssh` are the bats tests'.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from unittest import mock

from .test_turpin_core import DELIVER, PROFILE, Isolated

from turpinlib import hosts, profile, settings  # noqa: E402
from turpinlib.commands import host_install  # noqa: E402
from turpinlib.model import BusinessError, CredentialKind, Reason  # noqa: E402

EXTRA = '''
[turpin.ephemeral]
user_prefix = "acme-"
home = "/srv/acme"
secrets = ["ACME_SECRET"]

[[turpin.host_files]]
src = "ops/it's here.sh"
dest = "/opt/acme/two words's.sh"
enable = true
'''


def prof(extra=""):
    return profile.parse(PROFILE + extra, "app-profile.toml")


class Targets(unittest.TestCase):
    def test_every_credential_kind_says_which_tools_it_needs(self):
        self.assertEqual(set(CredentialKind), set(host_install.TOOLS))
        self.assertEqual(("oci",), host_install.TOOLS[CredentialKind.OCI_API_KEY])
        self.assertEqual((), host_install.TOOLS[CredentialKind.DOCKER_CONFIG])

    def test_an_environment_is_its_own_machine_and_login(self):
        machine, login, env = host_install.target_of(prof(), "production")
        self.assertEqual(("acme-prod", CredentialKind.OCI_INSTANCE_PRINCIPAL, "production"),
                         (machine, login, env.name))

    def test_the_copier_and_the_builder_are_named_by_their_machine(self):
        extra = '\n[turpin.release]\ncopy_on = "laptop"\ncopy_login = "oci-api-key"\n'
        text = PROFILE.replace('on = "control-node"', 'on = "builder-vm"\nlogin = "oci-api-key"') + extra
        both = profile.parse(text, "app-profile.toml")
        self.assertEqual(("laptop", CredentialKind.OCI_API_KEY, None), host_install.target_of(both, "laptop"))
        self.assertEqual(("builder-vm", CredentialKind.OCI_API_KEY, None), host_install.target_of(both, "builder-vm"))

    def test_a_name_that_is_neither_is_refused_naming_the_two_it_could_be(self):
        with self.assertRaises(BusinessError) as caught:
            host_install.target_of(prof(), "nowhere")
        self.assertEqual(Reason.ENVIRONMENT_UNKNOWN.value, caught.exception.result.reason)
        self.assertIn("release copier (copy_on) or the builder (build.on)", caught.exception.result.message)


class Script(Isolated):
    """The script, run against a folder standing for the machine's root."""

    def setUp(self):
        super().setUp()
        self.root = self.dir / "root"
        self.root.mkdir()
        bindir = self.dir / "bin"
        bindir.mkdir()
        (bindir / "sudo").write_text('#!/bin/sh\n[ "$1" = -n ] && shift\nexec "$@"\n')
        (bindir / "sudo").chmod(0o755)
        self.path = f"{bindir}{os.pathsep}{os.environ['PATH']}"

    def run_script(self, text, path=None):
        env = {**os.environ, "PATH": path or self.path, "TURPIN_HOST_ROOT": str(self.root),
               "TURPIN_STATE_DIR": str(self.dir / "state")}
        return subprocess.run(["bash", "-s"], input=text, env=env, capture_output=True, text=True)

    def test_an_environment_gets_the_command_the_libraries_and_the_root_owned_files(self):
        done = self.run_script(host_install.script_for(prof(EXTRA), CredentialKind.DOCKER_CONFIG, True))
        self.assertEqual((0, "turpin-host installed\n"), (done.returncode, done.stdout), done.stderr)
        for source, dest in (("turpin-host", "usr/local/bin/turpin-host"), ("lib/common.sh", "usr/local/lib/turpin/common.sh"),
                             ("lib/toml.sh", "usr/local/lib/turpin/toml.sh"),
                             ("lib/toml.awk", "usr/local/lib/turpin/toml.awk"),
                             ("lib/registry.sh", "usr/local/lib/turpin/registry.sh")):
            self.assertEqual((DELIVER / source).read_bytes(), (self.root / dest).read_bytes(), dest)
        self.assertEqual(0o755, (self.root / "usr/local/bin/turpin-host").stat().st_mode & 0o777)
        rule = (self.root / "etc/sudoers.d/turpin-host").read_text()
        self.assertRegex(rule, r"^\S+ ALL=\(root\) NOPASSWD: /usr/local/bin/turpin-host root-ops \*\n$")
        self.assertEqual(0o440, (self.root / "etc/sudoers.d/turpin-host").stat().st_mode & 0o777)
        self.assertEqual("acme-\n", (self.root / "etc/turpin/acme/ephemeral.prefix").read_text())

    def test_a_destination_with_a_space_or_a_quote_stays_one_field_of_the_allowlist(self):
        done = self.run_script(host_install.script_for(prof(EXTRA), CredentialKind.DOCKER_CONFIG, True))
        self.assertEqual(0, done.returncode, done.stderr)
        lines = (self.root / "etc/turpin/acme/host_files.allow").read_text().splitlines()
        self.assertIn("/opt/acme/two words's.sh\tops/it's here.sh\t0644\ttrue", lines)
        self.assertIn("/opt/acme/backup.sh\tops/backup.sh\t0755\tfalse", lines)

    def test_the_allowlist_is_sent_with_the_closing_line_the_host_requires(self):
        text = host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True)
        self.assertIn(f"printf '\\n{hosts.CLOSING_LINE}\\n'", text)

    def test_a_copier_or_a_builder_gets_no_root_owned_file(self):
        done = self.run_script(host_install.script_for(prof(EXTRA), CredentialKind.DOCKER_CONFIG, False))
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertTrue((self.root / "usr/local/bin/turpin-host").exists())
        self.assertEqual([], [p.name for p in (self.root / "etc").glob("*")] if (self.root / "etc").exists() else [])

    def test_a_credential_kind_that_needs_oci_refuses_a_host_without_it_and_installs_with_it(self):
        text = host_install.script_for(prof(), CredentialKind.OCI_INSTANCE_PRINCIPAL, True)
        bare = self.dir / "bare"
        bare.mkdir()
        for tool in ("bash", "sudo", "jq", "flock", "install", "base64", "env", "id", "sed", "printf", "cat", "mkdir",
                     "dirname", "awk", "mktemp", "chmod", "mv", "grep", "head", "rm", "ls", "sort", "date", "tr", "realpath"):
            found = shutil.which(tool, path=self.path)
            if found:
                (bare / tool).symlink_to(found)
        done = self.run_script(text, path=str(bare))
        self.assertEqual(2, done.returncode)
        self.assertIn("oci is missing (needed by the oci-instance-principal login)", done.stderr)
        (bare / "oci").write_text("#!/bin/sh\n")
        (bare / "oci").chmod(0o755)
        self.assertEqual(0, self.run_script(text, path=str(bare)).returncode)

    def test_a_host_without_flock_is_refused(self):
        bare = self.dir / "noflock"
        bare.mkdir()
        for tool in ("bash", "sudo", "jq", "install", "base64", "id", "env"):
            (bare / tool).symlink_to(shutil.which(tool, path=self.path))
        done = self.run_script(host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True), path=str(bare))
        self.assertEqual(2, done.returncode)
        self.assertIn("flock (util-linux) is missing", done.stderr)

    def stubbed(self, **bodies):
        """A PATH of real tools with `sudo`, `apt-get` and the like as given."""
        bare = self.dir / "stubbed"
        bare.mkdir(exist_ok=True)
        for tool in ("bash", "jq", "flock", "install", "base64", "env", "id", "sed", "printf", "cat", "mkdir", "dirname",
                     "awk", "mktemp", "chmod", "mv", "grep", "head", "rm", "ls", "sort", "date", "tr", "realpath"):
            if not (bare / tool).exists() and shutil.which(tool, path=self.path):
                (bare / tool).symlink_to(shutil.which(tool, path=self.path))
        for name, body in bodies.items():
            (bare / name).unlink(missing_ok=True)
            (bare / name).write_text(f"#!/bin/sh\n{body}\n")
            (bare / name).chmod(0o755)
        return str(bare)

    def test_apt_get_failing_is_fundamental_with_its_text(self):
        path = self.stubbed(sudo='[ "$1" = -n ] && shift; exec "$@"', **{"apt-get": 'echo "E: Unable to locate package jq" >&2; exit 100'})
        (self.dir / "stubbed" / "jq").unlink()
        done = self.run_script(host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True), path=path)
        self.assertEqual(2, done.returncode)
        self.assertIn("E: Unable to locate package jq", done.stderr)
        self.assertIn("stopped at:", done.stderr)

    def test_sudo_wanting_a_password_is_fundamental_and_never_asks(self):
        path = self.stubbed(sudo='[ "$1" = -n ] || { echo asked >&2; exit 9; }; echo "sudo: a password is required" >&2; exit 1')
        done = self.run_script(host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True), path=path)
        self.assertEqual(2, done.returncode)
        self.assertIn("sudo: a password is required", done.stderr)
        self.assertNotIn("asked", done.stderr)

    def test_a_tool_not_found_is_fundamental_and_not_the_127_that_names_bash(self):
        path = self.stubbed(sudo='[ "$1" = -n ] && shift; exec "$@"')
        (self.dir / "stubbed" / "base64").unlink()
        done = self.run_script(host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True), path=path)
        self.assertEqual(2, done.returncode)

    def test_the_script_is_one_function_called_last_and_stops_on_an_unset_name_or_a_failed_pipe(self):
        text = host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True)
        self.assertTrue(text.startswith("main() {\n  set -euo pipefail\n"))
        self.assertTrue(text.endswith("}\nset -E\nmain\n"))
        self.assertEqual(1, text.count("\nmain\n"))
        self.assertEqual([], re.findall(r"\bsudo (?!-n )\S+", text))        # never a `sudo` that may ask

    def test_on_this_machine_the_sudo_may_ask_for_a_password(self):
        text = host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True, local=True)
        self.assertNotIn("sudo -n", text)
        self.assertGreater(len(re.findall(r"\bsudo (?!-n )\S+", text)), 4)
        self.assertEqual(0, self.run_script(text).returncode)

    def test_a_sudoers_line_visudo_refuses_is_not_installed_and_is_fundamental(self):
        path = self.stubbed(sudo='[ "$1" = -n ] && shift; exec "$@"', visudo='echo "visudo: syntax error" >&2; exit 1')
        done = self.run_script(host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True), path=path)
        self.assertEqual(2, done.returncode)
        self.assertIn("syntax error", done.stderr)
        self.assertFalse((self.root / "etc/sudoers.d/turpin-host").exists())

    def test_the_sudoers_file_made_for_the_check_is_removed_when_the_check_refuses_it(self):
        tmp = self.dir / "tmp"
        tmp.mkdir()
        path = self.stubbed(sudo='[ "$1" = -n ] && shift; exec "$@"', visudo='exit 1')
        env = {**os.environ, "PATH": path, "TURPIN_HOST_ROOT": str(self.root), "TMPDIR": str(tmp)}
        done = subprocess.run(["bash", "-s"], input=host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True),
                              env=env, capture_output=True, text=True)
        self.assertEqual((2, []), (done.returncode, list(tmp.iterdir())))

    def test_an_empty_user_name_makes_a_line_visudo_refuses(self):
        path = self.stubbed(sudo='[ "$1" = -n ] && shift; exec "$@"', id='echo ""')
        done = self.run_script(host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True), path=path)
        self.assertEqual(2, done.returncode)
        self.assertFalse((self.root / "etc/sudoers.d/turpin-host").exists())

    def test_a_second_run_updates_what_the_first_wrote(self):
        text = host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True)
        self.assertEqual(0, self.run_script(text).returncode)
        (self.root / "usr/local/lib/turpin/common.sh").write_text("# changed\n")
        self.assertEqual(0, self.run_script(text).returncode)
        self.assertEqual((DELIVER / "lib/common.sh").read_bytes(), (self.root / "usr/local/lib/turpin/common.sh").read_bytes())


class Run(Isolated):
    """The call the command makes: the script to `bash -s` on the machine, safe to repeat."""

    def call(self, name, attached_code=0):
        calls, attached = [], []

        def stopped(*a, **k):
            attached.append((a, k))
            if isinstance(attached_code, BaseException):
                raise attached_code

        with mock.patch.object(profile, "repo_dir", lambda: self.dir), \
                mock.patch.object(profile, "read_working_tree", lambda repo: prof()), \
                mock.patch.object(hosts, "call_attached", stopped), \
                mock.patch.object(hosts, "call_host", lambda *a, **k: calls.append((a, k))):
            code, _, err = self.run_main(["host-install", name])
        self.attached = attached
        return code, err, calls

    def test_the_script_goes_to_bash_on_the_environments_machine_and_may_be_retried(self):
        code, _, calls = self.call("production")
        (machine, args), kwargs = calls[0]
        self.assertEqual((0, "acme-prod", ["-s"]), (code, machine, args))
        self.assertEqual(("bash", True, settings.HOST_INSTALL_TIMEOUT),
                         (kwargs["program"], kwargs["retry"], kwargs["timeout"]))
        self.assertEqual(host_install.script_for(prof(), CredentialKind.OCI_INSTANCE_PRINCIPAL, True), kwargs["data"])
        self.assertEqual([], self.attached)

    def test_the_controllers_own_machine_runs_a_file_of_the_script_attached_with_a_sudo_that_may_ask(self):
        seen = []

        def attached(args, stopped, program=None):
            path = Path(args[0])
            seen.append((args, program, path.read_text(), path.stat().st_mode & 0o777, path))

        with mock.patch.object(profile, "repo_dir", lambda: self.dir), \
                mock.patch.object(profile, "read_working_tree", lambda repo: prof()), \
                mock.patch.object(hosts, "call_attached", attached):
            code, _, _ = self.run_main(["host-install", "preview"])
        (args, program, text, mode, path), = seen
        self.assertEqual((0, "bash", 0o600, 1), (code, program, mode, len(args)))
        self.assertEqual(host_install.script_for(prof(), CredentialKind.DOCKER_CONFIG, True, local=True), text)
        self.assertNotIn("sudo -n", text)
        self.assertFalse(path.exists())

    def test_the_file_is_removed_when_the_run_fails_too(self):
        seen = []

        def attached(args, stopped, program=None):
            seen.append(args[0])
            raise KeyboardInterrupt("interrupted")

        with mock.patch.object(profile, "repo_dir", lambda: self.dir), \
                mock.patch.object(profile, "read_working_tree", lambda repo: prof()), \
                mock.patch.object(hosts, "call_attached", attached):
            self.assertEqual(130, self.run_main(["host-install", "preview"])[0])
        self.assertFalse(Path(seen[0]).exists())

    def test_ctrl_c_at_the_password_prompt_is_130(self):
        code, err, _ = self.call("preview", attached_code=KeyboardInterrupt("interrupted: turpin host-install preview"))
        self.assertEqual(130, code)
        self.assertIn("turpin host-install preview", err)

    def test_the_prompt_is_the_terminals_and_a_death_by_the_ctrl_c_is_130(self):
        for body in ("kill -INT $$; sleep 5", "exit 130"):
            with self.subTest(body):
                bash = self.dir / "bin"
                bash.mkdir(exist_ok=True)
                (bash / "sudo").write_text(f"#!/bin/sh\n{body}\n")
                (bash / "sudo").chmod(0o755)
                with mock.patch.object(profile, "repo_dir", lambda: self.dir), \
                        mock.patch.object(profile, "read_working_tree", lambda repo: prof()), \
                        mock.patch.dict(os.environ, {"PATH": f"{bash}{os.pathsep}{os.environ['PATH']}",
                                                     "TURPIN_HOST_ROOT": str(self.dir / "root")}):
                    code, _, err = self.run_main(["host-install", "preview"])
                self.assertEqual(130, code)
                self.assertIn("turpin host-install preview", err)

    def test_a_failing_script_comes_back_as_a_fundamental_error_naming_no_missing_bash(self):
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        (bin_dir / "sudo").write_text('#!/bin/sh\necho "sudo: a password is required" >&2\nexit 1\n')
        (bin_dir / "sudo").chmod(0o755)
        with mock.patch.object(profile, "repo_dir", lambda: self.dir), \
                mock.patch.object(profile, "read_working_tree", lambda repo: prof()), \
                mock.patch.dict(os.environ, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                                             "TURPIN_HOST_ROOT": str(self.dir / "root")}):
            code, _, err = self.run_main(["host-install", "preview"])
        self.assertEqual(2, code)
        self.assertIn("host-install on this machine stopped (the lines above say why): "
                      "fix it, then run turpin host-install preview again", err)
        self.assertNotIn("bash is not on", err)

    def test_a_name_that_is_not_a_target_calls_nothing_and_exits_1(self):
        code, err, calls = self.call("nowhere")
        self.assertEqual((1, []), (code, calls))
        self.assertIn("nowhere", err)

    def test_two_environments_on_one_machine_that_both_install_host_files_are_refused_before_any_call(self):
        both = '\n[environments.second]\nrole = "rehearsal"\nssh = "acme-prod"\nlogin = "docker-config"\n'
        calls = []
        with mock.patch.object(profile, "repo_dir", lambda: self.dir), \
                mock.patch.object(profile, "read_working_tree", lambda repo: prof(both)), \
                mock.patch.object(hosts, "call_host", lambda *a, **k: calls.append(a)):
            code, _, err = self.run_main(["host-install", "second"])
        self.assertEqual((1, []), (code, calls))
        self.assertIn("each would remove the other's", err)


class Env(Isolated):
    def test_it_is_turpin_hosts_env_on_this_machine_with_the_callers_terminal(self):
        host = self.dir / "turpin-host"
        host.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$OUT"\nexit "${CODE:-0}"\n')
        host.chmod(0o755)
        out = self.dir / "args"
        with mock.patch.dict(os.environ, {"TURPIN_HOST_BIN": str(host), "OUT": str(out)}):
            code, _, _ = self.run_main(["env", "create", "e3"])
        self.assertEqual((0, "env\ncreate\ne3\n"), (code, out.read_text()))

    def test_the_hosts_exit_status_is_mapped(self):
        host = self.dir / "turpin-host"
        host.write_text('#!/bin/sh\nexit "$CODE"\n')
        host.chmod(0o755)
        for host_code, ours in ((1, 1), (2, 2), (70, 70), (75, 75), (130, 130)):
            with self.subTest(host_code), mock.patch.dict(os.environ, {"TURPIN_HOST_BIN": str(host), "CODE": str(host_code)}):
                self.assertEqual(ours, self.run_main(["env", "destroy", "e3"])[0])

    def test_a_host_that_dies_of_the_ctrl_c_or_exits_130_is_an_interruption_naming_the_command(self):
        host = self.dir / "turpin-host"
        for body in ("kill -INT $$; sleep 5", "exit 130"):
            host.write_text(f"#!/bin/sh\n{body}\n")
            host.chmod(0o755)
            with self.subTest(body), mock.patch.dict(os.environ, {"TURPIN_HOST_BIN": str(host)}):
                code, _, err = self.run_main(["env", "create", "e3"])
            self.assertEqual(130, code)
            self.assertIn("turpin env create e3", err)

    def test_a_ctrl_c_during_the_wait_is_130_whatever_the_program_then_exits_with(self):
        host = self.dir / "turpin-host"
        host.write_text("#!/bin/sh\nkill -INT $PPID\nsleep 1\nexit 1\n")      # it handles the Ctrl+C and says 1
        host.chmod(0o755)
        with mock.patch.dict(os.environ, {"TURPIN_HOST_BIN": str(host)}):
            code, _, err = self.run_main(["env", "create", "e3"])
        self.assertEqual(130, code)
        self.assertIn("turpin env create e3", err)

    def test_a_host_killed_by_another_signal_is_unexpected(self):
        host = self.dir / "turpin-host"
        host.write_text("#!/bin/sh\nkill -TERM $$; sleep 5\n")
        host.chmod(0o755)
        with mock.patch.dict(os.environ, {"TURPIN_HOST_BIN": str(host)}):
            self.assertEqual(70, self.run_main(["env", "create", "e3"])[0])

    def test_two_arguments_are_needed(self):
        self.assertEqual(64, self.run_main(["env", "create"])[0])
        self.assertEqual(64, self.run_main(["env", "create", "a", "b"])[0])


if __name__ == "__main__":
    unittest.main()
