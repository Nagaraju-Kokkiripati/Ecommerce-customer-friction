import json
from typing import Dict, Any, List, TypedDict
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    session_id: str
    risk_score: float
    features: Dict[str, Any]
    feedback_text: str
    root_cause: str
    confidence: float
    recommended_intervention: str
    compliance_approved: bool
    final_decision: str

def journey_analyst(state: AgentState):
    """Analyzes the session signals."""
    print(f"[Journey Analyst] Analyzing session {state['session_id']}")
    features = state.get('features', {})
    
    # Heuristic based on features (in a real app, this would use LLM)
    if features.get('payment_fail', 0) > 0:
        cause = "payment_failure"
    elif features.get('compare', 0) > 2:
        cause = "unclear_product_info"
    elif features.get('address_entry', 0) > 0 and features.get('checkout_start', 0) > 0 and features.get('payment_attempt', 0) == 0:
        cause = "delivery_uncertainty_or_price_shock"
    else:
        cause = "unknown_friction"
        
    return {"root_cause": cause, "confidence": 0.85}

def root_cause_agent(state: AgentState):
    """Fuses behavioral and feedback evidence to finalize root cause."""
    print(f"[Root Cause Agent] Refining cause: {state.get('root_cause')}")
    # Simulate LLM fusion
    cause = state.get('root_cause')
    if state.get('feedback_text'):
        if "delivery" in state['feedback_text'].lower():
            cause = "delivery_uncertainty"
    return {"root_cause": cause, "confidence": 0.9}

def recovery_strategist(state: AgentState):
    """Recommends an intervention."""
    print(f"[Recovery Strategist] Planning intervention for {state.get('root_cause')}")
    cause = state.get('root_cause')
    if cause == "payment_failure":
        intervention = "offer_alternate_payment"
    elif cause == "unclear_product_info":
        intervention = "add_size_fit_guidance"
    elif cause == "delivery_uncertainty":
        intervention = "show_delivery_promise"
    else:
        intervention = "targeted_incentive_10_percent"
        
    return {"recommended_intervention": intervention}

def critic_agent(state: AgentState):
    """Checks for compliance (e.g., discount caps)."""
    print(f"[Critic Agent] Checking compliance for {state.get('recommended_intervention')}")
    intervention = state.get('recommended_intervention')
    
    approved = True
    if "50_percent" in intervention:
        approved = False # Exceeds cap
        
    decision = "APPROVED" if approved else "REJECTED"
    return {"compliance_approved": approved, "final_decision": decision}

def build_graph():
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("analyst", journey_analyst)
    workflow.add_node("root_cause", root_cause_agent)
    workflow.add_node("strategist", recovery_strategist)
    workflow.add_node("critic", critic_agent)
    
    # Add edges
    workflow.set_entry_point("analyst")
    workflow.add_edge("analyst", "root_cause")
    workflow.add_edge("root_cause", "strategist")
    workflow.add_edge("strategist", "critic")
    workflow.add_edge("critic", END)
    
    return workflow.compile()

if __name__ == "__main__":
    graph = build_graph()
    test_state = {
        "session_id": "test_123",
        "risk_score": 88.5,
        "features": {"payment_fail": 2},
        "feedback_text": ""
    }
    result = graph.invoke(test_state)
    print("\n--- Final Graph State ---")
    print(json.dumps(result, indent=2))
