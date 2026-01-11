"""
Subagent 执行模块

此包包含 Subagent 执行流程的核心模块，供 run_subagent.py 主脚本调用。

模块列表：
- init_audit_dir: 初始化审计目录结构
- validate_request: 验证 request.json 文件
- run_subagent_exec: 通过 Codex CLI 执行 Subagent
- run_subagent_claude: 通过 Claude API 执行 Subagent
- validate_response: 验证 response.json 文件
"""

from .init_audit_dir import ensure_subagent_paths
from .validate_request import validate_request_file
from .run_subagent_exec import execute_subagent
from .run_subagent_claude import execute_subagent_claude
from .validate_response import validate_response_file

__all__ = [
    "ensure_subagent_paths",
    "validate_request_file",
    "execute_subagent",
    "execute_subagent_claude",
    "validate_response_file",
]
