import tempfile
import unittest
from pathlib import Path

from demo import staged_telemetry_validation_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class StagedTelemetryValidationAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = staged_telemetry_validation_audit.load_json(
            REPO_ROOT / "config/staged-telemetry-validation-policy.json"
        )
        self.inputs = {
            "rollout_guard": staged_telemetry_validation_audit.load_json(REPO_ROOT / "docs/evidence/rollout-guard.json"),
            "trace_quality": staged_telemetry_validation_audit.load_json(REPO_ROOT / "docs/evidence/trace-quality-audit.json"),
            "telemetry_redaction": staged_telemetry_validation_audit.load_json(
                REPO_ROOT / "docs/evidence/telemetry-redaction-audit.json"
            ),
            "telemetry_cost": staged_telemetry_validation_audit.load_json(REPO_ROOT / "docs/evidence/telemetry-cost-budget.json"),
            "telemetry_exporter_authority": staged_telemetry_validation_audit.load_json(
                REPO_ROOT / "docs/evidence/telemetry-exporter-authority-audit.json"
            ),
            "synthetic_probe": staged_telemetry_validation_audit.load_json(REPO_ROOT / "docs/evidence/synthetic-probe-audit.json"),
            "model_release_safety": staged_telemetry_validation_audit.load_json(
                REPO_ROOT / "docs/evidence/model-release-safety-audit.json"
            ),
        }

    def report_for_fixture(self, fixture_name: str) -> dict:
        fixture = next(item for item in self.policy["fixtures"] if item["name"] == fixture_name)
        mutated = staged_telemetry_validation_audit.apply_fixture(self.inputs, fixture)
        checks, _ = staged_telemetry_validation_audit.evaluate_inputs(mutated, self.policy)
        return {"checks": {item["name"]: item["status"] for item in checks}}

    def test_current_staged_telemetry_validation_passes(self) -> None:
        report = staged_telemetry_validation_audit.build_report(self.inputs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(7, report["artifact_count"])
        self.assertEqual(5, report["scenario_count"])
        self.assertEqual(4, report["validated_surface_count"])
        self.assertGreaterEqual(report["preflight_block_count"], 2)
        self.assertGreaterEqual(report["blocked_candidate_count"], 1)
        self.assertEqual(len(self.policy["fixtures"]), report["detected_fixture_count"])

    def test_detects_rollout_promoted_without_telemetry_block(self) -> None:
        report = self.report_for_fixture("rollout_promoted_without_telemetry_block")

        self.assertEqual("fail", report["checks"]["staged_rollout_guard"])

    def test_detects_trace_quality_failure(self) -> None:
        report = self.report_for_fixture("trace_quality_failed_before_promotion")

        self.assertEqual("fail", report["checks"]["evidence_status_contract"])

    def test_detects_redaction_violation(self) -> None:
        report = self.report_for_fixture("redaction_violation_during_stage")

        self.assertEqual("fail", report["checks"]["pre_promotion_telemetry_contract"])

    def test_detects_missing_canary_probe(self) -> None:
        report = self.report_for_fixture("missing_canary_probe")

        self.assertEqual("fail", report["checks"]["synthetic_preflight_contract"])

    def test_detects_unblocked_candidate(self) -> None:
        report = self.report_for_fixture("candidate_not_blocked")

        self.assertEqual("fail", report["checks"]["model_promotion_block"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = staged_telemetry_validation_audit.build_report(self.inputs, self.policy)

            staged_telemetry_validation_audit.write_json(report, output_dir)
            staged_telemetry_validation_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "staged-telemetry-validation-audit.json").exists())
            self.assertIn(
                "Staged Telemetry Validation Audit",
                (output_dir / "staged-telemetry-validation-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
