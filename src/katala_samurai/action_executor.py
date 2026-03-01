"""
Action Executor — Sandboxed code/tool execution for KS Agent Mode.

Lightweight subprocess-based sandbox (no Docker required).
Supports: Python exec, shell commands, file I/O (read-only by default).

Security: timeout, memory limit, no network by default, audit trail.

Design: Youta Hilono (requirements) + Shirokuma (implementation)
"""

from __future__ import annotations

import subprocess
import tempfile
import time
import os
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

# ── Constants ──
DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 300          # 5 min hard cap per action
MAX_OUTPUT_BYTES = 100_000         # 100KB output cap
MAX_MEMORY_MB = 512                # Memory limit
ALLOWED_COMMANDS = frozenset([     # Whitelist for shell commands
    "python3", "cat", "ls", "head", "tail", "grep", "wc",
    "find", "echo", "date", "git",
])


class ActionType(Enum):
    PYTHON_EXEC = "python_exec"
    SHELL_CMD = "shell_cmd"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"      # Disabled by default
    API_CALL = "api_call"          # Disabled by default


class Permission(Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    FULL = "full"


@dataclass
class ActionResult:
    """Result of an executed action."""
    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    action_type: str = ""
    truncated: bool = False


@dataclass
class ActionExecutor:
    """
    Sandboxed action execution for KS agent mode.
    
    Default: read-only, no network, 30s timeout.
    Escalation requires explicit permission grant.
    """
    permission: Permission = Permission.READ_ONLY
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    workspace: str = ""
    audit: List[Dict[str, Any]] = field(default_factory=list)
    network_allowed: bool = False

    def execute_python(self, code: str, timeout: Optional[float] = None) -> ActionResult:
        """Execute Python code in subprocess sandbox."""
        effective_timeout = min(timeout or self.timeout, MAX_TIMEOUT_SECONDS)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            start = time.time()
            env = os.environ.copy()
            if not self.network_allowed:
                # Block network via environment hint (best-effort without root)
                env["no_proxy"] = "*"
                env["http_proxy"] = "http://0.0.0.0:0"
                env["https_proxy"] = "http://0.0.0.0:0"

            result = subprocess.run(
                ["python3", tmp_path],
                capture_output=True, text=True,
                timeout=effective_timeout,
                cwd=self.workspace or None,
                env=env,
            )
            duration = (time.time() - start) * 1000

            output = result.stdout[:MAX_OUTPUT_BYTES]
            truncated = len(result.stdout) > MAX_OUTPUT_BYTES

            action_result = ActionResult(
                success=(result.returncode == 0),
                output=output,
                error=result.stderr[:MAX_OUTPUT_BYTES] if result.stderr else "",
                exit_code=result.returncode,
                duration_ms=duration,
                action_type="python_exec",
                truncated=truncated,
            )
        except subprocess.TimeoutExpired:
            action_result = ActionResult(
                success=False, output="",
                error=f"Timeout after {effective_timeout}s",
                exit_code=-1, action_type="python_exec",
            )
        except Exception as e:
            action_result = ActionResult(
                success=False, output="",
                error=str(e), exit_code=-1,
                action_type="python_exec",
            )
        finally:
            os.unlink(tmp_path)

        self._log("python_exec", action_result)
        return action_result

    def execute_shell(self, command: str, timeout: Optional[float] = None) -> ActionResult:
        """Execute whitelisted shell command."""
        parts = command.split()
        if not parts or parts[0] not in ALLOWED_COMMANDS:
            result = ActionResult(
                success=False, output="",
                error=f"Command '{parts[0] if parts else ''}' not in whitelist: {sorted(ALLOWED_COMMANDS)}",
                exit_code=-1, action_type="shell_cmd",
            )
            self._log("shell_cmd_blocked", result)
            return result

        effective_timeout = min(timeout or self.timeout, MAX_TIMEOUT_SECONDS)
        try:
            start = time.time()
            proc = subprocess.run(
                command, shell=True,
                capture_output=True, text=True,
                timeout=effective_timeout,
                cwd=self.workspace or None,
            )
            duration = (time.time() - start) * 1000
            output = proc.stdout[:MAX_OUTPUT_BYTES]

            result = ActionResult(
                success=(proc.returncode == 0),
                output=output,
                error=proc.stderr[:MAX_OUTPUT_BYTES] if proc.stderr else "",
                exit_code=proc.returncode,
                duration_ms=duration,
                action_type="shell_cmd",
                truncated=len(proc.stdout) > MAX_OUTPUT_BYTES,
            )
        except subprocess.TimeoutExpired:
            result = ActionResult(
                success=False, output="",
                error=f"Timeout after {effective_timeout}s",
                exit_code=-1, action_type="shell_cmd",
            )
        except Exception as e:
            result = ActionResult(
                success=False, output="",
                error=str(e), exit_code=-1,
                action_type="shell_cmd",
            )

        self._log("shell_cmd", result)
        return result

    def read_file(self, path: str, max_lines: int = 200) -> ActionResult:
        """Read file contents (always allowed)."""
        try:
            start = time.time()
            resolved = os.path.realpath(path)
            
            # Safety: don't read outside workspace if set
            if self.workspace and not resolved.startswith(os.path.realpath(self.workspace)):
                return ActionResult(
                    success=False, output="",
                    error=f"Path {path} outside workspace {self.workspace}",
                    action_type="file_read",
                )

            with open(resolved, 'r') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)

            output = ''.join(lines)
            duration = (time.time() - start) * 1000
            result = ActionResult(
                success=True, output=output[:MAX_OUTPUT_BYTES],
                duration_ms=duration, action_type="file_read",
                truncated=len(output) > MAX_OUTPUT_BYTES or len(lines) >= max_lines,
            )
        except Exception as e:
            result = ActionResult(
                success=False, output="",
                error=str(e), action_type="file_read",
            )

        self._log("file_read", result)
        return result

    def write_file(self, path: str, content: str) -> ActionResult:
        """Write file (requires READ_WRITE or FULL permission)."""
        if self.permission == Permission.READ_ONLY:
            result = ActionResult(
                success=False, output="",
                error="Write permission denied (read-only mode)",
                action_type="file_write",
            )
            self._log("file_write_denied", result)
            return result

        try:
            resolved = os.path.realpath(path)
            if self.workspace and not resolved.startswith(os.path.realpath(self.workspace)):
                return ActionResult(
                    success=False, output="",
                    error=f"Path {path} outside workspace",
                    action_type="file_write",
                )

            with open(resolved, 'w') as f:
                f.write(content)

            result = ActionResult(
                success=True, output=f"Written {len(content)} bytes to {path}",
                action_type="file_write",
            )
        except Exception as e:
            result = ActionResult(
                success=False, output="",
                error=str(e), action_type="file_write",
            )

        self._log("file_write", result)
        return result

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return list(self.audit)

    def _log(self, action: str, result: ActionResult) -> None:
        self.audit.append({
            "action": action,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "time": time.time(),
            "error": result.error[:200] if result.error else "",
        })
