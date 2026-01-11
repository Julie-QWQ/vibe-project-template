#!/usr/bin/env python
"""
Execute Subagent via Codex CLI.

This script handles the actual execution of the Subagent using Codex CLI,
including process management, stream handling, and timeout monitoring.
"""
import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

# Import utility functions
try:
    from .lib import (
        default_codex_cmd,
        load_prompt,
        build_prompt,
        write_info_file,
        write_fallback_response,
    )
except ImportError:
    # Fallback implementations when run as standalone script
    import json
    from datetime import datetime, timezone

    def default_codex_cmd():
        return "codex.cmd" if sys.platform.startswith("win") else "codex"

    def load_prompt(path):
        prompt_path = Path(path)
        if not prompt_path.exists():
            raise SystemExit(f"Prompt file not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8-sig").strip()

    def build_prompt(base_prompt, request_obj):
        import json
        request_json = json.dumps(request_obj, ensure_ascii=True, indent=2)
        return (
            f"{base_prompt}\n\n"
            "Request JSON:\n"
            "```json\n"
            f"{request_json}\n"
            "```"
        )

    def write_fallback_response(response_path, task_id, summary, issues):
        import json
        payload = {
            "version": "1.0",
            "task_id": task_id or "",
            "status": "failed",
            "summary": summary,
            "outputs": [],
            "issues": issues if issues else [],
        }
        response_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def read_stream(stream, out_queue):
    """Read from a stream and put chunks into a queue."""
    try:
        while True:
            chunk = stream.read(1024)
            if not chunk:
                break
            out_queue.put(chunk)
    finally:
        out_queue.put(None)


def execute_subagent(
    request_path,
    response_path,
    prompt_file=".agent/docs/subagent_prompt.md",
    codex_cmd=None,
    profile=None,
    sandbox=None,
    cd=".",
    skip_git_repo_check=False,
    idle_timeout=60,
    codex_args=None,
):
    """
    Execute Subagent via Codex CLI.

    Args:
        request_path: Path to request.json
        response_path: Path to response.json (will be created)
        prompt_file: Path to subagent prompt file
        codex_cmd: Codex CLI command (default: auto-detected)
        profile: Codex profile to use
        sandbox: Sandbox mode (read-only, workspace-write, danger-full-access)
        cd: Working directory for Codex exec
        skip_git_repo_check: Skip git repository check
        idle_timeout: Timeout in seconds if no stderr output
        codex_args: Additional arguments for codex exec

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    import os
    request_path = Path(request_path)
    response_path = Path(response_path)

    # Validate request file exists
    if not request_path.exists():
        raise SystemExit(f"Request file not found: {request_path}")

    # Load request JSON
    import json
    request_raw = request_path.read_text(encoding="utf-8-sig")
    try:
        request_obj = json.loads(request_raw)
    except json.JSONDecodeError:
        raise SystemExit(f"Request JSON is invalid: {request_path}")

    # Setup paths and record start time
    output_dir = response_path.parent
    stderr_path = output_dir / "stderr.txt"
    started_at = datetime.now(timezone.utc).isoformat()

    # Write initial info file and initialize stderr
    write_info_file(
        output_dir=output_dir,
        engine="codex",
        model=profile,
        started_at=started_at,
        pid=os.getpid(),
        working_directory=cd,
        command_args=["--idle-timeout", str(idle_timeout)] + (["--sandbox", sandbox] if sandbox else []),
    )
    stderr_path.write_text("", encoding="utf-8")

    # Build prompt
    base_prompt = load_prompt(prompt_file)
    prompt = build_prompt(base_prompt, request_obj)

    # Build Codex command
    if codex_cmd is None:
        codex_cmd = default_codex_cmd()

    cmd = [codex_cmd, "exec"]
    if profile:
        cmd += ["--profile", profile]
    if sandbox:
        cmd += ["--sandbox", sandbox]
    if cd:
        cmd += ["--cd", cd]
    if skip_git_repo_check:
        cmd += ["--skip-git-repo-check"]
    cmd += ["--output-last-message", str(response_path)]
    if codex_args:
        cmd += codex_args
    cmd.append("-")

    # Start process
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # Send prompt
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except Exception:
        proc.kill()
        raise

    # Stream handling
    from queue import Empty, Queue
    stdout_queue = Queue()
    stderr_queue = Queue()
    stdout_chunks = []
    stderr_chunks = []

    threading.Thread(target=read_stream, args=(proc.stdout, stdout_queue), daemon=True).start()
    threading.Thread(target=read_stream, args=(proc.stderr, stderr_queue), daemon=True).start()

    last_output = time.monotonic()
    stdout_done = False
    stderr_done = False
    timed_out = False

    # Monitor process
    while True:
        try:
            item = stdout_queue.get(timeout=0.1)
            if item is None:
                stdout_done = True
            else:
                stdout_chunks.append(item)
        except Empty:
            pass

        try:
            item = stderr_queue.get_nowait()
            if item is None:
                stderr_done = True
            else:
                stderr_chunks.append(item)
                last_output = time.monotonic()
        except Empty:
            pass

        if stdout_done and stderr_done:
            break

        if time.monotonic() - last_output > idle_timeout:
            timed_out = True
            proc.kill()
            break

    proc.wait()

    # Write stderr
    stderr_text = "".join(stderr_chunks)
    if timed_out:
        stderr_text = (stderr_text + "" if stderr_text else "") + f"Terminated after {idle_timeout}s of no output."
    stderr_path.write_text(stderr_text, encoding="utf-8")

    # Handle timeout
    if timed_out:
        write_fallback_response(
            response_path,
            request_obj.get("task_id"),
            f"Subagent timed out after {idle_timeout}s of no stderr output",
            ["timeout", f"no stderr output for {idle_timeout}s"],
        )
        # Update info.json with timeout error
        write_info_file(
            output_dir=output_dir,
            engine="codex",
            model=profile,
            started_at=started_at,
            pid=os.getpid(),
            exit_code=1,
            working_directory=cd,
            command_args=["--idle-timeout", str(idle_timeout)] + (["--sandbox", sandbox] if sandbox else []),
        )
        return 1

    # Handle non-zero exit code
    if proc.returncode != 0 and stderr_text.strip():
        print(
            f"Warning: Codex exited with code {proc.returncode}. stderr: {stderr_text.strip()}",
            file=sys.stderr,
        )

    # Verify response file exists and is valid JSON
    try:
        raw_response = response_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        write_fallback_response(
            response_path,
            request_obj.get("task_id"),
            "Codex did not produce response.json",
            ["missing response.json", f"exit code: {proc.returncode}"],
        )
        # Update info.json with exit code
        write_info_file(
            output_dir=output_dir,
            engine="codex",
            model=profile,
            started_at=started_at,
            pid=os.getpid(),
            exit_code=1,
            working_directory=cd,
            command_args=["--idle-timeout", str(idle_timeout)] + (["--sandbox", sandbox] if sandbox else []),
        )
        return 1

    try:
        json.loads(raw_response)
    except json.JSONDecodeError:
        write_fallback_response(
            response_path,
            request_obj.get("task_id"),
            "Codex returned invalid JSON",
            ["invalid json response", f"exit code: {proc.returncode}"],
        )
        # Update info.json with exit code
        write_info_file(
            output_dir=output_dir,
            engine="codex",
            model=profile,
            started_at=started_at,
            pid=os.getpid(),
            exit_code=1,
            working_directory=cd,
            command_args=["--idle-timeout", str(idle_timeout)] + (["--sandbox", sandbox] if sandbox else []),
        )
        return 1

    # Update info.json with final exit code
    write_info_file(
        output_dir=output_dir,
        engine="codex",
        model=profile,
        started_at=started_at,
        pid=os.getpid(),
        exit_code=proc.returncode,
        working_directory=cd,
        command_args=["--idle-timeout", str(idle_timeout)] + (["--sandbox", sandbox] if sandbox else []),
    )

    return proc.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Execute Subagent via Codex CLI."
    )
    parser.add_argument("--request", required=True, help="Path to request.json.")
    parser.add_argument("--response", required=True, help="Path to response.json.")
    parser.add_argument("--prompt-file", default=".agent/docs/subagent_prompt.md", help="Path to subagent prompt file.")
    parser.add_argument("--codex-cmd", default=None, help="Codex CLI command path.")
    parser.add_argument("--profile", default=None, help="Optional config profile.")
    parser.add_argument(
        "--sandbox",
        default=None,
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode for Codex exec.",
    )
    parser.add_argument("--cd", default=".", help="Working directory for Codex exec.")
    parser.add_argument("--skip-git-repo-check", action="store_true", help="Skip git repo check.")
    parser.add_argument("--idle-timeout", type=int, default=60, help="Terminate if stderr is silent for N seconds.")
    parser.add_argument(
        "--codex-args",
        nargs=argparse.REMAINDER,
        default=None,
        help="Extra args for codex exec (use after --codex-args).",
    )
    args = parser.parse_args()

    exit_code = execute_subagent(
        request_path=args.request,
        response_path=args.response,
        prompt_file=args.prompt_file,
        codex_cmd=args.codex_cmd,
        profile=args.profile,
        sandbox=args.sandbox,
        cd=args.cd,
        skip_git_repo_check=args.skip_git_repo_check,
        idle_timeout=args.idle_timeout,
        codex_args=args.codex_args,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
