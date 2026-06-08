from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo import alerting_rules, reliability_gate


REPO_ROOT = Path(__file__).resolve().parents[1]


class AlertingRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.slo_config = reliability_gate.load_slo_config(REPO_ROOT / "config/reliability-slo.json")
        self.policy = json.loads((REPO_ROOT / "config/alerting-policy.json").read_text())

    def test_builds_alerts_for_all_slo_scenarios(self) -> None:
        alerts = alerting_rules.build_alerts(self.slo_config, self.policy)
        scenarios = {item["labels"]["scenario"] for item in alerts}

        self.assertEqual(set(self.slo_config["scenarios"]), scenarios)
        self.assertGreaterEqual(len(alerts), 5)
        self.assertGreaterEqual(
            sum(1 for item in alerts if item["labels"]["severity"] == "page"),
            3,
        )

    def test_alert_audit_requires_runbook_annotations(self) -> None:
        alerts = alerting_rules.build_alerts(self.slo_config, self.policy)
        manifest = alerting_rules.render_prometheus_rule(alerts, self.policy)

        report = alerting_rules.evaluate(alerts, self.policy, manifest)
        self.assertEqual("pass", report["status"])

        alerts[0]["annotations"].pop("runbook_url")
        report = alerting_rules.evaluate(alerts, self.policy, manifest)
        checks = {item["name"]: item["ok"] for item in report["checks"]}
        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["required_annotations"])

    def test_alert_audit_requires_scenario_coverage(self) -> None:
        alerts = alerting_rules.build_alerts(self.slo_config, self.policy)
        manifest = alerting_rules.render_prometheus_rule(alerts, self.policy)

        report = alerting_rules.evaluate(alerts[:-1], self.policy, manifest)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["scenario_coverage"])

    def test_writes_evidence_and_manifest(self) -> None:
        alerts = alerting_rules.build_alerts(self.slo_config, self.policy)
        manifest = alerting_rules.render_prometheus_rule(alerts, self.policy)
        report = alerting_rules.evaluate(alerts, self.policy, manifest)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            alerting_rules.write_json(report, output_dir)
            alerting_rules.write_markdown(report, output_dir)
            manifest_path = output_dir / "alerting-rules.yaml"
            manifest_path.write_text(manifest, encoding="utf-8")

            self.assertTrue((output_dir / "alerting-rules.json").exists())
            self.assertIn("SLO Alerting Rules", (output_dir / "alerting-rules.md").read_text())
            self.assertIn("kind: PrometheusRule", manifest_path.read_text())


if __name__ == "__main__":
    unittest.main()
