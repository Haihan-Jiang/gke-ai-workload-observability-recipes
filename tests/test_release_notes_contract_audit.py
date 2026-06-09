from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import release_notes_contract_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleaseNotesContractAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = release_notes_contract_audit.load_json(REPO_ROOT / "config/release-notes-contract-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        for relative in self.policy["required_files"]:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_release_note_contract(self) -> None:
        report = release_notes_contract_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(4, report["present_file_count"])
        self.assertGreaterEqual(report["release_note_field_count"], 4)
        self.assertGreaterEqual(report["evidence_reference_count"], 8)
        self.assertGreaterEqual(report["validation_command_count"], 6)
        self.assertGreaterEqual(report["boundary_statement_count"], 3)
        self.assertEqual(6, report["detected_fixture_count"])

    def test_all_policy_fixtures_are_detected(self) -> None:
        report = release_notes_contract_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual(
            [fixture["name"] for fixture in self.policy["fixtures"]],
            [fixture["name"] for fixture in report["fixtures"] if fixture["detected"]],
        )

    def test_detects_missing_release_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / "docs/release-process.md").unlink()

            report = release_notes_contract_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_missing_release_note_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/release-process.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("the main reliability or governance capability added", ""),
                encoding="utf-8",
            )

            report = release_notes_contract_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_notes_template"])

    def test_detects_missing_proof_packet_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/release-process.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("proof-packet-integrity-audit.md", ""),
                encoding="utf-8",
            )

            report = release_notes_contract_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_reference_contract"])

    def test_detects_missing_ci_validation_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/release-process.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("CI=true ./scripts/validate.sh", ""),
                encoding="utf-8",
            )

            report = release_notes_contract_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["validation_command_contract"])

    def test_detects_missing_boundary_statement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/release-process.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("does not deploy a production service", ""),
                encoding="utf-8",
            )

            report = release_notes_contract_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["boundary_language_contract"])

    def test_detects_missing_contribution_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "CONTRIBUTING.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Summarize which evidence changed", ""),
                encoding="utf-8",
            )

            report = release_notes_contract_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["contribution_change_summary"])

    def test_writes_evidence(self) -> None:
        report = release_notes_contract_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            release_notes_contract_audit.write_json(report, output_dir)
            release_notes_contract_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "release-notes-contract-audit.json").exists())
            self.assertIn(
                "Release Notes Contract Audit",
                (output_dir / "release-notes-contract-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
