#!/usr/bin/env python
"""
Schema loader for request.json and response.json templates.

This module dynamically loads schema definitions from template files,
ensuring a single source of truth for JSON structure validation.
"""
import json
from pathlib import Path


# Default template paths (relative to project root)
DEFAULT_TEMPLATE_DIR = Path(".agent/templates")
REQUEST_TEMPLATE = DEFAULT_TEMPLATE_DIR / "template_request.json"
RESPONSE_TEMPLATE = DEFAULT_TEMPLATE_DIR / "template_response.json"


def _find_template_dir(start_dir=None):
    """
    Find the template directory by searching up from start_dir.

    Args:
        start_dir: Directory to start searching from (default: current file's directory)

    Returns:
        Path: Found template directory
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

    raise FileNotFoundError(
        "Cannot find .agent/templates/ directory. "
        "Please run this script from within the project root."
    )


def load_request_template():
    """
    Load request.json template.

    Returns:
        dict: Parsed template object

    Raises:
        FileNotFoundError: If template file not found
        json.JSONDecodeError: If template is invalid JSON
    """
    template_dir = _find_template_dir()
    template_path = template_dir / "template_request.json"

    if not template_path.exists():
        raise FileNotFoundError(f"Request template not found: {template_path}")

    content = template_path.read_text(encoding="utf-8-sig")
    return json.loads(content)


def load_response_template():
    """
    Load response.json template.

    Returns:
        dict: Parsed template object

    Raises:
        FileNotFoundError: If template file not found
        json.JSONDecodeError: If template is invalid JSON
    """
    template_dir = _find_template_dir()
    template_path = template_dir / "template_response.json"

    if not template_path.exists():
        raise FileNotFoundError(f"Response template not found: {template_path}")

    content = template_path.read_text(encoding="utf-8-sig")
    return json.loads(content)


def get_request_required_fields():
    """
    Extract required fields from request template.

    Returns:
        tuple: Required field names

    Note:
        This function determines required fields by checking which
        fields have non-empty placeholder values in the template.
    """
    template = load_request_template()

    # Fields that should always be present (even if empty in template)
    always_required = ("task", "context", "constraints")

    # Validate that all required fields exist in template
    missing = [f for f in always_required if f not in template]
    if missing:
        raise ValueError(
            f"Request template missing required fields: {', '.join(missing)}"
        )

    return always_required


def get_response_required_fields():
    """
    Extract required fields from response template.

    Returns:
        tuple: Required field names

    Note:
        This function determines required fields by checking which
        fields have non-empty placeholder values in the template.
    """
    template = load_response_template()

    # Fields that should always be present (even if empty in template)
    always_required = ("version", "task_id", "status", "summary", "outputs", "issues")

    # Validate that all required fields exist in template
    missing = [f for f in always_required if f not in template]
    if missing:
        raise ValueError(
            f"Response template missing required fields: {', '.join(missing)}"
        )

    return always_required


def get_response_default_values():
    """
    Get default values for response fields from template.

    Returns:
        dict: Default values for response fields

    Useful for:
        - Creating fallback responses
        - Initializing response objects
    """
    template = load_response_template()

    defaults = {}
    for key, value in template.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            defaults[key] = value
        elif isinstance(value, list):
            defaults[key] = []
        elif isinstance(value, dict):
            defaults[key] = {}

    return defaults


def validate_template_consistency():
    """
    Validate that templates contain expected structure.

    Returns:
        dict: Validation result with keys:
            - valid (bool)
            - errors (list)
            - warnings (list)
    """
    errors = []
    warnings = []

    try:
        request_template = load_request_template()
        response_template = load_response_template()

        # Check request template
        expected_request_fields = ["version", "task_id", "task", "context", "constraints", "acceptance_criteria"]
        for field in expected_request_fields:
            if field not in request_template:
                errors.append(f"Request template missing field: {field}")

        # Check response template
        expected_response_fields = ["version", "task_id", "status", "summary", "outputs", "issues"]
        for field in expected_response_fields:
            if field not in response_template:
                errors.append(f"Response template missing field: {field}")

        # Check version consistency
        if request_template.get("version") != response_template.get("version"):
            warnings.append(
                f"Version mismatch: request={request_template.get('version')}, "
                f"response={response_template.get('version')}"
            )

    except Exception as e:
        errors.append(f"Template validation error: {e}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    # Test schema loading
    import argparse

    parser = argparse.ArgumentParser(description="Test schema loader")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate template consistency",
    )
    parser.add_argument(
        "--show-request",
        action="store_true",
        help="Show request template",
    )
    parser.add_argument(
        "--show-response",
        action="store_true",
        help="Show response template",
    )
    args = parser.parse_args()

    if args.validate:
        result = validate_template_consistency()
        print(f"Valid: {result['valid']}")
        if result['errors']:
            print("Errors:")
            for error in result['errors']:
                print(f"  - {error}")
        if result['warnings']:
            print("Warnings:")
            for warning in result['warnings']:
                print(f"  - {warning}")

    if args.show_request:
        template = load_request_template()
        print(json.dumps(template, indent=2, ensure_ascii=False))
        print("\nRequired fields:", get_request_required_fields())

    if args.show_response:
        template = load_response_template()
        print(json.dumps(template, indent=2, ensure_ascii=False))
        print("\nRequired fields:", get_response_required_fields())
        print("\nDefault values:", get_response_default_values())
