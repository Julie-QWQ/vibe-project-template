#!/usr/bin/env python
"""
Validate request.json file for subagent tasks.

Checks that the request file exists, contains valid JSON,
and has all required fields.

Required fields are dynamically loaded from template_request.json.
"""
import argparse
import json
import sys
from pathlib import Path

# Import schema loader for dynamic template loading
try:
    from ..lib.schema_loader import load_request_template
except ImportError:
    # Fallback if schema_loader is not available
    def load_request_template():
        return {
            "version": "1.0",
            "task_id": "",
            "task": "",
            "context": {
                "files": [],
                "notes": ""
            },
            "constraints": [],
            "acceptance_criteria": []
        }


def validate_request_file(request_path):
    """
    Validate request.json file.

    Args:
        request_path: Path to request.json file

    Returns:
        dict: Validation result with keys:
            - valid (bool): Whether validation passed
            - errors (list): List of error messages (empty if valid)
            - request_obj (dict): Parsed request object (None if invalid)
    """
    request_path = Path(request_path)
    errors = []

    # Check file exists
    if not request_path.exists():
        return {
            "valid": False,
            "errors": [f"Request file not found: {request_path}"],
            "request_obj": None,
        }

    # Read and parse JSON
    try:
        request_raw = request_path.read_text(encoding="utf-8-sig")
        request_obj = json.loads(request_raw)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "errors": [f"Request JSON is invalid: {e}"],
            "request_obj": None,
        }

    # Load template and compare fields
    try:
        template = load_request_template()
        template_fields = set(template.keys())
        actual_fields = set(request_obj.keys())

        # Check for missing fields
        missing_fields = template_fields - actual_fields
        if missing_fields:
            errors.append(f"Request JSON missing fields: {', '.join(sorted(missing_fields))}")

        # Check for extra fields
        extra_fields = actual_fields - template_fields
        if extra_fields:
            errors.append(f"Request JSON has extra fields not in template: {', '.join(sorted(extra_fields))}")

    except Exception as e:
        # If template loading fails, report error
        errors.append(f"Could not load template for validation: {e}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "request_obj": request_obj,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate request.json file for subagent tasks."
    )
    parser.add_argument("request", help="Path to request.json file.")
    parser.add_argument(
        "--output-format",
        default="text",
        choices=["text", "json"],
        help="Output format.",
    )
    args = parser.parse_args()

    result = validate_request_file(args.request)

    if args.output_format == "json":
        output = {
            "valid": result["valid"],
            "errors": result["errors"],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if result["valid"]:
            print(f"[OK] Request file is valid: {args.request}")
        else:
            print(f"[ERROR] Request file validation failed: {args.request}", file=sys.stderr)

        for error in result["errors"]:
            print(f"  ERROR: {error}", file=sys.stderr)

    # Exit code: 0 if valid, 1 if invalid
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
