"""
Fundora — Unified Presentation & Live Browser Demonstration
Runs a complete, synchronized walkthrough for FinTechathon 2026 (Topic C):
  Act 1: Presentation Pitch Deck (Slides 1–7)
  Act 2: Live Browser Demonstration (Landing, Login, AI Tuition Split, Nonce Approval, Django Admin Audit)
  Act 3: Conclusion & Pitch Summary (Slide 8 / Q&A)

Features:
- Live headed browser execution (visible on screen) or headless mode
- Natural human typing speed and highlighted clicks
- Real-time tuition splitting respecting regulatory caps
- Cryptographic single-use approval gate authorization
- Live Django Admin audit inspection (Plans, Approvals, Double-Entry Ledger, Audit Logs)
- Automatic HD video recording saved to docs/demo_video/
"""

import os
import sys
import time
import shutil
import argparse
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

SERVER_URL = "http://127.0.0.1:8000"
VIDEO_DIR = Path(__file__).resolve().parent.parent / "docs" / "demo_video"
PRESENTATION_PATH = Path(__file__).resolve().parent.parent / "docs" / "presentation" / "index.html"


def ensure_server():
    """Verify Django server is running."""
    try:
        urllib.request.urlopen(f"{SERVER_URL}/", timeout=3)
        print("✓ Live Django server detected at", SERVER_URL)
        return True
    except Exception:
        print(f"✗ Error: Django server is not running on {SERVER_URL}.")
        print("Please run: python AI_Agent/manage.py runserver in another terminal first.")
        sys.exit(1)


def prepare_demo_environment():
    """
    Ensure the sandbox database has the expected accounts, verified KYC documents,
    and no conflicting stale pending plans so the demo runs deterministically.
    """
    print("• Initializing sandbox database & student KYC records...")
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AI_Agent.settings")
    ai_agent_path = str(Path(__file__).resolve().parent.parent / "AI_Agent")
    if ai_agent_path not in sys.path:
        sys.path.insert(0, ai_agent_path)
    django.setup()

    from django.contrib.auth import get_user_model
    from Agent.models import Session, Plan, Approval, Document
    User = get_user_model()

    # 1. Student demo account (demo@example.com)
    student = User.objects.filter(email="demo@example.com").first()
    if not student:
        student = User.objects.filter(username="demo@example.com").first()
    if not student:
        student = User.objects.create(
            username="demo@example.com",
            email="demo@example.com",
            first_name="Alex",
            last_name="Rahman",
        )
    student.username = "demo@example.com"
    student.email = "demo@example.com"
    student.set_password("DemoStudent2026!")
    student.save()

    # Clean up any stray duplicate user named 'demo'
    User.objects.filter(username="demo").exclude(pk=student.pk).delete()

    # 2. Superuser admin account
    admin_user = User.objects.filter(username="admin").first()
    if not admin_user:
        admin_user = User.objects.create(
            username="admin",
            email="admin@example.com",
            is_staff=True,
            is_superuser=True,
        )
    admin_user.set_password("Admin2026!")
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()

    # 3. Clean session for student
    session = Session.objects.filter(user=student).first()
    if not session:
        session = Session.objects.create(user=student, corridor="BD-CN", tier=2)
    session.messages = []
    session.tier = 2
    session.corridor = "BD-CN"
    session.save()

    # 4. Verified KYC documents for student
    for doc_type in ["university_fee_invoice", "admission_letter", "student_visa"]:
        doc = Document.objects.filter(user=student, doc_type=doc_type).first()
        if not doc:
            doc = Document.objects.create(user=student, session=session, doc_type=doc_type, verified=True)
        else:
            doc.verified = True
            doc.session = session
            doc.save()

    # 5. Cancel previous pending plans to prevent duplicate warnings
    Plan.objects.filter(user=student, status="pending").update(status="cancelled")
    Approval.objects.filter(user=student, status="pending").update(status="expired")

    print("✓ Sandbox database ready (demo@example.com / DemoStudent2026! & admin / Admin2026!)")


def highlight_and_click(page: Page, selector: str, description: str = ""):
    """Visually highlights an element before clicking it for demo clarity."""
    if description:
        print(f"  ➔ [Action] {description}")
    el = page.locator(selector).first
    el.scroll_into_view_if_needed()
    try:
        el.evaluate("""(node) => {
            node.style.outline = '3px solid #14b8a6';
            node.style.outlineOffset = '3px';
            node.style.transition = 'all 0.2s ease';
            setTimeout(() => { node.style.outline = ''; }, 600);
        }""")
    except Exception:
        pass
    time.sleep(0.4)
    el.click()


def run_pitch_and_demo(
    headless: bool = False,
    record: bool = True,
    slow_mo: int = 250,
    slide_delay: float = 7.0,
    skip_slides: bool = False,
    skip_demo: bool = False,
):
    ensure_server()
    prepare_demo_environment()
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 75)
    print("  FUNDORA: COMPLETE COMPETITION PITCH & LIVE DEMONSTRATION")
    print("  Shenzhen International FinTech Competition • Topic C")
    print("=" * 75)
    print(f"• Mode: {'Headless (Background)' if headless else 'Headed (Visible on Screen)'}")
    print(f"• Video Recording: {'Enabled (docs/demo_video/)' if record else 'Disabled'}")
    print(f"• Slide Pace: {slide_delay}s per slide")
    print(f"• Skip Slides: {skip_slides} | Skip Live Demo: {skip_demo}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        )

        context_kwargs = {
            "viewport": {"width": 1600, "height": 900},
            "locale": "en-US",
        }
        if record:
            context_kwargs["record_video_dir"] = str(VIDEO_DIR)
            context_kwargs["record_video_size"] = {"width": 1600, "height": 900}

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        # =====================================================================
        # ACT 1: PRESENTATION PITCH DECK (SLIDES 1 TO 7)
        # =====================================================================
        if not skip_slides:
            print("\n" + "—" * 75)
            print("  ACT 1: PITCH DECK PRESENTATION (Slides 1–7)")
            print("—" * 75)
            page.goto(PRESENTATION_PATH.as_uri(), wait_until="networkidle")
            time.sleep(1.0)

            slide_titles = [
                "Slide 1: Title & Architectural Principle ('LLM reasons. Deterministic code decides.')",
                "Slide 2: The Problem (Cross-Border Student Financial Friction)",
                "Slide 3: System Architecture (Fail-Closed Zero-Trust Separation)",
                "Slide 4: The 4 Financial Pillars (Tasks T1–T3)",
                "Slide 5: Dialogue Resilience & Rail Failover (Tasks T4–T5)",
                "Slide 6: Security Defense Benchmark (100% Defense Against A1–A4)",
                "Slide 7: Evaluator Verification & Tamper-Evident Admin Audit",
            ]

            for idx, title in enumerate(slide_titles, start=1):
                print(f"  [Slide {idx}/8] {title}")
                if idx > 1:
                    page.keyboard.press("ArrowRight")
                time.sleep(slide_delay)

        # =====================================================================
        # ACT 2: LIVE PRODUCT DEMONSTRATION
        # =====================================================================
        if not skip_demo:
            print("\n" + "—" * 75)
            print("  ACT 2: LIVE PRODUCT DEMONSTRATION (Real Django Instance)")
            print("—" * 75)

            # Scene 1: Landing Page & Currency Converter
            print("\n[Scene 1/5] Landing Page & Fluid FX Converter...")
            page.goto(f"{SERVER_URL}/", wait_until="networkidle")
            time.sleep(1.2)

            converter = page.locator(".conv")
            if converter.is_visible():
                converter.scroll_into_view_if_needed()
                time.sleep(0.8)

                amt_input = page.locator("#amtF")
                if amt_input.is_visible():
                    print("  ➔ Simulating currency conversion: 750,000 BDT...")
                    amt_input.click()
                    amt_input.fill("")
                    amt_input.type("750000", delay=40)
                    time.sleep(0.8)

                swap_btn = page.locator("#swapBtn")
                if swap_btn.is_visible():
                    print("  ➔ Interacting with spring swap button...")
                    highlight_and_click(page, "#swapBtn", "Clicking Currency Swap")
                    time.sleep(1.0)
                    highlight_and_click(page, "#swapBtn", "Reversing Currency Swap")
                    time.sleep(1.0)

            # Scene 2: Student Sign-in
            print("\n[Scene 2/5] Authenticating as Student (Alex Rahman)...")
            highlight_and_click(page, 'button[data-open-modal="login-modal"]', "Opening Login Modal")
            page.wait_for_selector("#login-modal[open]", timeout=4000)
            time.sleep(0.5)

            print("  ➔ Entering credentials: demo@example.com...")
            email_field = page.locator('#login-modal input[name="email"]')
            email_field.click()
            email_field.type("demo@example.com", delay=35)

            pwd_field = page.locator('#login-modal input[name="password"]')
            pwd_field.click()
            pwd_field.type("DemoStudent2026!", delay=35)
            time.sleep(0.5)

            highlight_and_click(page, '#login-form button[type="submit"]', "Submitting Sign In")
            page.wait_for_url("**/dashboard/**", timeout=8000)
            print("  ✓ Successfully logged into Student Dashboard!")
            time.sleep(1.5)

            # Scene 3: Tuition Split (Scenario T1)
            print("\n[Scene 3/5] Executing Scenario T1: Student Tuition Split (BD -> CN)...")
            chat_panel = page.locator("#panel-chat")
            chat_panel.scroll_into_view_if_needed()

            prompt_input = page.locator('textarea[name="question_text"]')
            prompt_text = "I need to pay 45,000 CNY tuition at Shenzhen University from Bangladesh."
            print(f"  ➔ Student prompt: \"{prompt_text}\"")

            prompt_input.click()
            prompt_input.type(prompt_text, delay=35)
            time.sleep(0.6)

            highlight_and_click(page, '#assistant-question-form .composer-submit', "Submitting to Fundora Agent Loop")

            print("  ➔ Real AI reasoning loop in progress (inspecting caps, rails & FX)...")
            page.wait_for_selector(".assistant-message.assistant", timeout=35000)
            time.sleep(1.5)

            print("  ✓ Structured AI Response received!")
            app_card = page.locator(".approval-card")
            app_card.wait_for(state="visible", timeout=25000)
            app_card.scroll_into_view_if_needed()
            print("  ✓ Cryptographic Approval Card rendered on screen with Single-Use Nonce & TTL!")
            time.sleep(3.0)

            # Scene 4: Authorize Payment
            print("\n[Scene 4/5] Authorizing Payment via Cryptographic Gate...")
            approve_btn = page.locator('.approval-btn[data-decision="approve"]')
            highlight_and_click(page, '.approval-btn[data-decision="approve"]', "Clicking 'Authorize Payment'")

            page.wait_for_selector("text=Successfully Authorized", timeout=12000)
            print("  ✓ Payment Authorized! Real ledger entry written to sandbox database.")
            time.sleep(3.0)

            # Scene 5: Django Admin Live Database Audit
            print("\n[Scene 5/5] Inspecting Live Django Admin Audit Records...")
            page.goto(f"{SERVER_URL}/admin/", wait_until="networkidle")
            time.sleep(0.8)

            if page.locator('input[name="username"]').is_visible():
                print("  ➔ Logging into Django Admin as superuser...")
                page.locator('input[name="username"]').fill("admin")
                page.locator('input[name="password"]').fill("Admin2026!")
                highlight_and_click(page, 'input[type="submit"]', "Submitting Admin Login")
                page.wait_for_url("**/admin/**", timeout=6000)
                time.sleep(1.0)

            # 1. Plans
            print("  ➔ Inspecting database Plans...")
            page.goto(f"{SERVER_URL}/admin/Agent/plan/", wait_until="networkidle")
            time.sleep(1.8)
            first_plan = page.locator("#result_list tbody tr th a").first
            if first_plan.is_visible():
                highlight_and_click(page, "#result_list tbody tr th a", "Opening Executed Plan Detail")
                time.sleep(2.5)

            # 2. Approvals
            print("  ➔ Inspecting cryptographic Approvals...")
            page.goto(f"{SERVER_URL}/admin/Agent/approval/", wait_until="networkidle")
            time.sleep(1.8)
            first_app = page.locator("#result_list tbody tr th a").first
            if first_app.is_visible():
                highlight_and_click(page, "#result_list tbody tr th a", "Opening Approval Nonce Record")
                time.sleep(2.5)

            # 3. Ledger Entries
            print("  ➔ Inspecting double-entry Ledger Entries...")
            page.goto(f"{SERVER_URL}/admin/Agent/ledgerentry/", wait_until="networkidle")
            time.sleep(1.8)
            first_ledger = page.locator("#result_list tbody tr th a").first
            if first_ledger.is_visible():
                highlight_and_click(page, "#result_list tbody tr th a", "Opening Ledger Entry Detail")
                time.sleep(2.5)

            # 4. Audit Logs
            print("  ➔ Inspecting immutable Audit Logs...")
            page.goto(f"{SERVER_URL}/admin/Agent/auditlog/", wait_until="networkidle")
            time.sleep(2.0)
            first_log = page.locator("#result_list tbody tr th a").first
            if first_log.is_visible():
                highlight_and_click(page, "#result_list tbody tr th a", "Opening Security Audit Log Detail")
                time.sleep(2.5)

        # =====================================================================
        # ACT 3: CONCLUSION & PITCH SUMMARY (SLIDE 8)
        # =====================================================================
        if not skip_slides:
            print("\n" + "—" * 75)
            print("  ACT 3: CONCLUSION & PITCH SUMMARY (Slide 8)")
            print("—" * 75)
            page.goto(PRESENTATION_PATH.as_uri(), wait_until="networkidle")
            time.sleep(1.0)
            # Jump directly to Slide 8
            page.evaluate("currentSlide = 8; updateSlide();")
            print("  [Slide 8/8] Why Fundora Wins Topic C / Q&A")
            time.sleep(slide_delay + 2.0)

        # Close page and context to finish video
        print("\n" + "=" * 75)
        print("  PRESENTATION & LIVE DEMONSTRATION COMPLETE")
        print("=" * 75)
        video = page.video if record else None
        page.close()
        context.close()
        browser.close()

        if video:
            try:
                raw_path = video.path()
                if raw_path and os.path.exists(raw_path):
                    final_mp4 = VIDEO_DIR / "Fundora_Live_Browser_Demo.webm"
                    if final_mp4.exists():
                        try:
                            final_mp4.unlink()
                        except Exception:
                            pass
                    shutil.copy2(raw_path, str(final_mp4))
                    print(f"\n✓ Video saved successfully to: {final_mp4}")
                # Clean up intermediate raw playwright video chunks
                for raw_chunk in VIDEO_DIR.glob("page@*.webm"):
                    try:
                        raw_chunk.unlink()
                    except Exception:
                        pass
            except Exception as e:
                print(f"\nNotice: Video recorded at: {VIDEO_DIR} ({e})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fundora Pitch & Live Browser Demo")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (default: False/headed)")
    parser.add_argument("--no-record", action="store_true", help="Disable video recording")
    parser.add_argument("--slow-mo", type=int, default=250, help="Playwright slow-mo delay in ms (default: 250)")
    parser.add_argument("--slide-delay", type=float, default=6.5, help="Seconds to linger on each presentation slide (default: 6.5s)")
    parser.add_argument("--skip-slides", action="store_true", help="Skip presentation slides and run only the live platform demo")
    parser.add_argument("--skip-demo", action="store_true", help="Skip live platform demo and run only presentation slides")
    args = parser.parse_args()

    run_pitch_and_demo(
        headless=args.headless,
        record=not args.no_record,
        slow_mo=args.slow_mo,
        slide_delay=args.slide_delay,
        skip_slides=args.skip_slides,
        skip_demo=args.skip_demo,
    )
