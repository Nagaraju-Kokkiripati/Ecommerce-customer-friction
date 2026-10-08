"""
Tests for FrictionIQ LangGraph multi-agent workflow, compliance rules, and guardrails.
"""
import unittest
from agents.agent_graph import run_agents

class TestAgentGraph(unittest.TestCase):
    def test_payment_failure_workflow(self):
        result = run_agents(
            session_id="session_pf_001",
            risk_score=92.5,
            features={
                "num_payment_fails": 3,
                "reached_checkout": 1,
                "reached_payment": 1,
                "payment_fail_rate": 1.0,
            },
            payment_context={"gateway": "Stripe", "failure_code": "card_declined"},
            feedback_text="My card got declined twice even though funds are available",
            customer_segment="VIP",
        )
        self.assertEqual(result["session_id"], "session_pf_001")
        self.assertIn("root_causes", result)
        self.assertGreater(len(result["root_causes"]), 0)
        top_cause = result["root_causes"][0]
        self.assertEqual(top_cause["cause"], "payment_failure")
        self.assertIn("recommended_interventions", result)
        self.assertTrue(result["compliance_approved"])

    def test_delivery_uncertainty_workflow(self):
        result = run_agents(
            session_id="session_del_002",
            risk_score=78.0,
            features={
                "has_delivery_check": 1,
                "num_payment_fails": 0,
                "exited_at_checkout": 1,
            },
            feedback_text="Could not tell when it would arrive before buying",
            customer_segment="New Customers",
        )
        self.assertEqual(result["session_id"], "session_del_002")
        causes = [rc["cause"] for rc in result["root_causes"]]
        self.assertTrue(any("delivery" in c for c in causes))

    def test_compliance_discount_cap(self):
        """Ensures that no agent recommends an incentive higher than company discount cap (e.g., 20%)."""
        result = run_agents(
            session_id="session_disc_003",
            risk_score=88.0,
            features={"num_cart_removes": 2, "num_compares": 5},
            customer_segment="Returning",
        )
        for rec in result.get("recommended_interventions", []):
            rec_type = rec.get("type", "")
            # Verify no illegal high discount codes
            self.assertNotIn("50pct", rec_type)
            self.assertNotIn("30pct", rec_type)
        self.assertTrue(result["compliance_approved"])

if __name__ == "__main__":
    unittest.main()
