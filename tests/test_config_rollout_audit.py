from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import config_rollout_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ConfigRolloutAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = config_rollout_audit.load_json(REPO_ROOT / "config/config-rollout-policy.json")
        self.docs = config_rollout_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = config_rollout_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return config_rollout_audit.evaluate_documents(docs, self.policy)

    def test_current_config_rollout_audit_passes(self) -> None:
        report = config_rollout_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(1, report["config_map_count"])
        self.assertEqual(1, report["deployment_count"])
        self.assertEqual(1, report["checksum_annotation_count"])
        self.assertEqual(1, report["read_only_config_mount_count"])
        self.assertEqual(0, report["secret_marker_count"])
        self.assertEqual(10, report["detected_fixture_count"])

    def test_detects_missing_config_map(self) -> None:
        report = self.mutated_report("missing_config_map")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["config_map_schema"])

    def test_detects_missing_config_key(self) -> None:
        report = self.mutated_report("missing_config_key")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["config_map_schema"])

    def test_detects_missing_checksum_annotation(self) -> None:
        report = self.mutated_report("missing_checksum_annotation")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["checksum_rollout_binding"])

    def test_detects_stale_checksum_annotation(self) -> None:
        report = self.mutated_report("stale_checksum_annotation")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["checksum_rollout_binding"])

    def test_detects_config_changed_without_checksum(self) -> None:
        report = self.mutated_report("config_changed_without_checksum")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["checksum_rollout_binding"])

    def test_detects_writable_config_mount(self) -> None:
        report = self.mutated_report("writable_config_mount")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["config_volume_mount_safety"])

    def test_detects_wrong_config_arg(self) -> None:
        report = self.mutated_report("wrong_config_arg")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["config_path_alignment"])

    def test_detects_inline_secret_literal(self) -> None:
        report = self.mutated_report("inline_secret_literal")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["config_secret_hygiene"])

    def test_detects_missing_config_map_owner_label(self) -> None:
        report = self.mutated_report("missing_config_map_owner_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["config_label_governance"])

    def test_detects_missing_deployment_owner_label(self) -> None:
        report = self.mutated_report("missing_deployment_owner_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["config_label_governance"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = config_rollout_audit.build_report(self.docs, self.policy)

            config_rollout_audit.write_json(report, output_dir)
            config_rollout_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "config-rollout-audit.json").exists())
            self.assertIn(
                "Config Rollout Audit",
                (output_dir / "config-rollout-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
