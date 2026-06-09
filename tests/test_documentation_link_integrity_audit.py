from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import documentation_link_integrity_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class DocumentationLinkIntegrityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = documentation_link_integrity_audit.load_json(
            REPO_ROOT / "config/documentation-link-policy.json"
        )
        self.files = documentation_link_integrity_audit.load_markdown(REPO_ROOT, self.policy)

    def report_for_files(self, files: dict[str, str | None]) -> dict:
        checks, metrics, links = documentation_link_integrity_audit.evaluate_files(
            REPO_ROOT,
            files,
            self.policy,
        )
        fixtures = documentation_link_integrity_audit.evaluate_fixtures(
            REPO_ROOT,
            files,
            self.policy,
        )
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            documentation_link_integrity_audit.check(
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
            "links": links,
            "fixture_results": fixtures,
            "detected_fixture_count": detected_fixture_count,
        }

    def test_passes_current_documentation_links(self) -> None:
        report = documentation_link_integrity_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["markdown_file_count"], 80)
        self.assertGreaterEqual(report["local_link_count"], 520)
        self.assertGreaterEqual(report["external_link_count"], 10)
        self.assertGreaterEqual(report["image_link_count"], 2)
        self.assertEqual(0, report["missing_target_count"])
        self.assertEqual(0, report["bad_anchor_count"])
        self.assertEqual(6, report["detected_fixture_count"])

    def test_detects_missing_required_file(self) -> None:
        files = copy.deepcopy(self.files)
        files["docs/case-study.md"] = None

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["required_file_inventory"])

    def test_detects_broken_local_link(self) -> None:
        files = copy.deepcopy(self.files)
        files["README.md"] += "\n[missing](docs/evidence/not-real.md)\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["local_link_targets"])

    def test_rejects_path_outside_repo(self) -> None:
        files = copy.deepcopy(self.files)
        files["docs/case-study.md"] += "\n[outside](../../outside.md)\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["path_safety"])

    def test_rejects_unsupported_scheme(self) -> None:
        files = copy.deepcopy(self.files)
        files["README.md"] += "\n[ftp](ftp://example.com/file.txt)\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["scheme_contract"])

    def test_detects_missing_anchor(self) -> None:
        files = copy.deepcopy(self.files)
        files["docs/case-study.md"] += "\n[bad anchor](case-study.md#not-a-real-section)\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["anchor_targets"])

    def test_writes_evidence(self) -> None:
        report = documentation_link_integrity_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            documentation_link_integrity_audit.write_json(report, output_dir)
            documentation_link_integrity_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "documentation-link-integrity-audit.json").exists())
            self.assertIn(
                "Documentation Link Integrity Audit",
                (output_dir / "documentation-link-integrity-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
