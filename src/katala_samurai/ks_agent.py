"""
KS Agent (KSA-1a) — KS41b + PEV Loop Integration.

Connects KS41b verification pipeline as the Verify step in the
Plan-Execute-Verify (PEV) loop. Each iteration:
  Plan:    KS41b Goal Planning → decompose task into actionable steps
  Execute: ActionExecutor → run file reads, shell commands, or KS verifications
  Verify:  KS41b verify() → validate execution results with confidence scoring

Theoretical basis:
  - KS41b: 28-solver hybrid verification with anti-accumulation (KS30c C-4)
  - PEV Loop: inspired by OODA (Observe-Orient-Decide-Act) adapted for
    verification-centric AI agents
  - Self-Other Boundary (KS39b): agent verifies its own outputs, maintaining
    provenance tracking between planning and execution roles

Design: Youta Hilono + Nicolas
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import sys
import os
import json
from typing import Any, Optional

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from session_state import SessionStateManager
from action_executor import ActionExecutor, Permission
from pev_loop import PEVLoop, PEVResult

# Try to import KS41b, fall back gracefully
try:
    from ks41b import KS41b, Claim
    KS_AVAILABLE = True
except ImportError:
    try:
        from ks41a import KS41a as KS41b, Claim
        KS_AVAILABLE = True
    except ImportError:
        KS_AVAILABLE = False
        KS41b = None

# ── Named Constants ──
AGENT_VERSION: str = "KSA-1a"
"""Current agent version identifier."""

DEFAULT_SESSION_TTL: float = 1800.0
"""Default session time-to-live in seconds (30 minutes)."""

DEFAULT_MAX_ITERATIONS: int = 10
"""Default maximum PEV loop iterations before giving up."""

CONFIDENCE_VALID_THRESHOLD: float = 0.7
"""Minimum confidence for verification to pass."""

CONFIDENCE_CRITICAL_THRESHOLD: float = 0.3
"""Below this confidence, task approach needs fundamental rethinking."""

CONFIDENCE_WEAK_THRESHOLD: float = 0.5
"""Below this confidence, significant adjustment needed."""

FALLBACK_CONFIDENCE: float = 0.6
"""Confidence assigned when KS verification errors but execution succeeded."""

NO_KS_SUCCESS_CONFIDENCE: float = 0.75
"""Confidence when no KS is available and execution succeeded."""

NO_KS_FAILURE_CONFIDENCE: float = 0.2
"""Confidence when execution failed (with or without KS)."""

OUTPUT_TRUNCATE_CONTENT: int = 2000
"""Max characters of file/exec output to preserve."""

OUTPUT_TRUNCATE_ERROR: int = 500
"""Max characters of error output to preserve."""

CLAIM_TRUNCATE: int = 500
"""Max characters in verification claim text."""

VERIFY_CONFIDENCE_MAP: dict[str, float] = {
    "SUPPORT": 0.85,
    "LEAN_SUPPORT": 0.70,
    "UNCERTAIN": 0.45,
    "LEAN_REJECT": 0.25,
    "REJECT": 0.10,
    "NO_EVIDENCE": 0.30,
}
"""Mapping from KS verdict strings to numeric confidence scores."""


def _ks_verdict_to_confidence(verdict: str) -> float:
    """Map a KS verification verdict string to a numeric confidence score."""
    return VERIFY_CONFIDENCE_MAP.get(verdict, 0.5)


class KSAgent:
    """
    KS Agent: Plan-Execute-Verify with KS41b as verifier.

    Usage:
        agent = KSAgent(workspace="/path/to/project")
        result = agent.run("Verify that function X handles edge case Y")
    """

    def __init__(
        self,
        workspace: str = "",
        permission: Permission = Permission.READ_ONLY,
        session_ttl: float = DEFAULT_SESSION_TTL,
        max_iterations: int = 10,
        network: bool = False,
    ):
        self.workspace = workspace
        self.state = SessionStateManager(default_ttl=session_ttl)
        self.executor = ActionExecutor(
            permission=permission,
            workspace=workspace,
            network_allowed=network,
        )
        self.ks = KS41b() if KS_AVAILABLE else None
        self.max_iterations = max_iterations

        self.pev = PEVLoop(
            planner=self._plan,
            executor=self._execute,
            verifier=self._verify,
            adjuster=self._adjust,
            state_manager=self.state,
            max_iterations=max_iterations,
        )

    def run(self, task: str, context: Optional[dict] = None) -> PEVResult:
        """Run the full PEV agent loop on a task.

        Args:
            task: Natural language description of the task.
            context: Optional initial context dict.

        Returns:
            PEVResult with success status, iterations, and step history.
        """
        return self.pev.run(task, context)

    def _plan(self, task: str, context: dict) -> dict[str, Any]:
        """Plan step: decompose task into actionable steps using KS41b goal planning."""
        iteration = context.get("iteration", 0)
        last_feedback = context.get("last_feedback", "")

        if iteration == 0:
            # First iteration: analyze the task
            plan = {
                "plan": f"Analyze and execute: {task}",
                "steps": self._decompose_task(task),
                "current_step": 0,
            }
        else:
            # Subsequent: adjust based on feedback
            prev_plan = context.get("last_output", {})
            current_step = prev_plan.get("current_step", 0) + 1 if isinstance(prev_plan, dict) else iteration
            plan = {
                "plan": f"Retry/adjust based on: {last_feedback}",
                "steps": [f"address_feedback: {last_feedback}"],
                "current_step": current_step,
            }

        return plan

    def _execute_read(self, path: str) -> dict[str, Any]:
        """Execute a file read action."""
        r = self.executor.read_file(path)
        return {"type": "file_read", "path": path,
                "success": r.success, "content": r.output[:OUTPUT_TRUNCATE_CONTENT]}

    def _execute_python(self, code: str) -> dict[str, Any]:
        """Execute a Python code snippet."""
        r = self.executor.execute_python(code)
        return {"type": "python_exec", "success": r.success,
                "output": r.output[:OUTPUT_TRUNCATE_CONTENT], "error": r.error[:OUTPUT_TRUNCATE_ERROR]}

    def _execute_shell(self, cmd: str) -> dict[str, Any]:
        """Execute a shell command."""
        r = self.executor.execute_shell(cmd)
        return {"type": "shell", "success": r.success,
                "output": r.output[:OUTPUT_TRUNCATE_CONTENT], "error": r.error[:OUTPUT_TRUNCATE_ERROR]}

    def _execute_verify(self, claim_text: str) -> dict[str, Any]:
        """Execute a direct KS verification on a claim."""
        if not self.ks:
            return {"type": "ks_verify", "error": "KS not available"}
        try:
            claim = Claim(claim_text)
            ks_result = self.ks.verify(claim, skip_s28=True)
            return {"type": "ks_verify",
                    "verdict": str(ks_result.get("verdict", "UNKNOWN")),
                    "confidence": ks_result.get("confidence", 0.5)}
        except Exception as e:
            return {"type": "ks_verify", "error": str(e)}

    def _execute(self, plan: dict, context: dict) -> dict[str, Any]:
        """Execute step: dispatch the planned action to the appropriate handler."""
        steps = plan.get("steps", [])
        current = plan.get("current_step", 0)

        if not steps:
            return {"output": None, "success": False, "error": "No steps to execute"}

        step = steps[min(current, len(steps) - 1)]

        # Dispatch table: prefix → handler
        dispatch: dict[str, Any] = {
            "read:": lambda s: self._execute_read(s.split(":", 1)[1].strip()),
            "exec:": lambda s: self._execute_python(s.split(":", 1)[1].strip()),
            "shell:": lambda s: self._execute_shell(s.split(":", 1)[1].strip()),
            "verify:": lambda s: self._execute_verify(s.split(":", 1)[1].strip()),
        }

        output = {"type": "generic", "step": step}
        for prefix, handler in dispatch.items():
            if step.startswith(prefix):
                output = handler(step)
                break

        return {
            "step": step,
            "outputs": [output],
            "success": output.get("success", True),
            "current_step": current,
        }

    def _verify(self, output: dict, task: str) -> dict[str, Any]:
        """Verify step: use KS41b to validate execution results.

        Returns a dict with 'valid' (bool), 'confidence' (float), and 'feedback' (str).
        Falls back to basic success check if KS is unavailable or errors.
        """
        if not output or not output.get("success", False):
            error_msg = output.get("outputs", [{}])[0].get("error", "unknown") if output else "no output"
            return {"valid": False, "confidence": NO_KS_FAILURE_CONFIDENCE,
                    "feedback": f"Execution failed: {error_msg}"}

        if not self.ks:
            success = output.get("success", False)
            conf = NO_KS_SUCCESS_CONFIDENCE if success else NO_KS_FAILURE_CONFIDENCE
            return {"valid": success, "confidence": conf, "feedback": "No KS available, basic check only"}

        return self._verify_with_ks(output, task)

    def _verify_with_ks(self, output: dict, task: str) -> dict[str, Any]:
        """Run KS41b verification on execution output."""
        outputs = output.get("outputs", [])
        claim_text = f"Task '{task}' completed with: {json.dumps(outputs[:3], default=str)[:CLAIM_TRUNCATE]}"

        try:
            claim = Claim(claim_text)
            ks_result = self.ks.verify(claim, skip_s28=True)
            verdict = str(ks_result.get("verdict", "UNCERTAIN"))
            confidence = _ks_verdict_to_confidence(verdict)
            return {
                "valid": confidence >= CONFIDENCE_VALID_THRESHOLD,
                "confidence": confidence,
                "feedback": f"KS verdict: {verdict}",
                "ks_result": {k: str(v)[:200] for k, v in ks_result.items()},
            }
        except Exception as e:
            return {"valid": output.get("success", False),
                    "confidence": FALLBACK_CONFIDENCE,
                    "feedback": f"KS error (fallback): {e}"}

    def _adjust(self, task: str, output: dict, verify_result: dict, context: dict) -> dict:
        """Adjust step: generate feedback for next PEV iteration based on verification confidence."""
        feedback = verify_result.get("feedback", "Unknown issue")
        confidence = verify_result.get("confidence", 0.0)

        if confidence < CONFIDENCE_CRITICAL_THRESHOLD:
            return {"feedback": f"CRITICAL: {feedback}. Rethink approach entirely."}
        if confidence < CONFIDENCE_WEAK_THRESHOLD:
            return {"feedback": f"WEAK: {feedback}. Significant adjustment needed."}
        return {"feedback": f"CLOSE: {feedback}. Minor refinement."}

    def _decompose_task(self, task: str) -> list[str]:
        """Decompose a task string into actionable step prefixes."""
        task_lower = task.lower()

        if "verify" in task_lower or "check" in task_lower:
            return [f"verify: {task}"]
        elif "read" in task_lower or "file" in task_lower:
            # Extract path-like tokens
            tokens = task.split()
            paths = [t for t in tokens if '/' in t or '.' in t]
            if paths:
                return [f"read: {paths[0]}"]
            return [f"verify: {task}"]
        elif "run" in task_lower or "execute" in task_lower or "test" in task_lower:
            return [f"shell: python3 -m pytest --timeout=30 -x"]
        else:
            return [f"verify: {task}"]

    def get_status(self) -> dict[str, Any]:
        """Return current agent status including KS availability and session state."""
        return {
            "version": AGENT_VERSION,
            "ks_available": KS_AVAILABLE,
            "ks_version": getattr(self.ks, 'VERSION', 'N/A') if self.ks else 'N/A',
            "permission": self.permission.value if hasattr(self, 'permission') else self.executor.permission.value,
            "state": self.state.get_stats(),
            "executor_audit_len": len(self.executor.audit),
        }


def main():
    """Quick integration test."""
    print(f"KS Agent {AGENT_VERSION}")
    print(f"KS Available: {KS_AVAILABLE}")

    agent = KSAgent(workspace=os.path.dirname(_dir))

    # Test 1: Simple verification
    print("\n--- Test 1: Verification task ---")
    result = agent.run("Verify that 2+2=4")
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")
    print(f"Reason: {result.reason}")
    print(f"Steps: {len(result.steps)}")

    # Test 2: File read task
    print("\n--- Test 2: File read task ---")
    result2 = agent.run("Read file src/katala_samurai/ks41b.py")
    print(f"Success: {result2.success}")
    print(f"Iterations: {result2.iterations}")

    # Test 3: Shell task
    print("\n--- Test 3: Shell task ---")
    result3 = agent.run("Run tests")
    print(f"Success: {result3.success}")
    print(f"Iterations: {result3.iterations}")

    # Status
    print(f"\n--- Agent Status ---")
    status = agent.get_status()
    for k, v in status.items():
        print(f"  {k}: {v}")

    print("\n=== INTEGRATION TEST COMPLETE ===")


if __name__ == "__main__":
    main()
