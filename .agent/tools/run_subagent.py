#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REQUIRED_FIELDS = ("task", "context", "constraints", "expected_output")


def default_codex_cmd():
    return "codex.cmd" if sys.platform.startswith("win") else "codex"


def build_prompt(request_obj):
    request_json = json.dumps(request_obj, ensure_ascii=True, indent=2)
    return (
        "You are Subagent. Execute the task described in the request JSON. "
        "Follow constraints strictly. Return ONLY a JSON object for response.json. "
        "Do not include extra text.\n\n"
        "Request JSON:\n"
        "```json\n"
        f"{request_json}\n"
        "```\n\n"
        "Response JSON must include these keys:\n"
        "version, task_id, status, summary, outputs, validation, issues, "
        "follow_up, assumptions_used, context_used.\n"
        "Status must be one of: success, partial, failed."
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


def ensure_round_paths(audit_root, phase, step, round_name, request_path, response_path):
    if request_path and response_path:
        return Path(request_path), Path(response_path)
    if not (phase and step and round_name):
        raise SystemExit("Either provide --request/--response or provide --phase/--step/--round.")
    round_dir = Path(audit_root) / phase / step / round_name
    round_dir.mkdir(parents=True, exist_ok=True)
    return round_dir / "request.json", round_dir / "response.json"


def main():
    parser = argparse.ArgumentParser(description="Create audit round and run Subagent via Codex CLI.")
    parser.add_argument("--phase", default=None, help="Phase name, e.g. phase-001")
    parser.add_argument("--step", default=None, help="Step name, e.g. step-001")
    parser.add_argument("--round", dest="round_name", default=None, help="Round name, e.g. round-001")
    parser.add_argument("--audit-root", default=".agent/audit", help="Audit root directory.")
    parser.add_argument("--request", default=None, help="Path to request.json.")
    parser.add_argument("--response", default=None, help="Path to response.json.")
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
    parser.add_argument(
        "--codex-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Extra args for codex exec (use after --codex-args).",
    )
    args = parser.parse_args()

    request_path, response_path = ensure_round_paths(
        args.audit_root,
        args.phase,
        args.step,
        args.round_name,
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

    prompt = build_prompt(request_obj)

    schema = response_schema()
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        schema_path = Path(tmp.name)
        tmp.write(json.dumps(schema, ensure_ascii=True, indent=2))

    cmd = [args.codex_cmd, "exec", "-"]
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

    proc = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
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
