#!/usr/bin/env python
"""
Shared utilities for subagent tools.

This module provides common functions used across subagent tools,
including prompt loading, response generation, and metadata writing.

Schema-related functionality has been moved to schema_loader.py
to maintain a single source of truth from template files.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def default_codex_cmd():
    """Get default Codex CLI command based on platform."""
    return "codex.cmd" if sys.platform.startswith("win") else "codex"


def load_prompt(path):
    """Load subagent prompt from file."""
    prompt_path = Path(path)
    if not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8-sig").strip()


def build_prompt(base_prompt, request_obj):
    """Build full prompt by combining base prompt with request JSON."""
    request_json = json.dumps(request_obj, ensure_ascii=True, indent=2)
    return (
        f"{base_prompt}\n\n"
        "Request JSON:\n"
        "```json\n"
        f"{request_json}\n"
        "```"
    )


def write_fallback_response(response_path, task_id, summary, issues):
    """
    Write a fallback response when Subagent execution fails.

    Response structure is loaded from template_response.json
    to maintain consistency with the template schema.
    """
    from .schema_loader import load_response_template, get_response_default_values

    # Load template structure for consistency
    try:
        template = load_response_template()
        defaults = get_response_default_values()

        # Build response using template structure
        payload = {}
        for key in template.keys():
            if key in defaults:
                payload[key] = defaults[key]

        # Override with execution-specific values
        payload["version"] = template.get("version", "1.0")
        payload["task_id"] = task_id or ""
        payload["status"] = "failed"
        payload["summary"] = summary
        payload["issues"] = issues if issues else []

    except Exception:
        # Fallback to hardcoded structure if template loading fails
        payload = {
            "version": "1.0",
            "task_id": task_id or "",
            "status": "failed",
            "summary": summary,
            "outputs": [],
            "issues": issues if issues else [],
        }

    response_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def write_info_file(
    output_dir,
    engine="codex",
    model=None,
    started_at=None,
    pid=None,
    exit_code=None,
    working_directory=None,
    command_args=None,
    performance_metrics=None,
):
    """
    Write info.json with runtime execution data.

    Args:
        output_dir: Directory to write info.json
        engine: Execution engine ('codex' or 'claude')
        model: Model name (for Claude engine) or profile (for Codex engine)
        started_at: ISO timestamp of execution start
        pid: Process ID
        exit_code: Exit code (None if still running)
        working_directory: Working directory path
        command_args: Command line arguments used
        performance_metrics: Dict with token usage (only for Claude engine):
            - total_tokens: Total tokens used
            - prompt_tokens: Input tokens
            - completion_tokens: Output tokens
            - api_calls_count: Number of API calls
    """
    import socket
    import platform as platform_module

    # Load template structure
    try:
        from .schema_loader import load_response_template

        # Try to load info template if it exists
        template_path = Path(__file__).parent.parent.parent / "templates" / "template_info.json"
        if template_path.exists():
            template = json.loads(template_path.read_text(encoding="utf-8-sig"))
        else:
            # Fallback structure
            template = {
                "version": "1.0",
                "execution_info": {},
                "process_info": {},
                "command_info": {},
                "performance_metrics": {},
                "metadata": {},
            }
    except Exception:
        template = {
            "version": "1.0",
            "execution_info": {},
            "process_info": {},
            "command_info": {},
            "performance_metrics": {},
            "metadata": {},
        }

    # Default performance metrics
    default_metrics = {
        "total_tokens": None,  # Only available for Claude
        "prompt_tokens": None,  # Only available for Claude
        "completion_tokens": None,  # Only available for Claude
        "api_calls_count": 0,
    }

    # Merge with provided metrics (if any)
    if performance_metrics:
        default_metrics.update(performance_metrics)

    # Build info object
    info = {
        "version": template.get("version", "1.0"),
        "execution_info": {
            "engine": engine,
            "model": model or "",
            "started_at": started_at or datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat() if exit_code is not None else None,
            "duration_seconds": None,  # Will be calculated if both timestamps exist
        },
        "process_info": {
            "pid": pid,
            "exit_code": exit_code,
        },
        "command_info": {
            "working_directory": str(working_directory) if working_directory else "",
            "command_args": command_args or [],
        },
        "performance_metrics": default_metrics,
        "metadata": {
            "hostname": socket.gethostname(),
            "platform": platform_module.platform(),
            "python_version": sys.version,
        },
    }

    # Calculate duration if both timestamps exist
    if info["execution_info"]["started_at"] and info["execution_info"]["completed_at"]:
        try:
            start = datetime.fromisoformat(info["execution_info"]["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(info["execution_info"]["completed_at"].replace("Z", "+00:00"))
            info["execution_info"]["duration_seconds"] = (end - start).total_seconds()
        except Exception:
            pass

    # Write to info.json (replaces info.md)
    info_path = Path(output_dir) / "info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


# Backward compatibility: export REQUIRED_FIELDS for existing imports
# Deprecated: Use schema_loader.get_request_required_fields() instead
try:
    from .schema_loader import get_request_required_fields
    REQUIRED_FIELDS = get_request_required_fields()
except Exception:
    # Fallback if schema_loader is not available
    REQUIRED_FIELDS = ("task", "context", "constraints")
