import json
import os
from typing import Any, Dict, List, Optional
from asgiref.sync import sync_to_async
from django.conf import settings

from Agent import context, llm, prompts, security, tools
from Agent.models import Session


async def run_agent(session: Session, user_message: str) -> Dict[str, Any]:
    """
    Hand-written async agent loop per idea.md §10.
    Enforces:
    1. Deterministic code gate: LLM reasons, code decides.
    2. Context Assembly: Fresh deterministic context bundle built on every iteration,
       injected as a separate system message between system prompt and history.
    3. Structured Output: Validates fixed JSON envelope, retries once on format errors
       with JSON response_format, and falls back gracefully with audit logging.
    4. Tool turns never force JSON mode to prevent breaking tool dispatch.
    5. Safe approval interruption: halts loop and returns approval request to user.
    """
    max_iterations = getattr(settings, "MAX_AGENT_ITERATIONS", 12)

    # 1. Scan for prompt injection patterns
    injection_scan = security.scan_injection(user_message)
    if injection_scan["detected"]:
        await security.alog_security_event(
            session=session,
            action="injection_detected",
            status="flagged",
            tier=Session.Tier.READ_ONLY,
            meta={
                "matched_patterns": injection_scan["matched_patterns"],
                "input_snippet": user_message[:100],
            },
        )

    # 2. Append user message to session history
    session_messages = list(session.messages or [])
    user_entry = {
        "role": "user",
        "content": user_message,
    }
    session_messages.append(user_entry)
    session.messages = session_messages

    # Save session and log user_message event
    await sync_to_async(session.save)(update_fields=["messages", "updated_at"])
    await security.alog_security_event(
        session=session,
        action="user_message",
        status="received",
        tier=Session.Tier.READ_ONLY,
        meta={"message_length": len(user_message)},
    )

    # 3. Prototype Demo Mode Interceptor (when demo=True or DEMO=True in .env)
    is_demo = getattr(settings, "DEMO", False)
    if is_demo:
        from Agent import demo_engine
        demo_resp = await sync_to_async(demo_engine.handle_demo_query)(session, user_message)
        if demo_resp is not None:
            reply_text = demo_resp.get("content") or demo_resp.get("summary", "")
            # Ensure structured envelope compatibility
            demo_resp["reply"] = reply_text
            demo_resp["cards"] = demo_resp.get("cards", [])
            demo_resp["next_action"] = demo_resp.get("next_action", "await_approval" if demo_resp.get("type") == "approval" else "await_user")
            demo_resp["confidence"] = demo_resp.get("confidence", 1.0)
            demo_resp["grounded_in_context"] = demo_resp.get("grounded_in_context", True)

            session_messages.append({
                "role": "assistant",
                "content": reply_text,
            })
            session.messages = session_messages
            await sync_to_async(session.save)(update_fields=["messages", "updated_at"])
            return demo_resp

    # 4. Agent Execution Loop (up to MAX_AGENT_ITERATIONS)
    for iteration in range(max_iterations):
        # Build fresh, deterministic context bundle from database on EVERY loop iteration
        context_bundle, context_msg = await context.assemble_context(session)

        # Inject context bundle as a distinct system message immediately after main system prompt
        # and before conversation history (Message 0: System Prompt, Message 1: Context, Messages 2..N: History)
        llm_messages = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            context_msg,
        ] + session_messages

        # Call LLM provider with tools (NO JSON response_format on tool turns!)
        try:
            assistant_msg = await llm.call_llm(
                messages=llm_messages,
                session=session,
                response_format=None,
            )
        except llm.ProviderUnavailableError as exc:
            fallback_text = "I am currently unable to reach the AI reasoning provider due to a network connectivity error. Please try again in a moment."
            fallback_envelope = context.create_fallback_envelope(fallback_text)
            session_messages.append({"role": "assistant", "content": fallback_text})
            session.messages = session_messages
            await sync_to_async(session.save)(update_fields=["messages", "updated_at"])
            await security.alog_security_event(
                session=session,
                action="provider_unavailable_fallback",
                status="fallback",
                tier=session.tier,
                meta={"error": str(exc)},
            )
            return {
                "type": "message",
                "content": fallback_text,
                "reply": fallback_text,
                "cards": [],
                "next_action": "await_user",
                "confidence": 0.5,
                "grounded_in_context": False,
                "structured_output": fallback_envelope,
                "iterations": iteration + 1,
            }

        tool_calls = assistant_msg.get("tool_calls")

        # Case A: Assistant returned final message (no tool calls)
        if not tool_calls:
            raw_content = assistant_msg.get("content", "")
            parsed = context.parse_structured_output(raw_content)

            # Retry once if final message is not valid JSON
            if parsed is None:
                retry_instruction = {
                    "role": "user",
                    "content": (
                        "Your response must be valid JSON matching the exact envelope format. "
                        "Return a JSON object with keys: 'reply' (string), 'cards' (list), "
                        "'next_action' ('none'|'await_user'|'await_approval'|'continue'), "
                        "'confidence' (float 0.0-1.0), and 'grounded_in_context' (boolean). "
                        "Do not include any text outside the JSON."
                    ),
                }
                retry_messages = [
                    {"role": "system", "content": prompts.SYSTEM_PROMPT},
                    context_msg,
                ] + session_messages + [
                    {"role": "assistant", "content": raw_content},
                    retry_instruction,
                ]

                # Final retry uses provider's JSON response format with NO tools enabled
                retry_msg = await llm.call_llm(
                    messages=retry_messages,
                    tools=None,
                    session=session,
                    response_format={"type": "json_object"},
                )
                retry_raw = retry_msg.get("content", "")
                parsed = context.parse_structured_output(retry_raw)

                # If it fails a second time, wrap into guaranteed valid fallback envelope
                if parsed is None:
                    parsed = context.create_fallback_envelope(raw_content)
                    await security.alog_security_event(
                        session=session,
                        action="structured_output_fallback",
                        status="fallback",
                        tier=session.tier,
                        meta={
                            "error": "Malformed final message failed JSON parsing after retry",
                            "raw_content_preview": raw_content[:150],
                        },
                    )

            # Record final assistant response in session history
            session_messages.append({
                "role": "assistant",
                "content": parsed["reply"],
            })
            session.messages = session_messages
            await sync_to_async(session.save)(update_fields=["messages", "updated_at"])

            return {
                "type": "message",
                "content": parsed["reply"],
                "reply": parsed["reply"],
                "cards": parsed["cards"],
                "next_action": parsed["next_action"],
                "confidence": parsed["confidence"],
                "grounded_in_context": parsed["grounded_in_context"],
                "structured_output": parsed,
                "iterations": iteration + 1,
            }

        # Case B: Assistant requested one or more tool calls (mid-workflow: skip envelope)
        session_messages.append(assistant_msg)

        approval_needed = None

        for tc in tool_calls:
            call_id = tc.get("id", f"call_{iteration}")
            func = tc.get("function", {})
            name = func.get("name", "")
            raw_args = func.get("arguments", "{}")

            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {}
            else:
                args = raw_args or {}

            # Execute tool deterministically in Django layer
            try:
                tool_result = await sync_to_async(tools.execute_tool)(
                    tool_name=name,
                    arguments=args,
                    session=session,
                )
            except Exception as exc:
                tool_result = {
                    "status": "error",
                    "error": str(exc),
                }

            # Append tool result with matching call_id
            session_messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(tool_result, default=str),
            })

            # Check if human approval is requested
            if tool_result.get("requires_approval"):
                approval_needed = {
                    "type": "approval",
                    "plan_id": tool_result.get("plan_id"),
                    "summary": tool_result.get("summary"),
                    "status": "pending",
                }

        session.messages = session_messages
        await sync_to_async(session.save)(update_fields=["messages", "updated_at"])

        # If a tool requested human approval, return approval immediately
        if approval_needed:
            return approval_needed

    # Loop exceeded max iterations: fallback envelope
    fallback_text = "I have reached the maximum reasoning iterations for this step. Please review the plan details or clarify your request."
    fallback_envelope = context.create_fallback_envelope(fallback_text)
    session_messages.append({"role": "assistant", "content": fallback_text})
    session.messages = session_messages
    await sync_to_async(session.save)(update_fields=["messages", "updated_at"])

    return {
        "type": "message",
        "content": fallback_text,
        "reply": fallback_text,
        "cards": [],
        "next_action": "await_user",
        "confidence": 0.5,
        "grounded_in_context": False,
        "structured_output": fallback_envelope,
        "iterations": max_iterations,
    }

