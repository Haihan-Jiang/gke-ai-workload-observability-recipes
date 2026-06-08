from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo import alerting_rules, grafana_dashboard, reliability_gate


REPO_ROOT = Path(__file__).resolve().parents[1]


class GrafanaDashboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.slo_config = reliability_gate.load_slo_config(REPO_ROOT / "config/reliability-slo.json")
        self.alert_policy = alerting_rules.load_json(REPO_ROOT / "config/alerting-policy.json")
        self.dashboard_policy = grafana_dashboard.load_json(REPO_ROOT / "config/dashboard-policy.json")

    def test_dashboard_covers_required_scenarios_and_panel_types(self) -> None:
        dashboard = grafana_dashboard.build_dashboard(
            self.slo_config,
            self.alert_policy,
            self.dashboard_policy,
        )
        config_map = grafana_dashboard.render_config_map(dashboard, self.dashboard_policy)
        report = grafana_dashboard.evaluate(dashboard, self.dashboard_policy, config_map)

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["panel_count"], 6)
        self.assertGreaterEqual(set(report["scenarios"]), set(self.dashboard_policy["required_scenarios"]))
        self.assertGreaterEqual(set(report["panel_types"]), set(self.dashboard_policy["required_panel_types"]))

    def test_dashboard_audit_detects_missing_datasource(self) -> None:
        dashboard = grafana_dashboard.build_dashboard(
            self.slo_config,
            self.alert_policy,
            self.dashboard_policy,
        )
        dashboard["panels"][0]["targets"][0].pop("datasource")
        config_map = grafana_dashboard.render_config_map(dashboard, self.dashboard_policy)

        report = grafana_dashboard.evaluate(dashboard, self.dashboard_policy, config_map)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["prometheus_datasource"])

    def test_writes_evidence_dashboard_and_config_map(self) -> None:
        dashboard = grafana_dashboard.build_dashboard(
            self.slo_config,
            self.alert_policy,
            self.dashboard_policy,
        )
        config_map = grafana_dashboard.render_config_map(dashboard, self.dashboard_policy)
        report = grafana_dashboard.evaluate(dashboard, self.dashboard_policy, config_map)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            grafana_dashboard.write_json(report, output_dir)
            grafana_dashboard.write_markdown(report, dashboard, output_dir)
            dashboard_path = output_dir / "dashboard.json"
            config_map_path = output_dir / "dashboard-configmap.yaml"
            dashboard_path.write_text(json.dumps(dashboard, indent=2) + "\n", encoding="utf-8")
            config_map_path.write_text(config_map, encoding="utf-8")

            self.assertTrue((output_dir / "grafana-dashboard.json").exists())
            self.assertIn("Grafana Dashboard Evidence", (output_dir / "grafana-dashboard.md").read_text())
            self.assertIn("kind: ConfigMap", config_map_path.read_text())
            self.assertIn("panels", dashboard_path.read_text())


if __name__ == "__main__":
    unittest.main()
