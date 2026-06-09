from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import proof_packet_integrity_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProofPacketIntegrityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = proof_packet_integrity_audit.load_json(
            REPO_ROOT / "config/proof-packet-integrity-policy.json"
        )
        self.provenance = proof_packet_integrity_audit.load_json(
            REPO_ROOT / "docs/evidence/evidence-provenance.json"
        )

    def test_passes_current_provenance_manifest(self) -> None:
        report = proof_packet_integrity_audit.evaluate(
            REPO_ROOT,
            self.provenance,
            self.policy,
        )

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["manifest_entry_count"], 274)
        self.assertGreaterEqual(report["evidence_artifact_count"], 137)
        self.assertGreaterEqual(report["source_input_count"], 133)
        self.assertEqual(report["manifest_entry_count"], report["matched_digest_count"])
        self.assertEqual(6, report["detected_fixture_count"])

    def test_detects_source_digest_drift(self) -> None:
        provenance = copy.deepcopy(self.provenance)
        provenance["source_inputs"][0]["sha256"] = "0" * 64

        report = proof_packet_integrity_audit.evaluate(REPO_ROOT, provenance, self.policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["current_digest_match"])

    def test_detects_missing_artifact_path(self) -> None:
        provenance = copy.deepcopy(self.provenance)
        provenance["artifacts"][0]["path"] = "docs/evidence/not-present.json"

        report = proof_packet_integrity_audit.evaluate(REPO_ROOT, provenance, self.policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["current_digest_match"])

    def test_rejects_circular_release_artifact(self) -> None:
        provenance = copy.deepcopy(self.provenance)
        release_entry = copy.deepcopy(provenance["artifacts"][0])
        release_entry["path"] = "docs/evidence/release-readiness.json"
        provenance["artifacts"].append(release_entry)

        report = proof_packet_integrity_audit.evaluate(REPO_ROOT, provenance, self.policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["circular_artifact_boundary"])

    def test_rejects_absolute_manifest_path(self) -> None:
        provenance = copy.deepcopy(self.provenance)
        provenance["source_inputs"][0]["path"] = "/tmp/not-in-repo.py"

        report = proof_packet_integrity_audit.evaluate(REPO_ROOT, provenance, self.policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["path_safety_contract"])

    def test_writes_evidence(self) -> None:
        report = proof_packet_integrity_audit.evaluate(
            REPO_ROOT,
            self.provenance,
            self.policy,
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            proof_packet_integrity_audit.write_json(report, output_dir)
            proof_packet_integrity_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "proof-packet-integrity-audit.json").exists())
            self.assertIn(
                "Proof Packet Integrity Audit",
                (output_dir / "proof-packet-integrity-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
