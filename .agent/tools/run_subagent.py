#!/usr/bin/env python
"""
Main entry point for running Subagents.

This script orchestrates the complete Subagent workflow:
1. Initialize audit directory structure
2. Validate request.json
3. Execute Subagent via Codex CLI
4. Validate response.json

This is the primary interface for Master Agent to delegate tasks to Subagents.
"""
import argparse
import sys

from lib import (
    default_codex_cmd,
    REQUIRED_FIELDS,
)
from lib.modules import (
    ensure_subagent_paths,
    validate_request_file,
    execute_subagent,
    execute_subagent_claude,
    validate_response_file,
)


def main():
    parser = argparse.ArgumentParser(
        description="Create audit subagent directory and run Subagent.",
    )
    parser.add_argument("--phase", default=None, help="Phase name, e.g. phase-001")
    parser.add_argument("--task", dest="task_name", default=None, help="Task name, e.g. task-001")
    parser.add_argument(
        "--subagent", dest="subagent_name", default=None, help="Subagent name, e.g. subagent-001"
    )
    parser.add_argument("--audit-root", default=".agent/audit", help="Audit root directory.")
    parser.add_argument("--request", default=None, help="Path to request.json.")
    parser.add_argument("--response", default=None, help="Path to response.json.")
    parser.add_argument("--prompt-file", default=".agent/docs/subagent_prompt.md", help="Path to subagent prompt file.")

    # Execution engine selection
    parser.add_argument(
        "--engine",
        default="codex",
        choices=["codex", "claude"],
        help="Execution engine: codex (Codex CLI) or claude (Claude API). Default: codex",
    )

    # Codex CLI specific parameters
    parser.add_argument("--codex-cmd", default=None, help="Codex CLI command path (only for --engine codex).")
    parser.add_argument("--profile", default=None, help="Codex config profile (only for --engine codex).")
    parser.add_argument(
        "--sandbox",
        default=None,
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode for Codex exec (only for --engine codex).",
    )
    parser.add_argument("--cd", default=".", help="Working directory for Codex exec (only for --engine codex).")
    parser.add_argument("--skip-git-repo-check", action="store_true", help="Skip git repo check (only for --engine codex).")
    parser.add_argument(
        "--codex-args",
        nargs=argparse.REMAINDER,
        default=None,
        help="Extra args for codex exec (use after --codex-args, only for --engine codex).",
    )

    # Claude API specific parameters
    parser.add_argument("--model", default="claude-sonnet-4-5-20250929", help="Claude model to use (only for --engine claude).")
    parser.add_argument("--api-key", default=None, help="Anthropic API key (only for --engine claude, or set ANTHROPIC_API_KEY env var).")

    # Common parameters
    parser.add_argument("--idle-timeout", type=int, default=60, help="Terminate if stderr is silent for N seconds.")

    args = parser.parse_args()

    # Set default codex command (only needed for codex engine)
    if args.engine == "codex" and args.codex_cmd is None:
        args.codex_cmd = default_codex_cmd()

    # Step 1: Initialize audit directory structure
    request_path, response_path = ensure_subagent_paths(
        args.audit_root,
        args.phase,
        args.task_name,
        args.subagent_name,
        args.request,
        args.response,
    )

    # Step 2: Validate request.json
    validation_result = validate_request_file(request_path)
    if not validation_result["valid"]:
        errors = validation_result["errors"]
        # Filter out warnings
        real_errors = [e for e in errors if not e.startswith("Warning:")]
        if real_errors:
            print(f"Request validation failed:", file=sys.stderr)
            for error in real_errors:
                print(f"  {error}", file=sys.stderr)
            sys.exit(1)

    # Step 3: Execute Subagent via selected engine
    if args.engine == "codex":
        exit_code = execute_subagent(
            request_path=request_path,
            response_path=response_path,
            prompt_file=args.prompt_file,
            codex_cmd=args.codex_cmd,
            profile=args.profile,
            sandbox=args.sandbox,
            cd=args.cd,
            skip_git_repo_check=args.skip_git_repo_check,
            idle_timeout=args.idle_timeout,
            codex_args=args.codex_args,
        )
    elif args.engine == "claude":
        exit_code = execute_subagent_claude(
            request_path=request_path,
            response_path=response_path,
            prompt_file=args.prompt_file,
            api_key=args.api_key,
            model=args.model,
            cwd=args.cd,
        )
    else:
        print(f"Error: Unknown engine '{args.engine}'", file=sys.stderr)
        sys.exit(1)

    # Step 4: Validate response.json (best effort, don't fail if invalid)
    response_result = validate_response_file(response_path)
    if not response_result["valid"]:
        print("Warning: Response validation failed:", file=sys.stderr)
        for error in response_result["errors"]:
            print(f"  {error}", file=sys.stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
