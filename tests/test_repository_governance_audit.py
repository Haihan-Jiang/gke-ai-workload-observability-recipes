from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import repository_governance_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class RepositoryGovernanceAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = repository_governance_audit.load_json(REPO_ROOT / "config/repository-governance-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        for relative in self.policy["required_files"]:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_governance_surface(self) -> None:
        report = repository_governance_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(6, report["present_file_count"])
        self.assertGreaterEqual(report["owned_pattern_count"], 9)
        self.assertEqual(8, report["detected_fixture_count"])

    def test_detects_missing_contributing_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / "CONTRIBUTING.md").unlink()

            report = repository_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_missing_private_security_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "SECURITY.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("GitHub private vulnerability reporting", ""),
                encoding="utf-8",
            )

            report = repository_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["security_reporting"])

    def test_detects_missing_ci_mode_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "CONTRIBUTING.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("make ci", ""),
                encoding="utf-8",
            )

            report = repository_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["contribution_workflow"])

    def test_detects_missing_release_evidence_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/release-process.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("repository-governance-audit.md", ""),
                encoding="utf-8",
            )

            report = repository_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_process"])

    def test_detects_missing_default_codeowner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / ".github/CODEOWNERS"
            path.write_text(
                path.read_text(encoding="utf-8").replace("* @Haihan-Jiang\n", ""),
                encoding="utf-8",
            )

            report = repository_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["codeowners_coverage"])

    def test_detects_wrong_codeowner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / ".github/CODEOWNERS"
            path.write_text(
                path.read_text(encoding="utf-8").replace("@Haihan-Jiang", "@someone-else"),
                encoding="utf-8",
            )

            report = repository_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["codeowners_coverage"])

    def test_writes_evidence(self) -> None:
        report = repository_governance_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            repository_governance_audit.write_json(report, output_dir)
            repository_governance_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "repository-governance-audit.json").exists())
            self.assertIn(
                "Repository Governance Audit",
                (output_dir / "repository-governance-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
