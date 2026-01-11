#!/usr/bin/env python
"""
Validate response.json file from subagent execution.

Checks that the response file exists and contains valid JSON.
Can also validate against an expected schema or acceptance criteria.

Required fields are dynamically loaded from template_response.json.
"""
import argparse
import json
import sys
from pathlib import Path

# Import schema loader for dynamic template loading
try:
    from ..lib.schema_loader import load_response_template
except ImportError:
    # Fallback if schema_loader is not available
    def load_response_template():
        return {
            "version": "1.0",
            "task_id": "",
            "status": "",
            "summary": "",
            "outputs": [],
            "issues": []
        }


def validate_response_file(response_path, check_required_fields=True):
    """
    Validate response.json file.

    Args:
        response_path: Path to response.json file
        check_required_fields: Whether to check for required fields

    Returns:
        dict: Validation result with keys:
            - valid (bool): Whether validation passed
            - errors (list): List of error messages (empty if valid)
            - response_obj (dict): Parsed response object (None if invalid)
    """
    response_path = Path(response_path)
    errors = []

    # Check file exists
    if not response_path.exists():
        return {
            "valid": False,
            "errors": [f"Response file not found: {response_path}"],
            "response_obj": None,
        }

    # Read and parse JSON
    try:
        response_raw = response_path.read_text(encoding="utf-8-sig")
        response_obj = json.loads(response_raw)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "errors": [f"Response JSON is invalid: {e}"],
            "response_obj": None,
        }

    # Load template and compare fields
    if check_required_fields:
        try:
            template = load_response_template()
            template_fields = set(template.keys())
            actual_fields = set(response_obj.keys())

            # Check for missing fields
            missing_fields = template_fields - actual_fields
            if missing_fields:
                errors.append(f"Response JSON missing fields: {', '.join(sorted(missing_fields))}")

            # Check for extra fields
            extra_fields = actual_fields - template_fields
            if extra_fields:
                errors.append(f"Response JSON has extra fields not in template: {', '.join(sorted(extra_fields))}")

            # Validate status field value
            if "status" in response_obj:
                valid_statuses = ("success", "partial", "failed")
                if response_obj["status"] not in valid_statuses:
                    errors.append(f"Invalid status: {response_obj['status']}. Must be one of {valid_statuses}")

        except Exception as e:
            # If template loading fails, report error
            errors.append(f"Could not load template for validation: {e}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "response_obj": response_obj,
    }


def print_validation_result(result, output_format="text"):
    """Print validation result in specified format."""
    if output_format == "json":
        output = {
            "valid": result["valid"],
            "errors": result["errors"],
        }
        if result["response_obj"]:
            output["status"] = result["response_obj"].get("status", "N/A")
            output["summary"] = result["response_obj"].get("summary", "")
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if result["valid"]:
            status = result["response_obj"].get("status", "N/A") if result["response_obj"] else "N/A"
            print(f"[OK] Response file is valid (status: {status})")
            if result["response_obj"] and result["response_obj"].get("summary"):
                print(f"  Summary: {result['response_obj']['summary']}")
        else:
            print(f"[ERROR] Response file validation failed", file=sys.stderr)
            for error in result["errors"]:
                print(f"  ERROR: {error}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Validate response.json file from subagent execution."
    )
    parser.add_argument("response", help="Path to response.json file.")
    parser.add_argument(
        "--output-format",
        default="text",
        choices=["text", "json"],
        help="Output format.",
    )
    parser.add_argument(
        "--no-field-check",
        action="store_true",
        help="Skip required field validation (only check JSON syntax).",
    )
    parser.add_argument(
        "--check-status",
        choices=["success", "partial", "failed"],
        help="Check if response status matches the specified value.",
    )
    args = parser.parse_args()

    result = validate_response_file(
        args.response,
        check_required_fields=not args.no_field_check,
    )

    # Additional status check
    if args.check_status and result["response_obj"]:
        actual_status = result["response_obj"].get("status")
        if actual_status != args.check_status:
            result["valid"] = False
            result["errors"].append(f"Status check failed: expected '{args.check_status}', got '{actual_status}'")

    print_validation_result(result, args.output_format)

    # Exit code: 0 if valid, 1 if invalid
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
