# Fundora Project Instructions

Use this guide for every Fundora implementation session. It explains how the project documents fit together and how to move work through the checklist with reliable test evidence.

## 1. Project files and authority

Read these files in this order before starting a new phase:

1. **`instruction.md`** — workflow and collaboration rules for implementing work.
2. **`idea.md`** — product scope, architecture constraints, locked choices, and competition requirements. Treat items marked locked and non-negotiable as binding. Do not silently change them.
3. **`build.md`** — ordered implementation checklist and acceptance criteria. This is the active work queue and status tracker.
4. **`test_results.md`** — current implementation/test baseline and evidence from completed phases. Check outstanding failures before choosing work.
5. **`README.md`**, `requirements.txt`, `.env.example`, and relevant application code — current setup and implementation details. These describe the current repository and may lag behind `idea.md`.

If the files disagree, follow `idea.md` for product and architecture, `build.md` for sequencing and acceptance criteria, and `instruction.md` for process. Record any conflict or missing decision in `test_results.md`; do not quietly rewrite a locked requirement. Ask the project owner only when the conflict prevents safe, useful progress.

## 2. Select work

1. Review the current git/workspace changes before editing; preserve unrelated work and secrets.
2. Review the latest test-results entry and outstanding failures.
3. Select the earliest incomplete, unblocked phase in `build.md`. Work on one phase at a time unless a dependency clearly requires a small prerequisite first.
4. Read the relevant portions of `idea.md`, the checklist acceptance criteria, and the current code before changing anything.
5. State the phase and its acceptance checks in a short progress update.
6. If an acceptance criterion is ambiguous, use the rules in `idea.md` and existing behavior to make a safe implementation choice. Record the assumption. Ask for clarification only when a decision materially changes product behavior, data handling, or a locked design choice.

## 3. Implement safely

- Keep financial decisions deterministic and in Django/sandbox code. The LLM may interpret, plan, and explain; it must not own money movement, approval tokens, compliance decisions, user tier, or access control.
- Only the specified `execute_transfer_plan` path may execute a transfer, and execution must stay inside the simulated sandbox.
- Require explicit authenticated user approval before execution. Recheck plan ownership, status, expiry, compliance, and idempotency in server-side code at execution time.
- Treat user messages, uploads, OCR output, provider output, and retrieved content as untrusted input. Validate tool arguments and uploaded files; mask private data; never log secrets or unmasked sensitive identifiers.
- Fail closed for approval, compliance, identity, provider, and document-validation failures. Explain the failure and offer a legitimate recovery path where possible.
- Keep `.env`, API keys, SMTP credentials, uploads, local databases, and generated runtime files out of version control.
- Do not add dependencies or frameworks that conflict with `idea.md`. Avoid network-dependent tests; mock provider and sandbox boundaries.
- Keep changes focused on the selected checklist items. Do not claim unsupported capabilities or change unrelated UI/setup behavior without documenting the reason.

## 4. Test every phase

Before implementation, identify the exact checks listed in that phase of `build.md`. Add or update automated tests alongside each behavior. Prefer isolated unit tests for rules and mocked integration tests for providers; add end-to-end scenario coverage where the checklist calls for it.

After implementation:

1. Run the focused test module(s) for changed behavior.
2. Run the full Django test suite explicitly with `python AI_Agent/manage.py test Agent sandbox`; a bare `manage.py test` currently discovers no tests because the project lives under `AI_Agent/`.
3. Run Django system checks and migration checks; create/apply migrations where needed.
4. Run the phase-specific task/attack scenario or manual smoke check listed in `build.md`.
5. Inspect the diff for secret leakage, accidental generated files, scope changes, and untested edge cases.
6. If a command cannot run, record it as `BLOCKED` or `NOT RUN`, with the reason. Never mark a phase complete just because implementation code exists.

Use the repository's actual Python environment and database configuration. State the exact commands and relevant configuration assumptions in the test log. Do not include secret values in commands copied into documentation or output.

## 5. Update progress records

For each completed implementation attempt:

1. Append a dated entry at the top of the `Subsequent runs` section in `test_results.md`.
2. Record the phase, exact commands/methods, PASS/FAIL/BLOCKED/NOT RUN, counts where available, and concise evidence.
3. Record known failures, limitations, and follow-up actions.
4. Update only the related `build.md` checkboxes: `[x]` when implementation and all listed checks pass, `[/]` for partial work, `[!]` for a blocking failure, and `[ ]` for untouched work.
5. Keep the test log and checklist consistent. A failed test or unverified acceptance criterion prevents `[x]`.

Do not erase old test evidence. Append new runs so progress and regressions remain visible.

## 6. Finish a work session

Before reporting completion:

- Review changed files and ensure only intended files changed.
- Confirm `build.md` statuses match the evidence in `test_results.md`.
- Report what was implemented, which checks passed or failed, and what phase should come next.
- Mention any behavior still simulated, unavailable, or dependent on credentials/services.
- Leave the app in a clear state (running or stopped) and say which it is when relevant.

## 7. Definition of done

The project is complete only when the final acceptance criteria in `build.md` pass: a clean setup and migration, registration and core workflows, tuition invoice planning, audited simulated execution, scripted task and attack runners, passing scenario evidence, deployment documentation, and a reproducible demo. Individual phases may be reported complete earlier only when their own exit criteria pass.
