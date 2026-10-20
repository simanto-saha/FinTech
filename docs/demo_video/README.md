# Fundora — Live Browser Demonstration & Video

This directory contains automated demonstration artifacts recorded directly against the running Django instance using **Playwright**.

## How to Run the Live Browser Demo

You can run the full browser demo live on your screen or in the background:

### Option 1: Live Headed Mode (Watch Browser on Screen)
Launches Chromium, opens maximized, simulates real keystrokes and highlighted button interactions:
```bash
python scripts/browser_demo.py
```

### Option 2: Headless Mode (Background Recording)
Runs completely in the background without opening a browser window:
```bash
python scripts/browser_demo.py --headless
```

### Generated Video Artifact
- **File:** `Fundora_Live_Browser_Demo.webm`
- **Resolution:** 1600 × 900 HD
- **Contents:**
  1. **Landing Page:** Interactive currency converter and spring swap animation.
  2. **Authentication:** Student sign-in (`demo@example.com` / `DemoStudent2026!`).
  3. **AI Tuition Split (T1):** Real agent loop reasoning over daily caps, corridor rails, and student balances.
  4. **Cryptographic Approval Gate:** Single-use nonce authorization writing real double-entry ledger records.
  5. **Django Admin Audit:** Verification of database Plans, Approvals, Ledger Entries, and SHA-256 Audit Logs.
  6. **Slide Deck Finale:** Automated walkthrough of the competition presentation deck.
