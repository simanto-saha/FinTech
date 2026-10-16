import hashlib
import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union

from . import corridors
from . import fx
from . import failures

# In-memory execution store for offline testing idempotency tracking
_EXECUTED_KEYS_CACHE: Dict[str, Dict[str, Any]] = {}


class RailDefinition:
    def __init__(
        self,
        rail_id: str,
        name: str,
        supported_corridors: List[str],
        source_currencies: List[str],
        target_currencies: List[str],
        fee_pct: Decimal,
        fixed_fee: Decimal,
        min_fee: Decimal,
        max_per_txn: Decimal,
        estimated_speed: str,
        compliance_level: str = "standard",
        description: str = "",
    ):
        self.rail_id = rail_id
        self.name = name
        self.supported_corridors = supported_corridors
        self.source_currencies = [c.upper() for c in source_currencies]
        self.target_currencies = [c.upper() for c in target_currencies]
        self.fee_pct = Decimal(str(fee_pct))
        self.fixed_fee = Decimal(str(fixed_fee))
        self.min_fee = Decimal(str(min_fee))
        self.max_per_txn = Decimal(str(max_per_txn))
        self.estimated_speed = estimated_speed
        self.compliance_level = compliance_level
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rail_id": self.rail_id,
            "name": self.name,
            "supported_corridors": self.supported_corridors,
            "source_currencies": self.source_currencies,
            "target_currencies": self.target_currencies,
            "fee_pct": float(self.fee_pct),
            "fixed_fee": float(self.fixed_fee),
            "min_fee": float(self.min_fee),
            "max_per_txn": float(self.max_per_txn),
            "estimated_speed": self.estimated_speed,
            "compliance_level": self.compliance_level,
            "description": self.description,
            "is_simulated": True,
        }


# Reference Rails Catalog
_RAILS_CATALOG: Dict[str, RailDefinition] = {
    # BD-CN rails
    "bdt_bank_wire": RailDefinition(
        rail_id="bdt_bank_wire",
        name="Bangladesh Bank SWIFT Education Wire",
        supported_corridors=["BD-CN", "BD-GB"],
        source_currencies=["BDT"],
        target_currencies=["CNY", "GBP", "USD"],
        fee_pct=Decimal("0.005"),
        fixed_fee=Decimal("500.00"),
        min_fee=Decimal("500.00"),
        max_per_txn=Decimal("500000.00"),
        estimated_speed="2-3 business days",
        compliance_level="standard",
        description="Direct central bank approved education wire transfer.",
    ),
    "alipay_crossborder": RailDefinition(
        rail_id="alipay_crossborder",
        name="Alipay Cross-Border Tuition Rail",
        supported_corridors=["BD-CN"],
        source_currencies=["BDT"],
        target_currencies=["CNY"],
        fee_pct=Decimal("0.008"),
        fixed_fee=Decimal("300.00"),
        min_fee=Decimal("300.00"),
        max_per_txn=Decimal("400000.00"),
        estimated_speed="Instant - 2 hours",
        compliance_level="enhanced",
        description="Real-time educational remittance directly to Chinese university accounts.",
    ),
    "unionpay_intl": RailDefinition(
        rail_id="unionpay_intl",
        name="UnionPay International Direct",
        supported_corridors=["BD-CN"],
        source_currencies=["BDT"],
        target_currencies=["CNY"],
        fee_pct=Decimal("0.006"),
        fixed_fee=Decimal("400.00"),
        min_fee=Decimal("400.00"),
        max_per_txn=Decimal("500000.00"),
        estimated_speed="1 business day",
        compliance_level="enhanced",
        description="UnionPay international cross-border settlement rail.",
    ),
    # IN-GB rails
    "swift_wire": RailDefinition(
        rail_id="swift_wire",
        name="SWIFT Commercial Banking Wire",
        supported_corridors=["IN-GB", "BD-GB"],
        source_currencies=["INR", "BDT"],
        target_currencies=["GBP", "USD", "EUR"],
        fee_pct=Decimal("0.012"),
        fixed_fee=Decimal("1500.00"),
        min_fee=Decimal("1500.00"),
        max_per_txn=Decimal("700000.00"),
        estimated_speed="2-4 business days",
        compliance_level="standard",
        description="Standard commercial banking correspondent wire.",
    ),
    "wise_transfer": RailDefinition(
        rail_id="wise_transfer",
        name="Wise Multi-Currency Direct Transfer",
        supported_corridors=["IN-GB", "PH-AE"],
        source_currencies=["INR", "PHP"],
        target_currencies=["GBP", "AED", "SGD", "EUR"],
        fee_pct=Decimal("0.006"),
        fixed_fee=Decimal("450.00"),
        min_fee=Decimal("450.00"),
        max_per_txn=Decimal("500000.00"),
        estimated_speed="Instant - 1 day",
        compliance_level="enhanced",
        description="Low-fee mid-market digital settlement rail.",
    ),
    "flywire_edu": RailDefinition(
        rail_id="flywire_edu",
        name="Flywire Global Education Payment Rail",
        supported_corridors=["IN-GB", "BD-CN"],
        source_currencies=["INR", "BDT"],
        target_currencies=["GBP", "CNY", "SGD", "AUD"],
        fee_pct=Decimal("0.007"),
        fixed_fee=Decimal("600.00"),
        min_fee=Decimal("600.00"),
        max_per_txn=Decimal("700000.00"),
        estimated_speed="1-2 business days",
        compliance_level="enhanced",
        description="Specialized tuition payment network with tracking ID.",
    ),
    # PH-AE rails
    "direct_remit": RailDefinition(
        rail_id="direct_remit",
        name="DirectRemit OFW Express",
        supported_corridors=["PH-AE"],
        source_currencies=["PHP"],
        target_currencies=["AED"],
        fee_pct=Decimal("0.008"),
        fixed_fee=Decimal("150.00"),
        min_fee=Decimal("150.00"),
        max_per_txn=Decimal("250000.00"),
        estimated_speed="Same day",
        compliance_level="standard",
        description="Designated Overseas Filipino Worker corridor channel.",
    ),
    "instapay_intl": RailDefinition(
        rail_id="instapay_intl",
        name="InstaPay Cross-Border Network",
        supported_corridors=["PH-AE"],
        source_currencies=["PHP"],
        target_currencies=["AED"],
        fee_pct=Decimal("0.010"),
        fixed_fee=Decimal("80.00"),
        min_fee=Decimal("80.00"),
        max_per_txn=Decimal("50000.00"),
        estimated_speed="Instant",
        compliance_level="enhanced",
        description="Real-time retail remittance with immediate SMS notification.",
    ),
    "exchange_house": RailDefinition(
        rail_id="exchange_house",
        name="Al Ansari / UAE Exchange Partner Rail",
        supported_corridors=["PH-AE"],
        source_currencies=["PHP"],
        target_currencies=["AED"],
        fee_pct=Decimal("0.012"),
        fixed_fee=Decimal("200.00"),
        min_fee=Decimal("200.00"),
        max_per_txn=Decimal("250000.00"),
        estimated_speed="1-2 business days",
        compliance_level="standard",
        description="Over-the-counter cash pickup and bank account deposit rail.",
    ),
}


def list_rails(
    corridor: Optional[str] = None,
    from_ccy: Optional[str] = None,
    to_ccy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List available simulated rails, optionally filtered by corridor and currencies."""
    results = []
    norm_corridor = corridors.normalize_corridor_code(corridor) if corridor else None

    for rail in _RAILS_CATALOG.values():
        if norm_corridor and norm_corridor not in rail.supported_corridors:
            continue
        if from_ccy and from_ccy.upper() not in rail.source_currencies:
            continue
        if to_ccy and to_ccy.upper() not in rail.target_currencies:
            continue
        results.append(rail.to_dict())

    return results


def get_rail(rail_id: str) -> Optional[RailDefinition]:
    """Retrieve rail definition by ID."""
    return _RAILS_CATALOG.get(rail_id)


def quote_cost(
    rail_id: str,
    amount_from: Decimal | float | int | str,
    from_ccy: str,
    to_ccy: str,
) -> Dict[str, Any]:
    """Calculate exact fees and converted amount for a specific rail."""
    rail = get_rail(rail_id)
    if not rail:
        raise ValueError(f"Unknown rail: {rail_id}")

    amt = Decimal(str(amount_from))
    rate = fx.get_base_rate(from_ccy, to_ccy)

    variable_fee = amt * rail.fee_pct
    fixed_fee = rail.fixed_fee
    total_fee_source = max(variable_fee + fixed_fee, rail.min_fee)
    total_fee_source = fx.round_amount(total_fee_source, from_ccy)

    # Net target delivered
    raw_target = amt * rate
    target_delivered = fx.round_amount(raw_target, to_ccy)
    total_cost_source = amt + total_fee_source

    return {
        "rail_id": rail.rail_id,
        "rail_name": rail.name,
        "amount_from": amt,
        "currency_from": from_ccy.upper(),
        "exchange_rate": rate,
        "target_amount": target_delivered,
        "currency_to": to_ccy.upper(),
        "fee_breakdown": {
            "variable_fee": fx.round_amount(variable_fee, from_ccy),
            "fixed_fee": fx.round_amount(fixed_fee, from_ccy),
            "total_fee": total_fee_source,
            "currency": from_ccy.upper(),
        },
        "total_cost_source": total_cost_source,
        "estimated_speed": rail.estimated_speed,
        "compliance_level": rail.compliance_level,
        "is_simulated": True,
    }


def build_plan(
    corridor: str,
    amount_from: Optional[Union[Decimal, float, int, str]] = None,
    currency_from: Optional[str] = None,
    target_amount: Optional[Union[Decimal, float, int, str]] = None,
    target_ccy: Optional[str] = None,
    rail_preference: str = "cheapest",
) -> Dict[str, Any]:
    """
    Construct a compliant transfer plan.
    Enforces corridor daily caps, automatic multi-leg splitting, and cost optimization.
    """
    corridor_rules = corridors.get_corridor_rules(corridor)
    if not corridor_rules:
        raise ValueError(f"Unsupported corridor: {corridor}")

    src_ccy = (currency_from or corridor_rules["from_ccy"]).upper()
    dst_ccy = (target_ccy or corridor_rules["to_ccy"]).upper()

    rate = fx.get_base_rate(src_ccy, dst_ccy)

    # Resolve total amounts
    if target_amount is not None:
        total_target = Decimal(str(target_amount))
        # Total source amount required
        total_source = fx.round_amount(total_target / rate, src_ccy)
    elif amount_from is not None:
        total_source = Decimal(str(amount_from))
        total_target = fx.round_amount(total_source * rate, dst_ccy)
    else:
        raise ValueError("Must provide either amount_from or target_amount")

    # Check corridor daily cap
    cap_info = corridors.check_corridor_cap(corridor, total_source, src_ccy)
    cap = Decimal(str(cap_info["cap_daily"]))
    requires_split = cap_info["requires_split"]

    # Select candidate rails for this corridor
    available_rails = list_rails(corridor=corridor, from_ccy=src_ccy, to_ccy=dst_ccy)
    if not available_rails:
        raise ValueError(f"No available rails for corridor {corridor} ({src_ccy} -> {dst_ccy})")

    # If user specified a rail by name, try to use it
    selected_rail = None
    if rail_preference not in {"cheapest", "fastest"}:
        for r in available_rails:
            if r["rail_id"] == rail_preference:
                selected_rail = r
                break

    if not selected_rail:
        if rail_preference == "fastest":
            # Sort by speed
            selected_rail = min(available_rails, key=lambda r: "instant" not in r["estimated_speed"].lower())
        else:
            # Default to cheapest (lowest fee_pct)
            selected_rail = min(available_rails, key=lambda r: r["fee_pct"])

    selected_rail_def = get_rail(selected_rail["rail_id"])
    effective_cap = min(cap, selected_rail_def.max_per_txn)

    # Calculate leg amounts
    legs = []
    if total_source > effective_cap:
        # Multi-leg split required
        from math import ceil
        num_legs = int(ceil(total_source / effective_cap))
        leg_source_base = fx.round_amount(total_source / Decimal(str(num_legs)), src_ccy)
        remaining_source = total_source
        remaining_target = total_target

        for i in range(num_legs):
            is_last = (i == num_legs - 1)
            leg_src = remaining_source if is_last else leg_source_base
            leg_tgt = remaining_target if is_last else fx.round_amount(leg_src * rate, dst_ccy)

            remaining_source -= leg_src
            remaining_target -= leg_tgt

            leg_quote = quote_cost(selected_rail["rail_id"], leg_src, src_ccy, dst_ccy)
            legs.append({
                "leg_index": i,
                "rail_id": selected_rail["rail_id"],
                "rail_name": selected_rail["name"],
                "amount_from": str(leg_src),
                "currency_from": src_ccy,
                "target_amount": str(leg_tgt),
                "target_ccy": dst_ccy,
                "exchange_rate": str(rate),
                "fee": str(leg_quote["fee_breakdown"]["total_fee"]),
                "estimated_speed": selected_rail["estimated_speed"],
                "status": "planned",
            })
    else:
        # Single leg
        leg_quote = quote_cost(selected_rail["rail_id"], total_source, src_ccy, dst_ccy)
        legs.append({
            "leg_index": 0,
            "rail_id": selected_rail["rail_id"],
            "rail_name": selected_rail["name"],
            "amount_from": str(total_source),
            "currency_from": src_ccy,
            "target_amount": str(total_target),
            "target_ccy": dst_ccy,
            "exchange_rate": str(rate),
            "fee": str(leg_quote["fee_breakdown"]["total_fee"]),
            "estimated_speed": selected_rail["estimated_speed"],
            "status": "planned",
        })

    total_fee = sum((Decimal(str(leg["fee"])) for leg in legs), Decimal("0"))
    total_cost = total_source + total_fee

    return {
        "corridor": corridor_rules["code"],
        "target_amount": total_target,
        "target_ccy": dst_ccy,
        "total_source_amount": total_source,
        "currency_from": src_ccy,
        "total_cost": total_cost,
        "total_fee": total_fee,
        "exchange_rate": rate,
        "requires_split": len(legs) > 1,
        "number_of_legs": len(legs),
        "legs": legs,
        "selected_rail": selected_rail,
        "corridor_daily_cap": cap,
        "warnings": [
            f"Transfer amount {total_source} {src_ccy} exceeds single transaction cap {effective_cap} {src_ccy}; split into {len(legs)} compliant legs."
        ] if len(legs) > 1 else [],
        "is_simulated": True,
    }


def clear_execution_cache() -> None:
    """Clear in-memory idempotency cache (useful between isolated test runs)."""
    global _EXECUTED_KEYS_CACHE
    _EXECUTED_KEYS_CACHE = {}


def _execute_single_leg(
    leg: Dict[str, Any],
    idempotency_key: str,
    plan_id: Optional[int] = None,
    user: Optional[Any] = None,
    document: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute a single simulated transfer leg with idempotency and failure simulation."""
    # 1. Check LedgerEntry database if user and model are available
    if user is not None:
        try:
            from Agent.models import LedgerEntry
            existing_entry = LedgerEntry.objects.filter(
                user=user,
                meta__idempotency_key=idempotency_key,
                status=LedgerEntry.Status.EXECUTED,
            ).first()
            if existing_entry:
                cached_res = {
                    "status": "executed",
                    "idempotency_key": idempotency_key,
                    "leg_index": leg.get("leg_index", 0),
                    "rail_id": leg.get("rail_id"),
                    "amount": str(existing_entry.amount),
                    "currency": existing_entry.currency,
                    "reference": existing_entry.meta.get("reference"),
                    "executed_at": existing_entry.ts.isoformat(),
                    "duplicate": True,
                }
                return cached_res
        except Exception:
            pass
    elif idempotency_key in _EXECUTED_KEYS_CACHE:
        return _EXECUTED_KEYS_CACHE[idempotency_key]

    # 3. Check for simulated failure injection
    leg_idx = leg.get("leg_index", 0)
    failure_hit = failures.check_should_fail(
        leg_index=leg_idx,
        rail_id=leg.get("rail_id"),
        plan_id=plan_id,
    )
    if failure_hit:
        fail_res = {
            "status": "failed",
            "idempotency_key": idempotency_key,
            "leg_index": leg_idx,
            "rail_id": leg.get("rail_id"),
            "error_code": failure_hit["error_code"],
            "error_message": failure_hit["error_message"],
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "is_simulated": True,
        }
        return fail_res

    # 4. Successful execution
    ref = f"SIM-TX-{secrets.token_hex(6).upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    leg_amount = Decimal(str(leg.get("target_amount", leg.get("amount_from"))))
    leg_ccy = leg.get("target_ccy", leg.get("currency_from", "CNY"))

    exec_result = {
        "status": "executed",
        "idempotency_key": idempotency_key,
        "leg_index": leg_idx,
        "rail_id": leg.get("rail_id"),
        "rail_name": leg.get("rail_name", leg.get("rail_id")),
        "amount": leg_amount,
        "currency": leg_ccy,
        "reference": ref,
        "executed_at": now_iso,
        "is_simulated": True,
    }

    # Record in database if user is available
    if user is not None:
        try:
            from Agent.models import LedgerEntry
            LedgerEntry.objects.create(
                user=user,
                entry_type="simulated_transfer_leg",
                amount=leg_amount,
                currency=leg_ccy,
                category="tuition_remittance" if "CNY" in leg_ccy or "GBP" in leg_ccy else "cross_border_remittance",
                counterparty=leg.get("rail_name", "Simulated Rail"),
                status=LedgerEntry.Status.EXECUTED,
                document=document,
                meta={
                    "idempotency_key": idempotency_key,
                    "plan_id": plan_id,
                    "leg_index": leg_idx,
                    "rail_id": leg.get("rail_id"),
                    "reference": ref,
                },
            )
        except Exception:
            pass

    _EXECUTED_KEYS_CACHE[idempotency_key] = exec_result
    return exec_result


def execute(
    plan: Any,
    idempotency_key: Optional[str] = None,
    user: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Execute a transfer plan (all legs) within the simulated sandbox.
    Generates receipt ID and cryptographic audit hash.
    Enforces per-leg idempotency and failure simulation.
    """
    # Extract plan properties whether it's a Django model instance or a dict
    plan_id = getattr(plan, "id", None)
    if isinstance(plan, dict):
        legs_data = plan.get("legs", [])
        target_amt = plan.get("target_amount")
        target_ccy = plan.get("target_ccy")
        plan_user = user or plan.get("user")
    else:
        legs_data = plan.legs or []
        target_amt = plan.target_amount
        target_ccy = plan.target_ccy
        plan_user = user or getattr(plan, "user", None)

    base_idem = idempotency_key or (f"plan_{plan_id}" if plan_id else secrets.token_hex(8))

    executed_legs = []
    has_failure = False
    failed_details = None

    for leg in legs_data:
        leg_idx = leg.get("leg_index", len(executed_legs))
        leg_idem_key = f"{base_idem}:{leg_idx}"
        leg_result = _execute_single_leg(
            leg=leg,
            idempotency_key=leg_idem_key,
            plan_id=plan_id,
            user=plan_user,
        )
        executed_legs.append(leg_result)
        if leg_result["status"] == "failed":
            has_failure = True
            failed_details = leg_result
            break

    # Construct receipt and audit payload
    receipt_token = secrets.token_hex(4).upper()
    receipt_id = f"REC-{plan_id or 'SIM'}-{receipt_token}"

    audit_payload = {
        "plan_id": plan_id,
        "receipt_id": receipt_id,
        "status": "failed" if has_failure else "executed",
        "legs": executed_legs,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "is_simulated": True,
    }
    audit_hash = hashlib.sha256(json.dumps(audit_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    if has_failure:
        return {
            "status": "failed",
            "receipt_id": receipt_id,
            "audit_hash": audit_hash,
            "failed_leg": failed_details,
            "legs": executed_legs,
            "error": failed_details.get("error_message", "One or more transfer legs failed."),
            "is_simulated": True,
        }

    return {
        "status": "executed",
        "receipt_id": receipt_id,
        "audit_hash": audit_hash,
        "legs": executed_legs,
        "target_amount": target_amt,
        "target_ccy": target_ccy,
        "is_simulated": True,
    }
