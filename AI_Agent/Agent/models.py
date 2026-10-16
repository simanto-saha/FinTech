from django.db import models
from django.contrib.auth.models import User 



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