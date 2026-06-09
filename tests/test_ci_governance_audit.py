from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import ci_governance_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class CIGovernanceAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ci_governance_audit.load_json(REPO_ROOT / "config/ci-governance-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        for relative in [self.policy["workflow_path"]]:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_hardened_ci_workflow(self) -> None:
        report = ci_governance_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(1, report["workflow_count"])
        self.assertEqual(1, report["job_count"])
        self.assertEqual(2, report["action_count"])
        self.assertEqual(2, report["hardened_action_count"])
        self.assertEqual(8, report["detected_fixture_count"])

    def test_detects_missing_top_level_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "permissions:\n  contents: read\n\n", ""
                ),
                encoding="utf-8",
            )

            report = ci_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["least_privilege_permissions"])

    def test_detects_node20_action_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "actions/checkout@v6", "actions/checkout@v4"
                ),
                encoding="utf-8",
            )

            report = ci_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["action_runtime_hygiene"])

    def test_detects_floating_action_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "actions/setup-python@v6", "actions/setup-python@main"
                ),
                encoding="utf-8",
            )

            report = ci_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["action_runtime_hygiene"])

    def test_detects_missing_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "concurrency:\n  group: ${{ github.workflow }}-${{ github.ref }}\n  cancel-in-progress: true\n\n",
                    "",
                ),
                encoding="utf-8",
            )

            report = ci_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["concurrency_cancellation"])

    def test_detects_missing_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace("    timeout-minutes: 15\n", ""),
                encoding="utf-8",
            )

            report = ci_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["job_execution_bounds"])

    def test_detects_validation_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "run: ./scripts/validate.sh", "run: echo skipped validation"
                ),
                encoding="utf-8",
            )

            report = ci_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["validation_contract"])

    def test_detects_forbidden_pull_request_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "  pull_request:\n", "  pull_request:\n  pull_request_target:\n"
                ),
                encoding="utf-8",
            )

            report = ci_governance_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["trigger_surface"])

    def test_writes_evidence(self) -> None:
        report = ci_governance_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            ci_governance_audit.write_json(report, output_dir)
            ci_governance_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "ci-governance-audit.json").exists())
            self.assertIn("CI Governance Audit", (output_dir / "ci-governance-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
