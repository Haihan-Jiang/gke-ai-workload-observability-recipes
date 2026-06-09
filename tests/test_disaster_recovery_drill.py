from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from demo import disaster_recovery_drill


REPO_ROOT = Path(__file__).resolve().parents[1]


class DisasterRecoveryDrillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = disaster_recovery_drill.load_json(REPO_ROOT / "config/disaster-recovery-policy.json")

    def test_current_artifacts_restore_with_matching_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = disaster_recovery_drill.build_report(
                REPO_ROOT,
                self.policy,
                Path(tmp) / "restore",
            )

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["failed_count"])
        self.assertGreaterEqual(report["artifact_count"], 132)
        self.assertEqual(report["artifact_count"], report["restored_count"])
        self.assertEqual(report["artifact_count"], report["hash_match_count"])

    def test_detects_missing_critical_artifact(self) -> None:
        policy = copy.deepcopy(self.policy)
        missing = policy["artifact_groups"][0]["artifacts"][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            restore = Path(tmp) / "restore"
            for artifact in disaster_recovery_drill.flatten_artifacts(policy):
                source = REPO_ROOT / artifact["path"]
                target = root / artifact["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_file() and artifact["path"] != missing:
                    shutil.copy2(source, target)

            report = disaster_recovery_drill.build_report(root, policy, restore)
            checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["critical_artifacts_present"])

    def test_detects_rto_policy_violation(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["operator_step_minutes"] = 30
        with tempfile.TemporaryDirectory() as tmp:
            report = disaster_recovery_drill.build_report(
                REPO_ROOT,
                policy,
                Path(tmp) / "restore",
            )
            checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rto_budget"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            report = disaster_recovery_drill.build_report(
                REPO_ROOT,
                self.policy,
                Path(tmp) / "restore",
            )

            disaster_recovery_drill.write_json(report, output_dir)
            disaster_recovery_drill.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "disaster-recovery-drill.json").exists())
            self.assertIn(
                "Disaster Recovery Drill",
                (output_dir / "disaster-recovery-drill.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
