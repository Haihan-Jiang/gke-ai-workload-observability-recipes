from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import dependency_update_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class DependencyUpdateAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = dependency_update_audit.load_json(
            REPO_ROOT / "config/dependency-update-policy.json"
        )
        self.config = dependency_update_audit.load_yaml(REPO_ROOT / self.policy["config_path"])
        self.docs = dependency_update_audit.read_docs(REPO_ROOT, self.policy["documentation_paths"])
        self.release_source = (REPO_ROOT / "demo/release_readiness.py").read_text(encoding="utf-8")

    def report_for(
        self,
        *,
        config_exists: bool = True,
        config: dict | None = None,
        docs: dict[str, str] | None = None,
        release_source: str | None = None,
    ) -> dict:
        checks, metrics = dependency_update_audit.evaluate_inputs(
            config_exists=config_exists,
            config=config if config is not None else self.config,
            docs=docs if docs is not None else self.docs,
            release_source=release_source if release_source is not None else self.release_source,
            policy=self.policy,
        )
        fixtures = dependency_update_audit.evaluate_fixtures(
            config_exists=config_exists,
            config=config if config is not None else self.config,
            docs=docs if docs is not None else self.docs,
            release_source=release_source if release_source is not None else self.release_source,
            policy=self.policy,
        )
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            dependency_update_audit.check(
                "negative_fixture_coverage",
                detected_fixture_count >= self.policy["minimum_detected_fixtures"],
                {"detected_fixture_count": detected_fixture_count},
            )
        )
        failed_count = sum(1 for item in checks if not item["ok"])
        return {
            "status": "pass" if failed_count == 0 else "fail",
            **metrics,
            "detected_fixture_count": detected_fixture_count,
            "checks": checks,
        }

    def test_passes_current_dependency_update_policy(self) -> None:
        report = dependency_update_audit.build_report(
            REPO_ROOT,
            self.policy,
            release_readiness_source=Path("demo/release_readiness.py"),
        )

        self.assertEqual("pass", report["status"])
        self.assertEqual(1, report["config_file_count"])
        self.assertGreaterEqual(report["update_count"], 1)
        self.assertGreaterEqual(report["ecosystem_count"], 1)
        self.assertGreaterEqual(report["weekly_schedule_count"], 1)
        self.assertGreaterEqual(report["label_count"], 2)
        self.assertGreaterEqual(report["validation_term_count"], 8)
        self.assertGreaterEqual(report["release_control_count"], 6)
        self.assertEqual(7, report["detected_fixture_count"])

    def test_fixtures_detect_expected_contract_breaks(self) -> None:
        results = dependency_update_audit.evaluate_fixtures(
            config_exists=True,
            config=self.config,
            docs=self.docs,
            release_source=self.release_source,
            policy=self.policy,
        )

        self.assertEqual(7, len(results))
        self.assertTrue(all(item["detected"] for item in results))

    def test_detects_missing_config(self) -> None:
        report = self.report_for(config_exists=False, config={})
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["config_file_contract"])

    def test_detects_missing_required_ecosystem(self) -> None:
        config = copy.deepcopy(self.config)
        config["updates"] = []
        report = self.report_for(config=config)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["ecosystem_contract"])

    def test_detects_schedule_drift(self) -> None:
        config = copy.deepcopy(self.config)
        config["updates"][0]["schedule"]["interval"] = "monthly"
        report = self.report_for(config=config)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["schedule_contract"])

    def test_detects_missing_review_boundaries(self) -> None:
        config = copy.deepcopy(self.config)
        config["updates"][0]["labels"] = []
        config["updates"][0]["open-pull-requests-limit"] = 25
        report = self.report_for(config=config)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["review_boundary_contract"])

    def test_detects_missing_validation_linkage(self) -> None:
        docs = {path: text.replace("CI=true ./scripts/validate.sh", "") for path, text in self.docs.items()}
        report = self.report_for(docs=docs)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["validation_linkage"])

    def test_detects_missing_release_control_linkage(self) -> None:
        release_source = self.release_source.replace("proof_packet_integrity_audit", "")
        report = self.report_for(release_source=release_source)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["release_control_linkage"])

    def test_writes_evidence(self) -> None:
        report = dependency_update_audit.build_report(
            REPO_ROOT,
            self.policy,
            release_readiness_source=Path("demo/release_readiness.py"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            dependency_update_audit.write_json(report, output_dir)
            dependency_update_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "dependency-update-audit.json").exists())
            self.assertIn(
                "Dependency Update Audit",
                (output_dir / "dependency-update-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
