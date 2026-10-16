import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

_CORRIDORS_FILE = Path(__file__).resolve().parent / "data" / "corridors.json"
_CACHE: Optional[Dict[str, Any]] = None


def _load_corridors() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        with open(_CORRIDORS_FILE, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def reload_corridors() -> Dict[str, Any]:
    """Force reload of the corridors reference data from disk."""
    global _CACHE
    _CACHE = None
    return _load_corridors()


def list_supported_corridors() -> List[str]:
    """Return a list of supported corridor codes (e.g. ['BD-CN', 'IN-GB', 'PH-AE'])."""
    return list(_load_corridors().keys())


def normalize_corridor_code(code_or_from: str, to_country: Optional[str] = None) -> str:
    """Normalize corridor input into 'FROM-TO' format."""
    if to_country:
        return f"{code_or_from.strip().upper()}-{to_country.strip().upper()}"
    clean = code_or_from.strip().upper().replace("_", "-").replace(" ", "-")
    if "-" in clean:
        parts = clean.split("-")
        return f"{parts[0]}-{parts[1]}"
    return clean


def get_corridor_rules(corridor_code: str, to_country: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve corridor rules, caps, requirements, and rail options.
    Returns None if corridor is not supported.
    """
    code = normalize_corridor_code(corridor_code, to_country)
    data = _load_corridors()
    rule = data.get(code)
    if not rule:
        return None
    # Return a copy with Decimal cap for safe financial calculations
    result = dict(rule)
    result["cap_daily"] = Decimal(str(result["cap_daily"]))
    return result


def check_corridor_cap(
    corridor_code: str,
    amount: Decimal | float | int | str,
    currency: str,
) -> Dict[str, Any]:
    """
    Check if a transfer amount breaches the corridor daily cap.
    Returns details on whether multi-leg splitting is required.
    """
    rules = get_corridor_rules(corridor_code)
    if not rules:
        raise ValueError(f"Unsupported corridor: {corridor_code}")

    amt = Decimal(str(amount))
    cap = Decimal(str(rules["cap_daily"]))
    cap_ccy = rules["cap_ccy"]

    if currency.upper() != cap_ccy.upper():
        # Currency must match cap currency or caller must convert
        pass

    breaches_cap = amt > cap
    recommended_legs = 1
    if breaches_cap:
        # Calculate minimum number of legs required to satisfy the cap
        from math import ceil
        recommended_legs = int(ceil(amt / cap))

    return {
        "corridor": rules["code"],
        "amount": amt,
        "currency": currency.upper(),
        "cap_daily": cap,
        "cap_currency": cap_ccy,
        "breaches_cap": breaches_cap,
        "recommended_legs": recommended_legs,
        "requires_split": breaches_cap,
        "notes": rules.get("notes", ""),
        "requires_compliance_checks": rules.get("requires", []),
    }

