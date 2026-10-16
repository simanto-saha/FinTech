from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

# Base USD rates for deterministic simulation
# USD: 1.00
# 120.00 BDT per USD, 7.20 CNY per USD => 7.20 / 120.00 = 0.060000 CNY per BDT
_BASE_USD_RATES: Dict[str, Decimal] = {
    "USD": Decimal("1.000000"),
    "CNY": Decimal("7.200000"),
    "BDT": Decimal("120.000000"),
    "PHP": Decimal("58.000000"),
    "AED": Decimal("3.672500"),
    "GBP": Decimal("0.790000"),
    "EUR": Decimal("0.920000"),
    "SGD": Decimal("1.340000"),
    "AUD": Decimal("1.520000"),
    "CAD": Decimal("1.380000"),
    "INR": Decimal("84.000000"),
    "JPY": Decimal("155.000000"),
    "HKD": Decimal("7.820000"),
}

# Precision per currency for rounding monetary amounts
_CURRENCY_DECIMALS: Dict[str, int] = {
    "JPY": 0,
    "KRW": 0,
    "BDT": 2,
    "CNY": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "PHP": 2,
    "AED": 2,
    "SGD": 2,
    "AUD": 2,
    "CAD": 2,
    "INR": 2,
    "HKD": 2,
}


def round_amount(amount: Decimal | float | int | str, currency: str) -> Decimal:
    """Round a monetary amount according to the currency's standard decimal precision."""
    dec = Decimal(str(amount))
    places = _CURRENCY_DECIMALS.get(currency.upper(), 2)
    if places == 0:
        return dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    exponent = Decimal(f"0.{'0' * (places - 1)}1")
    return dec.quantize(exponent, rounding=ROUND_HALF_UP)


def get_base_rate(from_ccy: str, to_ccy: str) -> Decimal:
    """
    Compute deterministic cross rate from base USD table.
    rate = USD_base[to_ccy] / USD_base[from_ccy]
    """
    f = from_ccy.strip().upper()
    t = to_ccy.strip().upper()

    if f == t:
        return Decimal("1.000000")

    if f not in _BASE_USD_RATES:
        raise ValueError(f"Unsupported source currency for sandbox FX: {f}")
    if t not in _BASE_USD_RATES:
        raise ValueError(f"Unsupported target currency for sandbox FX: {t}")

    usd_to_from = _BASE_USD_RATES[f]
    usd_to_target = _BASE_USD_RATES[t]

    rate = usd_to_target / usd_to_from
    return rate.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def get_fx_quote(
    from_ccy: str,
    to_ccy: str,
    amount_from: Optional[Decimal | float | int | str] = None,
    target_amount: Optional[Decimal | float | int | str] = None,
    jitter: bool = False,
    jitter_bps: int = 0,
) -> Dict[str, Any]:
    """
    Generate a deterministic simulated FX quote.
    Every quote is explicitly flagged as simulated to satisfy competition and safety requirements.
    """
    f = from_ccy.strip().upper()
    t = to_ccy.strip().upper()
    base_rate = get_base_rate(f, t)

    rate = base_rate
    if jitter and jitter_bps != 0:
        # 1 bps = 0.0001
        jitter_factor = Decimal("1.0") + (Decimal(str(jitter_bps)) * Decimal("0.0001"))
        rate = (base_rate * jitter_factor).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    # Compute converted amounts
    amt_from: Optional[Decimal] = None
    amt_to: Optional[Decimal] = None

    if amount_from is not None:
        amt_from = Decimal(str(amount_from))
        raw_to = amt_from * rate
        amt_to = round_amount(raw_to, t)
    elif target_amount is not None:
        amt_to = Decimal(str(target_amount))
        raw_from = amt_to / rate
        amt_from = round_amount(raw_from, f)

    inverse_rate = (Decimal("1.0") / rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    return {
        "from_currency": f,
        "to_currency": t,
        "rate": rate,
        "inverse_rate": inverse_rate,
        "amount_from": amt_from,
        "target_amount": amt_to,
        "is_simulated": True,
        "rate_type": "sandbox_deterministic",
        "provider": "Fundora Deterministic FX Sandbox",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": 300,
        "disclaimer": "Simulated FX rate for test and competition environment. Not for real money movement.",
    }

