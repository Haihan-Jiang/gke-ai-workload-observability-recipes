from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import sbom_inventory_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class SbomInventoryAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = sbom_inventory_audit.load_json(REPO_ROOT / "config/sbom-inventory-policy.json")
        self.files = sbom_inventory_audit.read_files(REPO_ROOT, sbom_inventory_audit.policy_paths(self.policy))

    def report_for(self, files: dict[str, str | None], policy: dict) -> dict:
        checks, metrics, _ = sbom_inventory_audit.evaluate(REPO_ROOT, files, policy)
        fixtures = sbom_inventory_audit.evaluate_fixtures(REPO_ROOT, files, policy)
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            sbom_inventory_audit.check(
                "negative_fixture_coverage",
                detected_fixture_count >= policy["minimum_detected_fixtures"],
                {"detected_fixture_count": detected_fixture_count},
            )
        )
        failed_count = sum(1 for item in checks if not item["ok"])
        return {
            "status": "pass" if failed_count == 0 else "fail",
            "checks": checks,
            "metrics": metrics,
            "fixtures": fixtures,
        }

    def test_current_sbom_inventory_audit_passes(self) -> None:
        report, sbom = sbom_inventory_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(8, report["component_count"])
        self.assertEqual(2, report["action_count"])
        self.assertEqual(4, report["image_count"])
        self.assertEqual(2, report["runtime_count"])
        self.assertEqual(9, report["source_path_count"])
        self.assertEqual(6, report["detected_fixture_count"])
        self.assertEqual("CycloneDX", sbom["bomFormat"])
        self.assertEqual(8, len(sbom["components"]))

    def test_detects_missing_action_component(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["expected_components"] = [
            item for item in policy["expected_components"] if item["bom_ref"] != "github-action:actions/setup-python@v6"
        ]

        report = self.report_for(self.files, policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["sbom_component_coverage"])

    def test_detects_uninventoried_action_reference(self) -> None:
        files = copy.deepcopy(self.files)
        files[".github/workflows/ci.yml"] += "\n      - uses: third-party/not-in-sbom@v1\n"

        report = self.report_for(files, self.policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["sbom_component_coverage"])

    def test_detects_duplicate_bom_refs(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["expected_components"][-1]["bom_ref"] = policy["expected_components"][-2]["bom_ref"]

        report = self.report_for(self.files, policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["cyclonedx_shape"])

    def test_detects_missing_source_traceability(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["expected_components"][0]["source_paths"] = []

        report = self.report_for(self.files, policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["source_traceability"])

    def test_detects_python_runtime_mismatch(self) -> None:
        policy = copy.deepcopy(self.policy)
        for component in policy["expected_components"]:
            if component["bom_ref"] == "runtime:python@3.12":
                component["version"] = "3.11"

        report = self.report_for(self.files, policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["runtime_boundary"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report, sbom = sbom_inventory_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            sbom_inventory_audit.write_json(report, sbom, output_dir)
            sbom_inventory_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "sbom-inventory-audit.json").exists())
            self.assertTrue((output_dir / "sbom-inventory.json").exists())
            self.assertIn("SBOM Inventory Audit", (output_dir / "sbom-inventory-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
