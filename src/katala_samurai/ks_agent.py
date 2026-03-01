"""
KS Agent — KS41b + PEV Loop Integration.

Connects KS41b verification pipeline as the Verify step in PEV loop.
Plan: KS41b Goal Planning → Execute: Action Executor → Verify: KS41b verify()

This is the minimal viable agent: KS can now plan, act, and verify in a loop.

Design: Youta Hilono + Nicolas
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import sys
import os
import time
import json
from typing import Any, Dict, Optional

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

# ── Constants ──
AGENT_VERSION = "KSA-1a"
DEFAULT_SESSION_TTL = 1800   # 30 min
VERIFY_CONFIDENCE_MAP = {
    "SUPPORT": 0.85,
    "LEAN_SUPPORT": 0.70,
    "UNCERTAIN": 0.45,
    "LEAN_REJECT": 0.25,
    "REJECT": 0.10,
    "NO_EVIDENCE": 0.30,
}


def _ks_verdict_to_confidence(verdict: str) -> float:
    """Map KS verdict string to confidence float."""
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

    def run(self, task: str, context: Optional[Dict] = None) -> PEVResult:
        """Run the full agent loop on a task."""
        return self.pev.run(task, context)

    def _plan(self, task: str, context: Dict) -> Dict[str, Any]:
        """Plan step: decompose task into actionable steps."""
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

    def _execute(self, plan: Dict, context: Dict) -> Dict[str, Any]:
        """Execute step: run the planned action."""
        steps = plan.get("steps", [])
        current = plan.get("current_step", 0)

        if not steps:
            return {"output": None, "success": False, "error": "No steps to execute"}

        step = steps[min(current, len(steps) - 1)]
        result = {"step": step, "outputs": []}

        if step.startswith("read:"):
            # File read action
            path = step.split(":", 1)[1].strip()
            r = self.executor.read_file(path)
            result["outputs"].append({"type": "file_read", "path": path,
                                       "success": r.success, "content": r.output[:2000]})

        elif step.startswith("exec:"):
            # Python execution
            code = step.split(":", 1)[1].strip()
            r = self.executor.execute_python(code)
            result["outputs"].append({"type": "python_exec", "success": r.success,
                                       "output": r.output[:2000], "error": r.error[:500]})

        elif step.startswith("shell:"):
            # Shell command
            cmd = step.split(":", 1)[1].strip()
            r = self.executor.execute_shell(cmd)
            result["outputs"].append({"type": "shell", "success": r.success,
                                       "output": r.output[:2000], "error": r.error[:500]})

        elif step.startswith("verify:"):
            # Direct KS verification
            claim_text = step.split(":", 1)[1].strip()
            if self.ks:
                try:
                    claim = Claim(claim_text)
                    ks_result = self.ks.verify(claim, skip_s28=True)
                    result["outputs"].append({"type": "ks_verify",
                                               "verdict": str(ks_result.get("verdict", "UNKNOWN")),
                                               "confidence": ks_result.get("confidence", 0.5)})
                except Exception as e:
                    result["outputs"].append({"type": "ks_verify", "error": str(e)})
            else:
                result["outputs"].append({"type": "ks_verify", "error": "KS not available"})

        else:
            # Generic: treat as verification claim
            result["outputs"].append({"type": "generic", "step": step})

        result["success"] = all(o.get("success", True) for o in result["outputs"])
        result["current_step"] = current
        return result

    def _verify(self, output: Dict, task: str) -> Dict[str, Any]:
        """Verify step: use KS41b to validate execution results."""
        if not output or not output.get("success", False):
            return {
                "valid": False,
                "confidence": 0.2,
                "feedback": f"Execution failed: {output.get('outputs', [{}])[0].get('error', 'unknown')}",
            }

        # If KS is available, verify the output claim
        if self.ks:
            # Construct verification claim from output
            outputs = output.get("outputs", [])
            claim_text = f"Task '{task}' was successfully completed with result: {json.dumps(outputs[:3], default=str)[:500]}"
            
            try:
                claim = Claim(claim_text)
                ks_result = self.ks.verify(claim, skip_s28=True)
                verdict = str(ks_result.get("verdict", "UNCERTAIN"))
                confidence = _ks_verdict_to_confidence(verdict)

                return {
                    "valid": confidence >= 0.7,
                    "confidence": confidence,
                    "feedback": f"KS verdict: {verdict}",
                    "ks_result": {k: str(v)[:200] for k, v in ks_result.items()},
                }
            except Exception as e:
                # KS verification failed, fall back to basic check
                return {
                    "valid": output.get("success", False),
                    "confidence": 0.6,
                    "feedback": f"KS error (fallback): {e}",
                }
        else:
            # No KS: basic success check only
            return {
                "valid": output.get("success", False),
                "confidence": 0.75 if output.get("success") else 0.2,
                "feedback": "No KS available, basic check only",
            }

    def _adjust(self, task: str, output: Dict, verify_result: Dict, context: Dict) -> Dict:
        """Adjust step: generate feedback for next iteration."""
        feedback = verify_result.get("feedback", "Unknown issue")
        confidence = verify_result.get("confidence", 0.0)

        if confidence < 0.3:
            return {"feedback": f"CRITICAL: {feedback}. Rethink approach entirely."}
        elif confidence < 0.5:
            return {"feedback": f"WEAK: {feedback}. Significant adjustment needed."}
        else:
            return {"feedback": f"CLOSE: {feedback}. Minor refinement."}

    def _decompose_task(self, task: str) -> list:
        """Simple task decomposition heuristic."""
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

    def get_status(self) -> Dict[str, Any]:
        """Agent status."""
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
