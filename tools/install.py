"""Copy a verified, pinned pstack distribution without changing existing files."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys


ROOT = Path(__file__).absolute().parents[1]
NATIVE = Path(".agents/skills/pstack-codex")
RESOURCE = Path(".agents/pstack-codex")


@dataclass(frozen=True)
class CopyEntry:
    relative_path: Path
    content: bytes


def checked_path(path: Path) -> Path:
    path = path.expanduser().absolute()
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise ValueError("symlinks are not supported")
        if part != path and part.exists() and not part.is_dir():
            raise ValueError("an ancestor is not a directory")
    return path.resolve()


def git(directory: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(directory), *args], capture_output=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
             "GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": ""},
    )
    if result.returncode:
        raise ValueError("local Git source unavailable; initialize the recorded submodule separately")
    return result.stdout


def regular_bytes(path: Path) -> bytes:
    checked_path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("source or destination is not a regular file")
    return path.read_bytes()


def build_plan(root: Path) -> tuple[CopyEntry, ...]:
    root = checked_path(root)
    lock_bytes = regular_bytes(root / "upstream/pstack.lock.json")
    lock = json.loads(lock_bytes)
    if (not isinstance(lock, dict)
            or lock.get("repository") != "https://github.com/cursor/plugins.git"
            or lock.get("path") != "pstack"
            or any(not isinstance(lock.get(key), str)
                   or not re.fullmatch(r"[0-9a-f]{40}", lock[key])
                   for key in ("commit", "tree"))):
        raise ValueError("invalid upstream lock")
    source = checked_path(root / "upstream/cursor-plugins")
    if Path(os.fsdecode(git(source, "rev-parse", "--show-toplevel")).strip()).resolve() != source:
        raise ValueError("upstream submodule is not initialized")
    if git(source, "rev-parse", "HEAD").decode().strip() != lock["commit"]:
        raise ValueError("upstream HEAD does not match the lock")
    if git(source, "rev-parse", "HEAD:pstack").decode().strip() != lock["tree"]:
        raise ValueError("upstream tree does not match the lock")
    link = git(root, "ls-files", "--stage", "-z", "--", "upstream/cursor-plugins").split()
    if link[:3] != [b"160000", lock["commit"].encode(), b"0"]:
        raise ValueError("upstream gitlink does not match the lock")
    entries = []
    inventory = git(source, "ls-tree", "-r", "-z", lock["commit"], "--", "pstack")
    for record in inventory.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        relative = PurePosixPath(os.fsdecode(raw_path))
        if (mode not in (b"100644", b"100755") or kind != b"blob"
                or relative.parts[0] != "pstack" or relative.is_absolute()
                or any(part in ("..", ".git") for part in relative.parts)):
            raise ValueError("unsupported upstream entry")
        content = regular_bytes(source / relative)
        digest = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if digest.encode() != oid:
            raise ValueError("upstream source bytes do not match the locked Git tree")
        entries.append(CopyEntry(RESOURCE / relative, content))
    if not any(entry.relative_path == RESOURCE / "pstack/LICENSE" for entry in entries):
        raise ValueError("upstream license is missing")
    entries.extend((
        CopyEntry(RESOURCE / "pstack.lock.json", lock_bytes),
        CopyEntry(RESOURCE / "LICENSE.adapter", regular_bytes(root / "LICENSE")),
        CopyEntry(NATIVE / "MAPPING.md", regular_bytes(root / "codex/pstack-codex/MAPPING.md")),
        CopyEntry(NATIVE / "SKILL.md", regular_bytes(root / "codex/pstack-codex/SKILL.md")),
    ))
    return tuple(entries)


def preflight(target: Path, plan: tuple[CopyEntry, ...]) -> tuple[CopyEntry, ...]:
    files = {entry.relative_path for entry in plan}
    directories = {parent for file in files for parent in file.parents if parent != Path(".")}
    missing = []
    if target.exists() and not target.is_dir():
        raise ValueError("target is not a directory")
    for entry in plan:
        destination = checked_path(target / entry.relative_path)
        if destination.exists():
            if regular_bytes(destination) != entry.content:
                raise ValueError("conflicting existing target bytes; nothing was copied")
        else:
            missing.append(entry)
    for owned in (NATIVE, RESOURCE):
        start = target / owned
        if not start.exists():
            continue
        for directory, child_dirs, child_files in os.walk(start, followlinks=False):
            for name in child_dirs + child_files:
                path = Path(directory) / name
                checked_path(path)
                relative = path.relative_to(target)
                expected = directories if path.is_dir() else files
                if relative not in expected:
                    raise ValueError("unexpected entry in an owned directory; nothing was copied")
    return tuple(missing)


def install(root: Path, target: Path) -> int:
    root, target = checked_path(root), checked_path(target)
    for owned in (NATIVE, RESOURCE):
        destination = target / owned
        if (root == destination or root in destination.parents
                or destination in root.parents):
            raise ValueError("source and destination must not overlap")
    plan = build_plan(root)
    missing = preflight(target, plan)
    for entry in missing:
        destination = target / entry.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(entry.content)
    return len(missing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="project directory, or your home directory")
    args = parser.parse_args()
    try:
        copied = install(ROOT, args.target)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Install refused: {error}", file=sys.stderr)
        return 1
    print(f"Copied {copied} files. Existing identical files were unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
