from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import evidence_pipeline_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class EvidencePipelineAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = evidence_pipeline_audit.load_json(REPO_ROOT / "config/evidence-pipeline-policy.json")
        script = (REPO_ROOT / "scripts/generate-evidence.sh").read_text(encoding="utf-8")
        self.steps = evidence_pipeline_audit.extract_steps(script, self.policy)

    def report_for_steps(self, steps: list[dict]) -> dict:
        checks, metrics = evidence_pipeline_audit.evaluate_steps(steps, self.policy)
        fixtures = evidence_pipeline_audit.evaluate_fixtures(steps, self.policy)
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            evidence_pipeline_audit.check(
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
            "detected_fixture_count": detected_fixture_count,
        }

    def test_current_generate_pipeline_order_passes(self) -> None:
        report = evidence_pipeline_audit.build_report(
            REPO_ROOT,
            self.policy,
            Path("scripts/generate-evidence.sh"),
        )

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["step_count"], 56)
        self.assertGreaterEqual(report["dependency_count"], 70)
        self.assertEqual(4, report["detected_fixture_count"])

    def test_detects_regional_failover_before_disaster_recovery(self) -> None:
        steps = evidence_pipeline_audit.move_after(
            self.steps,
            "disaster_recovery_drill",
            "regional_failover_audit",
        )

        report = self.report_for_steps(steps)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["dependency_order"])

    def test_detects_provenance_before_rendered_index(self) -> None:
        steps = evidence_pipeline_audit.move_after(
            self.steps,
            "render_incident_evidence",
            "evidence_provenance",
        )

        report = self.report_for_steps(steps)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["dependency_order"])

    def test_detects_missing_required_step(self) -> None:
        steps = [step for step in self.steps if step["name"] != "release_readiness"]

        report = self.report_for_steps(steps)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["step_inventory"])

    def test_detects_duplicate_step(self) -> None:
        steps = self.steps + [dict(self.steps[0])]

        report = self.report_for_steps(steps)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["step_inventory"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = evidence_pipeline_audit.build_report(
            REPO_ROOT,
            self.policy,
            Path("scripts/generate-evidence.sh"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            json_output = output_dir / "pipeline.json"
            markdown_output = output_dir / "pipeline.md"

            evidence_pipeline_audit.write_json(report, json_output)
            evidence_pipeline_audit.write_markdown(report, markdown_output)

            self.assertTrue(json_output.exists())
            self.assertIn("Evidence Pipeline Audit", markdown_output.read_text())


if __name__ == "__main__":
    unittest.main()
