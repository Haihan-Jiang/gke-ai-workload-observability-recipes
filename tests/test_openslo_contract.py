from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import alerting_rules, openslo_contract, reliability_gate


REPO_ROOT = Path(__file__).resolve().parents[1]


class OpenSLOContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.slo_config = reliability_gate.load_slo_config(REPO_ROOT / "config/reliability-slo.json")
        self.alert_policy = alerting_rules.load_json(REPO_ROOT / "config/alerting-policy.json")
        self.policy = openslo_contract.load_json(REPO_ROOT / "config/openslo-policy.json")

    def test_contract_covers_scenarios_and_operational_links(self) -> None:
        contract = openslo_contract.build_contract(self.slo_config, self.alert_policy, self.policy)
        rendered = "\n".join(openslo_contract.render_yaml(contract)) + "\n"
        report = openslo_contract.evaluate(contract, self.policy, rendered)

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["scenario_count"], 5)
        self.assertEqual(99.5, report["objective_target"])

    def test_audit_detects_missing_runbook_link(self) -> None:
        contract = openslo_contract.build_contract(self.slo_config, self.alert_policy, self.policy)
        contract["spec"]["operationalLinks"].pop("runbooks")
        rendered = "\n".join(openslo_contract.render_yaml(contract)) + "\n"

        report = openslo_contract.evaluate(contract, self.policy, rendered)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["operational_links"])

    def test_audit_detects_missing_latency_guardrail(self) -> None:
        contract = openslo_contract.build_contract(self.slo_config, self.alert_policy, self.policy)
        contract["spec"]["latencyGuardrails"] = []
        rendered = "\n".join(openslo_contract.render_yaml(contract)) + "\n"

        report = openslo_contract.evaluate(contract, self.policy, rendered)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["latency_guardrails"])

    def test_writes_evidence_and_contract(self) -> None:
        contract = openslo_contract.build_contract(self.slo_config, self.alert_policy, self.policy)
        rendered = "\n".join(openslo_contract.render_yaml(contract)) + "\n"
        report = openslo_contract.evaluate(contract, self.policy, rendered)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            contract_path = output_dir / "contract.yaml"
            openslo_contract.write_json(report, output_dir)
            openslo_contract.write_markdown(report, contract, output_dir)
            contract_path.write_text(rendered, encoding="utf-8")

            self.assertTrue((output_dir / "openslo-contract.json").exists())
            self.assertIn("OpenSLO Contract Evidence", (output_dir / "openslo-contract.md").read_text())
            self.assertIn("apiVersion:", contract_path.read_text())


if __name__ == "__main__":
    unittest.main()
