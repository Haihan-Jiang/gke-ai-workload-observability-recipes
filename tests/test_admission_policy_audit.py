from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import admission_policy_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class AdmissionPolicyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = admission_policy_audit.load_json(REPO_ROOT / "config/admission-policy.json")
        self.docs = admission_policy_audit.load_manifest_set(
            REPO_ROOT,
            list(self.config["target_manifests"]),
        )

    def test_current_manifests_and_policy_pass(self) -> None:
        report = admission_policy_audit.build_report(REPO_ROOT, self.config)

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["failed_count"])
        self.assertGreaterEqual(report["allowed_deployment_count"], 2)
        self.assertGreaterEqual(report["denied_fixture_count"], 8)

    def test_admission_denies_unpinned_image(self) -> None:
        fixture = admission_policy_audit.build_fixture(
            [doc for doc in self.docs if doc.get("kind") == "Deployment"],
            "unpinned_image",
        )

        decision = admission_policy_audit.evaluate_deployment(fixture, self.config)

        self.assertEqual("deny", decision["decision"])
        self.assertIn("digest_pinned_images", decision["failed_controls"])

    def test_admission_denies_privileged_container(self) -> None:
        fixture = admission_policy_audit.build_fixture(
            [doc for doc in self.docs if doc.get("kind") == "Deployment"],
            "privileged_container",
        )

        decision = admission_policy_audit.evaluate_deployment(fixture, self.config)

        self.assertEqual("deny", decision["decision"])
        self.assertIn("restricted_container_security", decision["failed_controls"])

    def test_policy_manifest_check_detects_missing_control(self) -> None:
        policy_docs = admission_policy_audit.load_yaml_documents(
            REPO_ROOT / self.config["policy_manifest"],
        )
        altered = copy.deepcopy(policy_docs)
        policy = next(doc for doc in altered if doc.get("kind") == "ValidatingAdmissionPolicy")
        policy["spec"]["validations"] = [
            validation
            for validation in policy["spec"]["validations"]
            if "readiness and liveness probes" not in validation.get("message", "")
        ]

        checks = admission_policy_audit.validate_policy_manifest(altered, self.config)
        by_name = {item["name"]: item["status"] for item in checks}

        self.assertEqual("fail", by_name["control_health_probes"])

    def test_writes_json_and_markdown(self) -> None:
        report = admission_policy_audit.build_report(REPO_ROOT, self.config)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            admission_policy_audit.write_json(report, output_dir)
            admission_policy_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "admission-policy-audit.json").exists())
            self.assertIn(
                "Admission Policy Audit",
                (output_dir / "admission-policy-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
