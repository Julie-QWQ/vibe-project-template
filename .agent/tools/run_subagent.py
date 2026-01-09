#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from queue import Empty, Queue
from pathlib import Path


REQUIRED_FIELDS = ("task", "context", "constraints", "expected_output")


def default_codex_cmd():
    return "codex.cmd" if sys.platform.startswith("win") else "codex"


def load_prompt(path):
    prompt_path = Path(path)
    if not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8-sig").strip()


def build_prompt(base_prompt, request_obj):
    request_json = json.dumps(request_obj, ensure_ascii=True, indent=2)
    return (
        f"{base_prompt}\n\n"
        "Request JSON:\n"
        "```json\n"
        f"{request_json}\n"
        "```"
    )


def response_schema():
    array_item = {
        "anyOf": [
            {"type": "string"},
            {"type": "object", "additionalProperties": False},
        ]
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "version",
            "task_id",
            "status",
            "summary",
            "outputs",
            "validation",
            "issues",
            "follow_up",
            "assumptions_used",
            "context_used",
        ],
        "properties": {
            "version": {"type": "string"},
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": ["success", "partial", "failed"]},
            "summary": {"type": "string"},
            "outputs": {"type": "array", "items": array_item},
            "validation": {"type": "array", "items": array_item},
            "issues": {"type": "array", "items": array_item},
            "follow_up": {"type": "array", "items": array_item},
            "assumptions_used": {"type": "array", "items": array_item},
            "context_used": {"type": "array", "items": array_item},
        },
        "additionalProperties": False,
    }


def write_fallback_response(response_path, task_id, summary, issues):
    payload = {
        "version": "1.0",
        "task_id": task_id or "",
        "status": "failed",
        "summary": summary,
        "outputs": [],
        "validation": [],
        "issues": issues,
        "follow_up": [],
        "assumptions_used": [],
        "context_used": [],
    }
    response_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def ensure_subagent_paths(audit_root, phase, task_name, subagent_name, request_path, response_path):
    if request_path and response_path:
        return Path(request_path), Path(response_path)
    if not (phase and task_name and subagent_name):
        raise SystemExit(
            "Either provide --request/--response or provide --phase/--task/--subagent."
        )
    subagent_dir = Path(audit_root) / phase / task_name / subagent_name
    subagent_dir.mkdir(parents=True, exist_ok=True)
    return subagent_dir / "request.json", subagent_dir / "response.json"


def read_stream(stream, out_queue):
    try:
        while True:
            chunk = stream.read(1024)
            if not chunk:
                break
            out_queue.put(chunk)
    finally:
        out_queue.put(None)


def main():
    parser = argparse.ArgumentParser(description="Create audit subagent directory and run Subagent via Codex CLI.")
    parser.add_argument("--phase", default=None, help="Phase name, e.g. phase-001")
    parser.add_argument("--task", dest="task_name", default=None, help="Task name, e.g. task-001")
    parser.add_argument(
        "--subagent", dest="subagent_name", default=None, help="Subagent name, e.g. subagent-001"
    )
    parser.add_argument("--audit-root", default=".agent/audit", help="Audit root directory.")
    parser.add_argument("--request", default=None, help="Path to request.json.")
    parser.add_argument("--response", default=None, help="Path to response.json.")
    parser.add_argument("--prompt-file", default=".agent/docs/subagent_prompt.md", help="Path to subagent prompt file.")
    parser.add_argument("--codex-cmd", default=default_codex_cmd(), help="Codex CLI command path.")
    parser.add_argument("--model", default=None, help="Optional model override.")
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
        default=[],
        help="Extra args for codex exec (use after --codex-args).",
    )
    args = parser.parse_args()

    request_path, response_path = ensure_subagent_paths(
        args.audit_root,
        args.phase,
        args.task_name,
        args.subagent_name,
        args.request,
        args.response,
    )

    if not request_path.exists():
        raise SystemExit(f"Request file not found: {request_path}")

    request_raw = request_path.read_text(encoding="utf-8-sig")
    try:
        request_obj = json.loads(request_raw)
    except json.JSONDecodeError:
        raise SystemExit(f"Request JSON is invalid: {request_path}")

    missing = [field for field in REQUIRED_FIELDS if field not in request_obj]
    if missing:
        raise SystemExit(f"Request JSON missing required fields: {', '.join(missing)}")

    output_dir = response_path.parent
    stderr_path = output_dir / "stderr.txt"

    stderr_path.write_text("", encoding="utf-8")

    base_prompt = load_prompt(args.prompt_file)
    prompt = build_prompt(base_prompt, request_obj)

    schema = response_schema()
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        schema_path = Path(tmp.name)
        tmp.write(json.dumps(schema, ensure_ascii=True, indent=2))

    cmd = [args.codex_cmd, "exec"]
    if args.model:
        cmd += ["--model", args.model]
    if args.profile:
        cmd += ["--profile", args.profile]
    if args.sandbox:
        cmd += ["--sandbox", args.sandbox]
    if args.cd:
        cmd += ["--cd", args.cd]
    if args.skip_git_repo_check:
        cmd += ["--skip-git-repo-check"]
    cmd += ["--output-schema", str(schema_path)]
    cmd += ["--output-last-message", str(response_path)]
    cmd += args.codex_args
    cmd.append("-")

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except Exception:
        proc.kill()
        raise

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

    while True:
        got_output = False
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
                got_output = True
                last_output = time.monotonic()
        except Empty:
            pass

        if got_output:
            pass

        if stdout_done and stderr_done:
            break

        if time.monotonic() - last_output > args.idle_timeout:
            timed_out = True
            proc.kill()
            break

    proc.wait()

    stderr_text = "".join(stderr_chunks)
    if timed_out:
        stderr_text = (stderr_text + "" if stderr_text else "") + f"Terminated after {args.idle_timeout}s of no output."

    stderr_path.write_text(stderr_text, encoding="utf-8")

    if timed_out:
        write_fallback_response(
            response_path,
            request_obj.get("task_id"),
            f"Subagent timed out after {args.idle_timeout}s of no stderr output",
            ["timeout", f"no stderr output for {args.idle_timeout}s"],
        )
        raise SystemExit(1)

    if proc.returncode != 0 and stderr_text.strip():
        print(
            f"Warning: Codex exited with code {proc.returncode}. stderr: {stderr_text.strip()}",
            file=sys.stderr,
        )
    if proc.returncode != 0 and proc.stderr.strip():
        print(
            f"Warning: Codex exited with code {proc.returncode}. stderr: {proc.stderr.strip()}",
            file=sys.stderr,
        )

    try:
        raw_response = response_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        write_fallback_response(
            response_path,
            request_obj.get("task_id"),
            "Codex did not produce response.json",
            ["missing response.json", f"exit code: {proc.returncode}"],
        )
        raise SystemExit(1)
    finally:
        schema_path.unlink(missing_ok=True)

    try:
        json.loads(raw_response)
    except json.JSONDecodeError:
        write_fallback_response(
            response_path,
            request_obj.get("task_id"),
            "Codex returned invalid JSON",
            ["invalid json response", f"exit code: {proc.returncode}"],
        )
        raise SystemExit(1)


    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
