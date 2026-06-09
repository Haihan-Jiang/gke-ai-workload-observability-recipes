from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import evidence_schema_audit


REPO_ROOT = Path(__file__).resolve().parents[1]
CIRCULAR_ARTIFACTS = {
    "docs/evidence/release-readiness.json",
    "docs/evidence/evidence-provenance.json",
    "docs/evidence/disaster-recovery-drill.json",
}


class EvidenceSchemaAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = evidence_schema_audit.load_json(REPO_ROOT / "config/evidence-schema-policy.json")
        self.artifacts = evidence_schema_audit.load_artifacts(REPO_ROOT, self.policy)

    def report_for(self, artifacts: dict) -> dict:
        checks, metrics = evidence_schema_audit.evaluate_artifacts(artifacts, self.policy)
        fixtures = evidence_schema_audit.evaluate_fixtures(artifacts, self.policy)
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            evidence_schema_audit.check(
                "negative_fixture_coverage",
                detected_fixture_count >= self.policy["minimum_detected_fixtures"],
                {"detected_fixture_count": detected_fixture_count},
            )
        )
        failed_count = sum(1 for item in checks if not item["ok"])
        return {
            "status": "pass" if failed_count == 0 else "fail",
            "checks": checks,
            "metrics": metrics,
            "fixtures": fixtures,
            "detected_fixture_count": detected_fixture_count,
        }

    def test_passes_current_evidence_contracts(self) -> None:
        report = evidence_schema_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(25, report["artifact_count"])
        self.assertGreaterEqual(report["required_field_count"], 287)
        self.assertGreaterEqual(report["required_check_count"], 169)
        self.assertGreaterEqual(report["metric_contract_count"], 60)
        self.assertEqual(25, report["detected_fixture_count"])

    def test_policy_avoids_generated_evidence_cycles(self) -> None:
        policy_paths = {artifact["path"] for artifact in self.policy["artifacts"]}

        self.assertTrue(policy_paths.isdisjoint(CIRCULAR_ARTIFACTS))

    def test_detects_missing_required_field(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/developer-runtime-audit.json"].pop("status")

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["required_fields"])

    def test_detects_invalid_status(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/ci-governance-audit.json"]["status"] = "green"

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["status_contract"])

    def test_detects_invalid_allowed_value(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/deployment-policy.json"]["decision"] = "ship_it"

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["value_contract"])

    def test_detects_missing_required_check(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        checks = artifacts["docs/evidence/pod-security-admission-audit.json"]["checks"]
        artifacts["docs/evidence/pod-security-admission-audit.json"]["checks"] = [
            item for item in checks if item.get("name") != "namespace_psa_labels"
        ]

        report = self.report_for(artifacts)
        checks_by_name = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks_by_name["check_inventory"])

    def test_detects_bad_check_shape(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/synthetic-probe-audit.json"]["checks"] = "bad"

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["check_shape"])

    def test_detects_missing_check_result(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/k8s-hardening-audit.json"]["checks"][0].pop("status")

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["check_shape"])

    def test_detects_metric_contract_drift(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/developer-runtime-audit.json"]["make_target_count"] = 2

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["metric_contract"])

    def test_detects_metric_ceiling_drift(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/supply-chain-audit.json"]["failed_count"] = 1

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["metric_contract"])

    def test_detects_array_contract_drift(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/workload-identity-audit.json"]["identity_boundaries"] = []

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["array_contract"])

    def test_detects_missing_deployment_decision(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/deployment-policy.json"].pop("decision")

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["required_fields"])

    def test_detects_model_release_candidate_regression(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["docs/evidence/model-release-safety-audit.json"]["blocked_candidate_count"] = 0

        report = self.report_for(artifacts)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["metric_contract"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = evidence_schema_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            json_output = output_dir / "schema.json"
            markdown_output = output_dir / "schema.md"

            evidence_schema_audit.write_json(report, json_output)
            evidence_schema_audit.write_markdown(report, markdown_output)

            self.assertTrue(json_output.exists())
            self.assertIn("Evidence Schema Audit", markdown_output.read_text())


if __name__ == "__main__":
    unittest.main()
