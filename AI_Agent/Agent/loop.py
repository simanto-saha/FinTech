import json
import os
from typing import Any, Dict, List, Optional
from asgiref.sync import sync_to_async
from django.conf import settings

from Agent import llm, prompts, security, tools
from Agent.models import Session


async def run_agent(session: Session, user_message: str) -> Dict[str, Any]:
    """
    Hand-written async agent loop per idea.md §10.
    Enforces:
    1. Deterministic code gate: LLM reasons, code decides.
    2. Hard iteration limit: MAX_AGENT_ITERATIONS (default 12).
    3. Preserved tool-call IDs and unmodified tool results.
    4. Explicit prompt-injection scanning and untrusted wrapping.
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
            session_messages.append({
                "role": "assistant",
                "content": demo_resp.get("content") or demo_resp.get("summary", ""),
            })
            session.messages = session_messages
            await sync_to_async(session.save)(update_fields=["messages", "updated_at"])
            return demo_resp

    # 4. Agent Execution Loop (up to MAX_AGENT_ITERATIONS)
    for iteration in range(max_iterations):
        # Build prompt: [system] + session.messages
        llm_messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}] + session_messages

        # Call LLM provider
        assistant_msg = await llm.call_llm(
            messages=llm_messages,
            session=session,
        )

        tool_calls = assistant_msg.get("tool_calls")

        # Case A: Assistant returned normal message (no tool calls)
        if not tool_calls:
            content = assistant_msg.get("content", "")
            session_messages.append({
                "role": "assistant",
                "content": content,
            })
            session.messages = session_messages
            await sync_to_async(session.save)(update_fields=["messages", "updated_at"])
            return {
                "type": "message",
                "content": content,
                "iterations": iteration + 1,
            }

        # Case B: Assistant requested one or more tool calls
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

    # Loop exceeded max iterations
    fallback_content = "I have reached the maximum reasoning iterations for this step. Please review the plan details or clarify your request."
    session_messages.append({"role": "assistant", "content": fallback_content})
    session.messages = session_messages
    await sync_to_async(session.save)(update_fields=["messages", "updated_at"])

    return {
        "type": "message",
        "content": fallback_content,
        "iterations": max_iterations,
    }

