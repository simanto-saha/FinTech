# Fundora Build Checklist

This checklist turns [`idea.md`](idea.md) into staged work. Update the checkboxes here as each item is implemented and its exit checks pass. Keep [`test_results.md`](test_results.md) as the evidence log; do not mark an item complete based on code alone.

## Status key

- `[ ]` Not started / not complete
- `[/]` In progress
- `[x]` Implemented and its listed checks pass
- `[!]` Blocked; explain why in `test_results.md`

Only mark a phase complete after all required checks pass. A failing or unrun check stays open.

## 0. Product rules and scope

- [x] Confirm the product scope and four pillars in `idea.md`: remittances, tuition payments, credit building, and multi-currency management.
- [x] Preserve the architecture rule: the LLM interprets and explains; deterministic Django code enforces rules, approvals, and execution.
- [x] Keep the implementation within the specified tool list and locked stack; document any required change before adopting it.
- [x] Define demo-only behavior clearly: all rails and transfers are simulated and cannot move real money.

**Checks / exit criteria**

- [x] Review the product workflow and threat boundaries before each feature phase.
- [x] Ensure UI, API responses, and demo material identify simulated financial actions as simulations.

## 1. Foundation, configuration, and project layout

- [/] Align runtime and dependencies with the spec: Python 3.12+, Django 5.2, PostgreSQL, `httpx`, Pillow, `python-dotenv`, PyYAML, and Uvicorn. Remove unrelated/forbidden dependencies where unused.
- [x] Configure `.env.example` for database, email, LLM, vision, sandbox, approval TTL, and agent iteration limit. Keep `.env` and all secrets out of version control.
- [/] Use PostgreSQL for the specified application database; configure media upload paths and safe upload limits.
- [x] Adapt the existing `Agent` app for agent workflows and create the `sandbox` Django app. Keep the adaptation documented; Windows cannot hold both `Agent` and `agent` directories because names are case-insensitive.
- [x] Add Windows and Linux/macOS setup instructions and reliable ASGI/development entry points.

**Checks / exit criteria**

- [!] Fresh-environment dependency install succeeds from the documented requirements.
- [x] Configuration validation rejects missing production secrets and invalid settings without printing secret values.
- [!] PostgreSQL migrations and Django system checks pass from a clean database.
- [ ] Media upload configuration cannot write outside the intended media directory.

## 2. Domain models, migrations, and audit admin

- [x] Preserve the existing user, profile, OTP, conversation, and question models where appropriate.
- [x] Add `Session` with user, message history, code-owned tier, user type, corridor, and timestamps.
- [x] Add `Document` with owner/session, file, type, extracted data, confidence, and verification state.
- [x] Add `Plan` with owner/session, legs, target, total cost, status, approval/execution timestamps.
- [x] Add `Approval` with an opaque 64-character token, plan/user, status, and expiry.
- [x] Add `AuditLog` with session, timestamp, tier, action, status, metadata, ordering, and `(session, ts)` index.
- [x] Add `LedgerEntry` with owner, amount/currency, category, counterparty, status, optional document, and metadata.
- [x] Add `University` with unique slug, country, aliases, payment channels, common issues, and support details.
- [x] Register all seven domain models in Django admin; make audit records read-only and searchable/filterable.

**Checks / exit criteria**

- [!] Migration applies on an empty PostgreSQL database; migration consistency check passes.
- [x] Model tests cover constraints, ownership relationships, statuses, timestamps, and audit index.
- [x] Admin access and safe read-only audit behavior are verified for each relevant role.

## 3. Deterministic sandbox and reference data

- [x] Implement sandbox rails: list available rails, quote costs, build multi-leg plans, execute simulated legs, and support idempotency keys.
- [x] Add corridor rules for BD-CN, IN-GB, and PH-AE, including caps, required checks, available rails, and explanatory notes.
- [x] Add university reference data for SZU, Tsinghua, NUS, Manchester, and Melbourne, including aliases and payment channels.
- [x] Implement deterministic FX quotes/rates for simulation; clearly distinguish simulated data from live quotes.
- [x] Implement deterministic compliance checks for AML, sanctions, PEP, and adverse media, including the documented blocked test identity.
- [x] Add explicit simulated failure controls for multi-leg recovery scenarios.

**Checks / exit criteria**

- [x] Unit tests prove caps, cost comparisons, currency rounding, compliant-route selection, and multi-leg split behavior.
- [x] Compliance tests prove a failed check stops planning/execution and cannot be bypassed by model output.
- [x] Repeated execution with the same idempotency key does not duplicate a leg or ledger entry.

## 4. Security primitives and tool validation

- [x] Implement field masking for passport, account, card, email, phone, and unknown sensitive fields.
- [x] Wrap all extracted/document text as untrusted data and detect/log prompt-injection patterns.
- [x] Validate every tool name and argument against strict schemas before invocation; reject unknown tools and malformed arguments.
- [x] Ensure only the masked-field tool can return user data, and it never returns unmasked sensitive values.
- [x] Add security audit events for tool calls, approvals, denials, and suspicious input/output.
- [x] Keep approval tokens out of LLM prompts, messages, and tool results.

**Checks / exit criteria**

- [x] Unit tests cover mask edge cases, injection strings in documents, malformed tool arguments, and unknown tools.
- [x] Tests prove secrets, full identifiers, and approval tokens do not appear in LLM inputs or user-visible output.
- [x] No user-controlled content can set a tier or execute a privileged action.

## 5. LLM and vision provider clients

- [x] Configure DeepSeek chat and Gemini vision providers using the environment variables in `idea.md`.
- [x] Implement async `httpx` requests with timeouts, bounded retry/backoff, provider error handling, and retry audit events.
- [x] Validate response structure and tool calls before handing them to the agent loop.
- [x] Support missing/invalid keys and provider downtime with honest user-facing fallback behavior.
- [x] Keep provider keys and sensitive user data out of logs.

**Checks / exit criteria**

- [x] Mocked client tests cover success, malformed responses, timeout, HTTP errors, retries, and exhausted retries.
- [x] Offline test run requires no real provider credentials or network access.
- [x] Manual sandbox smoke test confirms configured providers can respond without invoking privileged behavior directly.

## 6. Tool layer and agent loop

- [x] Define exactly the 16 tools from `idea.md` in `tools.py` with schemas and tests.
- [x] Implement the hand-written async `run_agent(session, user_message)` loop with a hard iteration limit and preserved tool-call IDs/results.
- [x] Implement conversation persistence and explicit clarification, refusal, correction, and fallback responses.
- [x] Enforce tier transitions in Django code only: read-only, suggest/plan, execute after approval, and opt-in recurring automation.
- [x] Implement the system prompt and workflows from `idea.md`; never let prompt instructions replace deterministic checks.
- [x] Implement LLM retry and loop-limit behavior without skipped or altered tool results.

**Checks / exit criteria**

- [x] Unit tests cover tool selection/dispatch, multiple calls, malformed calls, loop limit, provider errors, clarification, and persistence.
- [x] Tests prove tool calls cannot directly change tier, issue approvals, or move funds outside the execution gate.
- [x] Every tool invocation has a matching audit event and accurate result.

## 7. Plans, approval, execution gate, and ledger

- [x] Implement plan creation from deterministic quotes, corridor rules, compliance, and available rails.
- [x] Implement approval/reject UI and endpoint bound to the authenticated user and plan.
- [x] Enforce approval expiry (default 300 seconds), one-time token use, plan ownership/status, and fresh compliance checks.
- [x] Implement `execute_transfer_plan` as the only transfer-moving operation; use sandbox rails only.
- [x] Create one ledger entry per executed leg and return a simulated receipt and audit reference.
- [x] Implement status/reconciliation responses and safe cancellation/expiry states.

**Checks / exit criteria**

- [x] Tests prove unauthenticated, wrong-owner, unapproved, expired, already-used, stale, or compliance-failed executions are rejected.
- [x] Concurrency/idempotency tests prove approval and execution cannot create duplicate transfers or ledger entries.
- [x] No execution occurs without explicit user approval; approval token never reaches the LLM.
- [x] Successful simulated execution leaves a consistent plan, ledger, and audit trail.

## 8. Document upload and invoice workflow

- [ ] Add authenticated multipart upload for allowed image/PDF formats, size limits, MIME/content validation, and safe storage.
- [ ] Preprocess images with Pillow (resize, contrast, orientation) and classify/extract supported document fields with Gemini vision.
- [ ] Support the document types listed in `idea.md`: tuition invoice, utility/rent/phone bill, admission letter, passport, visa, scholarship letter, and receipt.
- [ ] Validate confidence, currencies, dates, university matches, amount ranges, and KYC name similarity; ask for confirmation below 0.85 confidence.
- [ ] Store extraction and verification state; wrap OCR output as untrusted data before LLM use.
- [ ] For tuition invoices, look up the university and compare its payment channels before proposing a plan.

**Checks / exit criteria**

- [ ] Tests cover valid/invalid files, limits, OCR schema errors, low confidence, wrong university, invalid dates/currency, and malicious document text.
- [ ] Integration test uploads an invoice, shows extracted fields for confirmation, and produces a plan only after confirmation.
- [ ] File access is owner-scoped and uploaded files are not executable or publicly exposed by default.

## 9. Frontend workflows and finance pillars

- [/] Keep the existing landing page, authentication, FX display, budget/remittance UI, chat history, and reminders where useful.
- [ ] Build the authenticated HTMX chat flow, approval/plan/document cards, and status dashboard described by the spec.
- [ ] Complete cross-border remittance planning, multi-leg caps, route comparison, and failure recovery.
- [ ] Complete tuition invoice-first workflow, university/channel comparison, split payment plan, and receipt.
- [ ] Add multi-currency balances, budgets in home/local currency, FX alerts, and strategic conversion suggestions.
- [ ] Add destination-country secured/student-card guidance, utilization tracking, and user-opted autopay guidance.
- [ ] Clearly label simulated balances, rates, compliance, rails, and transfers; do not imply real financial services.
- [ ] Make clarifications, corrections, re-planning, and unreadable/unknown-document fallbacks visible and actionable.

**Checks / exit criteria**

- [ ] Django client/integration tests cover auth gates, chat, plan approval, upload, status, and each finance workflow.
- [ ] Manual browser checks cover desktop/mobile layout, keyboard navigation, clear loading/error states, and all primary flows.
- [ ] Accessibility and privacy review confirms no sensitive details leak into chat history, browser URLs, or logs.

## 10. Scripted task runner and competition scenarios

- [ ] Add YAML task definitions and a `run_task` management command with isolated sandbox state and machine-readable logs.
- [ ] T1: student tuition BD-CN split into two legs when a cap requires it.
- [ ] T2: worker remittance PH-AE via one leg.
- [ ] T3: invoice upload, extraction, confirmation, and plan creation.
- [ ] T4: user corrects university mid-flow; agent rechecks and updates the plan without losing context.
- [ ] T5: second leg fails; system detects, replans, requests approval, and completes safely.
- [ ] Ensure each scenario asserts both successful outcome and absence of unapproved execution.

**Checks / exit criteria**

- [ ] `run_task T1` through `run_task T5` pass from a clean sandbox database.
- [ ] Each run saves reproducible inputs, tool sequence, assertions, and execution/audit logs.

## 11. Security attack runner and self-assessment

- [ ] Add YAML attack cases and a `run_attack` command with machine-readable evidence.
- [ ] A1 induced transfer: no plan/execute without a valid user request and approval; event is logged.
- [ ] A2 data extraction: only masked data is returned.
- [ ] A3 privilege escalation: prompts/tool arguments cannot change code-owned tier.
- [ ] A4 prompt injection via document: content stays data, no privileged action occurs, detection is logged.
- [ ] Write a security self-assessment covering trust boundaries, secrets, uploads, authorization, approval, idempotency, and residual risks.

**Checks / exit criteria**

- [ ] `run_attack A1` through `run_attack A4` pass and save evidence.
- [ ] Review logs and test artifacts for leaked credentials, PII, or approval tokens.
- [ ] Security review confirms fail-closed behavior on provider, OCR, compliance, and sandbox errors.

## 12. Documentation, release, and demo readiness

- [ ] Update README for the actual stack, Windows and Linux/macOS setup, environment variables, migrations, local demo, and deployment.
- [ ] Document data flow, model/tool boundaries, approval sequence, sandbox assumptions, and known limitations.
- [ ] Add a presentation outline (10 minutes maximum) and optional demo video (5 minutes maximum).
- [ ] Prepare clean-clone instructions and ensure `.env`, media, SQLite databases, caches, and secrets are gitignored.
- [ ] Capture final task and attack logs and link them from the test results file.
- [ ] Verify competition deliverables and team constraints separately; these cannot be verified from code alone.

**Checks / exit criteria**

- [ ] Fresh clone can install, configure, migrate, run, register, complete a tuition demo, upload an invoice, inspect admin audit, and run T1/A1.
- [ ] All automated tests, task scenarios, attack scenarios, and Django deployment checks pass; evidence is recorded.
- [ ] Final demo is reproducible from documented commands.

## Working rule

Work one phase at a time. Before coding, identify its acceptance checks; after coding, run them and record command, outcome, and date in `test_results.md`. Update this checklist to `[x]` only when its exit criteria pass. Keep partial work as `[/]`, failed work as `[!]`, and unfinished requirements as `[ ]`.
