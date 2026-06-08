from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import incident_response_drill


REPO_ROOT = Path(__file__).resolve().parents[1]


class IncidentResponseDrillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = incident_response_drill.load_json(REPO_ROOT / "config/incident-response-policy.json")
        self.alerting = incident_response_drill.load_json(REPO_ROOT / "docs/evidence/alerting-rules.json")
        self.runbooks = incident_response_drill.load_json(REPO_ROOT / "docs/evidence/incident-runbooks.json")
        self.incident_correlation = incident_response_drill.load_json(REPO_ROOT / "docs/evidence/incident-correlation.json")
        self.rollback_drill = incident_response_drill.load_json(REPO_ROOT / "docs/evidence/rollback-drill.json")
        self.post_incident_review = incident_response_drill.load_json(REPO_ROOT / "docs/evidence/post-incident-review.json")

    def build_report(
        self,
        *,
        alerting: dict | None = None,
        runbooks: dict | None = None,
        rollback_drill: dict | None = None,
        post_incident_review: dict | None = None,
    ) -> dict:
        return incident_response_drill.build_report(
            alerting=alerting or self.alerting,
            runbooks=runbooks or self.runbooks,
            incident_correlation=self.incident_correlation,
            rollback_drill=rollback_drill or self.rollback_drill,
            post_incident_review=post_incident_review or self.post_incident_review,
            policy=self.policy,
        )

    def test_current_incident_response_drill_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["response_count"])
        self.assertEqual(4, report["incident_response_count"])
        self.assertEqual(5, report["detected_fixture_count"])
        self.assertEqual(0, report["failed_count"])

    def test_detects_missing_runbook_owner(self) -> None:
        runbooks = copy.deepcopy(self.runbooks)
        for item in runbooks["runbooks"]:
            if item["scenario"] == "dependency_timeout":
                item["owner"] = ""

        report = self.build_report(runbooks=runbooks)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["owner_coverage"])

    def test_detects_slow_page_acknowledgement(self) -> None:
        rollback_drill = copy.deepcopy(self.rollback_drill)
        for drill in rollback_drill["drills"]:
            if drill["scenario"] == "rollout_regression":
                incident_response_drill.set_timeline_phase_minute(drill["timeline"], "acknowledge", 6)

        report = self.build_report(rollback_drill=rollback_drill)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["response_sla"])

    def test_detects_missing_post_incident_review(self) -> None:
        post_incident_review = copy.deepcopy(self.post_incident_review)
        post_incident_review["reviews"] = [
            item
            for item in post_incident_review["reviews"]
            if item["scenario"] != "collector_queue_pressure"
        ]

        report = self.build_report(post_incident_review=post_incident_review)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["incident_evidence_linkage"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            incident_response_drill.write_json(report, output_dir)
            incident_response_drill.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "incident-response-drill.json").exists())
            self.assertIn(
                "Incident Response Drill",
                (output_dir / "incident-response-drill.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
