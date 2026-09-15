// Dollar Skill Autocomplete
//
// Adds `$`-triggered skill suggestions to the editor, working anywhere in a
// prompt — not just at the start like the built-in `/skill:name` command.
//
//  - Type `$` (at a token boundary, e.g. after a space or at the start) to
//    open a dropdown of every skill currently loaded in Pi.
//  - Selecting a skill inserts a `$skill-name` marker at the cursor.
//  - On submit, the literal `$skill-name` marker stays untouched in your typed
//    prompt (so it always reads cleanly), BUT the full SKILL.md body for every
//    resolved marker is delivered to the model as a separate custom message,
//    same content pi injects for `/skill:name`. So you get full-context skill
//    loading without "$ast-analysis" being replaced by a wall of text.
//
// Install: place in ~/.pi/agent/extensions/ for global availability, or
// .pi/extensions/ for the current project. Restart pi (or /reload) to load.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { stripFrontmatter } from "@earendil-works/pi-coding-agent";
import { fuzzyFilter, type AutocompleteItem } from "@earendil-works/pi-tui";
import { readFileSync } from "node:fs";
import { dirname } from "node:path";

const MAX_SUGGESTIONS = 12;

/** A skill as reported by pi.getCommands() for source === "skill". */
type Skill = {
	name: string;
	description?: string;
	path: string;
	baseDir?: string;
};

function getSkills(pi: ExtensionAPI): Skill[] {
	try {
		return pi
			.getCommands()
			.filter((command) => command.source === "skill")
			.map((command) => {
				const info = command.sourceInfo ?? { path: "" };
				// The invokable command name is literally "skill:<name>".
				const rawName = command.name.startsWith("skill:") ? command.name.slice(6) : command.name;
				return {
					name: rawName,
					description: command.description,
					path: info.path || "",
					baseDir: info.baseDir,
				};
			})
			.filter((skill) => skill.name.length > 0 && skill.path.length > 0);
	} catch {
		return [];
	}
}

/**
 * Find a `$name` token at the end of the text before the cursor.
 * Requires `$` to sit at a token boundary (start of line or preceded by a
 * non-alphanumeric char) so `$` inside a word like `foo$bar` is ignored.
 * Returns the partial name (possibly empty) or null when no trigger is active.
 */
function extractDollarToken(textBeforeCursor: string): string | null {
	const match = textBeforeCursor.match(/(?:^|[^a-zA-Z0-9])\$([a-zA-Z0-9-]*)$/);
	return match ? match[1] ?? "" : null;
}

function buildSkillItems(skills: Skill[], query: string): AutocompleteItem[] {
	// Fuzzy match against name + description, then list.
	const matches = fuzzyFilter(skills, query, (skill) => `${skill.name} ${skill.description ?? ""}`);
	return matches.slice(0, MAX_SUGGESTIONS).map((skill) => ({
		value: "$" + skill.name,
		label: "$" + skill.name,
		...(skill.description && { description: skill.description }),
	}));
}

/**
 * Build the same <skill> XML block pi injects when expanding a /skill:name
 * command, carrying the full SKILL.md body of the resolved skill.
 */
function buildSkillBlock(skill: Skill): string {
	try {
		const content = readFileSync(skill.path, "utf-8");
		const body = stripFrontmatter(content).trim();
		const baseDir = skill.baseDir ?? dirname(skill.path);
		return `<skill name="${skill.name}" location="${skill.path}">\nReferences are relative to ${baseDir}.\n\n${body}\n</skill>`;
	} catch {
		return ""; // Unreadable skill -> deliver nothing, keep the literal marker.
	}
}

export default function (pi: ExtensionAPI): void {
	pi.on("session_start", async (_event, ctx) => {
		// 1) Autocomplete dropdown: type `$` anywhere to pick a skill.
		ctx.ui.addAutocompleteProvider((current) => ({
			triggerCharacters: ["$"],
			async getSuggestions(lines, cursorLine, cursorCol, options) {
				const line = lines[cursorLine] ?? "";
				const beforeCursor = line.slice(0, cursorCol);
				const partial = extractDollarToken(beforeCursor);
				if (partial === null) {
					return current.getSuggestions(lines, cursorLine, cursorCol, options);
				}

				const skills = getSkills(pi);
				if (skills.length === 0) {
					return current.getSuggestions(lines, cursorLine, cursorCol, options);
				}

				const items = buildSkillItems(skills, partial);
				if (items.length === 0) {
					return current.getSuggestions(lines, cursorLine, cursorCol, options);
				}

				return { prefix: "$" + partial, items };
			},

			applyCompletion(lines, cursorLine, cursorCol, item, prefix) {
				// Only handle our own `$skill` completions. Delegate everything else
				// (slash commands, @-attachments, file paths) back to the base
				// provider: its applyCompletion special-cases slash commands (inserts
				// the leading "/" and a trailing space) which the generic
				// replacement below would otherwise eat (e.g. "clear" instead of
				// "/clear "), breaking built-in /commands.
				if (!prefix.startsWith("$") || !item.value.startsWith("$")) {
					return current.applyCompletion(lines, cursorLine, cursorCol, item, prefix);
				}

				const line = lines[cursorLine] ?? "";
				const beforeCursor = line.slice(0, cursorCol);
				const beforePrefix = beforeCursor.slice(0, beforeCursor.length - prefix.length);
				const afterCursor = line.slice(cursorCol);
				const newLine = beforePrefix + item.value + afterCursor;
				const newLines = [...lines];
				newLines[cursorLine] = newLine;
				return {
					lines: newLines,
					cursorLine,
					cursorCol: beforePrefix.length + item.value.length,
				};
			},

			shouldTriggerFileCompletion(lines, cursorLine, cursorCol) {
				return current.shouldTriggerFileCompletion?.(lines, cursorLine, cursorCol) ?? true;
			},
		}));
	});

	// 2) On submit, resolve every `$skill-name` marker in the prompt against the
	//    loaded skill registry and deliver each resolved skill's full content as
	//    a separate hidden custom message. The typed `$skill-name` marker stays
	//    as-is in the user's own prompt (never replaced), while the model still
	//    receives the full SKILL.md body — matching how /skill: supplies content
	//    without the in-place substitution that made the prompt look messy.
	pi.on("before_agent_start", async (event) => {
		const text = event.prompt;
		if (!text.includes("$")) return; // fast path

		const skills = new Map(getSkills(pi).map((skill) => [skill.name, skill]));
		const seen = new Set<string>();
		const blocks: string[] = [];

		for (const match of text.matchAll(/(^|[^a-zA-Z0-9])\$([a-zA-Z0-9-]+)/g)) {
			const name = match[2];
			if (seen.has(name)) continue;
			const skill = skills.get(name);
			if (!skill) continue;
			seen.add(name);
			const block = buildSkillBlock(skill);
			if (block) blocks.push(block);
		}

		if (blocks.length === 0) return;
		return {
			message: {
				customType: "skill-doc",
				content: [{ type: "text", text: blocks.join("\n\n") }],
				display: false, // keep the user's typed prompt clean
			},
		};
	});
}