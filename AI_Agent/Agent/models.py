from django.db import models
from django.contrib.auth.models import User 
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.core.exceptions import ValidationError
import secrets


class Session(models.Model):
    class Tier(models.IntegerChoices):
        READ_ONLY = 0, 'Read only'
        SUGGEST = 1, 'Suggest and plan'
        EXECUTE_WITH_APPROVAL = 2, 'Execute with approval'
        RECURRING_AUTOMATION = 3, 'Recurring automation'

    class UserType(models.TextChoices):
        STUDENT = 'student', 'Student'
        WORKER = 'worker', 'Worker'
        TOURIST = 'tourist', 'Tourist'
        BUSINESS = 'business', 'Business'
        FAMILY = 'family', 'Family'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fundora_sessions')
    messages = models.JSONField(default=list, blank=True)
    tier = models.PositiveSmallIntegerField(
        choices=Tier.choices,
        default=Tier.SUGGEST,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
    )
    user_type = models.CharField(max_length=20, choices=UserType.choices, blank=True)
    corridor = models.CharField(max_length=5, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_session'
        ordering = ['-updated_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(tier__gte=0, tier__lte=3), name='agent_session_tier_range'),
        ]

    def __str__(self):
        return f'Session {self.pk} ({self.user})'


class Document(models.Model):
    class Type(models.TextChoices):
        UNIVERSITY_FEE_INVOICE = 'university_fee_invoice', 'University fee invoice'
        UTILITY_BILL = 'utility_bill', 'Utility bill'
        RENT_INVOICE = 'rent_invoice', 'Rent invoice'
        PHONE_BILL = 'phone_bill', 'Phone bill'
        ADMISSION_LETTER = 'admission_letter', 'Admission letter'
        PASSPORT = 'passport', 'Passport'
        VISA = 'visa', 'Visa'
        SCHOLARSHIP_LETTER = 'scholarship_letter', 'Scholarship letter'
        RECEIPT = 'receipt', 'Receipt'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fundora_documents')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='documents/%Y/%m/')
    doc_type = models.CharField(max_length=40, choices=Type.choices, blank=True)
    extracted = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_document'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(confidence__gte=0.0, confidence__lte=1.0),
                name='agent_document_confidence_range',
            ),
        ]

    def clean(self):
        super().clean()
        if self.session_id and self.user_id and self.session.user_id != self.user_id:
            raise ValidationError({'session': 'The document session must belong to the document owner.'})

    def __str__(self):
        return f'{self.get_doc_type_display() or "Document"} #{self.pk}'


class Plan(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING = 'pending', 'Pending approval'
        APPROVED = 'approved', 'Approved'
        EXECUTED = 'executed', 'Executed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='plans')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fundora_plans')
    legs = models.JSONField(default=list, blank=True)
    target_amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0.01)])
    target_ccy = models.CharField(max_length=3, validators=[RegexValidator(r'^[A-Z]{3}$')])
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    approved_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_plan'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(target_amount__gt=0), name='agent_plan_target_positive'),
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name='agent_plan_cost_nonnegative'),
        ]

    def clean(self):
        super().clean()
        if self.session_id and self.user_id and self.session.user_id != self.user_id:
            raise ValidationError({'session': 'The plan session must belong to the plan owner.'})

    def __str__(self):
        return f'{self.target_amount} {self.target_ccy} ({self.get_status_display()})'


def _new_approval_token():
    return secrets.token_urlsafe(48)


class Approval(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        USED = 'used', 'Used'
        EXPIRED = 'expired', 'Expired'

    token = models.CharField(primary_key=True, max_length=64, default=_new_approval_token, editable=False)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='approvals')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fundora_approvals')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agent_approval'
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.plan_id and self.user_id and self.plan.user_id != self.user_id:
            raise ValidationError({'user': 'The approval user must own the plan.'})

    def __str__(self):
        return f'Approval for plan {self.plan_id} ({self.get_status_display()})'


class AuditLog(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='audit_events')
    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    tier = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    action = models.CharField(max_length=100)
    status = models.CharField(max_length=32)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'agent_audit_log'
        ordering = ['-ts']
        indexes = [models.Index(fields=['session', 'ts'], name='agent_audit_sess_ts_idx')]
        constraints = [
            models.CheckConstraint(condition=models.Q(tier__gte=0, tier__lte=3), name='agent_audit_tier_range'),
        ]

    def __str__(self):
        return f'{self.action} ({self.status}) at {self.ts}'


class LedgerEntry(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        EXECUTED = 'executed', 'Executed'
        FAILED = 'failed', 'Failed'
        VOID = 'void', 'Void'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fundora_ledger_entries')
    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    entry_type = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, validators=[RegexValidator(r'^[A-Z]{3}$')])
    category = models.CharField(max_length=64)
    counterparty = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        related_name='ledger_entries',
        null=True,
        blank=True,
    )
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'agent_ledger_entry'
        ordering = ['-ts']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='agent_ledger_amount_positive'),
        ]

    def __str__(self):
        return f'{self.amount} {self.currency} — {self.entry_type}'


class University(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=2, validators=[RegexValidator(r'^[A-Z]{2}$')])
    aliases = models.JSONField(default=list, blank=True)
    payment_channels = models.JSONField(default=list, blank=True)
    common_issues = models.JSONField(default=list, blank=True)
    support = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_university'
        ordering = ['name']

    def __str__(self):
        return self.name



class AgentUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    Full_Name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.user.username


class RegistrationOTP(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)
    password_hash = models.CharField(max_length=128)
    otp_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class AiAgentConversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_agent_conversations')
    title = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class AiAgentQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        AiAgentConversation,
        on_delete=models.CASCADE,
        related_name='questions',
        blank=True,
        null=True,
    )
    question_text = models.TextField()
    answer_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.question_text
