from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import supply_chain_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class SupplyChainAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = supply_chain_audit.load_json(REPO_ROOT / "config/supply-chain-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        for relative in self.policy["target_manifests"]:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_digest_pinned_images(self) -> None:
        report = supply_chain_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["image_count"])
        self.assertEqual(2, report["digest_pinned_count"])

    def test_detects_unpinned_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "k8s/gke/sample-app.yaml"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203",
                "python:3.12-slim",
            )
            path.write_text(text, encoding="utf-8")

            report = supply_chain_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["digest_pinning"])

    def test_detects_latest_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "k8s/gke/sample-app.yaml"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203",
                "python:latest@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203",
            )
            path.write_text(text, encoding="utf-8")

            report = supply_chain_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["forbidden_tags"])

    def test_detects_missing_pull_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            path = root / "k8s/gke/sample-app.yaml"
            text = path.read_text(encoding="utf-8").replace("          imagePullPolicy: IfNotPresent\n", "")
            path.write_text(text, encoding="utf-8")

            report = supply_chain_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["pull_policy"])

    def test_writes_evidence(self) -> None:
        report = supply_chain_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            supply_chain_audit.write_json(report, output_dir)
            supply_chain_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "supply-chain-audit.json").exists())
            self.assertIn("Supply Chain Audit", (output_dir / "supply-chain-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
