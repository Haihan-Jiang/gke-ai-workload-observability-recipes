from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from demo import incident_replay, telemetry_redaction_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class TelemetryRedactionAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = telemetry_redaction_audit.load_json(REPO_ROOT / "config/telemetry-redaction-policy.json")
        self.summary = [incident_replay.summarize_scenario(item) for item in incident_replay.SCENARIOS]

    def write_payloads(self, payload_dir: Path) -> None:
        payloads = [
            (
                str(scenario["name"]),
                incident_replay.build_scenario_payload(scenario, 1_780_000_000_000_000_000 + index * 2_000_000_000),
            )
            for index, scenario in enumerate(incident_replay.SCENARIOS)
        ]
        incident_replay.write_payloads(payloads, payload_dir)

    def build_report(self, payload_dir: Path, policy: dict | None = None) -> dict:
        return telemetry_redaction_audit.build_report(
            summary=self.summary,
            payload_dir=payload_dir,
            policy=policy or self.policy,
        )

    def test_passes_safe_ai_metadata_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)

            report = self.build_report(payload_dir)

            self.assertEqual("pass", report["status"])
            self.assertEqual(5, report["payload_count"])
            self.assertEqual(0, report["redaction_violation_count"])

    def test_detects_raw_prompt_attribute_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            path = payload_dir / "baseline.otlp.json"
            payload = telemetry_redaction_audit.load_json(path)
            payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"].append(
                incident_replay.attribute("ai.prompt.text", "summarize the account")
            )
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            report = self.build_report(payload_dir)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["forbidden_attribute_keys"])
            self.assertGreater(report["redaction_violation_count"], 0)

    def test_detects_secret_like_attribute_value_without_echoing_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            path = payload_dir / "baseline.otlp.json"
            payload = telemetry_redaction_audit.load_json(path)
            payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"].append(
                incident_replay.attribute("debug.note", "Bearer super-secret-token")
            )
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            report = self.build_report(payload_dir)
            value_check = next(item for item in report["checks"] if item["name"] == "forbidden_attribute_values")
            violation = value_check["evidence"]["violations"][0]

            self.assertEqual("fail", report["status"])
            self.assertFalse(value_check["ok"])
            self.assertIn("value_sha256", violation)
            self.assertNotIn("super-secret-token", str(violation))

    def test_detects_missing_payload_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            (payload_dir / "collector_queue_pressure.otlp.json").unlink()

            report = self.build_report(payload_dir)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["payload_coverage"])

    def test_detects_unapproved_ai_attribute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp)
            self.write_payloads(payload_dir)
            policy = copy.deepcopy(self.policy)
            policy["approved_ai_metadata_attributes"] = ["ai.model"]

            report = self.build_report(payload_dir, policy=policy)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["approved_ai_metadata"])

    def test_writes_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload_dir = Path(tmp) / "payloads"
            output_dir = Path(tmp) / "evidence"
            self.write_payloads(payload_dir)

            report = self.build_report(payload_dir)
            output_dir.mkdir()
            telemetry_redaction_audit.write_json(report, output_dir)
            telemetry_redaction_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "telemetry-redaction-audit.json").exists())
            self.assertIn("Telemetry Redaction Audit", (output_dir / "telemetry-redaction-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
