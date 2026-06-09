from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import threat_model_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ThreatModelAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = threat_model_audit.load_json(REPO_ROOT / "config/threat-model-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        paths = set(self.policy["required_files"])
        paths.add(self.policy["threat_model_surface"])
        paths.add("demo/release_readiness.py")
        for threat in self.policy["threats"]:
            paths.update(threat["evidence_links"])
        for relative in paths:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_threat_model(self) -> None:
        report = threat_model_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["present_file_count"])
        self.assertEqual(6, report["asset_count"])
        self.assertEqual(6, report["trust_boundary_count"])
        self.assertEqual(6, report["threat_count"])
        self.assertEqual(29, report["mitigation_count"])
        self.assertEqual(6, report["owner_count"])
        self.assertEqual(6, report["residual_risk_count"])
        self.assertEqual(19, report["evidence_link_count"])
        self.assertEqual(19, report["existing_evidence_link_count"])
        self.assertEqual(19, report["release_control_count"])
        self.assertEqual(7, report["detected_fixture_count"])

    def test_all_policy_fixtures_are_detected(self) -> None:
        report = threat_model_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual(
            [fixture["name"] for fixture in self.policy["fixtures"]],
            [fixture["name"] for fixture in report["fixtures"] if fixture["detected"]],
        )

    def test_detects_missing_threat_model_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / "docs/threat-model.md").unlink()

            report = threat_model_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_missing_trust_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/threat-model.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("TB-03: Telemetry export boundary", ""),
                encoding="utf-8",
            )

            report = threat_model_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["scope_boundary_contract"])

    def test_detects_missing_threat_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/threat-model.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("TM-03: Prompt/response leakage through telemetry", ""),
                encoding="utf-8",
            )

            report = threat_model_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["threat_register_contract"])

    def test_detects_missing_evidence_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/threat-model.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("docs/evidence/telemetry-redaction-audit.md", ""),
                encoding="utf-8",
            )

            report = threat_model_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_linkage"])

    def test_detects_missing_release_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/threat-model.md"
            path.write_text(path.read_text(encoding="utf-8").replace("workload_identity_audit", ""), encoding="utf-8")

            report = threat_model_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_control_linkage"])

    def test_detects_missing_residual_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "docs/threat-model.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Residual risk: low after redaction, replay contract, and secret-hygiene",
                    "",
                ),
                encoding="utf-8",
            )

            report = threat_model_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["residual_risk_contract"])

    def test_writes_evidence(self) -> None:
        report = threat_model_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            threat_model_audit.write_json(report, output_dir)
            threat_model_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "threat-model-audit.json").exists())
            self.assertIn("Threat Model Audit", (output_dir / "threat-model-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
