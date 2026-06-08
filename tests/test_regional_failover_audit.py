from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import regional_failover_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class RegionalFailoverAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = regional_failover_audit.load_json(REPO_ROOT / "config/regional-failover-policy.json")
        self.capacity = regional_failover_audit.load_json(REPO_ROOT / "docs/evidence/capacity-plan.json")
        self.error_budget = regional_failover_audit.load_json(REPO_ROOT / "docs/evidence/error-budget-ledger.json")
        self.rollback_drill = regional_failover_audit.load_json(REPO_ROOT / "docs/evidence/rollback-drill.json")
        self.disaster_recovery = regional_failover_audit.load_json(
            REPO_ROOT / "docs/evidence/disaster-recovery-drill.json"
        )
        self.synthetic_probe = regional_failover_audit.load_json(
            REPO_ROOT / "docs/evidence/synthetic-probe-audit.json"
        )
        self.load_shedding = regional_failover_audit.load_json(
            REPO_ROOT / "docs/evidence/load-shedding-policy-audit.json"
        )
        self.runbooks = regional_failover_audit.load_json(REPO_ROOT / "docs/evidence/incident-runbooks.json")
        self.k8s_hardening = regional_failover_audit.load_json(REPO_ROOT / "docs/evidence/k8s-hardening-audit.json")

    def build_report(
        self,
        *,
        policy: dict | None = None,
        disaster_recovery: dict | None = None,
        k8s_hardening: dict | None = None,
    ) -> dict:
        return regional_failover_audit.build_report(
            policy=policy or self.policy,
            capacity=self.capacity,
            error_budget=self.error_budget,
            rollback_drill=self.rollback_drill,
            disaster_recovery=disaster_recovery or self.disaster_recovery,
            synthetic_probe=self.synthetic_probe,
            load_shedding=self.load_shedding,
            runbooks=self.runbooks,
            k8s_hardening=k8s_hardening or self.k8s_hardening,
        )

    def test_current_regional_failover_audit_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["event_count"])
        self.assertEqual(2, report["standby_region_count"])
        self.assertEqual(5, report["detected_fixture_count"])

    def test_detects_restore_exceeding_rto(self) -> None:
        disaster_recovery = copy.deepcopy(self.disaster_recovery)
        disaster_recovery["estimated_restore_minutes"] = 30

        report = self.build_report(disaster_recovery=disaster_recovery)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["dr_recovery_contract"])

    def test_detects_small_standby_capacity(self) -> None:
        policy = copy.deepcopy(self.policy)
        for event in policy["events"]:
            if event["name"] == "retrieval_cache_region_failover":
                event["standby_replicas"] = 2

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["capacity_failover_guard"])

    def test_detects_release_action_mismatch(self) -> None:
        policy = copy.deepcopy(self.policy)
        for event in policy["events"]:
            if event["name"] == "feature_store_region_failover":
                event["expected_release_action"] = "eligible_for_release"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["traffic_safety_linkage"])

    def test_detects_missing_k8s_control(self) -> None:
        k8s_hardening = copy.deepcopy(self.k8s_hardening)
        for item in k8s_hardening["checks"]:
            if item["name"] == "collector_durable_queue":
                item["status"] = "fail"

        report = self.build_report(k8s_hardening=k8s_hardening)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["rollback_observability_contract"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            regional_failover_audit.write_json(report, output_dir)
            regional_failover_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "regional-failover-audit.json").exists())
            self.assertIn(
                "Regional Failover Audit",
                (output_dir / "regional-failover-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
