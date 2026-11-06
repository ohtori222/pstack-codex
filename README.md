# pstack-codex

Unofficial [Codex](https://github.com/openai/codex) adapter for
[pstack](https://github.com/cursor/plugins/tree/main/pstack).

pstack itself stays unmodified (pinned upstream). This repository only maps
harness details for Codex. It is not affiliated with Cursor or the pstack
author.

Upstream pstack is MIT-licensed; see [LICENSE](./LICENSE) (Copyright (c) 2026
Lauren Tan for pstack; Copyright (c) 2026 ohtori222 for this adapter).

## Install a local copy

Use Python 3.10 or newer and Git. Clone this repository with its recorded
submodule, then run one installer command from the clone:

```sh
git clone --recurse-submodules <repository-url> pstack-codex
cd pstack-codex
python3 tools/install.py --target /path/to/project
```

For user scope, use `--target "$HOME"` instead. Choose the scope explicitly.
The installer never modifies global configuration. A user-scope copy is visible
to multiple projects, so project scope is the narrower default.

The installer copies this layout without rendering or editing upstream files:

```text
<target>/.agents/skills/pstack-codex/SKILL.md
<target>/.agents/skills/pstack-codex/MAPPING.md
<target>/.agents/pstack-codex/pstack/       # complete official tree and LICENSE
<target>/.agents/pstack-codex/pstack.lock.json
<target>/.agents/pstack-codex/LICENSE.adapter
```

Only the adapter enters native skill discovery. Official skills stay outside it
because Cursor frontmatter does not have identical Codex semantics. The adapter
reads them by path. Hidden resources and relative references remain intact.
The installer verifies tracked source bytes against the locked Git tree and
ignores untracked source files. It does not copy `.git` or other plugins.

The installer refuses symlinks, source/destination overlap, unsupported source
entries, conflicting bytes, and unexpected entries inside its two owned
directories. It checks the full plan before writing and creates files
exclusively, with native `SKILL.md` last. An identical repeat changes nothing.
A matching partial copy can be completed. A truncated or conflicting file needs
manual attention. This is not a transactional deployment or a sandbox against
hostile concurrent filesystem changes.

New files use the normal umask. The installer does not preserve permission bits,
timestamps, or other metadata, and never runs chmod. Invoke copied scripts with
their documented interpreters, such as `python3 script.py` or `bash script.sh`.
No network calls, source mutations, Git writes, deletions, overwrites, moves,
renames, service operations, or setup-pstack configuration are part of install.
Existing `AGENTS.md`, `.codex/config.toml`, and other skills stay untouched.

If the recorded submodule is missing, initialize it separately, then retry:

```sh
git submodule update --init --recursive
```

The installer never initializes or fetches it for you. A tracked upstream byte
change, wrong HEAD, wrong tree, or gitlink/lock mismatch causes refusal.

## Activate the adapter

In Codex CLI or the IDE, mention `$pstack-codex` or select it with `/skills`.
See [Codex skills](https://developers.openai.com/codex/build-skills.md).
Official `/poteto-mode` and other Cursor slash commands are not registered by
this installer. Ask Codex to use the adapter and read the named official skill.

Optionally append [examples/AGENTS.md](examples/AGENTS.md) to the applicable
`AGENTS.md` if desired. That file is an optional example of lines for
`~/.codex/AGENTS.md`: the pstack loading rules plus an optional personal
task-list workflow. The installer never creates or edits `AGENTS.md`, so
appending is up to you:

```sh
curl -fsSL https://raw.githubusercontent.com/ohtori222/pstack-codex/main/examples/AGENTS.md >> ~/.codex/AGENTS.md
```

Review [MAPPING.md](codex/pstack-codex/MAPPING.md) for tool translations,
version-specific agent schemas, read-only limitations, and sequential fallback.
Current Codex supports parallel subagents. The adapter does not install custom
agents or assume Cursor roles are native. It inherits parent model settings and
operator defaults without overrides. Sequential work is not independent or
multi-model review. Required unavailable gates remain blockers.
Existing [Codex instructions](https://developers.openai.com/codex/agent-configuration/agents-md.md)
and approvals retain their authority.

## Update a copy

1. Update the source clone with normal `git pull`.
2. Run `git submodule update --init --recursive` to the recorded pin. Do not use
   `--remote`.
3. Back up and manually move the old `<target>/.agents/skills/pstack-codex` and
   `<target>/.agents/pstack-codex` directories outside all native skill discovery
   locations. Check local edits before moving them.
4. Rerun `python3 tools/install.py --target /path/to/project`.

The installer never replaces or removes an old copy. It has no force flag or
generated activation path. To uninstall, manually remove only these two owned
directories after checking their contents and any instruction snippet you added.

For an intentional upstream pin change, maintainers review the desired upstream
commit and pstack tree, update the submodule gitlink and
`upstream/pstack.lock.json` together, stage the new gitlink, then rerun all tests
before committing. The installer checks the index so an intentional pin update
can be verified before its commit. Keep official files
unmodified, including `pstack/LICENSE`. Do not point the installer at a moving
branch. The official [Cursor pstack plugin](https://github.com/cursor/plugins/tree/main/pstack)
is separately installable for Cursor, independently of this unofficial adapter.

## Run checks

```sh
python3 -m unittest discover -s tests -v
python3 tools/denylist.py
```

The stdlib tests check installed bytes, refusal behavior, mapping contracts,
licenses, pin agreement, private-pattern diagnostics, and fork-safe CI settings.
They require no packages, model calls, or secrets. CI uses `ubuntu-latest` and
read-only repository permission. Tests are not a live Codex discovery or agent
smoke test. No live Codex binary smoke test has been performed.

For local private-data checks, set exactly one of these inputs:

- `PSTACK_CODEX_DENYLIST` contains newline-delimited literal terms.
- `PSTACK_CODEX_DENYLIST_FILE` names an untracked UTF-8 file of those terms.

`denylist.example` contains generic examples only. Copy it to ignored
`.denylist.local` and edit locally if useful. Tracked pattern files are rejected.
The checker scans tracked adapter paths and current file bytes, including binary
files. It excludes `.git`, untracked files, and the public submodule contents.
Upstream source integrity is checked separately by the installer and tests.
Diagnostics show counts only, never terms, matching content, or filenames.
Without a private configured list it explicitly reports not configured. A clean
check cannot prove absence of unknown private data. Never put private terms in
committed tests, documentation, or workflow configuration.

The original upstream MIT license is copied unchanged with every install.
The existing root [LICENSE](LICENSE) remains unchanged and is copied as
`LICENSE.adapter` alongside it.
