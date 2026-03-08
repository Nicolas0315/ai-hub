from __future__ import annotations

import json
import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_ROOT = "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src"

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from kq_solver_unit import run_solver_unit_pipeline
from katala_samurai.inf_bridge import run_inf_bridge
from katala_samurai.kq_input_layer import build_kq_input_packet


class SolverUnitPipelineTest(unittest.TestCase):
    def test_pipeline_exposes_required_sections_for_general_command(self) -> None:
        command = "git status"
        packet = build_kq_input_packet(command).to_dict()
        bridge = run_inf_bridge(command)

        bundle = run_solver_unit_pipeline(command, input_packet=packet, bridge_result=bridge)

        self.assertIn("formal_probe", bundle)
        self.assertIn("kq3_control", bundle)
        self.assertIn("planner_vs_verifier", bundle)
        self.assertIn("complementary_5_loops", bundle)
        self.assertIn("mandatory_gate", bundle)
        self.assertTrue(bundle["mandatory_gate"]["required"])
        self.assertTrue(bundle["mandatory_gate"]["always_on"])
        self.assertEqual(bundle["complementary_5_loops"]["loop_count"], 5)
        self.assertEqual(bundle["complementary_5_loops"]["completed_loops"], 5)
        self.assertTrue(bundle["complementary_5_loops"]["always_on"])
        self.assertEqual(
            [row["loop"] for row in bundle["complementary_5_loops"]["loops"]],
            [1, 2, 3, 4, 5],
        )
        self.assertTrue(all(row["status"] == "completed" for row in bundle["complementary_5_loops"]["loops"]))
        self.assertFalse(bundle["iut_core_subset_v1"]["enabled"])
        self.assertIn("json", bundle)
        json.loads(bundle["json"])

    def test_pipeline_enables_iut_for_formal_command(self) -> None:
        command = "formal proof lemma for IUT theorem with forall x in [0,5]: x*x >= 0"
        packet = build_kq_input_packet(command).to_dict()
        bridge = run_inf_bridge(command)

        bundle = run_solver_unit_pipeline(command, input_packet=packet, bridge_result=bridge)

        self.assertIn("iut_core_subset_v1", bundle)
        self.assertIn("external_cross_verification", bundle)
        self.assertIn("observability_outputs", bundle)
        self.assertIn("final_artifacts", bundle)
        self.assertIn("coverage_report_per_solver_unit", bundle["final_artifacts"])
        self.assertTrue(bundle["ci_always_on_validation"]["kq_always_on"])
        self.assertTrue(bundle["observability_outputs"]["kq_always_on"])
        self.assertTrue(
            bundle["iut_core_subset_v1"]["enabled"]
            or bundle["iut_core_subset_v1"]["reason"] == "iut-core-evaluation-failed"
        )


if __name__ == "__main__":
    unittest.main()
