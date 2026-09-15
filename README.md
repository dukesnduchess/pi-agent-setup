# pi-agent-setup

Pi agent setup (extensions, skills, prompts, SYSTEM.md) which has been useful for my use cases and could be point of reference for anyone getting started with Pi as your coding harness.

## What's in here

### `APPEND_SYSTEM.md` - safety guardrails

Pi is deliberately minimal, and that includes its system prompt. It ships with no built-in behavioral guardrails: no rules about destructive shell commands, no protected-file list, no operational boundaries. Out of the box the model gets tool access and not much else.

Most other coding agents launch with a baseline of safety instructions baked in. Pi does not, so I bring my own. This file adds:

- **Behavioral instructions** - response style and phrasing preferences.
- **Banned commands and actions** - no destructive file operations on system paths, no drive formatting or partitioning, no power/init changes, no piping remote content into shells, no fork bombs, no global system modifications. Plus git rules: no force pushes to protected branches, no destructive cleans without approval, no deleting primary remote branches, no hard resets of shared history.
- **Protected files and directories** - secrets and credential stores (`.env`, SSH keys, cloud credentials, tokens), database files, package lockfiles, and a strict no-touch zone of system paths (`/etc`, `/usr`, `/var`, `/bin`, `/proc`, `/sys`, `/dev`).
- **Read-only and managed paths** - `.git/` and other VCS metadata, dependency caches, and build output directories.
- **Operational instructions** - a "script first" rule for repetitive or high-volume tasks.

**Install:** copy it to `~/.pi/agent/APPEND_SYSTEM.md` for global use, or `.pi/APPEND_SYSTEM.md` inside a project. Pi appends it to the default system prompt rather than replacing it. Note that a project-local `.pi/APPEND_SYSTEM.md` is a trust-requiring resource, so Pi will ask before loading it.

This is a starting point, not a policy engine. It is prompt-level guidance for the model, not an enforced sandbox - Pi still runs with your user account's permissions.

### `extensions/skill-autocomplete.ts` - `$` skill autocomplete

Pi's built-in skill invocation is `/skill:name`, which only works at the start of a prompt. I tend to reference skills in the middle of a prompt, which the slash command can't do.

This extension adds a `$`-triggered dropdown: type `$` at a token boundary, pick a skill, and a `$skill-name` marker is inserted at the cursor. On submit the marker stays readable in your prompt, while the full `SKILL.md` body is delivered to the model as a separate message - the same content Pi injects for `/skill:name`.

Nothing significant, just a convenience I like having.

**Install:** place in `~/.pi/agent/extensions/` for global availability, or `.pi/extensions/` for a single project, then restart Pi or run `/reload`.

### `skills/skill-creator/` - skill authoring toolkit

A skill for creating new skills, editing existing ones, and measuring skill performance: write a draft, run test prompts, evaluate results qualitatively and quantitatively with the bundled eval viewer, then iterate. It also includes a description optimizer for improving trigger accuracy.

**Forked from Anthropic's `skill-creator`**: <https://github.com/anthropics/skills/tree/main/skills/skill-creator>

The upstream version targets Claude's harness. This fork is modified to work under Pi:

- The Claude.ai and Cowork sections have been removed; a **Pi-specific notes** section replaces them.
- The eval scripts (`run_eval.py`, `improve_description.py`, `run_loop.py`) were ported to shell out to headless `pi -p` instead of the `claude` CLI. Trigger detection works by watching for the model reading the skill's `SKILL.md`.
- The eval viewer accounts for a terminal-first workflow: server mode when a browser is available, `--static` output otherwise.
- Packaging into a `.skill` file is documented as optional, since Pi installs skills directly from directories.
- Adapted for Pi's native `subagent` tool, which drives the parallel test runs, grading, and blind comparison steps.

Licensed Apache 2.0, as upstream. See `LICENSE.txt`.

**Install:** copy the `skill-creator/` directory into `~/.pi/agent/skills/` (global) or `.pi/skills/` (project). Test it with `pi --skill <path>`.

## Layout

```
APPEND_SYSTEM.md                     # safety guardrails and operational boundaries
extensions/
  skill-autocomplete.ts              # $ skill autocomplete anywhere in a prompt
skills/
  skill-creator/
    SKILL.md                         # the skill definition and workflow
    agents/                          # subagent prompts: grader, comparator, analyzer
    assets/                          # HTML template for the eval review UI
    eval-viewer/                     # browser UI for reviewing eval results
    references/schemas.md            # JSON schemas for evals.json, grading.json, etc.
    scripts/                         # eval, benchmarking and packaging scripts
```

## Credits

- [`skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator) - Anthropic, Apache 2.0.
- [Pi](https://github.com/earendil-works/pi) - the coding harness these files are built for.
