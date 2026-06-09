from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import reviewer_reproducibility_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReviewerReproducibilityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = reviewer_reproducibility_audit.load_json(
            REPO_ROOT / "config/reviewer-reproducibility-policy.json"
        )

    def copy_repo_inputs(self, root: Path) -> None:
        paths = set(self.policy["required_files"])
        paths.add(self.policy["reviewer_surface"])
        paths.update(self.policy["required_evidence_paths"])
        paths.add("demo/release_readiness.py")
        for relative in paths:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_reviewer_surface(self) -> None:
        report = reviewer_reproducibility_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(8, report["present_file_count"])
        self.assertEqual(6, report["command_count"])
        self.assertEqual(6, report["evidence_path_count"])
        self.assertEqual(6, report["existing_evidence_path_count"])
        self.assertEqual(7, report["boundary_term_count"])
        self.assertEqual(6, report["release_control_count"])
        self.assertEqual(6, report["detected_fixture_count"])

    def test_all_policy_fixtures_are_detected(self) -> None:
        report = reviewer_reproducibility_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual(
            [fixture["name"] for fixture in self.policy["fixtures"]],
            [fixture["name"] for fixture in report["fixtures"] if fixture["detected"]],
        )

    def test_detects_missing_quickstart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / "docs/reviewer-quickstart.md").unlink()

            report = reviewer_reproducibility_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_missing_reviewer_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/reviewer-quickstart.md"
            path.write_text(path.read_text(encoding="utf-8").replace("make ci", ""), encoding="utf-8")

            report = reviewer_reproducibility_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["reviewer_command_contract"])

    def test_detects_missing_evidence_packet_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/reviewer-quickstart.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("docs/evidence/evidence-provenance.md", ""),
                encoding="utf-8",
            )

            report = reviewer_reproducibility_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_packet_contract"])

    def test_detects_missing_boundary_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/reviewer-quickstart.md"
            path.write_text(path.read_text(encoding="utf-8").replace("no cloud account", ""), encoding="utf-8")

            report = reviewer_reproducibility_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["review_boundary_contract"])

    def test_detects_missing_release_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/reviewer-quickstart.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("proof_packet_integrity_audit", ""),
                encoding="utf-8",
            )

            report = reviewer_reproducibility_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_control_linkage"])

    def test_writes_evidence(self) -> None:
        report = reviewer_reproducibility_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            reviewer_reproducibility_audit.write_json(report, output_dir)
            reviewer_reproducibility_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "reviewer-reproducibility-audit.json").exists())
            self.assertIn(
                "Reviewer Reproducibility Audit",
                (output_dir / "reviewer-reproducibility-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
