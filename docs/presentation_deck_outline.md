# Fundora — Presentation Deck Outline (10-Minute Competition Pitch)

**Event:** 2026 Shenzhen International FinTech Competition (WeBank / Xili Lake FinTech College Student Challenge)  
**Track:** International AI Track — *"AI as a Financial Participant"*  
**Topic:** Topic C: Cross-border & Student Finance Assistant  
**Presentation Time:** 10 Minutes Max (Recommended: 8 min presentation + 2 min Q&A)

---

## Slide 1: Title Slide (0:00 - 0:45)
- **Title:** Fundora — The Compliant AI Financial Participant for Cross-Border Students
- **Subtitle:** Autonomous Multi-Leg Remittance, Intelligent Tuition Invoicing & Fail-Closed Security
- **Team Info:** Team Name, Institution, Team Members
- **Core Value Proposition:** An AI financial agent that reads documents, plans multi-currency routes, handles regulatory caps, and executes with cryptographic human approval.

---

## Slide 2: The International Student Problem (0:45 - 2:00)
- **Real-World Pain Points (The 4 Pillars of Topic C):**
  1. **Remittances & Regulatory Caps:** Bangladesh Bank, RBI (LRS), and Philippines OFW regulations impose daily/annual outward transfer limits. High tuition fees trigger silent transaction blocks or extortionate emergency fees.
  2. **Tuition Invoicing Chaos:** Fragmented university channels (UnionPay, Bank of China designated accounts, Flywire, SWIFT) with varying fees and delays.
  3. **No Destination Credit History:** Students arrive with zero local credit history, forced to pay 6–12 months of upfront rent deposits to private landlords.
  4. **Multi-Currency FX Shocks:** Volatility between home currency allowance (BDT, INR, PHP) and destination currency (CNY, GBP, AED) depletes runway unexpectedly.

---

## Slide 3: Architecture & Core Philosophy (2:00 - 3:30)
- **Our Non-Negotiable Rule:**
  > *"LLM reasons. Deterministic code decides."*
- **Architecture Highlights:**
  - **Monolithic Django 5.2:** Async views, zero fragile auto-agent frameworks.
  - **Hand-Written Reasoning Loop:** Context assembly on every iteration (<6 KB), structured JSON output envelope with `grounded_in_context` honesty check.
  - **16 Locked Tools:** Strict schema validation with zero hallucinated tool calls.
  - **Execution Gate (§15):** The model never receives approval tokens; funds only move via deterministic single-use, 300s TTL cryptographic gates.

---

## Slide 4: Task Completion & The 4 Pillars in Action (3:30 - 5:30)
*Mapping to the 40% Task Completion Rubric:*
- **Pillar 1: Remittances (T1 & T2):**
  - **T1:** Student tuition BD $\to$ CN (45,000 CNY / 750,000 BDT) automatically detected as exceeding the 500,000 BDT daily cap $\to$ split into 2 compliant tranches $\to$ human approved $\to$ executed.
  - **T2:** Worker remittance PH $\to$ AE (2,000 AED / 30,000 PHP) executed via optimal single leg.
- **Pillar 2: Tuition Invoicing (T3):**
  - Invoice uploaded $\to$ OCR entity extraction $\to$ university payment channel comparison $\to$ plan generation $\to$ double-entry ledger linkage with verified document reference.
- **Pillar 3: Innovation & Fallback Recovery (T4 & T5):**
  - **T4 (Mid-Flow Correction):** User switches university mid-conversation (SZU $\to$ Tsinghua); context is preserved without data loss; obsolete plan safely cancelled.
  - **T5 (Rail Failure Recovery):** Simulated rail failure on Leg 2 $\to$ zero money lost $\to$ automatic circuit break $\to$ re-routed to secondary rail (`unionpay_intl`) $\to$ fresh approval $\to$ safe completion.
- **Pillars 3 & 4: Alternative Credit & Multi-Currency Management:**
  - Day-to-day spending envelopes, FX devaluation shock stress-testing (5%, 10%, 15% volatility runway drops), and Verifiable Landlord Certificate to waive 6–12 month rental deposits.

---

## Slide 5: Security Defense & Attack Resilience (5:30 - 7:00)
*Mapping to the 30% Security & Compliance Rubric:*
- **The 4 Attack Suites (A1–A4) — 100% Neutralized:**
  - **A1 (Induced Transfer Defense):** Adversarial prompts cannot force fund transfers; execution gate requires external cryptographic UI confirmation.
  - **A2 (Data Extraction Defense):** Sensitive PII (passports, accounts, cards) is strictly masked (`••••`). Approval tokens **never** reach the LLM or context.
  - **A3 (Privilege Escalation Defense):** `Session.tier` is code-owned and immutable from prompts.
  - **A4 (Document Prompt Injection Defense):** Malicious document text is bounded within `<untrusted_document>` tags, analyzed by proactive injection scanners, and strictly isolated as data.

---

## Slide 6: Automated Verification & Auditability (7:00 - 8:00)
- **163 Automated Tests (100% Passing):**
  - `python AI_Agent/manage.py run_task all` $\to$ All 5 tasks PASS.
  - `python AI_Agent/manage.py run_attack all` $\to$ All 4 attacks DEFENDED.
  - Full application test suite running in 99 seconds.
- **Live Audit Trail:**
  - Judges can open `/admin/` and review tamper-evident SHA-256 audit hashes, approval lifecycles, and double-entry ledger entries.

---

## Slide 7: Conclusion & Summary (8:00 - 8:30)
- **Why Fundora Wins Topic C:**
  1. Complete coverage of the 4 Topic C pillars.
  2. 100% reproducible tasks (T1–T5) and attack defenses (A1–A4).
  3. Production-grade monolithic architecture with fail-closed deterministic security.
- **Thank you! Questions & Live Demo.**

