from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import evidence_provenance


REPO_ROOT = Path(__file__).resolve().parents[1]


class EvidenceProvenanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = evidence_provenance.load_json(REPO_ROOT / "config/evidence-provenance-policy.json")

    def test_builds_checksum_manifest_for_committed_evidence(self) -> None:
        report = evidence_provenance.build_provenance(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["artifact_count"], 133)
        self.assertGreaterEqual(report["source_input_count"], 129)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in report["artifacts"]))

    def test_detects_missing_required_artifact(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["required_artifacts"].append("docs/evidence/not-real.json")

        report = evidence_provenance.build_provenance(REPO_ROOT, policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["required_evidence_present"])

    def test_detects_release_readiness_cycle(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["required_artifacts"].append("docs/evidence/release-readiness.json")

        report = evidence_provenance.build_provenance(REPO_ROOT, policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["no_release_readiness_cycle"])

    def test_writes_evidence(self) -> None:
        report = evidence_provenance.build_provenance(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            evidence_provenance.write_json(report, output_dir)
            evidence_provenance.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "evidence-provenance.json").exists())
            self.assertIn("Evidence Provenance", (output_dir / "evidence-provenance.md").read_text())


if __name__ == "__main__":
    unittest.main()
