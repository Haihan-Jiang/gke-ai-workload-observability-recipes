from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo import detailed_reliability, incident_replay


REPO_ROOT = Path(__file__).resolve().parents[1]


class DetailedReliabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = [
            incident_replay.summarize_scenario(scenario)
            for scenario in incident_replay.SCENARIOS
        ]
        self.config = json.loads((REPO_ROOT / "config/detailed-reliability.json").read_text())

    def write_payloads(self, payload_dir: Path) -> None:
        payloads = [
            (
                str(scenario["name"]),
                incident_replay.build_scenario_payload(scenario, 1_700_000_000_000_000_000 + offset),
            )
            for offset, scenario in enumerate(incident_replay.SCENARIOS)
        ]
        incident_replay.write_payloads(payloads, payload_dir)

    def test_critical_path_finds_dominant_child_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.write_payloads(Path(tmp))
            report = detailed_reliability.build_critical_path(Path(tmp), self.config)
        by_scenario = {item["scenario"]: item for item in report["scenarios"]}
        self.assertEqual("vector-cache lookup", by_scenario["cache_miss_storm"]["dominant_span"])
        self.assertEqual("feature-store lookup", by_scenario["dependency_timeout"]["dominant_span"])
        self.assertEqual("model inference", by_scenario["rollout_regression"]["dominant_span"])

    def test_evidence_coverage_preserves_tail_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.write_payloads(Path(tmp))
            report = detailed_reliability.build_evidence_coverage(self.summary, Path(tmp), self.config)
        self.assertEqual("C07", report["problem_id"])
        self.assertEqual("pass", report["status"])
        by_scenario = {item["scenario"]: item for item in report["scenarios"]}
        self.assertIn("error", by_scenario["dependency_timeout"]["observed_tail_reasons"])
        self.assertIn("telemetry_loss", by_scenario["collector_queue_pressure"]["observed_tail_reasons"])

    def test_hpa_lag_separates_scaling_from_dependency_failures(self) -> None:
        report = detailed_reliability.build_hpa_lag(self.summary, self.config)
        by_scenario = {item["scenario"]: item for item in report["scenarios"]}
        self.assertEqual("steady_state", by_scenario["baseline"]["decision"])
        self.assertEqual("fix_dependency_or_rollout", by_scenario["dependency_timeout"]["decision"])
        self.assertEqual("fix_dependency_or_rollout", by_scenario["rollout_regression"]["decision"])

    def test_tenant_blast_radius_detects_premium_regression(self) -> None:
        report = detailed_reliability.build_tenant_blast_radius(self.summary, self.config)
        by_scenario = {item["scenario"]: item for item in report["scenarios"]}
        self.assertEqual("premium", by_scenario["rollout_regression"]["tenant_tier"])
        self.assertEqual("tenant_slo_breach", by_scenario["rollout_regression"]["blast_radius"])
        self.assertIn("rollout_regression", report["breached_scenarios"])

    def test_token_cost_guard_blocks_expensive_rollout(self) -> None:
        report = detailed_reliability.build_token_cost_guard(self.summary, self.config)
        by_scenario = {item["scenario"]: item for item in report["scenarios"]}
        self.assertEqual("allow", by_scenario["baseline"]["decision"])
        self.assertEqual("block_or_review", by_scenario["rollout_regression"]["decision"])
        self.assertGreater(by_scenario["rollout_regression"]["total_tokens"], 520)


if __name__ == "__main__":
    unittest.main()
