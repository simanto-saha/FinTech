from typing import Any, Dict, List, Optional

# In-memory registry of simulated failure injection rules
_FAILURE_RULES: List[Dict[str, Any]] = []


def set_simulated_failure(
    leg_index: Optional[int] = None,
    rail_id: Optional[str] = None,
    plan_id: Optional[int] = None,
    error_code: str = "SIMULATED_RAIL_TIMEOUT",
    error_message: str = "Simulated downstream rail partner failure/timeout.",
    once: bool = True,
) -> Dict[str, Any]:
    """
    Register an explicit simulated failure rule for multi-leg recovery testing (e.g. Task T5).
    """
    rule = {
        "leg_index": leg_index,
        "rail_id": rail_id,
        "plan_id": plan_id,
        "error_code": error_code,
        "error_message": error_message,
        "once": once,
        "triggered_count": 0,
    }
    _FAILURE_RULES.append(rule)
    return rule


def clear_simulated_failures() -> None:
    """Clear all active failure rules."""
    global _FAILURE_RULES
    _FAILURE_RULES = []


def list_simulated_failures() -> List[Dict[str, Any]]:
    """List current failure injection rules."""
    return list(_FAILURE_RULES)


def check_should_fail(
    leg_index: int,
    rail_id: Optional[str] = None,
    plan_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Check if the specified leg should fail based on active failure rules.
    If a matching rule is found and configured with once=True, it is consumed.
    """
    for rule in list(_FAILURE_RULES):
        match = True
        if rule.get("leg_index") is not None and rule["leg_index"] != leg_index:
            match = False
        if rule.get("rail_id") is not None and rail_id and rule["rail_id"] != rail_id:
            match = False
        if rule.get("plan_id") is not None and plan_id and rule["plan_id"] != plan_id:
            match = False

        if match:
            rule["triggered_count"] += 1
            failure_info = {
                "error_code": rule["error_code"],
                "error_message": rule["error_message"],
                "leg_index": leg_index,
                "rail_id": rail_id,
            }
            if rule.get("once"):
                _FAILURE_RULES.remove(rule)
            return failure_info

    return None

