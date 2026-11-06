import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import install
import denylist


def git(directory, *args):
    return subprocess.check_output(["git", "-C", str(directory), *args])


def run_cli(script, *args, env=None, **kwargs):
    clean = {key: value for key, value in os.environ.items()
             if not key.startswith("PSTACK_CODEX_DENYLIST")}
    clean.update(env or {})
    return subprocess.run([sys.executable, str(ROOT / "tools" / script), *map(str, args)],
                          capture_output=True, env=clean, **kwargs)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pstack contract ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.target = self.base / "project with spaces"

    def cli(self, target=None):
        return run_cli("install.py", "--target", target or self.target)

    def snapshot(self, directory):
        return {str(path.relative_to(directory)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in directory.rglob("*") if path.is_file()}

    def source_fixture(self):
        root = self.base / "source"
        for name in ("LICENSE", "upstream/pstack.lock.json", "codex/pstack-codex/SKILL.md",
                     "codex/pstack-codex/MAPPING.md"):
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / name).read_bytes())
        shutil.copytree(ROOT / "upstream/cursor-plugins/pstack", root / "upstream/cursor-plugins/pstack")
        return root

    def fixture_git(self, root):
        original_git = install.git

        def read(directory, *args):
            original = ROOT / Path(directory).relative_to(root)
            if args == ("rev-parse", "--show-toplevel"):
                return os.fsencode(directory) + b"\n"
            return original_git(original, *args)
        return read

    def test_real_cli_copies_complete_git_archive_bytes_and_licenses(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        lock = json.loads((ROOT / "upstream/pstack.lock.json").read_bytes())
        archive = git(ROOT / "upstream/cursor-plugins", "archive", lock["commit"], "pstack")
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            expected = {member.name: stream.extractfile(member).read()
                        for member in stream.getmembers() if member.isfile()}
        installed = self.target / ".agents/pstack-codex"
        actual = {str(path.relative_to(installed)): path.read_bytes()
                  for path in (installed / "pstack").rglob("*") if path.is_file()}
        self.assertEqual(actual, expected)
        self.assertEqual((installed / "pstack.lock.json").read_bytes(),
                         (ROOT / "upstream/pstack.lock.json").read_bytes())
        self.assertEqual((installed / "LICENSE.adapter").read_bytes(), (ROOT / "LICENSE").read_bytes())
        native = self.target / ".agents/skills/pstack-codex"
        self.assertEqual({p.name for p in native.iterdir()}, {"SKILL.md", "MAPPING.md"})
        for name in ("SKILL.md", "MAPPING.md"):
            self.assertEqual((native / name).read_bytes(), (ROOT / "codex/pstack-codex" / name).read_bytes())
        self.assertEqual((native / "../../pstack-codex/pstack").resolve(), installed / "pstack")
        self.assertFalse(any(path.name == ".git" for path in self.target.rglob("*")))
        self.assertTrue(any(part.startswith(".") for name in actual for part in Path(name).parts))

    def test_repeat_is_noop_and_unrelated_configuration_is_untouched(self):
        for name in ("AGENTS.md", ".codex/config.toml", ".agents/skills/other/SKILL.md"):
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"existing\x00instruction\n")
        before = self.snapshot(self.target)
        self.assertEqual(self.cli().returncode, 0)
        first = self.snapshot(self.target)
        for name, value in before.items():
            self.assertEqual(first[name], value)
        again = self.cli()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn(b"Copied 0 files", again.stdout)
        self.assertEqual(self.snapshot(self.target), first)

    def test_matching_partial_install_is_completed(self):
        path = self.target / ".agents/pstack-codex/pstack/LICENSE"
        path.parent.mkdir(parents=True)
        path.write_bytes((ROOT / "upstream/cursor-plugins/pstack/LICENSE").read_bytes())
        timestamp = path.stat().st_mtime_ns
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(path.stat().st_mtime_ns, timestamp)
        self.assertTrue((self.target / install.NATIVE / "SKILL.md").is_file())

    def test_conflict_is_refused_before_any_writes(self):
        path = self.target / install.NATIVE / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"local edits")
        before = self.snapshot(self.target)
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertEqual(self.snapshot(self.target), before)
        self.assertFalse((self.target / install.RESOURCE).exists())

    def test_unexpected_files_and_empty_directories_are_refused(self):
        for name in ("stray.log", "stray-directory"):
            with self.subTest(name=name):
                target = self.base / name
                unexpected = target / install.RESOURCE / name
                unexpected.parent.mkdir(parents=True)
                if "directory" in name:
                    unexpected.mkdir()
                else:
                    unexpected.write_bytes(b"unexpected")
                self.assertNotEqual(self.cli(target).returncode, 0)
                self.assertFalse((target / install.NATIVE).exists())

    def test_symlink_target_parent_and_owned_entries_are_refused(self):
        real = self.base / "real"
        real.mkdir()
        link = self.base / "link"
        link.symlink_to(real, target_is_directory=True)
        self.assertNotEqual(self.cli(link / "project").returncode, 0)
        self.assertEqual(list(real.iterdir()), [])
        owned = self.target / install.NATIVE
        owned.parent.mkdir(parents=True)
        owned.symlink_to(real, target_is_directory=True)
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertEqual(list(real.iterdir()), [])

    def test_overlap_is_refused(self):
        self.assertNotEqual(self.cli(ROOT).returncode, 0)
        self.assertFalse((ROOT / ".agents").exists())

    def test_destination_wrapping_source_is_refused(self):
        source = self.target / install.RESOURCE / "checkout"
        source.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "overlap"):
            install.install(source, self.target)
        self.assertEqual(list(source.iterdir()), [])

    def test_home_scope_can_contain_source_without_destination_overlap(self):
        root = self.source_fixture()
        read = self.fixture_git(root)
        with mock.patch.object(install, "git", side_effect=read):
            copied = install.install(root, self.base)
        self.assertGreater(copied, 0)
        self.assertTrue((self.base / install.NATIVE / "SKILL.md").is_file())

    def test_staged_pin_update_can_be_verified_before_commit(self):
        root = self.source_fixture()
        lock = json.loads((root / "upstream/pstack.lock.json").read_bytes())
        git(root, "init", "--quiet", "--initial-branch=fixture")
        git(root, "update-index", "--add", "--cacheinfo",
            f"160000,{'1' * 40},upstream/cursor-plugins")
        git(root, "-c", "core.hooksPath=/dev/null", "-c", "user.name=Example",
            "-c", "user.email=example@example.invalid", "commit", "--no-gpg-sign",
            "--quiet", "-m", "Synthetic previous pin")
        git(root, "update-index", "--cacheinfo",
            f"160000,{lock['commit']},upstream/cursor-plugins")
        original = install.git
        fixture_read = self.fixture_git(root)

        def read(directory, *args):
            return original(directory, *args) if directory == root else fixture_read(directory, *args)

        with mock.patch.object(install, "git", side_effect=read):
            plan = install.build_plan(root)
        self.assertTrue(any(entry.relative_path == install.NATIVE / "SKILL.md" for entry in plan))
        committed = git(root, "ls-tree", "HEAD", "upstream/cursor-plugins").split()[2]
        self.assertNotEqual(committed, lock["commit"].encode())

    def test_dirty_missing_symlink_and_wrong_pin_sources_are_refused(self):
        root = self.source_fixture()
        read = self.fixture_git(root)
        file = root / "upstream/cursor-plugins/pstack/LICENSE"
        original = file.read_bytes()
        for fault in ("dirty", "missing", "symlink", "pin", "tree"):
            with self.subTest(fault=fault):
                lock = json.loads((ROOT / "upstream/pstack.lock.json").read_bytes())
                if fault == "dirty":
                    file.write_bytes(b"changed license")
                elif fault == "missing":
                    file.unlink()
                elif fault == "symlink":
                    file.unlink()
                    file.symlink_to(ROOT / "upstream/cursor-plugins/pstack/LICENSE")
                else:
                    lock["commit" if fault == "pin" else "tree"] = "0" * 40
                (root / "upstream/pstack.lock.json").write_text(json.dumps(lock))
                with mock.patch.object(install, "git", side_effect=read):
                    with self.assertRaises((ValueError, OSError)):
                        install.install(root, self.target)
                self.assertFalse(self.target.exists())
                if file.is_symlink():
                    file.unlink()
                file.write_bytes(original)

    def test_missing_submodule_cli_is_refused_without_target_writes(self):
        source = self.base / "missing source"
        (source / "tools").mkdir(parents=True)
        (source / "upstream").mkdir()
        shutil.copyfile(ROOT / "tools/install.py", source / "tools/install.py")
        shutil.copyfile(ROOT / "upstream/pstack.lock.json", source / "upstream/pstack.lock.json")
        result = subprocess.run([sys.executable, str(source / "tools/install.py"), "--target", str(self.target)],
                                capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())

    def test_untracked_source_files_are_ignored(self):
        root = self.source_fixture()
        extra = root / "upstream/cursor-plugins/pstack/local.log"
        extra.write_bytes(b"must not distribute")
        read = self.fixture_git(root)
        with mock.patch.object(install, "git", side_effect=read):
            install.install(root, self.target)
        self.assertFalse((self.target / install.RESOURCE / "pstack/local.log").exists())

    def test_unsupported_source_modes_and_gitlink_mismatch_are_refused(self):
        original = install.git
        for fault in ("symlink-mode", "gitlink"):
            with self.subTest(fault=fault):
                def invalid(directory, *args):
                    value = original(directory, *args)
                    if fault == "symlink-mode" and args[:3] == ("ls-tree", "-r", "-z"):
                        return value.replace(b"100644 blob", b"120000 blob", 1)
                    if fault == "gitlink" and directory == ROOT and args[0] == "ls-files":
                        return b"160000 " + b"0" * 40 + b" 0\tupstream/cursor-plugins\0"
                    return value
                with mock.patch.object(install, "git", side_effect=invalid):
                    with self.assertRaises(ValueError):
                        install.install(ROOT, self.target)
                self.assertFalse(self.target.exists())

    def test_activation_is_last_and_interruption_before_it_can_be_completed(self):
        plan = install.build_plan(ROOT)
        activation = self.target / install.NATIVE / "SKILL.md"
        original = Path.open

        def interrupt(path, mode="r", *args, **kwargs):
            if path == activation and mode == "xb":
                for entry in plan:
                    if entry.relative_path != install.NATIVE / "SKILL.md":
                        self.assertEqual((self.target / entry.relative_path).read_bytes(), entry.content)
                raise InterruptedError("synthetic interruption")
            return original(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", interrupt):
            with self.assertRaises(InterruptedError):
                install.install(ROOT, self.target)
        self.assertFalse(activation.exists())
        completed = self.cli()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(b"Copied 1 files", completed.stdout)

    def test_exclusive_create_does_not_overwrite_a_late_conflict(self):
        plan = (install.CopyEntry(Path(".agents/pstack-codex/file"), b"resource"),
                install.CopyEntry(install.NATIVE / "SKILL.md", b"native"))
        original = Path.open

        def collision(path, mode="r", *args, **kwargs):
            if mode == "xb":
                with original(path, "wb") as output:
                    output.write(b"late conflicting bytes")
            return original(path, mode, *args, **kwargs)

        with mock.patch.object(install, "build_plan", return_value=plan):
            with mock.patch.object(Path, "open", collision):
                with self.assertRaises(FileExistsError):
                    install.install(ROOT, self.target)
        self.assertEqual((self.target / plan[0].relative_path).read_bytes(), b"late conflicting bytes")
        self.assertFalse((self.target / install.NATIVE / "SKILL.md").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX umask contract")
    def test_copies_use_umask_instead_of_source_executable_modes(self):
        result = run_cli("install.py", "--target", self.target, preexec_fn=lambda: os.umask(0o027))
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = git(ROOT / "upstream/cursor-plugins", "ls-tree", "-r", "HEAD", "pstack").splitlines()
        executable = next(line.split(b"\t", 1)[1] for line in inventory if line.startswith(b"100755"))
        destination = self.target / install.RESOURCE / os.fsdecode(executable)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o640)

    def test_cli_has_no_force_option(self):
        result = run_cli("install.py", "--target", self.target, "--force")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.directory = ROOT / "codex/pstack-codex"
        self.mapping = (self.directory / "MAPPING.md").read_text()
        self.rows = {}
        for line in self.mapping.splitlines():
            if not line.startswith("| "):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells[0] in ("ID", "---"):
                continue
            self.assertEqual(len(cells), 5)
            self.assertTrue(all(cells))
            self.assertNotIn(cells[0], self.rows)
            self.assertRegex(cells[0], r"^[a-z]+(?:-[a-z]+)*$")
            self.rows[cells[0]] = cells

    def test_required_mapping_rows_and_local_links_exist(self):
        expected = {"skills", "read", "grep", "glob", "bash", "edits", "questions", "plans",
                    "poteto-role", "comment-role", "general-role", "readonly", "background", "resume",
                    "attachments", "local", "cloud", "models", "setup", "unsupported", "companions", "sequential"}
        self.assertTrue(expected <= self.rows.keys())
        for link in re.findall(r"\]\(([^)]+)\)", self.mapping):
            if "://" not in link:
                self.assertTrue((self.directory / link).is_file(), link)
        for reference in re.findall(r"\]\[([^]]+)\]", self.mapping):
            self.assertIn(f"[{reference}]: https://", self.mapping)

    def test_versioned_agent_and_safety_contracts_are_not_silently_dropped(self):
        background = " ".join(self.rows["background"])
        for term in ("multi_agent_v1", "fork_context", "task_name", "message", "fork_turns",
                     "V2 defaults to `all`", "mailbox", "does not return result contents"):
            self.assertIn(term, background)
        for term in ("fresh context", "fork_turns=none", "new agent identity", "inherited context"):
            self.assertIn(term, self.mapping)
        self.assertIn("not an independent sandbox", " ".join(self.rows["comment-role"]))
        self.assertIn("not create a separate read-only sandbox", " ".join(self.rows["readonly"]))
        self.assertIn("blockers, not successful skips", " ".join(self.rows["sequential"]))
        self.assertIn("No universal attachments field", " ".join(self.rows["attachments"]))
        self.assertIn("Omit model and reasoning overrides", " ".join(self.rows["models"]))
        self.assertIn("does not install setup-pstack", " ".join(self.rows["setup"]))
        for path in ("SKILL.md", "MAPPING.md", "../../pstack-codex/pstack/agents/poteto-agent.md",
                     "../../pstack-codex/pstack/agents/comment-sicko.md",
                     "../../pstack-codex/pstack/skills/poteto-mode/SKILL.md"):
            self.assertIn(f"<adapter>/{path}", self.mapping)
        for requirement in ("original goal", "assigned scope", "success criteria", "restrictions",
                            "approval boundaries", "authorized working directory"):
            self.assertIn(requirement, self.mapping)

    def test_native_skill_is_adapter_only_and_points_to_full_mode(self):
        skill = (self.directory / "SKILL.md").read_text()
        self.assertTrue(skill.startswith("---\nname: pstack-codex\ndescription: "))
        self.assertIn("MAPPING.md", skill)
        self.assertIn("../../pstack-codex/pstack/skills/poteto-mode/SKILL.md", skill)
        self.assertIn("in full", skill)
        self.assertIn("primary session", skill)
        self.assertIn("missing required gate remains a blocker", skill)


class UpstreamTests(unittest.TestCase):
    def test_gitlink_lock_head_tree_and_original_license_agree(self):
        lock = json.loads((ROOT / "upstream/pstack.lock.json").read_bytes())
        source = ROOT / "upstream/cursor-plugins"
        self.assertEqual(lock["repository"], "https://github.com/cursor/plugins.git")
        self.assertEqual(lock["path"], "pstack")
        self.assertEqual(git(source, "rev-parse", "HEAD").decode().strip(), lock["commit"])
        self.assertEqual(git(source, "rev-parse", "HEAD:pstack").decode().strip(), lock["tree"])
        link = git(ROOT, "ls-files", "--stage", "--", "upstream/cursor-plugins").split()
        self.assertEqual(link[:3], [b"160000", lock["commit"].encode(), b"0"])
        original = git(source, "show", f'{lock["commit"]}:pstack/LICENSE')
        self.assertEqual((source / "pstack/LICENSE").read_bytes(), original)
        self.assertIn(b"Copyright (c) 2026 Lauren Tan", original)
        self.assertEqual((ROOT / "LICENSE").read_bytes(), git(ROOT, "show", "HEAD:LICENSE"))
        plan = install.build_plan(ROOT)
        self.assertGreater(len(plan), 4)

    def test_installer_only_invokes_local_read_git_commands(self):
        original = install.git
        calls = []

        def recording(directory, *args):
            calls.append(args)
            return original(directory, *args)

        with mock.patch.object(install, "git", side_effect=recording):
            install.build_plan(ROOT)
        self.assertTrue(calls)
        self.assertTrue(all(args[0] in ("rev-parse", "ls-tree", "ls-files") for args in calls))

    def test_local_git_reads_disable_lazy_fetch_and_transport(self):
        with mock.patch.object(install.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")) as run:
            install.git(ROOT, "rev-parse", "HEAD")
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(environment["GIT_ALLOW_PROTOCOL"], "")


class DenylistTests(unittest.TestCase):
    def test_no_configuration_is_explicit_and_does_not_claim_absence(self):
        result = run_cli("denylist.py")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"not configured", result.stdout)
        self.assertIn(b"No private-data absence claim", result.stdout)

    def test_environment_literals_match_tracked_path_and_content_with_redaction(self):
        for term in (".gitmodules", "MIT License"):
            with self.subTest(term=term):
                result = run_cli("denylist.py", env={"PSTACK_CODEX_DENYLIST": term})
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"Denylist findings:", result.stdout)
                self.assertNotIn(term.encode(), result.stdout + result.stderr)
                self.assertNotIn(b"LICENSE", result.stdout + result.stderr)

    def test_untracked_pattern_file_works_and_unknown_terms_are_not_echoed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic-private-patterns"
            term = "synthetic-unmatched-" + os.urandom(16).hex()
            path.write_text(term + "\n")
            result = run_cli("denylist.py", env={"PSTACK_CODEX_DENYLIST_FILE": str(path)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"findings: 0", result.stdout)
            self.assertNotIn(path.name.encode(), result.stdout + result.stderr)
            self.assertNotIn(term.encode(), result.stdout + result.stderr)

    def test_invalid_missing_tracked_and_conflicting_pattern_inputs_are_redacted(self):
        cases = [
            {"PSTACK_CODEX_DENYLIST": ""},
            {"PSTACK_CODEX_DENYLIST_FILE": ""},
            {"PSTACK_CODEX_DENYLIST_FILE": str(ROOT / "missing-synthetic-patterns")},
            {"PSTACK_CODEX_DENYLIST_FILE": str(ROOT / "README.md")},
            {"PSTACK_CODEX_DENYLIST": "synthetic-term", "PSTACK_CODEX_DENYLIST_FILE": "synthetic-name"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            invalid = Path(temporary) / "invalid-synthetic-patterns"
            invalid.write_bytes(b"\xff")
            cases.append({"PSTACK_CODEX_DENYLIST_FILE": str(invalid)})
            for env in cases:
                with self.subTest(env=list(env)):
                    result = run_cli("denylist.py", env=env)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stderr, b"Denylist check failed. Configuration or tracked input is invalid.\n")
                    self.assertEqual(result.stdout, b"")

    def test_binary_and_path_matching_excludes_submodule_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "synthetic-path.bin").write_bytes(b"\x00synthetic-content\xff")
            index = (b"100644 " + b"0" * 40 + b" 0\tsynthetic-path.bin\0"
                     + b"160000 " + b"1" * 40 + b" 0\tupstream/submodule\0")
            result = subprocess.CompletedProcess([], 0, index, b"")
            with mock.patch.object(denylist, "git", return_value=result):
                self.assertEqual(denylist.scan(root, (b"synthetic-path", b"synthetic-content")), 2)
                self.assertEqual(denylist.scan(root, (b"upstream",)), 1)


class WorkflowTests(unittest.TestCase):
    def test_fork_safe_workflow_needs_no_secrets_or_dependencies(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("on: [push, pull_request]", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn("actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803", workflow)
        self.assertIn("submodules: true", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("python3 -m unittest discover -s tests -v", workflow)
        for forbidden in ("secrets.", "pull_request_target", "self-hosted", "pip install",
                          "upload-artifact", "deploy", "token:", "write", "--remote"):
            self.assertNotIn(forbidden, workflow)


if __name__ == "__main__":
    unittest.main()
