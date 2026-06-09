from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import public_claim_evidence_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class PublicClaimEvidenceAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = public_claim_evidence_audit.load_json(
            REPO_ROOT / "config/public-claim-evidence-policy.json"
        )
        self.surfaces = public_claim_evidence_audit.load_surfaces(REPO_ROOT, self.policy)
        self.evidence = public_claim_evidence_audit.load_evidence(REPO_ROOT, self.policy)
        self.release_source = (REPO_ROOT / "demo/release_readiness.py").read_text(encoding="utf-8")

    def report_for(
        self,
        surfaces: dict[str, str] | None = None,
        evidence: dict | None = None,
        release_source: str | None = None,
    ) -> dict:
        checks, metrics = public_claim_evidence_audit.evaluate_inputs(
            REPO_ROOT,
            self.policy,
            surfaces=surfaces or self.surfaces,
            evidence=evidence or self.evidence,
            release_source=release_source or self.release_source,
        )
        failed_count = sum(1 for item in checks if not item["ok"])
        return {
            "status": "pass" if failed_count == 0 else "fail",
            "checks": checks,
            **metrics,
        }

    def test_current_public_claim_evidence_passes(self) -> None:
        report = public_claim_evidence_audit.build_report(
            REPO_ROOT,
            self.policy,
            release_readiness_source=Path("demo/release_readiness.py"),
        )

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["claim_count"], 14)
        self.assertGreaterEqual(report["evidence_claim_count"], 14)
        self.assertGreaterEqual(report["release_check_count"], 14)
        self.assertEqual(0, report["forbidden_phrase_count"])
        self.assertEqual(6, report["detected_fixture_count"])

    def test_fixtures_detect_expected_contract_breaks(self) -> None:
        results = public_claim_evidence_audit.evaluate_fixtures(
            REPO_ROOT,
            self.policy,
            self.surfaces,
            self.evidence,
            self.release_source,
        )

        self.assertEqual(6, len(results))
        self.assertTrue(all(item["detected"] for item in results))

    def test_detects_missing_public_claim_text(self) -> None:
        fixture = self.policy["fixtures"][0]
        surfaces, evidence, release_source = public_claim_evidence_audit.apply_fixture(
            REPO_ROOT,
            self.policy,
            self.surfaces,
            self.evidence,
            self.release_source,
            fixture,
        )

        report = self.report_for(surfaces, evidence, release_source)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["claim_text_contract"])

    def test_detects_failed_evidence_status(self) -> None:
        fixture = self.policy["fixtures"][1]
        surfaces, evidence, release_source = public_claim_evidence_audit.apply_fixture(
            REPO_ROOT,
            self.policy,
            self.surfaces,
            self.evidence,
            self.release_source,
            fixture,
        )

        report = self.report_for(surfaces, evidence, release_source)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["evidence_status_contract"])

    def test_detects_low_evidence_metric(self) -> None:
        fixture = self.policy["fixtures"][2]
        surfaces, evidence, release_source = public_claim_evidence_audit.apply_fixture(
            REPO_ROOT,
            self.policy,
            self.surfaces,
            self.evidence,
            self.release_source,
            fixture,
        )

        report = self.report_for(surfaces, evidence, release_source)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["evidence_metric_contract"])

    def test_detects_missing_release_check(self) -> None:
        fixture = self.policy["fixtures"][3]
        surfaces, evidence, release_source = public_claim_evidence_audit.apply_fixture(
            REPO_ROOT,
            self.policy,
            self.surfaces,
            self.evidence,
            self.release_source,
            fixture,
        )

        report = self.report_for(surfaces, evidence, release_source)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["release_check_contract"])

    def test_detects_missing_boundary_statement(self) -> None:
        fixture = self.policy["fixtures"][4]
        surfaces, evidence, release_source = public_claim_evidence_audit.apply_fixture(
            REPO_ROOT,
            self.policy,
            self.surfaces,
            self.evidence,
            self.release_source,
            fixture,
        )

        report = self.report_for(surfaces, evidence, release_source)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["boundary_language_contract"])

    def test_detects_forbidden_public_claim(self) -> None:
        fixture = self.policy["fixtures"][5]
        surfaces, evidence, release_source = public_claim_evidence_audit.apply_fixture(
            REPO_ROOT,
            self.policy,
            self.surfaces,
            self.evidence,
            self.release_source,
            fixture,
        )

        report = self.report_for(surfaces, evidence, release_source)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["boundary_language_contract"])
        self.assertGreater(report["forbidden_phrase_count"], 0)

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = public_claim_evidence_audit.build_report(
            REPO_ROOT,
            self.policy,
            release_readiness_source=Path("demo/release_readiness.py"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            public_claim_evidence_audit.write_json(report, output_dir)
            public_claim_evidence_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "public-claim-evidence-audit.json").exists())
            self.assertIn(
                "Public Claim Evidence Audit",
                (output_dir / "public-claim-evidence-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
