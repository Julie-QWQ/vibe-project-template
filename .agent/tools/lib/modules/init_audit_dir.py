#!/usr/bin/env python
"""
Initialize audit directory structure for a subagent.

Creates the .agent/audit/phase-xxx/task-xxx/subagent-xxx/ directory structure
and returns the paths to request.json and response.json files.

Optionally copies template files as placeholders for request.json.
"""
import argparse
import json
import shutil
from pathlib import Path


def _find_template_dir(start_dir=None):
    """
    Find the template directory by searching up from start_dir.

    Args:
        start_dir: Directory to start searching from

    Returns:
        Path: Found template directory or None
    """
    if start_dir is None:
        start_dir = Path(__file__).parent.parent.parent

    current = Path(start_dir).resolve()

    # Search up to 5 levels
    for _ in range(5):
        template_dir = current / ".agent" / "templates"
        if template_dir.exists():
            return template_dir
        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent

    # Fallback to relative path from current directory
    fallback = Path(".agent/templates")
    if fallback.exists():
        return fallback

    return None


def ensure_subagent_paths(audit_root, phase, task_name, subagent_name, request_path, response_path,
                          copy_template=False):
    """
    Ensure subagent directory structure exists.

    Returns paths to request.json and response.json.

    Args:
        audit_root: Root directory for audit files
        phase: Phase identifier (e.g., "phase-001")
        task_name: Task identifier (e.g., "task-001")
        subagent_name: Subagent identifier (e.g., "subagent-001")
        request_path: Direct path to request.json (optional)
        response_path: Direct path to response.json (optional)
        copy_template: If True, copy template_request.json to request.json as placeholder

    Returns:
        tuple: (request_path, response_path) as Path objects
    """
    if request_path and response_path:
        # Use direct paths if provided
        return Path(request_path), Path(response_path)

    if not (phase and task_name and subagent_name):
        raise SystemExit(
            "Either provide --request/--response or provide --phase/--task/--subagent."
        )

    # Create directory structure
    subagent_dir = Path(audit_root) / phase / task_name / subagent_name
    subagent_dir.mkdir(parents=True, exist_ok=True)

    request_file = subagent_dir / "request.json"
    response_file = subagent_dir / "response.json"

    # Optionally copy template as placeholder
    if copy_template and not request_file.exists():
        template_dir = _find_template_dir()
        if template_dir:
            template_file = template_dir / "template_request.json"
            if template_file.exists():
                shutil.copy(template_file, request_file)

    return request_file, response_file


def main():
    parser = argparse.ArgumentParser(
        description="Initialize audit directory structure for a subagent."
    )
    parser.add_argument("--phase", default=None, help="Phase name, e.g. phase-001")
    parser.add_argument("--task", dest="task_name", default=None, help="Task name, e.g. task-001")
    parser.add_argument(
        "--subagent", dest="subagent_name", default=None, help="Subagent name, e.g. subagent-001"
    )
    parser.add_argument("--audit-root", default=".agent/audit", help="Audit root directory.")
    parser.add_argument("--request", default=None, help="Path to request.json.")
    parser.add_argument("--response", default=None, help="Path to response.json.")
    parser.add_argument(
        "--copy-template",
        action="store_true",
        help="Copy template_request.json as a placeholder for request.json.",
    )
    parser.add_argument(
        "--output-format",
        default="text",
        choices=["text", "json"],
        help="Output format for paths.",
    )
    args = parser.parse_args()

    request_path, response_path = ensure_subagent_paths(
        args.audit_root,
        args.phase,
        args.task_name,
        args.subagent_name,
        args.request,
        args.response,
        copy_template=args.copy_template,
    )

    if args.output_format == "json":
        output = {
            "request_path": str(request_path),
            "response_path": str(response_path),
        }
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(f"Request path: {request_path}")
        print(f"Response path: {response_path}")
        if args.copy_template and not request_path.exists():
            print(f"Note: Template would be copied to {request_path}")


if __name__ == "__main__":
    main()
