"""
PEV Loop — Plan-Execute-Verify Agent Orchestrator for KS.

Integrates:
- KS41b Goal Planning (Plan)
- Action Executor (Execute)
- KS Verification Pipeline (Verify)
- Session State Manager (Memory)

ReAct-inspired but KS-native: verification is not LLM hallucination check,
it's full 28-solver + 10-type formal verification.

Design: Youta Hilono (requirements) + Shirokuma (implementation)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

# ── Constants ──
MAX_ITERATIONS = 20          # Hard cap on loop iterations
MAX_TOTAL_TIME_SECONDS = 600  # 10 min total cap
CONFIDENCE_THRESHOLD = 0.7   # Accept result if confidence >= this
RETRY_LIMIT = 3              # Max retries per step


class StepType(Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    ADJUST = "adjust"
    DONE = "done"
    FAILED = "failed"


@dataclass
class PEVStep:
    """Single step in the PEV loop."""
    iteration: int
    step_type: StepType
    input_data: Any
    output_data: Any = None
    confidence: float = 0.0
    duration_ms: float = 0.0
    error: str = ""


@dataclass
class PEVResult:
    """Final result of a PEV loop execution."""
    success: bool
    final_output: Any
    iterations: int
    total_time_ms: float
    steps: List[PEVStep]
    reason: str = ""


class PEVLoop:
    """
    Plan-Execute-Verify loop orchestrator.
    
    Usage:
        pev = PEVLoop(
            planner=my_plan_fn,
            executor=my_exec_fn,
            verifier=my_verify_fn,
            state_manager=session_state,
        )
        result = pev.run("Implement and test feature X")
    
    Each function signature:
        planner(task, context) -> {"plan": str, "steps": list}
        executor(plan_step, context) -> {"output": Any, "success": bool}
        verifier(output, original_task) -> {"valid": bool, "confidence": float, "feedback": str}
    """

    def __init__(
        self,
        planner: Callable,
        executor: Callable,
        verifier: Callable,
        adjuster: Optional[Callable] = None,
        state_manager: Optional[Any] = None,
        max_iterations: int = MAX_ITERATIONS,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ):
        self.planner = planner
        self.executor = executor
        self.verifier = verifier
        self.adjuster = adjuster or self._default_adjuster
        self.state = state_manager
        self.max_iterations = min(max_iterations, MAX_ITERATIONS)
        self.confidence_threshold = confidence_threshold
        self.steps: List[PEVStep] = []

    def run(self, task: str, context: Optional[Dict] = None) -> PEVResult:
        """Execute the full PEV loop."""
        context = context or {}
        start_time = time.time()
        iteration = 0
        current_plan = None
        last_output = None
        last_feedback = ""

        while iteration < self.max_iterations:
            elapsed = (time.time() - start_time) * 1000
            if elapsed > MAX_TOTAL_TIME_SECONDS * 1000:
                return self._finish(False, last_output, iteration, elapsed,
                                    reason="Time limit exceeded")

            # ── PLAN ──
            plan_context = {
                **context,
                "iteration": iteration,
                "last_feedback": last_feedback,
                "last_output": last_output,
            }

            step_start = time.time()
            try:
                plan_result = self.planner(task, plan_context)
                current_plan = plan_result
            except Exception as e:
                self._record(iteration, StepType.PLAN, task, error=str(e))
                return self._finish(False, None, iteration, 
                                    (time.time()-start_time)*1000,
                                    reason=f"Planning failed: {e}")

            plan_duration = (time.time() - step_start) * 1000
            self._record(iteration, StepType.PLAN, task, 
                         output_data=plan_result, duration_ms=plan_duration)

            # Store plan in session state
            if self.state:
                self.state.store(
                    f"plan_iter_{iteration}", plan_result,
                    confidence=0.8, source="SELF"
                )

            # ── EXECUTE ──
            step_start = time.time()
            try:
                exec_result = self.executor(current_plan, plan_context)
                last_output = exec_result
            except Exception as e:
                self._record(iteration, StepType.EXECUTE, current_plan, error=str(e))
                last_feedback = f"Execution error: {e}"
                iteration += 1
                continue

            exec_duration = (time.time() - step_start) * 1000
            self._record(iteration, StepType.EXECUTE, current_plan,
                         output_data=exec_result, duration_ms=exec_duration)

            # ── VERIFY ──
            step_start = time.time()
            try:
                verify_result = self.verifier(exec_result, task)
            except Exception as e:
                self._record(iteration, StepType.VERIFY, exec_result, error=str(e))
                last_feedback = f"Verification error: {e}"
                iteration += 1
                continue

            verify_duration = (time.time() - step_start) * 1000
            confidence = verify_result.get("confidence", 0.0)
            valid = verify_result.get("valid", False)

            self._record(iteration, StepType.VERIFY, exec_result,
                         output_data=verify_result, confidence=confidence,
                         duration_ms=verify_duration)

            # Store verified result
            if self.state and valid:
                self.state.store(
                    f"result_iter_{iteration}", exec_result,
                    confidence=confidence, source="SELF"
                )

            # ── CHECK: Done? ──
            if valid and confidence >= self.confidence_threshold:
                elapsed = (time.time() - start_time) * 1000
                self._record(iteration, StepType.DONE, exec_result,
                             confidence=confidence)
                return self._finish(True, exec_result, iteration + 1, elapsed,
                                    reason=f"Verified with confidence {confidence:.2f}")

            # ── ADJUST ──
            feedback = verify_result.get("feedback", "Verification failed")
            try:
                adjust_result = self.adjuster(
                    task, exec_result, verify_result, plan_context
                )
                last_feedback = adjust_result.get("feedback", feedback)
            except Exception:
                last_feedback = feedback

            self._record(iteration, StepType.ADJUST, verify_result,
                         output_data={"feedback": last_feedback})

            iteration += 1

        elapsed = (time.time() - start_time) * 1000
        return self._finish(False, last_output, iteration, elapsed,
                            reason="Max iterations reached")

    def _default_adjuster(self, task, output, verify_result, context):
        """Default adjuster: just pass feedback through."""
        return {"feedback": verify_result.get("feedback", "Try again")}

    def _record(self, iteration, step_type, input_data, 
                output_data=None, confidence=0.0, duration_ms=0.0, error=""):
        self.steps.append(PEVStep(
            iteration=iteration, step_type=step_type,
            input_data=str(input_data)[:500],
            output_data=str(output_data)[:500] if output_data else None,
            confidence=confidence, duration_ms=duration_ms, error=error,
        ))

    def _finish(self, success, output, iterations, elapsed_ms, reason=""):
        return PEVResult(
            success=success, final_output=output,
            iterations=iterations, total_time_ms=elapsed_ms,
            steps=list(self.steps), reason=reason,
        )
