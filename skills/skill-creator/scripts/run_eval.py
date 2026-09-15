#!/usr/bin/env python3
"""Run trigger evaluation for a skill description on Pi.

Tests whether a skill's description causes Pi to trigger (read the skill)
for a set of queries. Outputs results as JSON.

How it works: for each query, a throwaway copy of the skill is created with
the description under test written into its SKILL.md, then pi runs headless
(`pi -p --mode json --skill <copy>`) with only that skill available. The
skill counts as triggered when the model reads the skill's SKILL.md through
any tool during the run.
"""

import argparse
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scripts.utils import parse_skill_md


def write_skill_copy(skill_path: Path, description: str, dest: Path) -> Path:
    """Create a copy of the skill with `description` in its frontmatter.

    Only SKILL.md is rewritten; every other entry is symlinked so we don't
    pay to copy references/assets for every query run.
    """
    dest.mkdir(parents=True, exist_ok=True)
    name, _, _ = parse_skill_md(skill_path)

    source_md = (skill_path / "SKILL.md").read_text()
    lines = source_md.split("\n")
    # Replace the description line (single-line or block scalar).
    out_lines: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("description:") and not replaced:
            out_lines.append("description: " + json.dumps(description))
            replaced = True
            i += 1
            # Skip a folded/literal YAML block if the original used one.
            while i < len(lines) and (lines[i].startswith("  ") or lines[i].startswith("\t")):
                i += 1
            continue
        out_lines.append(line)
        i += 1
    if not replaced:
        raise ValueError(f"No description field found in {skill_path / 'SKILL.md'}")
    (dest / "SKILL.md").write_text("\n".join(out_lines))

    for child in skill_path.iterdir():
        if child.name in ("SKILL.md", "__pycache__", "evals"):
            continue
        target = dest / child.name
        try:
            target.symlink_to(child.resolve(), target_is_directory=child.is_dir())
        except OSError:
            if child.is_dir():
                shutil.copytree(child, target, dirs_exist_ok=True)
            else:
                shutil.copy2(child, target)
    return dest


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    skill_path: str,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered."""
    skill_dir = Path(skill_path)
    tmp_root = Path(tempfile.mkdtemp(prefix="pi-skill-eval-"))
    temp_skill = tmp_root / skill_dir.name
    try:
        write_skill_copy(skill_dir, skill_description, temp_skill)
        # The model may reference the skill by absolute path or by a path
        # relative to cwd. Both contain the temp directory name, so matching
        # on that is enough.
        needle = str(temp_skill)

        cmd = [
            "pi",
            "-p",
            "--mode",
            "json",
            "--no-session",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-context-files",
            "--skill",
            str(temp_skill),
        ]
        if model:
            cmd.extend(["--model", model])
        cmd.append(query)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=str(tmp_root),
        )

        triggered = False
        start_time = time.time()
        buffer = ""
        try:
            while time.time() - start_time < timeout:
                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if not ready:
                    if process.poll() is not None:
                        break
                    continue
                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if event.get("type") != "tool_execution_start":
                        continue
                    # A read of the skill file (or any tool touching the temp
                    # skill directory, e.g. `cat` via bash) counts as a
                    # trigger.
                    if needle in json.dumps(event.get("args", {})):
                        triggered = True
                        break
                if triggered:
                    break
        finally:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            process.stdout.close()

        return triggered
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    skill_path: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(skill_path),
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description on Pi")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Model to use for pi -p (default: user's configured model)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _ = parse_skill_md(skill_path)
    description = args.description or original_description

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        skill_path=skill_path,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
