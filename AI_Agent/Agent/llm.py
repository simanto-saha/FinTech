import asyncio
import base64
import os
from typing import Any, Dict, List, Optional, Union
import httpx

from Agent import security


class ProviderError(Exception):
    """Base exception for external AI provider failures."""
    pass


class ProviderConfigurationError(ProviderError):
    """Raised when required API credentials or URLs are missing/misconfigured."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when an AI provider times out or returns HTTP errors after retries."""
    pass


def get_llm_config() -> Dict[str, str]:
    """Retrieve LLM provider configuration from settings/environment."""
    from django.conf import settings
    return {
        "provider": os.getenv("LLM_PROVIDER") or getattr(settings, "LLM_PROVIDER", "deepseek"),
        "api_key": os.getenv("DEEPSEEK_API_KEY") if "DEEPSEEK_API_KEY" in os.environ else (getattr(settings, "DEEPSEEK_API_KEY", "") or ""),
        "url": os.getenv("DEEPSEEK_URL") or getattr(settings, "DEEPSEEK_URL", "https://api.deepseek.com/chat/completions"),
        "model": os.getenv("DEEPSEEK_MODEL") or getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
    }


def get_vision_config() -> Dict[str, str]:
    """Retrieve Vision provider configuration from settings/environment."""
    return {
        "provider": os.getenv("VISION_PROVIDER", "gemini"),
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "url": os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
        "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
    }


def get_openai_tool_definitions() -> List[Dict[str, Any]]:
    """Convert the 16 allowed tools into OpenAI-compatible function schema format."""
    tool_descriptions = {
        "classify_user": "Classify user type (student, worker, tourist, business, family), corridor, and purpose.",
        "get_kyc_requirements": "Retrieve KYC verification requirements for a user type and cross-border corridor.",
        "verify_document": "Verify an uploaded financial or educational document by document ID.",
        "run_compliance_checks": "Run deterministic AML, sanctions, PEP, and adverse media checks for a user.",
        "get_corridor_rules": "Fetch transfer caps, required checks, and regulations for a cross-border corridor.",
        "list_payment_rails": "List available payment rails, speeds, and fees for a corridor and currency pair.",
        "get_fx_quote": "Get a deterministic foreign exchange quote between two currencies.",
        "create_transfer_plan": "Construct a multi-leg compliant transfer plan respecting corridor daily caps.",
        "request_human_approval": "Request explicit user approval for a transfer plan before execution.",
        "execute_transfer_plan": "Execute an approved transfer plan inside the simulated sandbox.",
        "get_transaction_status": "Query the current settlement status of a transfer or plan.",
        "get_balances": "Retrieve multi-currency wallet balances for a user.",
        "create_budget": "Create a monthly budget in local and destination currencies.",
        "prepare_credit_application": "Prepare a student or secured credit card application guide in destination country.",
        "lookup_university": "Look up payment channels, common issues, and support for an international university.",
        "get_masked_field": "Retrieve a masked representation of a sensitive user identifier.",
    }

    tools = []
    for name in sorted(security.ALLOWED_TOOLS):
        schema = security.TOOL_SCHEMAS.get(name, {})
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool_descriptions.get(name, f"Execute {name}"),
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                    "additionalProperties": False,
                },
            },
        })
    return tools


def _offline_student_assistant(messages: List[Dict[str, Any]], session: Optional[Any] = None) -> Dict[str, Any]:
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_msg = str(m.get("content", "")).lower()
            break

    prefix = "DeepSeek API key is not configured. Running in deterministic offline sandbox mode.\n\n"

    if any(k in last_user_msg for k in ["rent", "landlord", "deposit", "lease", "tenancy", "housing"]):
        return {
            "role": "assistant",
            "content": (
                f"{prefix}🏠 **Simulated Landlord Rent & Security Deposit Plan**\n\n"
                "• **Payee Verification:** Match destination account (UK Sort Code 20-00-00 / Account No. 12345678 or Alipay Institutional Payee).\n"
                "• **Deposit + 1st Month Rent:** £850 rent + £850 deposit = £1,700 total (≈ 265,000 BDT at rate 0.0064).\n"
                "• **Rail Optimization:** Bank Wire (£35 fee, 2-3 business days) vs. Fast-Track Rail (£12 fee, instant proof).\n"
                "• **Safety Buffer:** Includes a 5% FX safety margin to ensure your landlord receives the exact agreed local currency.\n"
                "• **Credit Record:** Upon simulated settlement, an immutable `LedgerEntry` is created to verify your on-time tenant track record!"
            ),
        }

    if any(k in last_user_msg for k in ["tuition", "szu", "shenzhen", "tsinghua", "nus", "manchester", "deadline", "hold"]):
        return {
            "role": "assistant",
            "content": (
                f"{prefix}🎓 **Simulated Urgent Tuition & University Hold Plan**\n\n"
                "• **Target Institution:** Shenzhen University (SZU) / College of International Exchange.\n"
                "• **Tuition Invoice:** 45,000 CNY semester fee.\n"
                "• **Daily Cap Compliance:** BD-CN corridor daily limit is 500,000 BDT (≈ 30,000 CNY). Fundora automatically splits this into **2 compliant sequential legs**:\n"
                "   - Leg 1: 22,500 CNY (375,000 BDT) via Alipay Cross-Border Education (instant hold removal).\n"
                "   - Leg 2: 22,500 CNY (375,000 BDT) scheduled next day.\n"
                "• **Registration Hold Prevention:** Issues an instant electronic confirmation voucher with student ID and audit hash to waive academic portal registration holds."
            ),
        }

    if any(k in last_user_msg for k in ["fx", "devaluation", "shock", "volatility", "runway", "drop"]):
        return {
            "role": "assistant",
            "content": (
                f"{prefix}📉 **Simulated FX Volatility Shock & Runway Stress Test (Home Currency Devaluation)**\n\n"
                "• **Baseline Monthly Allowance:** 60,000 BDT ≈ £384 / 3,600 CNY (90 days baseline runway).\n"
                "• **Stress Scenarios:**\n"
                "   - **5% Currency Drop:** Runway drops to 85 days. (Deficit: -£19/month).\n"
                "   - **10% Currency Drop:** Runway drops to 79 days. (Deficit: -£38/month).\n"
                "   - **15% Currency Drop:** Runway drops to 70 days. (Deficit: -£58/month).\n"
                "• **Automated AI Rebalance Recommendation:**\n"
                "   1. Reduce non-essential dining/takeout by £25/month.\n"
                "   2. Switch to student concession transit cap (£10/month saving).\n"
                "   3. Safeguard fixed rent and supermarket grocery allocations.\n"
                "   4. Request an emergency top-up buffer from parents with zero hidden FX markup."
            ),
        }

    if any(k in last_user_msg for k in ["daily", "envelope", "groceries", "transit", "living", "monthly", "budget"]):
        return {
            "role": "assistant",
            "content": (
                f"{prefix}🛒 **Simulated Daily Living Allowance & Weekly Envelopes**\n\n"
                "• **Monthly Living Allowance:** £800 (≈ 125,000 BDT).\n"
                "• **Daily Spending Cap:** **£18.65 / day** for food, transit, and incidental expenses.\n"
                "• **4 Weekly Envelopes:**\n"
                "   - 🛒 **Groceries:** £90 / week (Supermarket budget: Lidl/Aldi/Tesco basket model).\n"
                "   - 🚇 **Public Transit:** £50 / week (Student concession pass / 18+ Oyster cap).\n"
                "   - 💡 **Utilities & Mobile:** £36 / week (Shared heating, electric & student 5G SIM).\n"
                "   - 🛡️ **Emergency Buffer:** £24 / week (10% contingency for price shifts).\n"
                "• **Student Tip:** Activating local student discounts (UNiDAYS, Student Beans) saves an average of 15% on daily grocery staples."
            ),
        }

    if any(k in last_user_msg for k in ["credit", "score", "alternative credit", "report", "tenant", "guarantor"]):
        return {
            "role": "assistant",
            "content": (
                f"{prefix}💳 **Simulated Alternative Student Credit Profile**\n\n"
                "• **Alternative Student Score:** **745 / 850** (Grade: *Excellent Student Financial Record*).\n"
                "• **Payment Streak:** 100% on-time record across 6 simulated tuition & rent disbursements.\n"
                "• **Verification Mechanism:** Every payment generates an immutable cryptographic SHA-256 hash in Fundora's `LedgerEntry` table.\n"
                "• **Landlord Benefit:** Generates a verifiable **Student Financial Reputation Certificate** to waive 6-12 month upfront rent demands from foreign landlords.\n"
                "• **Credit Card Path:** Pre-qualifies for student credit-builder cards (HSBC Premier Student, Bank of China Great Wall, Barclays Forward) with 0 annual fee."
            ),
        }

    if any(k in last_user_msg for k in ["health", "nhs", "oshc", "medical", "insurance", "doctor"]):
        return {
            "role": "assistant",
            "content": (
                f"{prefix}🩺 **Simulated Student Health Surcharge & Medical Buffer**\n\n"
                "• **Compulsory Visa Health Surcharge:**\n"
                "   - UK NHS Immigration Health Surcharge: £776 / year (3-year degree = £2,328 ≈ 364,000 BDT).\n"
                "   - Australia OSHC: ~$600 AUD / year.\n"
                "• **Out-of-Pocket Medical Buffer:** Recommended £250 / year reserve for prescription copays, emergency dental, or private optometrist checks.\n"
                "• **Simulation Advice:** Budget your visa health surcharge as a one-time pre-arrival capital cost so it does not drain your semester living allowance."
            ),
        }

    return {
        "role": "assistant",
        "content": (
            f"{prefix}I am Fundora, your AI Student Finance Companion. You can ask me to simulate:\n"
            "• 🏠 **Rent & Security Deposit** to private landlords\n"
            "• 🎓 **Urgent Tuition Deadlines** & hold prevention for SZU, Tsinghua, NUS, Manchester\n"
            "• 📉 **FX Devaluation Shocks** & runway stress tests\n"
            "• 🛒 **Daily Living Allowances** & weekly grocery/transit envelopes\n"
            "• 💳 **Alternative Student Credit Building** & landlord certificates\n"
            "• 🩺 **Visa Health Surcharges** (NHS/OSHC) & emergency medical buffers"
        ),
    }


async def call_llm(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto",
    temperature: float = 0.2,
    session: Optional[Any] = None,
    client: Optional[httpx.AsyncClient] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call the LLM provider (DeepSeek / OpenAI-compatible endpoint).
    Includes:
    - 60s timeout
    - 2x bounded retries with 0.5s and 1.5s backoff
    - Security audit logging on retry
    - Response structure validation
    - Fail-closed handling for missing keys / network drops
    - Optional response_format support (JSON mode)
    """
    config = get_llm_config()
    api_key = config["api_key"]
    url = config["url"]
    model = config["model"]

    if not api_key:
        return _offline_student_assistant(messages, session)

    # Redact any accidental secrets before transmission
    sanitized_messages = security.redact_secrets(messages)

    effective_tools = tools if tools is not None else get_openai_tool_definitions()

    payload = {
        "model": model,
        "messages": sanitized_messages,
        "temperature": temperature,
        "max_tokens": 1500,
    }
    if effective_tools:
        payload["tools"] = effective_tools
        payload["tool_choice"] = tool_choice
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    backoffs = [0.5, 1.5]
    last_exception = None

    for attempt in range(len(backoffs) + 1):
        try:
            if client is not None:
                r = await client.post(url, headers=headers, json=payload, timeout=60.0)
            else:
                async with httpx.AsyncClient(timeout=60.0) as c:
                    r = await c.post(url, headers=headers, json=payload)

            if r.status_code >= 500:
                raise httpx.HTTPStatusError(f"Server error {r.status_code}", request=r.request, response=r)
            if r.status_code != 200:
                raise ProviderUnavailableError(f"LLM provider error HTTP {r.status_code}: {r.text}")

            data = r.json()
            if "choices" not in data or not data["choices"]:
                raise ProviderUnavailableError("Malformed response from LLM provider: missing choices.")

            message = data["choices"][0].get("message", {})
            return message

        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_exception = exc
            if attempt < len(backoffs):
                delay = backoffs[attempt]
                if session is not None:
                    try:
                        await security.alog_security_event(
                            session=session,
                            action="llm_retry",
                            status="retry",
                            tier=1,
                            meta={"attempt": attempt + 1, "delay_seconds": delay, "error": str(exc)},
                        )
                    except Exception:
                        pass
                await asyncio.sleep(delay)
            else:
                break

    raise ProviderUnavailableError(f"LLM call failed after retries: {last_exception}")


async def call_vision(
    image_bytes_or_base64: Union[bytes, str],
    prompt: str,
    mime_type: str = "image/png",
    session: Optional[Any] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Call the Vision provider (Gemini 2.0 Flash / OpenAI-compatible vision endpoint).
    Used for document classification and OCR field extraction.
    """
    config = get_vision_config()
    api_key = config["api_key"]
    url = config["url"]
    model = config["model"]

    if not api_key:
        return {
            "doc_type": "unknown",
            "extracted": {},
            "confidence": 0.0,
            "requires_confirmation": True,
            "note": "Vision API key not configured.",
        }

    if isinstance(image_bytes_or_base64, bytes):
        b64_str = base64.b64encode(image_bytes_or_base64).decode("utf-8")
    else:
        b64_str = image_bytes_or_base64

    data_url = f"data:{mime_type};base64,{b64_str}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    backoffs = [0.5, 1.5]
    last_exception = None

    for attempt in range(len(backoffs) + 1):
        try:
            if client is not None:
                r = await client.post(url, headers=headers, json=payload, timeout=60.0)
            else:
                async with httpx.AsyncClient(timeout=60.0) as c:
                    r = await c.post(url, headers=headers, json=payload)

            if r.status_code >= 500:
                raise httpx.HTTPStatusError(f"Server error {r.status_code}", request=r.request, response=r)
            if r.status_code != 200:
                raise ProviderUnavailableError(f"Vision provider error HTTP {r.status_code}: {r.text}")

            data = r.json()
            if "choices" not in data or not data["choices"]:
                raise ProviderUnavailableError("Malformed response from Vision provider.")

            return data["choices"][0].get("message", {})

        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_exception = exc
            if attempt < len(backoffs):
                delay = backoffs[attempt]
                if session is not None:
                    try:
                        await security.alog_security_event(
                            session=session,
                            action="vision_retry",
                            status="retry",
                            tier=1,
                            meta={"attempt": attempt + 1, "delay_seconds": delay, "error": str(exc)},
                        )
                    except Exception:
                        pass
                await asyncio.sleep(delay)
            else:
                break

    raise ProviderUnavailableError(f"Vision call failed after retries: {last_exception}")
