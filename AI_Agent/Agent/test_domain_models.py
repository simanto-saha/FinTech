from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import AuditLogAdmin
from .models import Approval, AuditLog, Document, LedgerEntry, Plan, Session, University


class FinanceDomainModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='Strong-test-password-123',
        )
        self.other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='Strong-test-password-123',
        )
        self.session = Session.objects.create(user=self.user, user_type=Session.UserType.STUDENT)

    def make_plan(self, **overrides):
        values = {
            'session': self.session,
            'user': self.user,
            'target_amount': '45000.00',
            'target_ccy': 'CNY',
            'legs': [{'rail': 'demo-bank', 'amount': '45000.00', 'currency': 'CNY'}],
        }
        values.update(overrides)
        return Plan.objects.create(**values)

    def test_session_defaults_and_tier_bounds(self):
        session = Session.objects.create(user=self.user)

        self.assertEqual(session.tier, Session.Tier.SUGGEST)
        self.assertEqual(session.messages, [])
        self.assertEqual(session.user_type, '')

        session.tier = 4
        with self.assertRaises(ValidationError):
            session.full_clean()

    def test_document_and_plan_must_belong_to_session_owner(self):
        document = Document(
            user=self.other_user,
            session=self.session,
            file=ContentFile(b'demo invoice', name='invoice.png'),
            doc_type=Document.Type.UNIVERSITY_FEE_INVOICE,
        )
        with self.assertRaises(ValidationError) as document_error:
            document.full_clean()
        self.assertIn('session', document_error.exception.message_dict)

        plan = Plan(
            session=self.session,
            user=self.other_user,
            target_amount='100.00',
            target_ccy='USD',
        )
        with self.assertRaises(ValidationError) as plan_error:
            plan.full_clean()
        self.assertIn('session', plan_error.exception.message_dict)

    def test_plan_and_approval_defaults_and_owner_validation(self):
        plan = self.make_plan()
        approval = Approval.objects.create(
            plan=plan,
            user=self.user,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        self.assertEqual(plan.status, Plan.Status.DRAFT)
        self.assertEqual(approval.status, Approval.Status.PENDING)
        self.assertEqual(len(approval.token), 64)
        self.assertNotEqual(approval.token, Approval.objects.create(
            plan=plan,
            user=self.user,
            expires_at=timezone.now() + timedelta(minutes=5),
        ).token)

        invalid_approval = Approval(
            plan=plan,
            user=self.other_user,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        with self.assertRaises(ValidationError) as error:
            invalid_approval.full_clean()
        self.assertIn('user', error.exception.message_dict)

    def test_document_confidence_currency_and_positive_amount_validators(self):
        document = Document(
            user=self.user,
            session=self.session,
            file=ContentFile(b'demo invoice', name='invoice.png'),
            confidence=1.1,
        )
        with self.assertRaises(ValidationError) as confidence_error:
            document.full_clean()
        self.assertIn('confidence', confidence_error.exception.message_dict)

        invalid_plan = Plan(
            session=self.session,
            user=self.user,
            target_amount='0.00',
            target_ccy='USD',
        )
        with self.assertRaises(ValidationError):
            invalid_plan.full_clean()

        ledger_entry = LedgerEntry(
            user=self.user,
            entry_type='transfer',
            amount='12.00',
            currency='US$',
            category='tuition',
        )
        with self.assertRaises(ValidationError) as currency_error:
            ledger_entry.full_clean()
        self.assertIn('currency', currency_error.exception.message_dict)

    def test_audit_and_ledger_records_capture_domain_events(self):
        event = AuditLog.objects.create(
            session=self.session,
            tier=Session.Tier.SUGGEST,
            action='plan_created',
            status='ok',
            meta={'simulated': True},
        )
        ledger_entry = LedgerEntry.objects.create(
            user=self.user,
            entry_type='transfer',
            amount='20.00',
            currency='USD',
            category='tuition',
            status=LedgerEntry.Status.PLANNED,
        )

        self.assertTrue(event.meta['simulated'])
        self.assertEqual(event.session, self.session)
        self.assertEqual(ledger_entry.user, self.user)
        self.assertEqual(ledger_entry.status, LedgerEntry.Status.PLANNED)
        self.assertIsNotNone(event.ts)
        self.assertIsNotNone(ledger_entry.ts)

    def test_database_constraints_reject_invalid_tiers_and_amounts(self):
        invalid_creations = (
            lambda: Session.objects.create(user=self.user, tier=4),
            lambda: AuditLog.objects.create(
                session=self.session,
                tier=4,
                action='invalid_tier',
                status='rejected',
            ),
            lambda: self.make_plan(target_amount='0.00'),
            lambda: self.make_plan(total_cost='-1.00'),
            lambda: LedgerEntry.objects.create(
                user=self.user,
                entry_type='transfer',
                amount='0.00',
                currency='USD',
                category='tuition',
            ),
            lambda: Document.objects.create(
                user=self.user,
                session=self.session,
                file='documents/invalid.png',
                confidence=1.1,
            ),
        )
        for create_invalid in invalid_creations:
            with self.subTest(create_invalid=create_invalid):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    create_invalid()

    def test_audit_session_timestamp_index_exists(self):
        matching_indexes = [
            index for index in AuditLog._meta.indexes
            if index.fields == ['session', 'ts']
        ]

        self.assertEqual(len(matching_indexes), 1)
        self.assertEqual(matching_indexes[0].name, 'agent_audit_sess_ts_idx')

    def test_university_slug_is_unique(self):
        University.objects.create(slug='szu', name='Shenzhen University', country='CN')
        duplicate = University(slug='szu', name='Another University', country='CN')

        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class AuditLogAdminTests(TestCase):
    def test_all_finance_models_are_registered_with_search_and_filters(self):
        finance_models = (Session, Document, Plan, Approval, AuditLog, LedgerEntry, University)

        for model in finance_models:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertTrue(model_admin.list_display)
                self.assertTrue(model_admin.list_filter)
                self.assertTrue(model_admin.search_fields)

    def test_audit_log_is_read_only_in_admin(self):
        model_admin = AuditLogAdmin(AuditLog, admin.site)
        request = RequestFactory().get('/admin/Agent/auditlog/')
        request.user = User(is_active=True, is_staff=True, is_superuser=True)

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertIn('meta', model_admin.get_readonly_fields(request))

    def test_admin_can_view_audit_list_but_cannot_add_records(self):
        admin_user = User.objects.create_superuser(
            username='admin@example.com',
            email='admin@example.com',
            password='Strong-admin-password-123',
        )
        self.client.force_login(admin_user)

        list_response = self.client.get(reverse('admin:Agent_auditlog_changelist'))
        add_response = self.client.get(reverse('admin:Agent_auditlog_add'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(add_response.status_code, 403)
