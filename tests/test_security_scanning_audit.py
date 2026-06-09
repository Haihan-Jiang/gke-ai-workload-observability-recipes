from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import security_scanning_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class SecurityScanningAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = security_scanning_audit.load_json(
            REPO_ROOT / "config/security-scanning-policy.json"
        )
        self.workflow = security_scanning_audit.load_workflow(
            REPO_ROOT / self.policy["workflow_path"]
        )
        self.release_source = (REPO_ROOT / "demo/release_readiness.py").read_text(encoding="utf-8")

    def report_for(
        self,
        *,
        workflow_exists: bool = True,
        workflow: dict | None = None,
        release_source: str | None = None,
    ) -> dict:
        checks, metrics = security_scanning_audit.evaluate_workflow(
            workflow_exists=workflow_exists,
            workflow=workflow if workflow is not None else self.workflow,
            release_source=release_source if release_source is not None else self.release_source,
            policy=self.policy,
        )
        fixtures = security_scanning_audit.evaluate_fixtures(
            workflow_exists=workflow_exists,
            workflow=workflow if workflow is not None else self.workflow,
            release_source=release_source if release_source is not None else self.release_source,
            policy=self.policy,
        )
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            security_scanning_audit.check(
                "negative_fixture_coverage",
                detected_fixture_count >= self.policy["minimum_detected_fixtures"],
                {"detected_fixture_count": detected_fixture_count},
            )
        )
        failed_count = sum(1 for item in checks if not item["ok"])
        return {
            "status": "pass" if failed_count == 0 else "fail",
            **metrics,
            "detected_fixture_count": detected_fixture_count,
            "checks": checks,
        }

    def test_passes_current_security_scanning_policy(self) -> None:
        report = security_scanning_audit.build_report(
            REPO_ROOT,
            self.policy,
            release_readiness_source=Path("demo/release_readiness.py"),
        )

        self.assertEqual("pass", report["status"])
        self.assertEqual(1, report["workflow_count"])
        self.assertGreaterEqual(report["job_count"], 1)
        self.assertGreaterEqual(report["language_count"], 1)
        self.assertGreaterEqual(report["codeql_action_count"], 2)
        self.assertGreaterEqual(report["query_suite_count"], 2)
        self.assertGreaterEqual(report["release_control_count"], 6)
        self.assertEqual(8, report["detected_fixture_count"])

    def test_fixtures_detect_expected_contract_breaks(self) -> None:
        results = security_scanning_audit.evaluate_fixtures(
            workflow_exists=True,
            workflow=self.workflow,
            release_source=self.release_source,
            policy=self.policy,
        )

        self.assertEqual(8, len(results))
        self.assertTrue(all(item["detected"] for item in results))

    def test_detects_missing_workflow(self) -> None:
        report = self.report_for(workflow_exists=False, workflow={})
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["workflow_inventory"])

    def test_detects_missing_trigger(self) -> None:
        workflow = copy.deepcopy(self.workflow)
        security_scanning_audit.workflow_on(workflow).pop("schedule", None)
        report = self.report_for(workflow=workflow)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["trigger_contract"])

    def test_detects_permission_drift(self) -> None:
        workflow = copy.deepcopy(self.workflow)
        workflow["permissions"].pop("security-events")
        report = self.report_for(workflow=workflow)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["permission_contract"])

    def test_detects_language_drift(self) -> None:
        workflow = copy.deepcopy(self.workflow)
        workflow["jobs"]["analyze"]["strategy"]["matrix"]["language"] = ["javascript-typescript"]
        report = self.report_for(workflow=workflow)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["job_contract"])

    def test_detects_floating_codeql_action_ref(self) -> None:
        workflow = copy.deepcopy(self.workflow)
        for step in workflow["jobs"]["analyze"]["steps"]:
            if str(step.get("uses", "")).startswith("github/codeql-action/init@"):
                step["uses"] = "github/codeql-action/init@main"
        report = self.report_for(workflow=workflow)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["codeql_action_contract"])

    def test_detects_missing_query_suite(self) -> None:
        workflow = copy.deepcopy(self.workflow)
        for step in workflow["jobs"]["analyze"]["steps"]:
            if step.get("uses") == "github/codeql-action/init@v4":
                step["with"]["queries"] = "security-and-quality"
        report = self.report_for(workflow=workflow)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["query_suite_contract"])

    def test_writes_evidence(self) -> None:
        report = security_scanning_audit.build_report(
            REPO_ROOT,
            self.policy,
            release_readiness_source=Path("demo/release_readiness.py"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            security_scanning_audit.write_json(report, output_dir)
            security_scanning_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "security-scanning-audit.json").exists())
            self.assertIn(
                "Security Scanning Audit",
                (output_dir / "security-scanning-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
