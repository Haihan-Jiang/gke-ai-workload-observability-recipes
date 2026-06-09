from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import architecture_decision_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ArchitectureDecisionAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = architecture_decision_audit.load_json(REPO_ROOT / "config/architecture-decision-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        paths = set(self.policy["required_files"])
        paths.update(item["path"] for item in self.policy["decisions"])
        for decision in self.policy["decisions"]:
            paths.update(decision["evidence_links"])
        for relative in paths:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_adr_surface(self) -> None:
        report = architecture_decision_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["present_file_count"])
        self.assertEqual(4, report["decision_count"])
        self.assertEqual(4, report["accepted_decision_count"])
        self.assertEqual(18, report["evidence_link_count"])
        self.assertEqual(18, report["existing_evidence_link_count"])
        self.assertEqual(18, report["release_control_count"])
        self.assertEqual(7, report["detected_fixture_count"])

    def test_all_policy_fixtures_are_detected(self) -> None:
        report = architecture_decision_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual(
            [fixture["name"] for fixture in self.policy["fixtures"]],
            [fixture["name"] for fixture in report["fixtures"] if fixture["detected"]],
        )

    def test_detects_missing_adr_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / "docs/adr/README.md").unlink()

            report = architecture_decision_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_pending_decision_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/adr/0002-fail-closed-release-readiness.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Status: Accepted", "Status: Proposed"),
                encoding="utf-8",
            )

            report = architecture_decision_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["adr_section_contract"])

    def test_detects_missing_evidence_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/adr/0003-privacy-safe-incident-replay-boundary.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("docs/evidence/telemetry-redaction-audit.md", ""),
                encoding="utf-8",
            )

            report = architecture_decision_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_linkage"])

    def test_detects_missing_release_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/adr/0002-fail-closed-release-readiness.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("proof_packet_integrity_audit", ""),
                encoding="utf-8",
            )

            report = architecture_decision_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_control_linkage"])

    def test_detects_missing_rationale_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/adr/0004-policy-as-code-change-control.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("policy-as-code plus tests", ""),
                encoding="utf-8",
            )

            report = architecture_decision_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["decision_rationale"])

    def test_writes_evidence(self) -> None:
        report = architecture_decision_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            architecture_decision_audit.write_json(report, output_dir)
            architecture_decision_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "architecture-decision-audit.json").exists())
            self.assertIn(
                "Architecture Decision Audit",
                (output_dir / "architecture-decision-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
