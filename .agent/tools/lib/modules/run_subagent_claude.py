#!/usr/bin/env python
"""
Execute Subagent via Anthropic Claude API with Tool Use.

This script provides an alternative to Codex CLI by using Claude's Messages API
with Tool Use capability, allowing Claude to function as an Agent that can use
tools like Read, Write, Bash, etc.

Required: pip install anthropic
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import utility functions
try:
    from ..lib import (
        load_prompt,
        build_prompt,
        write_info_file,
        write_fallback_response,
    )
except ImportError:
    # Fallback implementations when run as standalone script
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from lib import (
        load_prompt,
        build_prompt,
        write_info_file,
        write_fallback_response,
    )


# Tool definitions for Claude
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the complete contents of a file from the filesystem",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating it if it doesn't exist or overwriting if it does",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "execute_command",
        "description": "Execute a shell command and return the output",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for command execution (optional)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and directories in a given path",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to list (default: current directory)"
                }
            },
            "required": []
        }
    },
    {
        "name": "search_files",
        "description": "Search for text patterns in files using ripgrep",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (supports regex)"
                },
                "path": {
                    "type": "string",
                    "description": "Path to search in (optional)"
                }
            },
            "required": ["pattern"]
        }
    }
]


def execute_tool(tool_name, tool_input):
    """Execute a tool and return the result"""
    try:
        if tool_name == "read_file":
            file_path = Path(tool_input["file_path"])
            if not file_path.exists():
                return {"error": f"File not found: {file_path}"}
            return {"content": file_path.read_text(encoding="utf-8")}

        elif tool_name == "write_file":
            file_path = Path(tool_input["file_path"])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(tool_input["content"], encoding="utf-8")
            return {"success": True, "file_path": str(file_path)}

        elif tool_name == "execute_command":
            command = tool_input["command"]
            cwd = tool_input.get("cwd", ".")
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }

        elif tool_name == "list_directory":
            path = Path(tool_input.get("path", "."))
            if not path.exists():
                return {"error": f"Path not found: {path}"}
            items = []
            for item in path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file"
                })
            return {"items": items}

        elif tool_name == "search_files":
            pattern = tool_input["pattern"]
            search_path = tool_input.get("path", ".")
            result = subprocess.run(
                ["rg", "--json", pattern, search_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
            return {
                "output": result.stdout,
                "exit_code": result.returncode
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except subprocess.TimeoutExpired:
        return {"error": "Command timed out"}
    except Exception as e:
        return {"error": str(e)}


def run_tool_loop(client, model, system_prompt, user_message, max_iterations=25, stderr_path=None):
    """
    Run the agent tool use loop.

    Args:
        client: Anthropic client
        model: Model name
        system_prompt: System prompt
        user_message: Initial user message
        max_iterations: Maximum number of iterations
        stderr_path: Path to write conversation log (stderr.txt)

    Returns:
        dict: Result with keys:
            - status: 'success', 'partial', or 'failed'
            - summary: Final text summary
            - tool_results: List of tool executions
            - error: Error message (if failed)
            - performance_metrics: Token usage statistics
    """
    messages = [{"role": "user", "content": user_message}]
    tool_results = []

    # Initialize token counters
    total_input_tokens = 0
    total_output_tokens = 0
    api_calls_count = 0

    # Initialize conversation log for stderr
    conversation_log = []

    for iteration in range(max_iterations):
        try:
            response = client.messages.create(
                model=model,
                system=system_prompt,
                messages=messages,
                max_tokens=4096,
                tools=TOOLS
            )
            api_calls_count += 1

            # Collect token usage
            if hasattr(response, 'usage') and response.usage:
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

            # Log assistant response to stderr
            if stderr_path:
                conversation_log.append(f"\n{'='*60}\n")
                conversation_log.append(f"Iteration {iteration + 1}\n")
                conversation_log.append(f"Model: {model}\n")
                conversation_log.append(f"Input Tokens: {response.usage.input_tokens if hasattr(response, 'usage') and response.usage else 'N/A'}\n")
                conversation_log.append(f"Output Tokens: {response.usage.output_tokens if hasattr(response, 'usage') and response.usage else 'N/A'}\n")
                conversation_log.append(f"\n--- Assistant Response ---\n")

                for block in response.content:
                    if block.type == "text":
                        conversation_log.append(f"{block.text}\n")
                    elif block.type == "tool_use":
                        conversation_log.append(f"\n[Tool Call: {block.name}]\n")
                        conversation_log.append(f"Input: {json.dumps(block.input, ensure_ascii=False, indent=2)}\n")

        except Exception as e:
            # Write conversation log to stderr even on error
            if stderr_path:
                from pathlib import Path
                conversation_log.append(f"\n!!! ERROR: {e} !!!\n")
                stderr_content = "".join(conversation_log)
                Path(stderr_path).write_text(stderr_content, encoding="utf-8")

            return {
                "status": "failed",
                "error": f"API call failed: {e}",
                "tool_results": tool_results,
                "performance_metrics": {
                    "total_tokens": total_input_tokens + total_output_tokens if total_input_tokens > 0 else None,
                    "prompt_tokens": total_input_tokens if total_input_tokens > 0 else None,
                    "completion_tokens": total_output_tokens if total_output_tokens > 0 else None,
                    "api_calls_count": api_calls_count,
                }
            }

        # Check if response is complete
        if response.stop_reason == "end_turn":
            # Extract final text response
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text

            # Write conversation log to stderr
            if stderr_path:
                from pathlib import Path
                stderr_content = "".join(conversation_log)
                Path(stderr_path).write_text(stderr_content, encoding="utf-8")

            return {
                "status": "success",
                "summary": final_text,
                "tool_results": tool_results,
                "performance_metrics": {
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "prompt_tokens": total_input_tokens,
                    "completion_tokens": total_output_tokens,
                    "api_calls_count": api_calls_count,
                }
            }

        # Process tool calls
        assistant_message = {"role": "assistant", "content": []}
        user_message_blocks = []

        for block in response.content:
            if block.type == "text":
                assistant_message["content"].append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_message["content"].append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })

                # Execute the tool
                tool_result = execute_tool(block.name, block.input)
                tool_results.append({
                    "tool": block.name,
                    "input": block.input,
                    "result": tool_result
                })

                # Log tool result to stderr
                if stderr_path:
                    conversation_log.append(f"\n[Tool Result: {block.name}]\n")
                    if "error" in tool_result:
                        conversation_log.append(f"Error: {tool_result['error']}\n")
                    else:
                        conversation_log.append(f"{json.dumps(tool_result, ensure_ascii=False, indent=2)}\n")

                # Format result for Claude
                if "error" in tool_result:
                    result_text = f"Error: {tool_result['error']}"
                else:
                    result_text = json.dumps(tool_result, ensure_ascii=False)

                user_message_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text
                })

        messages.append(assistant_message)
        messages.append({"role": "user", "content": user_message_blocks})

    # Write conversation log to stderr when max iterations reached
    if stderr_path:
        from pathlib import Path
        conversation_log.append(f"\n!!! WARNING: Maximum iterations ({max_iterations}) reached !!!\n")
        stderr_content = "".join(conversation_log)
        Path(stderr_path).write_text(stderr_content, encoding="utf-8")

    return {
        "status": "partial",
        "summary": "Maximum iterations reached",
        "tool_results": tool_results,
        "performance_metrics": {
            "total_tokens": total_input_tokens + total_output_tokens if total_input_tokens > 0 else None,
            "prompt_tokens": total_input_tokens if total_input_tokens > 0 else None,
            "completion_tokens": total_output_tokens if total_output_tokens > 0 else None,
            "api_calls_count": api_calls_count,
        }
    }


def execute_subagent_claude(
    request_path,
    response_path,
    prompt_file=".agent/docs/subagent_prompt.md",
    api_key=None,
    model="claude-sonnet-4-5-20250929",
    cwd="."
):
    """Execute Subagent using Claude API with Tool Use"""
    import os
    request_path = Path(request_path)
    response_path = Path(response_path)

    # Check API key
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set. Provide --api-key or set environment variable.")

    # Validate request file exists
    if not request_path.exists():
        raise SystemExit(f"Request file not found: {request_path}")

    # Load request JSON
    request_raw = request_path.read_text(encoding="utf-8-sig")
    try:
        request_obj = json.loads(request_raw)
    except json.JSONDecodeError:
        raise SystemExit(f"Request JSON is invalid: {request_path}")

    # Setup paths and record start time
    output_dir = response_path.parent
    stderr_path = output_dir / "stderr.txt"
    started_at = datetime.now(timezone.utc).isoformat()

    # Initialize stderr file
    stderr_path.write_text("", encoding="utf-8")

    # Write initial info file
    write_info_file(
        output_dir=output_dir,
        engine="claude",
        model=model,
        started_at=started_at,
        pid=os.getpid(),
        working_directory=cwd,
    )

    # Build prompt
    base_prompt = load_prompt(prompt_file)
    user_message = build_prompt(base_prompt, request_obj)

    # Import anthropic
    try:
        import anthropic
    except ImportError:
        raise SystemExit("anthropic package not installed. Run: pip install anthropic")

    # Run agent loop
    client = anthropic.Anthropic(api_key=api_key)
    result = run_tool_loop(client, model, base_prompt, user_message, stderr_path=str(stderr_path))

    # Build response
    response_obj = {
        "version": "1.0",
        "task_id": request_obj.get("task_id", ""),
        "status": result.get("status", "failed"),
        "summary": result.get("summary", ""),
        "outputs": result.get("tool_results", []),
        "issues": []
    }

    if "error" in result:
        response_obj["issues"] = [result["error"]]

    # Write response
    response_path.write_text(json.dumps(response_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    # Update info.json with final exit code and performance metrics
    exit_code = 0 if result.get("status") == "success" else 1
    performance_metrics = result.get("performance_metrics", {
        "total_tokens": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "api_calls_count": 0,
    })

    write_info_file(
        output_dir=output_dir,
        engine="claude",
        model=model,
        started_at=started_at,
        pid=os.getpid(),
        exit_code=exit_code,
        working_directory=cwd,
        performance_metrics=performance_metrics,
    )

    return exit_code


def main():
    parser = argparse.ArgumentParser(
        description="Execute Subagent via Claude API with Tool Use."
    )
    parser.add_argument("--request", required=True, help="Path to request.json.")
    parser.add_argument("--response", required=True, help="Path to response.json.")
    parser.add_argument("--prompt-file", default=".agent/docs/subagent_prompt.md", help="Path to subagent prompt file.")
    parser.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY env var).")
    parser.add_argument("--model", default="claude-sonnet-4-5-20250929", help="Claude model to use.")
    parser.add_argument("--cwd", default=".", help="Working directory for file operations.")

    args = parser.parse_args()

    exit_code = execute_subagent_claude(
        request_path=args.request,
        response_path=args.response,
        prompt_file=args.prompt_file,
        api_key=args.api_key,
        model=args.model,
        cwd=args.cwd,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
