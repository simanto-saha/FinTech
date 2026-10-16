import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone as django_tz

from Agent import security
from Agent.models import Approval, AuditLog, Document, LedgerEntry, Plan, Session
from sandbox import compliance, corridors, fx, rails, universities


def tool_classify_user(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    user_type = args.get("user_type")
    from_c = args.get("from_country", "")
    to_c = args.get("to_country", "")
    purpose = args.get("purpose", "")

    corridor_code = ""
    if from_c and to_c:
        corridor_code = corridors.normalize_corridor_code(from_c, to_c)

    if session:
        if user_type:
            session.user_type = user_type
        if corridor_code:
            session.corridor = corridor_code
        session.save(update_fields=["user_type", "corridor", "updated_at"])

    return {
        "status": "classified",
        "user_type": user_type,
        "corridor": corridor_code,
        "purpose": purpose,
        "is_simulated": True,
    }


def tool_get_kyc_requirements(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    user_type = args.get("user_type", session.user_type if session else "student")
    corridor = args.get("corridor", session.corridor if session else "BD-CN")
    rule = corridors.get_corridor_rules(corridor) or {}
    requirements = rule.get("requires", ["student_visa", "admission_letter", "invoice"])
    return {
        "user_type": user_type,
        "corridor": corridor,
        "required_documents": requirements,
        "guidance": f"For {user_type} users in corridor {corridor}, please submit: {', '.join(requirements)}.",
    }


def tool_verify_document(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    doc_id = args.get("document_id")
    doc = Document.objects.filter(pk=doc_id, user=session.user).first()
    if not doc:
        return {"status": "not_found", "error": f"Document #{doc_id} not found."}

    doc.verified = True
    doc.save(update_fields=["verified", "updated_at"])
    return {
        "status": "verified",
        "document_id": doc.pk,
        "doc_type": doc.doc_type,
        "extracted": doc.extracted,
        "confidence": doc.confidence,
    }


def tool_run_compliance_checks(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    user_id = args.get("user_id", session.user_id)
    corridor = args.get("corridor", session.corridor)
    amount = args.get("amount")
    return compliance.run_all(user_id=user_id, amount=amount, corridor=corridor)


def tool_get_corridor_rules(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    corridor = args.get("corridor", session.corridor if session else "BD-CN")
    rule = corridors.get_corridor_rules(corridor)
    if not rule:
        return {"error": f"Corridor {corridor} is not currently supported."}
    return {
        "corridor": rule["code"],
        "from_country": rule["from_country"],
        "to_country": rule["to_country"],
        "from_currency": rule["from_ccy"],
        "to_currency": rule["to_ccy"],
        "daily_cap": f"{Decimal(str(rule['cap_daily'])):.2f}",
        "cap_currency": rule["cap_ccy"],
        "available_rails": rule["rails"],
        "required_checks": rule["requires"],
        "notes": rule.get("notes", ""),
    }


def tool_list_payment_rails(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    corridor = args.get("corridor", session.corridor if session else None)
    from_ccy = args.get("from_ccy")
    to_ccy = args.get("to_ccy")
    available = rails.list_rails(corridor=corridor, from_ccy=from_ccy, to_ccy=to_ccy)
    return {
        "corridor": corridor,
        "count": len(available),
        "rails": available,
    }


def tool_get_fx_quote(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    from_ccy = args.get("from_ccy")
    to_ccy = args.get("to_ccy")
    amount_from = args.get("amount_from")
    target_amount = args.get("target_amount")
    quote = fx.get_fx_quote(from_ccy, to_ccy, amount_from=amount_from, target_amount=target_amount)
    return {
        "from_currency": quote["from_currency"],
        "to_currency": quote["to_currency"],
        "rate": str(quote["rate"]),
        "amount_from": str(quote["amount_from"]) if quote["amount_from"] is not None else None,
        "target_amount": str(quote["target_amount"]) if quote["target_amount"] is not None else None,
        "is_simulated": True,
        "disclaimer": quote["disclaimer"],
    }


def tool_create_transfer_plan(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    corridor = args.get("corridor", session.corridor if session else "BD-CN")
    amount_from = args.get("amount_from")
    target_amount = args.get("target_amount")
    target_ccy = args.get("target_ccy")
    currency_from = args.get("currency_from")
    rail_pref = args.get("rail_preference", "cheapest")

    plan_data = rails.build_plan(
        corridor=corridor,
        amount_from=amount_from,
        currency_from=currency_from,
        target_amount=target_amount,
        target_ccy=target_ccy,
        rail_preference=rail_pref,
    )

    django_plan = Plan.objects.create(
        session=session,
        user=session.user,
        legs=plan_data["legs"],
        target_amount=plan_data["target_amount"],
        target_ccy=plan_data["target_ccy"],
        total_cost=plan_data["total_cost"],
        status=Plan.Status.DRAFT,
    )

    return {
        "plan_id": django_plan.id,
        "status": "draft",
        "corridor": plan_data["corridor"],
        "total_source_amount": str(plan_data["total_source_amount"]),
        "currency_from": plan_data["currency_from"],
        "target_amount": str(plan_data["target_amount"]),
        "target_ccy": plan_data["target_ccy"],
        "total_cost": str(plan_data["total_cost"]),
        "number_of_legs": plan_data["number_of_legs"],
        "legs": plan_data["legs"],
        "warnings": plan_data["warnings"],
        "requires_approval": False,
    }


def tool_request_human_approval(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    plan_id = args.get("plan_id")
    summary = args.get("summary", "")

    plan = Plan.objects.filter(pk=plan_id, user=session.user).first()
    if not plan:
        return {"error": f"Plan #{plan_id} not found or access denied."}

    plan.status = Plan.Status.PENDING
    plan.save(update_fields=["status", "updated_at"])

    ttl_seconds = getattr(settings, "APPROVAL_TTL_SECONDS", 300)
    expires_at = django_tz.now() + timedelta(seconds=ttl_seconds)

    approval = Approval.objects.create(
        plan=plan,
        user=session.user,
        status=Approval.Status.PENDING,
        expires_at=expires_at,
    )

    # Note: Approval token is NEVER sent to LLM.
    # It will only be presented to the user in the UI.
    return {
        "requires_approval": True,
        "plan_id": plan.id,
        "summary": summary or f"Confirm transfer of {plan.target_amount} {plan.target_ccy} (Total cost: {plan.total_cost})",
        "status": "pending_user_confirmation",
        "expires_in_seconds": ttl_seconds,
    }


def tool_execute_transfer_plan(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execution Gate per idea.md §15.
    This is the ONLY tool that moves money (in simulation).
    Enforces plan ownership, approved status, expiry, idempotency, and fresh compliance.
    """
    plan_id = args.get("plan_id")
    plan = Plan.objects.filter(pk=plan_id).first()
    if not plan:
        return {"status": "failed", "error": f"Plan #{plan_id} not found."}

    # 1. Verify plan.user == session.user
    if plan.user_id != session.user_id:
        return {"status": "failed", "error": "Access denied: plan does not belong to session user."}

    # 2. Verify plan.executed_at is None (idempotency check)
    if plan.executed_at is not None or plan.status == Plan.Status.EXECUTED:
        return {
            "status": "already_executed",
            "plan_id": plan.id,
            "executed_at": plan.executed_at.isoformat() if plan.executed_at else None,
        }

    # 3. Verify plan.status == 'approved'
    if plan.status != Plan.Status.APPROVED:
        return {"status": "failed", "error": f"Plan #{plan_id} is not approved (current status: {plan.status}). Explicit user approval is required."}

    # 4. Verify now - plan.approved_at <= 300s
    if plan.approved_at:
        age_seconds = (django_tz.now() - plan.approved_at).total_seconds()
        ttl_seconds = getattr(settings, "APPROVAL_TTL_SECONDS", 300)
        if age_seconds > ttl_seconds:
            plan.status = Plan.Status.FAILED
            plan.save(update_fields=["status", "updated_at"])
            return {"status": "failed", "error": "Approval token has expired. A fresh quote and approval are required."}

    # 5. Re-run compliance
    try:
        compliance.enforce_compliance(user_id=session.user_id, amount=plan.total_cost)
    except compliance.ComplianceCheckFailed as exc:
        plan.status = Plan.Status.FAILED
        plan.save(update_fields=["status", "updated_at"])
        return {"status": "failed", "error": f"Compliance check failed: {exc}"}

    # 6. Execute simulated transfer in sandbox
    idem_key = f"plan_{plan.id}"
    exec_res = rails.execute(plan, idempotency_key=idem_key, user=session.user)

    if exec_res.get("status") == "failed":
        plan.status = Plan.Status.FAILED
        plan.save(update_fields=["status", "updated_at"])
        return exec_res

    # 7. Update plan status
    plan.status = Plan.Status.EXECUTED
    plan.executed_at = django_tz.now()
    plan.save(update_fields=["status", "executed_at", "updated_at"])

    return {
        "status": "executed",
        "plan_id": plan.id,
        "receipt_id": exec_res.get("receipt_id"),
        "audit_hash": exec_res.get("audit_hash"),
        "target_amount": str(plan.target_amount),
        "target_ccy": plan.target_ccy,
        "legs": exec_res.get("legs", []),
        "is_simulated": True,
    }


def tool_get_transaction_status(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    plan_id = args.get("plan_id")
    tx_id = args.get("transaction_id")
    if plan_id:
        p = Plan.objects.filter(pk=plan_id, user=session.user).first()
        if p:
            return {"plan_id": p.id, "status": p.status, "target_amount": str(p.target_amount), "target_ccy": p.target_ccy, "executed_at": p.executed_at.isoformat() if p.executed_at else None}
    if tx_id:
        le = LedgerEntry.objects.filter(meta__reference=tx_id, user=session.user).first()
        if le:
            return {"transaction_id": tx_id, "status": le.status, "amount": str(le.amount), "currency": le.currency}
    return {"status": "not_found"}


def tool_get_balances(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": session.user_id,
        "balances": [
            {"currency": "BDT", "amount": "1500000.00"},
            {"currency": "CNY", "amount": "12500.00"},
            {"currency": "USD", "amount": "2500.00"},
            {"currency": "GBP", "amount": "800.00"},
        ],
        "is_simulated": True,
    }


def tool_create_budget(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    income = Decimal(str(args.get("monthly_income", 1000)))
    ccy = args.get("currency", "CNY").upper()
    tuition = (income * Decimal("0.40")).quantize(Decimal("0.01"))
    rent = (income * Decimal("0.30")).quantize(Decimal("0.01"))
    living = (income * Decimal("0.20")).quantize(Decimal("0.01"))
    savings = (income * Decimal("0.10")).quantize(Decimal("0.01"))

    # Day-to-day student living envelope breakdown (from living allowance)
    daily_spend = (living / Decimal("30")).quantize(Decimal("0.01"))
    groceries_weekly = (living * Decimal("0.45") / Decimal("4")).quantize(Decimal("0.01"))
    transit_weekly = (living * Decimal("0.25") / Decimal("4")).quantize(Decimal("0.01"))
    utilities_mobile_weekly = (living * Decimal("0.18") / Decimal("4")).quantize(Decimal("0.01"))
    contingency_weekly = (living * Decimal("0.12") / Decimal("4")).quantize(Decimal("0.01"))

    # FX Shock & Runway Stress Test
    baseline_runway_days = 90
    shock_5pct_runway = int(baseline_runway_days * 0.95)
    shock_10pct_runway = int(baseline_runway_days * 0.88)
    shock_15pct_runway = int(baseline_runway_days * 0.78)

    return {
        "monthly_income": str(income),
        "currency": ccy,
        "breakdown": {
            "tuition_allocation": str(tuition),
            "rent_utilities": str(rent),
            "food_transport": str(living),
            "emergency_savings": str(savings),
        },
        "daily_living_allowance": str(daily_spend),
        "weekly_envelopes": {
            "groceries": str(groceries_weekly),
            "transit": str(transit_weekly),
            "utilities_mobile": str(utilities_mobile_weekly),
            "contingency_buffer": str(contingency_weekly),
        },
        "fx_shock_test": {
            "baseline_runway_days": baseline_runway_days,
            "shock_5pct_runway_days": shock_5pct_runway,
            "shock_10pct_runway_days": shock_10pct_runway,
            "shock_15pct_runway_days": shock_15pct_runway,
            "recommended_rebalance": "Reduce dining out & non-essential leisure by 15% to safeguard rent and grocery minimums.",
        },
        "is_simulated": True,
    }


def tool_prepare_credit_application(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    dest = args.get("destination_country", "GB").upper()
    card_type = args.get("card_type", "student_credit_card")
    return {
        "destination_country": dest,
        "card_type": card_type,
        "recommended_options": [
            {"name": "Bank of China Great Wall International Student Card", "credit_limit": "5000 CNY", "security_deposit": "No", "annual_fee": "0"},
            {"name": "HSBC Premier Student Credit Card", "credit_limit": "1000 GBP", "security_deposit": "Optional", "annual_fee": "0"},
            {"name": "Barclays Forward Credit Card (Credit Builder)", "credit_limit": "500 GBP", "security_deposit": "No", "annual_fee": "0"},
        ],
        "prerequisites": ["Valid student visa", "Proof of enrollment", "University address"],
        "credit_building_tip": "Keep credit utilization below 30% and enable autopay to establish a positive credit score in your destination country.",
        "alternative_credit_score": 745,
        "score_grade": "Excellent Student Financial Record",
        "on_time_payment_streak": "100% on-time educational payment history",
        "verifiable_rental_reference": "Eligible for Fundora Verifiable Tenant Certificate to waive 6-12 month upfront landlord guarantees.",
        "is_simulated": True,
    }


def tool_lookup_university(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    res = universities.lookup_university(query)
    if not res:
        return {"found": False, "query": query, "message": f"University '{query}' not found in database or reference catalog."}
    return {
        "found": True,
        "slug": res["slug"],
        "name": res["name"],
        "country": res["country"],
        "payment_channels": res.get("payment_channels", []),
        "common_issues": res.get("common_issues", []),
        "support": res.get("support", {}),
    }


def tool_get_masked_field(session: Session, args: Dict[str, Any]) -> Dict[str, Any]:
    field = args.get("field", "")
    value = args.get("value", "")
    return security.get_masked_field(field, value)


# Dispatch table mapping tool names to functions
_TOOL_DISPATCH = {
    "classify_user": tool_classify_user,
    "get_kyc_requirements": tool_get_kyc_requirements,
    "verify_document": tool_verify_document,
    "run_compliance_checks": tool_run_compliance_checks,
    "get_corridor_rules": tool_get_corridor_rules,
    "list_payment_rails": tool_list_payment_rails,
    "get_fx_quote": tool_get_fx_quote,
    "create_transfer_plan": tool_create_transfer_plan,
    "request_human_approval": tool_request_human_approval,
    "execute_transfer_plan": tool_execute_transfer_plan,
    "get_transaction_status": tool_get_transaction_status,
    "get_balances": tool_get_balances,
    "create_budget": tool_create_budget,
    "prepare_credit_application": tool_prepare_credit_application,
    "lookup_university": tool_lookup_university,
    "get_masked_field": tool_get_masked_field,
}


def execute_tool(tool_name: str, arguments: Dict[str, Any], session: Session) -> Dict[str, Any]:
    """
    Validate schema and execute a tool within the deterministic sandbox/Django layer.
    Logs execution to AuditLog.
    """
    valid_args = security.validate_tool_call(tool_name, arguments)
    handler = _TOOL_DISPATCH.get(tool_name)
    if not handler:
        raise security.UnknownToolError(f"No execution handler registered for '{tool_name}'.")

    result = handler(session, valid_args)

    # Log tier 1 action to AuditLog
    if session:
        try:
            security.log_security_event(
                session=session,
                action=f"tool_call:{tool_name}",
                status="success" if not result.get("error") else "error",
                tier=Session.Tier.SUGGEST,
                meta={"args": valid_args, "result": result},
            )
        except Exception:
            pass

    return result
