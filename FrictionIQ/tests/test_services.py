"""
Tests for FrictionIQ Business Services: KPIs, Simulation, Workflow Trigger, Audit Logging.
"""
import unittest
from services.business import (
    AuditLogService, KPIService, SimulationService, WorkflowTriggerService
)

class TestBusinessServices(unittest.TestCase):
    def setUp(self):
        self.kpi_svc = KPIService()
        self.sim_svc = SimulationService()
        self.trigger_svc = WorkflowTriggerService()
        self.audit_svc = AuditLogService()

    def test_kpi_service(self):
        kpis = self.kpi_svc.get_kpis()
        self.assertIn("total_sessions", kpis)
        self.assertIn("conversion_rate", kpis)
        self.assertIn("revenue_at_risk", kpis)
        self.assertIn("revenue_recovered", kpis)
        self.assertGreater(kpis["total_sessions"], 0)

    def test_funnel_stages(self):
        stages = self.kpi_svc.get_funnel()
        self.assertIsInstance(stages, list)
        self.assertGreater(len(stages), 0)
        first_stage = stages[0]
        self.assertIn("stage", first_stage)
        self.assertIn("sessions", first_stage)
        self.assertIn("drop_off_rate", first_stage)

    def test_simulation_service_lift_and_roi(self):
        sim = self.sim_svc.simulate(
            intervention_type="targeted_incentive_10pct",
            audience_size=1000,
            baseline_conversion=3.0,
            incentive_pct=10.0,
            avg_order_value=100.0,
        )
        self.assertIn("expected_conversions", sim)
        self.assertIn("revenue_recovered", sim)
        self.assertIn("net_revenue", sim)
        self.assertIn("roi", sim)
        self.assertGreater(sim["revenue_recovered"], 0)
        self.assertGreater(sim["net_revenue"], 0)

    def test_workflow_trigger_and_audit(self):
        # Trigger intervention
        trigger_res = self.trigger_svc.trigger(
            session_id="session_svc_test",
            intervention_type="delivery_date_promise",
            channel="in_app_modal",
            message="Guaranteed delivery by Thursday 5 PM",
            metadata={"priority": "high"},
        )
        self.assertIn("trigger_id", trigger_res)
        self.assertEqual(trigger_res["status"], "sent")

        # Record and fetch audit log
        entry_id = self.audit_svc.record(
            actor="test_user",
            action="trigger_intervention",
            resource="session:session_svc_test",
            details={"channel": "in_app_modal"},
        )
        self.assertIsNotNone(entry_id)

        recent = self.audit_svc.get_recent(limit=10)
        self.assertGreater(len(recent), 0)
        top = recent[0]
        self.assertEqual(top["actor"], "test_user")
        self.assertEqual(top["action"], "trigger_intervention")

if __name__ == "__main__":
    unittest.main()
