from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import incident_replay, replay_source_contract_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReplaySourceContractAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = replay_source_contract_audit.load_json(
            REPO_ROOT / "config/replay-source-contract-policy.json"
        )
        self.summary = [
            incident_replay.summarize_scenario(scenario)
            for scenario in incident_replay.SCENARIOS
        ]
        self.payloads = {
            str(scenario["name"]): incident_replay.build_scenario_payload(
                scenario,
                1_780_000_000_000_000_000 + index * 2_000_000_000,
            )
            for index, scenario in enumerate(incident_replay.SCENARIOS)
        }

    def report_for(self, summary: list[dict], payloads: dict) -> dict:
        return replay_source_contract_audit.build_report(summary, payloads, self.policy)

    def test_passes_current_replay_source_contract(self) -> None:
        report = self.report_for(self.summary, self.payloads)

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["scenario_count"])
        self.assertEqual(5, report["payload_count"])
        self.assertEqual(34, report["root_span_count"])
        self.assertEqual(136, report["total_span_count"])
        self.assertGreaterEqual(report["attribute_key_count"], 19)
        self.assertEqual(7, report["detected_fixture_count"])

    def test_detects_missing_summary_scenario(self) -> None:
        summary = [item for item in self.summary if item["scenario"] != "baseline"]
        report = self.report_for(summary, self.payloads)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["scenario_inventory"])

    def test_detects_missing_summary_field(self) -> None:
        summary = copy.deepcopy(self.summary)
        summary[0].pop("model_variant")
        report = self.report_for(summary, self.payloads)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["summary_contract"])

    def test_detects_missing_payload(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        payloads["collector_queue_pressure"] = None
        report = self.report_for(self.summary, payloads)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["payload_inventory"])

    def test_detects_missing_root_attribute(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        replay_source_contract_audit.remove_root_attribute(payloads, "baseline", "ai.model.variant")
        report = self.report_for(self.summary, payloads)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["attribute_contract"])

    def test_detects_missing_child_span(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        replay_source_contract_audit.remove_child_span(payloads, "dependency_timeout", "feature-store lookup")
        report = self.report_for(self.summary, payloads)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["trace_shape_contract"])

    def test_detects_wrong_scenario_attribute(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        replay_source_contract_audit.set_root_attribute(
            payloads,
            "rollout_regression",
            "incident.scenario",
            "baseline",
        )
        report = self.report_for(self.summary, payloads)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["scenario_consistency"])

    def test_detects_forbidden_payload_attribute(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        replay_source_contract_audit.append_root_attribute(
            payloads,
            "baseline",
            "ai.prompt.text",
            "summarize the account",
        )
        report = self.report_for(self.summary, payloads)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["payload_privacy_boundary"])

    def test_writes_evidence(self) -> None:
        report = self.report_for(self.summary, self.payloads)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            replay_source_contract_audit.write_json(report, output_dir)
            replay_source_contract_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "replay-source-contract-audit.json").exists())
            self.assertIn(
                "Replay Source Contract Audit",
                (output_dir / "replay-source-contract-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
