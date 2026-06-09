from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import data_handling_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class DataHandlingAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = data_handling_audit.load_json(REPO_ROOT / "config/data-handling-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        paths = set(self.policy["required_files"])
        paths.add(self.policy["data_handling_surface"])
        paths.add("demo/release_readiness.py")
        for data_class in self.policy["data_classes"]:
            paths.update(data_class["evidence_links"])
        for relative in paths:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_data_handling_register(self) -> None:
        report = data_handling_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(6, report["present_file_count"])
        self.assertEqual(6, report["data_class_count"])
        self.assertEqual(54, report["handling_term_count"])
        self.assertEqual(6, report["retention_term_count"])
        self.assertEqual(6, report["owner_count"])
        self.assertEqual(18, report["evidence_link_count"])
        self.assertEqual(18, report["existing_evidence_link_count"])
        self.assertEqual(18, report["release_control_count"])
        self.assertEqual(7, report["detected_fixture_count"])

    def test_all_policy_fixtures_are_detected(self) -> None:
        report = data_handling_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual(
            [fixture["name"] for fixture in self.policy["fixtures"]],
            [fixture["name"] for fixture in report["fixtures"] if fixture["detected"]],
        )

    def test_detects_missing_data_handling_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / "docs/data-handling.md").unlink()

            report = data_handling_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_missing_data_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/data-handling.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("DC-02: AI model and tenant labels", ""),
                encoding="utf-8",
            )

            report = data_handling_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["data_class_contract"])

    def test_detects_missing_forbidden_data_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/data-handling.md"
            path.write_text(path.read_text(encoding="utf-8").replace("no prompt text", ""), encoding="utf-8")

            report = data_handling_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["handling_contract"])

    def test_detects_missing_retention_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/data-handling.md"
            path.write_text(path.read_text(encoding="utf-8").replace("retention_days=7", ""), encoding="utf-8")

            report = data_handling_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["retention_contract"])

    def test_detects_missing_evidence_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/data-handling.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("docs/evidence/telemetry-redaction-audit.md", ""),
                encoding="utf-8",
            )

            report = data_handling_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_linkage"])

    def test_detects_missing_release_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/data-handling.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("telemetry_exporter_authority_audit", ""),
                encoding="utf-8",
            )

            report = data_handling_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_control_linkage"])

    def test_writes_evidence(self) -> None:
        report = data_handling_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            data_handling_audit.write_json(report, output_dir)
            data_handling_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "data-handling-audit.json").exists())
            self.assertIn("Data Handling Audit", (output_dir / "data-handling-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
