from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import maintainer_intake_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class MaintainerIntakeAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = maintainer_intake_audit.load_json(REPO_ROOT / "config/maintainer-intake-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        for relative in self.policy["required_files"]:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_intake_surface(self) -> None:
        report = maintainer_intake_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(6, report["present_file_count"])
        self.assertEqual(2, report["issue_template_count"])
        self.assertEqual(3, report["pr_validation_command_count"])
        self.assertEqual(5, report["support_term_count"])
        self.assertEqual(6, report["detected_fixture_count"])

    def test_all_policy_fixtures_are_detected(self) -> None:
        report = maintainer_intake_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual(
            [fixture["name"] for fixture in self.policy["fixtures"]],
            [fixture["name"] for fixture in report["fixtures"] if fixture["detected"]],
        )

    def test_detects_missing_bug_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / ".github/ISSUE_TEMPLATE/bug_report.yml").unlink()

            report = maintainer_intake_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_missing_no_secret_bug_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / ".github/ISSUE_TEMPLATE/bug_report.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "No credentials, tokens, private customer data, or production secrets.",
                    "",
                ),
                encoding="utf-8",
            )

            report = maintainer_intake_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["issue_intake_contract"])

    def test_detects_missing_feature_validation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / ".github/ISSUE_TEMPLATE/feature_request.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Validation plan", ""),
                encoding="utf-8",
            )

            report = maintainer_intake_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["feature_request_contract"])

    def test_detects_missing_security_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / ".github/ISSUE_TEMPLATE/config.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Security vulnerability reporting", ""),
                encoding="utf-8",
            )

            report = maintainer_intake_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["issue_security_boundary"])

    def test_detects_missing_ci_validation_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / ".github/PULL_REQUEST_TEMPLATE.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("CI=true ./scripts/validate.sh", ""),
                encoding="utf-8",
            )

            report = maintainer_intake_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["pull_request_validation_contract"])

    def test_detects_missing_support_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "SUPPORT.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("does not provide production support", ""),
                encoding="utf-8",
            )

            report = maintainer_intake_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["support_boundary"])

    def test_writes_evidence(self) -> None:
        report = maintainer_intake_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            maintainer_intake_audit.write_json(report, output_dir)
            maintainer_intake_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "maintainer-intake-audit.json").exists())
            self.assertIn(
                "Maintainer Intake Audit",
                (output_dir / "maintainer-intake-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
