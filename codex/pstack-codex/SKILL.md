---
name: pstack-codex
description: Use the pinned, unmodified pstack workflows in Codex for nontrivial development, investigation, or review. Load this compatibility adapter before reading an official pstack workflow. Preserve the user's scope and approval boundaries.
---

# pstack in Codex

Read [MAPPING.md](./MAPPING.md) in full first. It is the sole normative
compatibility table. Apply its translations when an official instruction names
a Cursor feature. Never rewrite the official files to make them compatible.

Resolve resources relative to this skill's directory, not the working directory.
The complete official pstack is at `../../pstack-codex/pstack`.
Read `../../pstack-codex/pstack/skills/poteto-mode/SKILL.md` in full, including
its Principles index, before following a workflow. Read each applied principle's
leaf and the selected official playbook from that directory. The primary session
owns the playbook. Delegates perform only their assigned scoped work.

The installed adapter is the only native skill in this distribution.
An official `/name` means read the exact
`../../pstack-codex/pstack/skills/name/SKILL.md`, not invoke a Codex slash command
or assume that an official skill is registered. Missing files are unsupported
steps, not permission to install another plugin.

Preserve all existing AGENTS.md instructions, user limits, repository rules,
sandbox policy, and approval gates. Loading pstack does not authorize publishing,
merging, deploying, service operations, credential access, permission expansion,
configuration changes, or new external integrations. Do not install setup-pstack
configuration or select a model as a side effect. Inherit the parent's model and
operator defaults without overrides.

Inspect the tools actually exposed by this Codex session before using them.
If delegation is unavailable or forbidden, do the scoped steps sequentially and
report the limitation. Sequential work cannot satisfy a required independent,
multi-model, or isolation gate. A missing required gate remains a blocker.
Report actual checks and gaps separately. File reads and contract tests do not
prove native discovery, successful delegation, or a live Codex smoke test.
