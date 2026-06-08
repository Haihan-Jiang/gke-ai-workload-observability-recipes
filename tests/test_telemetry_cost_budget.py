from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import incident_replay, telemetry_cost_budget


REPO_ROOT = Path(__file__).resolve().parents[1]


class TelemetryCostBudgetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = telemetry_cost_budget.load_json(REPO_ROOT / "config/telemetry-cost-policy.json")
        self.summary = [incident_replay.summarize_scenario(item) for item in incident_replay.SCENARIOS]

    def write_payloads(self, payload_dir: Path) -> None:
        payloads = [
            (
                str(scenario["name"]),
                incident_replay.build_scenario_payload(scenario, 1_780_000_000_000_000_000 + index * 2_000_000_000),
            )
            for index, scenario in enumerate(incident_replay.SCENARIOS)
        ]
        incident_replay.write_payloads(payloads, payload_dir)

    def build_report(self, payload_dir: Path, policy: dict | None = None) -> dict:
        return telemetry_cost_budget.build_report(
            summary=self.summary,
            payload_dir=payload_dir,
            policy=policy or self.policy,
        )

    def test_passes_current_payload_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)

            report = self.build_report(payload_dir)

            self.assertEqual("pass", report["status"])
            self.assertEqual(5, report["scenario_count"])
            self.assertLess(report["daily_ingest_gib"], self.policy["max_daily_ingest_gib"])

    def test_detects_payload_size_budget_overrun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            policy = copy.deepcopy(self.policy)
            policy["max_payload_bytes_per_request"] = 100

            report = self.build_report(payload_dir, policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["payload_size_budget"])

    def test_detects_baseline_oversampling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            policy = copy.deepcopy(self.policy)
            policy["sampling_rates"]["baseline"] = 0.5

            report = self.build_report(payload_dir, policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["sampling_policy"])

    def test_detects_critical_scenario_undersampling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            policy = copy.deepcopy(self.policy)
            policy["sampling_rates"]["dependency_timeout"] = 0.5

            report = self.build_report(payload_dir, policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["critical_scenario_sampling"])

    def test_detects_daily_ingest_budget_overrun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            policy = copy.deepcopy(self.policy)
            policy["max_daily_ingest_gib"] = 0.1

            report = self.build_report(payload_dir, policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["daily_ingest_budget"])

    def test_writes_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp) / "payloads"
            output_dir = Path(tmp) / "evidence"
            self.write_payloads(payload_dir)
            output_dir.mkdir()

            report = self.build_report(payload_dir)
            telemetry_cost_budget.write_json(report, output_dir)
            telemetry_cost_budget.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "telemetry-cost-budget.json").exists())
            self.assertIn("Telemetry Cost Budget", (output_dir / "telemetry-cost-budget.md").read_text())


if __name__ == "__main__":
    unittest.main()
