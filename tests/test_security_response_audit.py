from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from demo import security_response_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class SecurityResponseAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = security_response_audit.load_json(REPO_ROOT / "config/security-response-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        for relative in self.policy["required_files"]:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_security_response_surface(self) -> None:
        report = security_response_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(3, report["present_file_count"])
        self.assertEqual(4, report["severity_tier_count"])
        self.assertLessEqual(report["critical_triage_hours"], 24)
        self.assertEqual(8, report["detected_fixture_count"])

    def test_detects_missing_private_reporting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "SECURITY.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("GitHub private vulnerability reporting", ""),
                encoding="utf-8",
            )

            report = security_response_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["private_reporting"])

    def test_detects_slow_critical_triage_policy(self) -> None:
        policy = copy.deepcopy(self.policy)
        for tier in policy["severity_tiers"]:
            if tier["name"] == "critical":
                tier["triage_hours"] = 48

        report = security_response_audit.build_report(REPO_ROOT, policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["severity_sla"])

    def test_detects_missing_disclosure_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "SECURITY.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("coordinated disclosure update", ""),
                encoding="utf-8",
            )

            report = security_response_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["disclosure_flow"])

    def test_detects_missing_release_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/release-process.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("security-response-audit.md", ""),
                encoding="utf-8",
            )

            report = security_response_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_process"])

    def test_detects_missing_contribution_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "CONTRIBUTING.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Security-sensitive changes must follow SECURITY.md", ""),
                encoding="utf-8",
            )

            report = security_response_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["contribution_boundary"])

    def test_writes_evidence(self) -> None:
        report = security_response_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            security_response_audit.write_json(report, output_dir)
            security_response_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "security-response-audit.json").exists())
            self.assertIn("Security Response Audit", (output_dir / "security-response-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
