# pi-agent-setup

Pi agent setup (extensions, skills, prompts, SYSTEM.md) which has been useful for my use cases and could be point of reference for anyone getting started with Pi as your coding harness.

## What's in here

- **`APPEND_SYSTEM.md`** - Safety guardrails for Pi. Pi is deliberately minimal, including its system prompt: unlike other coding agents it launches with no built-in behavioral rules or protected-path list, so I bring my own. Appends to the default prompt, it does not replace it. Install to `~/.pi/agent/` (global) or `.pi/` (project).
- **`extensions/skill-autocomplete.ts`** - `$`-triggered skill autocomplete that works anywhere in a prompt. Pi's built-in `/skill:name` only works at the start of a prompt, and I tend to reference skills mid-prompt. Nothing significant, just a convenience I like having.
- **`prompts/init.md`** - `/init` slash command that explores the current project and writes a starter `AGENT.md` (purpose, stack, layout, common commands, conventions).
- **`skills/skill-creator/`** - Create, edit and benchmark skills, with an eval viewer and a description optimizer for trigger accuracy. Forked from [Anthropic's `skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator) and adapted for Pi: Claude.ai/Cowork sections removed, eval scripts ported to headless `pi -p`, subagent workflow used for test runs. Apache 2.0.

## Layout

```
APPEND_SYSTEM.md                     # safety guardrails and operational boundaries
extensions/
  skill-autocomplete.ts              # $ skill autocomplete anywhere in a prompt
prompts/
  init.md                            # /init - generate a starter AGENT.md
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
- [Pi](https://github.com/earendil-works/pi) - the coding harness these files are built for, developed by @badlogicgames (Mario Zechner). You should read his blog on how he came up with this [minimal coding agent](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/), it could serve as point of reference too while you build your own.
