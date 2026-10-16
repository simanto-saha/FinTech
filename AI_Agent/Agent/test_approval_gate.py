import json
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from Agent.models import Approval, AuditLog, LedgerEntry, Plan, Session
from Agent import tools


class ApprovalGateAndEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="approver@example.com",
            email="approver@example.com",
            password="Strong-Password-123",
        )
        self.other_user = User.objects.create_user(
            username="other_approver@example.com",
            email="other_approver@example.com",
            password="Strong-Password-123",
        )
        self.session = Session.objects.create(user=self.user, corridor="BD-CN")
        self.plan = Plan.objects.create(
            session=self.session,
            user=self.user,
            target_amount=Decimal("45000.00"),
            target_ccy="CNY",
            total_cost=Decimal("755000.00"),
            legs=[
                {"leg_index": 0, "rail_id": "bdt_bank_wire", "amount_from": "375000.00", "target_amount": "22500.00", "target_ccy": "CNY"},
                {"leg_index": 1, "rail_id": "bdt_bank_wire", "amount_from": "375000.00", "target_amount": "22500.00", "target_ccy": "CNY"},
            ],
            status=Plan.Status.PENDING,
        )
        self.approval = Approval.objects.create(
            plan=self.plan,
            user=self.user,
            expires_at=timezone.now() + timedelta(seconds=300),
            status=Approval.Status.PENDING,
        )

    def test_approve_api_unauthenticated_rejected(self):
        response = self.client.post(
            reverse("approve_api"),
            data=json.dumps({"token": self.approval.token, "decision": "approve"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_approve_api_wrong_owner_rejected(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("approve_api"),
            data=json.dumps({"token": self.approval.token, "decision": "approve"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Access denied", response.json()["error"])

    def test_approve_api_expired_token_rejected(self):
        self.approval.expires_at = timezone.now() - timedelta(seconds=10)
        self.approval.save()

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("approve_api"),
            data=json.dumps({"token": self.approval.token, "decision": "approve"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["error"].lower())

    def test_approve_api_success_updates_plan_and_token(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("approve_api"),
            data=json.dumps({"token": self.approval.token, "decision": "approve"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["status"], "approved")

        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, Approval.Status.USED)

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, Plan.Status.APPROVED)
        self.assertIsNotNone(self.plan.approved_at)

        # Verify audit log entry
        audit = AuditLog.objects.filter(session=self.session, action="plan_approved").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.tier, Session.Tier.EXECUTE_WITH_APPROVAL)

    def test_approve_api_reject_cancels_plan(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("approve_api"),
            data=json.dumps({"token": self.approval.token, "decision": "reject"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")

        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, Approval.Status.USED)

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, Plan.Status.CANCELLED)

    def test_approve_api_already_used_token_rejected(self):
        self.approval.status = Approval.Status.USED
        self.approval.save()

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("approve_api"),
            data=json.dumps({"token": self.approval.token, "decision": "approve"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("no longer valid", response.json()["error"].lower())

    def test_execute_transfer_plan_requires_approval_and_succeeds(self):
        # 1. Reject execution while still pending
        res_pending = tools.execute_tool("execute_transfer_plan", {"plan_id": self.plan.id}, self.session)
        self.assertEqual(res_pending["status"], "failed")

        # 2. Approve via API
        self.client.force_login(self.user)
        self.client.post(
            reverse("approve_api"),
            data=json.dumps({"token": self.approval.token, "decision": "approve"}),
            content_type="application/json",
        )

        # 3. Now execution succeeds
        res_exec = tools.execute_tool("execute_transfer_plan", {"plan_id": self.plan.id}, self.session)
        self.assertEqual(res_exec["status"], "executed")
        self.assertTrue(res_exec["receipt_id"].startswith(f"REC-{self.plan.id}-"))
        self.assertTrue(len(res_exec["audit_hash"]) == 64)

        # 4. Check ledger entries created
        entries = LedgerEntry.objects.filter(user=self.user, status=LedgerEntry.Status.EXECUTED)
        self.assertEqual(entries.count(), 2)

        # 5. Idempotent re-execution does not duplicate ledger entries
        res_repeat = tools.execute_tool("execute_transfer_plan", {"plan_id": self.plan.id}, self.session)
        self.assertEqual(res_repeat["status"], "already_executed")
        self.assertEqual(LedgerEntry.objects.filter(user=self.user).count(), 2)

    def test_approval_token_never_reaches_llm_tool_result(self):
        # Create draft plan and request approval
        draft_plan = Plan.objects.create(
            session=self.session,
            user=self.user,
            target_amount=Decimal("1000.00"),
            target_ccy="CNY",
            status=Plan.Status.DRAFT,
        )
        tool_result = tools.execute_tool(
            "request_human_approval",
            {"plan_id": draft_plan.id, "summary": "Confirm transfer"},
            self.session,
        )
        # Approval token must not be in tool result returned to LLM
        self.assertNotIn("token", tool_result)
        self.assertTrue(tool_result["requires_approval"])

    def test_status_api_returns_dashboard_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("status_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_simulated"])
        self.assertEqual(data["user"], self.user.username)
        self.assertTrue(len(data["balances"]) > 0)
        self.assertTrue(len(data["recent_plans"]) > 0)

