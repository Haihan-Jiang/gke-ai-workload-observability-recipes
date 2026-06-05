from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo import advanced_reliability, incident_replay


REPO_ROOT = Path(__file__).resolve().parents[1]


class AdvancedReliabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = [
            incident_replay.summarize_scenario(scenario)
            for scenario in incident_replay.SCENARIOS
        ]
        self.slo_config = json.loads((REPO_ROOT / "config/reliability-slo.json").read_text())
        self.advanced_config = json.loads((REPO_ROOT / "config/advanced-reliability.json").read_text())

    def write_payloads(self, payload_dir: Path) -> None:
        payloads = [
            (
                str(scenario["name"]),
                incident_replay.build_scenario_payload(scenario, 1_700_000_000_000_000_000 + offset),
            )
            for offset, scenario in enumerate(incident_replay.SCENARIOS)
        ]
        incident_replay.write_payloads(payloads, payload_dir)

    def test_burn_rate_pages_on_fast_budget_burn(self) -> None:
        report = advanced_reliability.build_burn_rate(
            self.summary,
            self.slo_config,
            self.advanced_config,
        )
        self.assertEqual("C01", report["problem_id"])
        self.assertEqual("page", report["windows"][0]["action"])
        self.assertGreater(report["windows"][0]["burn_rate"], 14.4)

    def test_rollout_guard_blocks_bad_candidate(self) -> None:
        report = advanced_reliability.build_rollout_guard(self.summary, self.advanced_config)
        self.assertEqual("C02", report["problem_id"])
        self.assertEqual("rollback", report["decision"])
        self.assertIn("v2", report["candidate_version"])
        self.assertTrue(report["violations"])

    def test_trace_quality_audits_exported_otlp_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            report = advanced_reliability.build_trace_quality(payload_dir, self.advanced_config)
        self.assertEqual("C03", report["problem_id"])
        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["payloads"])
        self.assertEqual(136, report["spans"])
        self.assertEqual({}, report["resource_missing"])
        self.assertEqual({}, report["root_missing"])
        self.assertEqual({}, report["child_span_missing"])

    def test_collector_resilience_model_keeps_queue_inside_budget(self) -> None:
        report = advanced_reliability.build_collector_resilience(self.advanced_config)
        self.assertEqual("C04", report["problem_id"])
        self.assertEqual("ok", report["risk"])
        self.assertEqual(0, report["estimated_lost_spans"])
        self.assertLessEqual(report["required_storage_mib"], report["configured_storage_mib"])

    def test_incident_correlation_dedupes_scenarios_to_root_causes(self) -> None:
        report = advanced_reliability.build_incident_correlation(
            self.summary,
            self.slo_config,
            self.advanced_config,
        )
        self.assertEqual("C05", report["problem_id"])
        self.assertEqual(4, report["incident_count"])
        self.assertIn("rollout_regression:v2", report["unique_dedupe_keys"])
        self.assertIn("telemetry_delivery:v1", report["unique_dedupe_keys"])


if __name__ == "__main__":
    unittest.main()
