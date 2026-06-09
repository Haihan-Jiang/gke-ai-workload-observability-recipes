from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo import k8s_hardening_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class K8sHardeningAuditTest(unittest.TestCase):
    def test_current_manifests_pass_hardening_audit(self) -> None:
        config = json.loads((REPO_ROOT / "config/k8s-hardening-policy.json").read_text())
        docs = k8s_hardening_audit.load_manifest_set(
            [REPO_ROOT / path for path in config["target_manifests"]]
        )

        report = k8s_hardening_audit.evaluate_documents(docs, config)

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["failed_count"])
        self.assertGreaterEqual(report["check_count"], 11)

    def test_audit_detects_missing_collector_resources(self) -> None:
        config = json.loads((REPO_ROOT / "config/k8s-hardening-policy.json").read_text())
        docs = k8s_hardening_audit.load_manifest_set(
            [REPO_ROOT / path for path in config["target_manifests"]]
        )
        for doc in docs:
            if doc.get("kind") == "Deployment" and doc.get("metadata", {}).get("name") == "otel-collector":
                container = k8s_hardening_audit.find_container(doc, "otel-collector")
                container.pop("resources", None)

        report = k8s_hardening_audit.evaluate_documents(docs, config)
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["collector_resources"])

    def test_writes_json_and_markdown(self) -> None:
        report = {
            "status": "pass",
            "check_count": 1,
            "passed_count": 1,
            "failed_count": 0,
            "checks": [
                {
                    "name": "sample",
                    "status": "pass",
                    "reason": "covered",
                    "evidence": {},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            k8s_hardening_audit.write_json(report, output_dir)
            k8s_hardening_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "k8s-hardening-audit.json").exists())
            self.assertIn(
                "Kubernetes Manifest Hardening Audit",
                (output_dir / "k8s-hardening-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
