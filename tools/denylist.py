import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).absolute().parents[1]


def git(directory: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(directory), *args], capture_output=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
    )


def terms_from_environment() -> tuple[bytes, ...] | None:
    direct = os.environ.get("PSTACK_CODEX_DENYLIST")
    filename = os.environ.get("PSTACK_CODEX_DENYLIST_FILE")
    if direct is not None and filename is not None:
        raise ValueError
    if direct is None and filename is None:
        return None
    if filename is not None:
        path = Path(filename).expanduser().absolute()
        if path.is_symlink() or not path.is_file():
            raise ValueError
        top = git(path.parent, "rev-parse", "--show-toplevel")
        if top.returncode == 0:
            tracked = git(path.parent, "ls-files", "--error-unmatch", "--", ":(literal)" + path.name)
            if tracked.returncode == 0:
                raise ValueError
        direct = path.read_text(encoding="utf-8")
    terms = tuple(line.encode("utf-8") for line in direct.splitlines() if line)
    if not terms or any(b"\0" in term for term in terms):
        raise ValueError
    return terms


def scan(root: Path, terms: tuple[bytes, ...]) -> int:
    result = git(root, "ls-files", "--stage", "-z")
    if result.returncode:
        raise ValueError
    findings = 0
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, _, stage = metadata.split()
        findings += sum(term in name for term in terms)
        if mode == b"160000":
            continue
        if mode not in (b"100644", b"100755") or stage != b"0":
            raise ValueError
        path = root / os.fsdecode(name)
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError
        content = path.read_bytes()
        findings += sum(term in content for term in terms)
    return findings


def main() -> int:
    try:
        terms = terms_from_environment()
        if terms is None:
            print("Denylist not configured. No private-data absence claim is made.")
            return 0
        findings = scan(ROOT, terms)
    except (OSError, ValueError, UnicodeError):
        print("Denylist check failed. Configuration or tracked input is invalid.", file=sys.stderr)
        return 2
    print(f"Denylist findings: {findings}. Public submodule contents excluded; source integrity is checked separately.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
