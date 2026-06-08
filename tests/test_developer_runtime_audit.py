from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from demo import developer_runtime_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class DeveloperRuntimeAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = developer_runtime_audit.load_json(REPO_ROOT / "config/developer-runtime-policy.json")

    def copy_repo_inputs(self, root: Path) -> None:
        for relative in self.policy["required_files"]:
            source = REPO_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_passes_current_runtime_contract(self) -> None:
        report = developer_runtime_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(4, report["present_file_count"])
        self.assertEqual(8, report["make_target_count"])
        self.assertEqual(8, report["detected_fixture_count"])

    def test_detects_missing_makefile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / "Makefile").unlink()

            report = developer_runtime_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["required_files"])

    def test_detects_wrong_python_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            (root / ".python-version").write_text("3.10\n", encoding="utf-8")

            report = developer_runtime_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["python_runtime_contract"])

    def test_detects_missing_ci_make_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            makefile = root / "Makefile"
            makefile.write_text(
                developer_runtime_audit.remove_make_target(
                    makefile.read_text(encoding="utf-8"),
                    "ci",
                ),
                encoding="utf-8",
            )

            report = developer_runtime_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["make_target_inventory"])

    def test_detects_validation_command_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            makefile = root / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "./scripts/validate.sh",
                    "echo skipped validation",
                ),
                encoding="utf-8",
            )

            report = developer_runtime_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["make_command_contract"])

    def test_detects_missing_no_pip_dependency_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            docs = root / "docs/developer-runtime.md"
            docs.write_text(
                docs.read_text(encoding="utf-8").replace("No pip dependencies", ""),
                encoding="utf-8",
            )

            report = developer_runtime_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["developer_runtime_docs"])

    def test_detects_missing_output_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.copy_repo_inputs(root)
            gitignore = root / ".gitignore"
            gitignore.write_text(
                gitignore.read_text(encoding="utf-8").replace("out/\n", ""),
                encoding="utf-8",
            )

            report = developer_runtime_audit.build_report(root, self.policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["output_boundary"])

    def test_writes_evidence(self) -> None:
        report = developer_runtime_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            developer_runtime_audit.write_json(report, output_dir)
            developer_runtime_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "developer-runtime-audit.json").exists())
            self.assertIn(
                "Developer Runtime Audit",
                (output_dir / "developer-runtime-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
