# Codex compatibility contract

This table is the sole normative Cursor-to-Codex mapping. The adapter translates
tools and paths, not authority. The official files remain byte-for-byte intact.
`<adapter>` means the directory containing this document. `<pstack>` means
`<adapter>/../../pstack-codex/pstack`. Resolve both before reading resources.
The installed official tree is outside `.agents/skills` discovery.

Current Codex documentation describes native skills and parallel subagents.
The source examples below are anchored to Codex commit
`09358089b0dd2cc5aa7c6c37ad4c834e9066561c`, not a guarantee about every installed
client. The runtime tool names and schemas are authoritative. No live Codex
binary smoke test has been performed for this adapter.

Checked on 2026-11-06 against the official documentation and the latest stable
[Codex release, rust-v0.166.0](https://github.com/openai/codex/releases/tag/rust-v0.166.0).
The six source files cited below are identical in that release and the cited
commit. This source comparison is not a live runtime test.

| ID | Upstream instruction | Codex action | Fallback and boundary | Evidence |
| --- | --- | --- | --- | --- |
| skills | Load a skill, `/name`, `disable-model-invocation` | Invoke this adapter with `$pstack-codex` or `/skills`. Read official skills through `<pstack>/skills/name/SKILL.md`. Only this adapter is installed natively. | Cursor's `disable-model-invocation: true` is not a Codex invocation policy. The parser does not interpret it. Keep upstream outside native discovery rather than transform frontmatter. Missing official resources remain gaps. | [Skills][skills], [parser][parser], [adapter](./SKILL.md). |
| read | `Read` | Use an available file reader, or read files through the exposed shell tool. Source example `exec_command` in the shell spec. | Respect read restrictions. A different command is not a bypass for a denied read. | [Shell][shell]. |
| grep | `Grep` | Use an exposed search tool or `rg` through the shell, scoped to relevant files. | If `rg` is absent, use an available literal or regex search. Do not search private session histories. | [Shell][shell]. |
| glob | `Glob` | Use an exposed glob tool or scoped file enumeration through the shell. | Do not assume Cursor tool names exist in Codex. | [Shell][shell]. |
| bash | `Bash` | Use the runtime shell schema. Source example `exec_command`, with `write_stdin` for an existing command session. | Preserve command approvals and sandbox limits. Do not enable another shell or permission mode to bypass a rejection. | [Shell][shell], [instructions][instructions]. |
| edits | File edits | Use the exposed patch tool. Source example `apply_patch` takes freeform patch text, not JSON. | Follow the actual schema and repository edit rules. Do not rewrite official pstack. | [Patch][patch]. |
| questions | `AskQuestion` | Use the exposed structured question tool when available. Source example `request_user_input`. Explain the decision and consequences first. | If unavailable in the current mode, ask a plain-language question and wait when approval is required. Never treat tool absence as approval. | [Questions][questions]. |
| plans | Open a todolist | Use an exposed plan tool. Source example `update_plan`. | Keep a Markdown checklist if no plan tool exists. Do not change configuration to enable it. | [Plans][plans]. |
| poteto-role | `Task`, `subagent_type: poteto-agent` | Choose a runtime-available implementation role such as `worker` or `default`, with the original `agents/poteto-agent.md` role in the prompt. Read the delegate brief contract below. | No native custom role is assumed or installed. Without agents, own the scoped work sequentially. The primary still owns the playbook. | [Subagents][subagents], [agent schemas][agents]. |
| comment-role | `subagent_type: comment-sicko` | Choose an available role and prompt the original `agents/comment-sicko.md` role. Explicitly say do not edit files. Include all required brief paths. | A read-only prompt is not an independent sandbox. If required read-only enforcement is unavailable, report a blocker. | [Subagents][subagents], [agent schemas][agents]. |
| general-role | `subagent_type: generalPurpose` | Choose an available general role such as `default`, only when the routed workflow calls for generalPurpose. Include its routed workflow and the required brief paths. | Do not substitute a general role for the original poteto-agent instructions merely because that role is not registered. | [Subagents][subagents], [agent schemas][agents]. |
| readonly | `readonly: true` | Request read-only behavior explicitly, and use an authorized read-only environment if one is required. `explorer` is read-heavy, not proof of enforcement. | Children inherit parent permissions. A prompt does not create a separate read-only sandbox. Do not change permissions or claim isolation. | [Subagents][subagents]. |
| background | `run_in_background: true` | Delegate only independent work. In source V1, `multi_agent_v1.spawn_agent` uses agent IDs and `fork_context`. In source V2, `spawn_agent` requires `task_name` and `message`, with `fork_turns` values `all` or `none`. V2 defaults to `all`. | No universal background flag or JSON call is prescribed. Inspect the runtime. V1 `wait_agent` waits for final status. V2 `wait_agent` only signals mailbox activity and does not return result contents. Collect actual final messages separately. Do not confuse `wait` with `wait_agent`, poll in a sleep loop, or call a mailbox wake-up a completed review. | [Agent schemas][agents]. |
| resume | Resume or message a delegate | Start fresh agents by default with consolidated scope. Reuse only costly state in an existing checkout, uncommitted edits, or running process. Source V1 has `send_input`, `resume_agent`, and `close_agent`. V2 has `send_message`, `followup_task`, and `interrupt_agent`, addressed by task names. | V2 `send_message` does not trigger a turn. Use only the actual runtime schema. Do not invent a universal `resume` field or reuse a finished agent for unrelated work. | [Agent schemas][agents], `<pstack>/skills/poteto-mode/SKILL.md`. |
| attachments | `file_attachments` | Put exact readable file paths and scope in the message. Include the required brief paths below. | No universal attachments field is verified. Do not fabricate an attachment upload or expose private file contents to a new recipient. | [Agent schemas][agents]. |
| local | `environment: local` | Name the authorized working directory in the brief. Separate writable work before parallel agents touch the same files. | Spawning an agent does not create a worktree or filesystem isolation. Use sequential work when separation is unavailable. | [Subagents][subagents], [agent schemas][agents]. |
| cloud | `environment: cloud`, `cloud_base_branch` | No equivalent cloud provisioner is bundled. An explicitly authorized disposable local worktree at the named base can serve local work. | Never invent cloud fields or claim local work is a cloud run. Required cloud or isolation gates remain blockers when unavailable. | [Agent schemas][agents]. |
| models | Model slugs, reasoning suffixes, diverse panels | Inherit the parent's model and operator defaults. Omit model and reasoning overrides. Record actual model evidence before claiming diversity. | Cursor model slugs are not Codex model IDs. Same-model or sequential checks are not an independent multi-model panel. If the required panel is unavailable, report a blocker. | [Subagents][subagents]. |
| setup | `/setup-pstack`, model configuration | Read it only if relevant to a separately authorized configuration task. This distribution does not install setup-pstack configuration, custom agent TOML, providers, or permission settings. | Loading the adapter never changes `.codex/config.toml`, global configuration, or existing instruction files. No automatic conversion or model override. | [Subagents][subagents], [instructions][instructions]. |
| unsupported | Cursor Automations, Bugbot initiation, `/loop`, Cursor transcript paths | No verified native equivalent is bundled. Use only separately authorized repository tools for an applicable check. | Name unsupported steps. Do not start a service, add integrations, mine unrelated histories, or report an unperformed gate as passed. | [Agent schemas][agents], [instructions][instructions]. |
| companions | `deslop`, `control-cli`, `control-ui`, built-in create-skill | These companion skills are not bundled in the official pstack tree. Use authorized tools and report the gap. | Do not install another plugin implicitly or claim a named skill ran. A required acceptance gate remains a blocker. | `<pstack>/skills/poteto-mode/SKILL.md`, [Skills][skills]. |
| sequential | Delegation unavailable, forbidden, or nesting limit reached | Preserve the scoped steps in order and perform allowed work directly. Report which steps were sequential and what was not verified. | Sequential fallback cannot satisfy required independent, multi-model, or isolation gates. Those gates remain blockers, not successful skips. Do not fabricate independent or diverse review. | [Subagents][subagents], [instructions][instructions]. |

## Delegate brief contract

Every delegate brief carries the original goal, assigned scope, success criteria,
restrictions, approval boundaries, and authorized working directory. Include the
exact paths below, resolved from the installed adapter directory into paths the
delegate can read. Do not rely on inherited conversation history.

- Adapter instructions at `<adapter>/SKILL.md` and `<adapter>/MAPPING.md`.
- Original role at `<adapter>/../../pstack-codex/pstack/agents/poteto-agent.md`,
  or `<adapter>/../../pstack-codex/pstack/agents/comment-sicko.md` for that role.
  For generalPurpose, include the exact routed skill path and identify the
  general-purpose role. There is no bundled generalPurpose agent definition.
- Full official mode at
  `<adapter>/../../pstack-codex/pstack/skills/poteto-mode/SKILL.md`.

Tell the delegate to read the adapter, original role where present, and full
official mode before work, then each principle leaf it applies. It owns only its
scoped assignment, not the parent's playbook. Preserve user prohibitions on
further delegation. Select an available role without installing agent TOML or
changing the model, permissions, or global configuration. Fresh agents are the
default. A new agent identity is not automatically a fresh context. For an
official fresh-agent step, request a fresh context using the actual exposed
schema, for example V2 `fork_turns=none` when available or the corresponding V1
`fork_context` setting. If that is unavailable, disclose inherited context and
do not claim a fresh-context gate passed.
Independent review requires a genuinely separate reviewer and evidence
for its verdict. A sequential self-check is not an independent reviewer.

## Evidence references

[skills]: https://developers.openai.com/codex/build-skills.md
[subagents]: https://developers.openai.com/codex/agent-configuration/subagents.md
[instructions]: https://developers.openai.com/codex/agent-configuration/agents-md.md
[shell]: https://github.com/openai/codex/blob/09358089b0dd2cc5aa7c6c37ad4c834e9066561c/codex-rs/core/src/tools/handlers/shell_spec.rs
[patch]: https://github.com/openai/codex/blob/09358089b0dd2cc5aa7c6c37ad4c834e9066561c/codex-rs/core/src/tools/handlers/apply_patch_spec.rs
[plans]: https://github.com/openai/codex/blob/09358089b0dd2cc5aa7c6c37ad4c834e9066561c/codex-rs/core/src/tools/handlers/plan_spec.rs
[questions]: https://github.com/openai/codex/blob/09358089b0dd2cc5aa7c6c37ad4c834e9066561c/codex-rs/core/src/tools/handlers/request_user_input_spec.rs
[agents]: https://github.com/openai/codex/blob/09358089b0dd2cc5aa7c6c37ad4c834e9066561c/codex-rs/core/src/tools/handlers/multi_agents_spec.rs
[parser]: https://github.com/openai/codex/blob/09358089b0dd2cc5aa7c6c37ad4c834e9066561c/codex-rs/skills/src/parser.rs
