---
description: Generate a starter AGENT.md based on the current project structure
---

Run an initialization pass over the current project and write a starter `AGENT.md` to the project root.

1. Explore the project (do not read files inside `.git/`, `node_modules/`, or other dependency/build output directories):
   - List the top-level files and directories.
   - Read `README.md` (or `README`), any root config files (`package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml`, `pom.xml`, `CMakeLists.txt`, `Makefile`, `Taskfile.yml`, `justfile`, `docker-compose.yml`, etc.), and skim the main source directories.
2. From what you find, write a concise `AGENT.md` containing:
   - A one-paragraph summary of the project's purpose.
   - The tech stack (languages, frameworks, key dependencies).
   - Project layout: what the main directories contain.
   - Common commands: build, test, lint, format, run/dev server, deploy (only include the ones that actually exist).
   - Any conventions you can infer (module system, test framework style, code organization).
   - Notes on anything unusual or worth knowing for future sessions.
3. Rules:
   - Keep it short and factual. Do not invent commands, dependencies, or features you did not observe. Write "none found" instead of guessing.
   - If `AGENT.md` already exists, refine it accordingly.
   - Write the file in the current working directory.
4. Report back: where the file was written and a summary of what you included.
