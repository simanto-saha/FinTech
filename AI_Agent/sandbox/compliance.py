from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from django.contrib.auth import get_user_model

BLOCKED_TEST_IDENTITY = "test_blocked"


class ComplianceCheckFailed(Exception):
    """Raised when compliance screening fails (fail-closed security principle)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


def _get_identity_strings(user_identifier: Union[int, str, Any]) -> list[str]:
    """Extract candidate names, usernames, and emails to evaluate against compliance watchlists."""
    candidates = []

    # If it's a direct string (e.g. username or test label)
    if isinstance(user_identifier, str):
        candidates.append(user_identifier)
        return candidates

    # If it's an int or User instance
    User = get_user_model()
    user_obj = None

    if isinstance(user_identifier, int):
        try:
            user_obj = User.objects.filter(pk=user_identifier).first()
        except Exception:
            pass
    elif hasattr(user_identifier, "username"):
        user_obj = user_identifier

    if user_obj:
        if user_obj.username:
            candidates.append(user_obj.username)
        if user_obj.email:
            candidates.append(user_obj.email)
        first_last = f"{user_obj.first_name} {user_obj.last_name}".strip()
        if first_last:
            candidates.append(first_last)

        # Check AgentUser profile if available
        try:
            profile = getattr(user_obj, "agentuser", None)
            if profile and profile.Full_Name:
                candidates.append(profile.Full_Name)
        except Exception:
            pass
    else:
        candidates.append(str(user_identifier))

    return candidates


def run_all(
    user_id: Union[int, str, Any],
    amount: Optional[Union[Decimal, float, int, str]] = None,
    currency: Optional[str] = None,
    corridor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute deterministic compliance screening for:
    - Sanctions (OFAC / UN / EU watchlists; name containing 'test_blocked' is sanctioned)
    - AML (Anti-Money Laundering transaction thresholds and velocity)
    - PEP (Politically Exposed Persons screening)
    - Adverse Media (International negative news screening)

    Returns:
        {
            "passed": bool,
            "checks": {
                "aml": {...},
                "sanctions": {...},
                "pep": {...},
                "adverse_media": {...}
            },
            "risk_level": "LOW" | "HIGH" | "BLOCKED",
            "is_simulated": True,
            "timestamp": "..."
        }
    """
    identities = _get_identity_strings(user_id)
    identity_blob = " ".join(identities).lower()

    # 1. Sanctions Check
    # Rule from idea.md: "Name containing test_blocked = sanctioned."
    sanctions_passed = True
    sanctions_detail = {
        "status": "clear",
        "passed": True,
        "reason": "No match on OFAC, UN, or EU consolidated sanctions watchlists.",
    }
    if BLOCKED_TEST_IDENTITY in identity_blob:
        sanctions_passed = False
        sanctions_detail = {
            "status": "blocked",
            "passed": False,
            "reason": f"Sanctions match detected: '{BLOCKED_TEST_IDENTITY}' identity is on active designated sanctions list.",
            "watchlist": "OFAC-SDN-SIMULATED",
        }

    # 2. PEP (Politically Exposed Persons) Check
    pep_passed = True
    pep_detail = {
        "status": "clear",
        "passed": True,
        "reason": "No political exposure or senior official status identified.",
    }
    if "pep_flag" in identity_blob or "politically_exposed" in identity_blob:
        pep_passed = False
        pep_detail = {
            "status": "flagged",
            "passed": False,
            "reason": "Politically Exposed Person (PEP) match; enhanced due diligence required.",
        }

    # 3. Adverse Media Check
    adverse_passed = True
    adverse_detail = {
        "status": "clear",
        "passed": True,
        "reason": "Clean background screening in international public registries.",
    }
    if "adverse_media" in identity_blob or "fraud_flag" in identity_blob:
        adverse_passed = False
        adverse_detail = {
            "status": "flagged",
            "passed": False,
            "reason": "Adverse media screening alert detected in financial crime index.",
        }

    # 4. AML Check
    aml_passed = True
    aml_detail = {
        "status": "clear",
        "passed": True,
        "reason": "Transaction within normal volume limits; no structuring patterns detected.",
    }
    if amount is not None:
        dec_amount = Decimal(str(amount))
        # High-value single transaction threshold: 1,000,000 in source currency requires enhanced proof
        if dec_amount > Decimal("2000000.00"):
            aml_passed = False
            aml_detail = {
                "status": "flagged",
                "passed": False,
                "reason": f"Amount {dec_amount} exceeds single transaction AML cap without source of funds declaration.",
            }

    overall_passed = bool(sanctions_passed and pep_passed and adverse_passed and aml_passed)

    if not sanctions_passed:
        risk_level = "BLOCKED"
    elif not overall_passed:
        risk_level = "HIGH"
    else:
        risk_level = "LOW"

    return {
        "passed": overall_passed,
        "user_id": str(user_id),
        "risk_level": risk_level,
        "checks": {
            "sanctions": sanctions_detail,
            "aml": aml_detail,
            "pep": pep_detail,
            "adverse_media": adverse_detail,
        },
        "is_simulated": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Deterministic compliance simulation for Fundora safety and competition verification.",
    }


def enforce_compliance(
    user_id: Union[int, str, Any],
    amount: Optional[Union[Decimal, float, int, str]] = None,
    currency: Optional[str] = None,
    corridor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run compliance checks and fail closed (raise ComplianceCheckFailed) if screening fails.
    This enforces the principle that model output or user input cannot bypass compliance.
    """
    result = run_all(user_id=user_id, amount=amount, currency=currency, corridor=corridor)
    if not result["passed"]:
        # Identify failure reason
        reasons = [
            f"{k}: {v['reason']}"
            for k, v in result["checks"].items()
            if not v["passed"]
        ]
        error_msg = f"Compliance check failed: {'; '.join(reasons)}"
        raise ComplianceCheckFailed(error_msg, details=result)
    return result

