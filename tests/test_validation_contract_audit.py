from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import validation_contract_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ValidationContractAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = validation_contract_audit.load_json(
            REPO_ROOT / "config/validation-contract-policy.json"
        )
        self.inputs = {
            "generate": (REPO_ROOT / "scripts/generate-evidence.sh").read_text(encoding="utf-8"),
            "validate": (REPO_ROOT / "scripts/validate.sh").read_text(encoding="utf-8"),
            "release_readiness": (REPO_ROOT / "demo/release_readiness.py").read_text(encoding="utf-8"),
        }

    def test_current_validation_contract_passes(self) -> None:
        report = validation_contract_audit.build_report(
            REPO_ROOT,
            self.policy,
            generate_script=Path("scripts/generate-evidence.sh"),
            validate_script=Path("scripts/validate.sh"),
            release_readiness_source=Path("demo/release_readiness.py"),
        )

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["py_compile_script_count"], 65)
        self.assertGreaterEqual(report["generation_script_count"], 63)
        self.assertGreaterEqual(report["direct_validation_script_count"], 62)
        self.assertGreaterEqual(report["policy_json_count"], 58)
        self.assertGreaterEqual(report["committed_json_count"], 73)
        self.assertGreaterEqual(report["release_argument_count"], 62)
        self.assertEqual(6, report["detected_fixture_count"])

    def test_fixtures_detect_expected_contract_breaks(self) -> None:
        results = validation_contract_audit.evaluate_fixtures(
            REPO_ROOT,
            self.policy,
            self.inputs,
        )

        self.assertEqual(6, len(results))
        self.assertTrue(all(item["detected"] for item in results))

    def test_detects_missing_py_compile_script(self) -> None:
        fixture = self.policy["fixtures"][0]
        mutated = validation_contract_audit.apply_fixture(self.inputs, fixture)

        checks, _ = validation_contract_audit.evaluate_inputs(REPO_ROOT, self.policy, mutated)
        by_name = {item["name"]: item["ok"] for item in checks}

        self.assertFalse(by_name["py_compile_contract"])

    def test_detects_missing_direct_validation_script(self) -> None:
        fixture = self.policy["fixtures"][1]
        mutated = validation_contract_audit.apply_fixture(self.inputs, fixture)

        checks, _ = validation_contract_audit.evaluate_inputs(REPO_ROOT, self.policy, mutated)
        by_name = {item["name"]: item["ok"] for item in checks}

        self.assertFalse(by_name["generation_validation_contract"])

    def test_detects_missing_config_json_tool(self) -> None:
        fixture = self.policy["fixtures"][2]
        mutated = validation_contract_audit.apply_fixture(self.inputs, fixture)

        checks, _ = validation_contract_audit.evaluate_inputs(REPO_ROOT, self.policy, mutated)
        by_name = {item["name"]: item["ok"] for item in checks}

        self.assertFalse(by_name["policy_json_contract"])

    def test_detects_missing_committed_json_tool(self) -> None:
        fixture = self.policy["fixtures"][3]
        mutated = validation_contract_audit.apply_fixture(self.inputs, fixture)

        checks, _ = validation_contract_audit.evaluate_inputs(REPO_ROOT, self.policy, mutated)
        by_name = {item["name"]: item["ok"] for item in checks}

        self.assertFalse(by_name["committed_json_contract"])

    def test_detects_missing_release_readiness_arg(self) -> None:
        fixture = self.policy["fixtures"][4]
        mutated = validation_contract_audit.apply_fixture(self.inputs, fixture)

        checks, _ = validation_contract_audit.evaluate_inputs(REPO_ROOT, self.policy, mutated)
        by_name = {item["name"]: item["ok"] for item in checks}

        self.assertFalse(by_name["release_readiness_argument_contract"])

    def test_detects_missing_required_validate_command(self) -> None:
        fixture = self.policy["fixtures"][5]
        mutated = validation_contract_audit.apply_fixture(self.inputs, fixture)

        checks, _ = validation_contract_audit.evaluate_inputs(REPO_ROOT, self.policy, mutated)
        by_name = {item["name"]: item["ok"] for item in checks}

        self.assertFalse(by_name["required_command_contract"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = validation_contract_audit.build_report(
            REPO_ROOT,
            self.policy,
            generate_script=Path("scripts/generate-evidence.sh"),
            validate_script=Path("scripts/validate.sh"),
            release_readiness_source=Path("demo/release_readiness.py"),
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            validation_contract_audit.write_json(report, output_dir)
            validation_contract_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "validation-contract-audit.json").exists())
            self.assertIn(
                "Validation Contract Audit",
                (output_dir / "validation-contract-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
