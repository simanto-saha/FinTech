from django.db import models
from django.contrib.auth.models import User 



class AgentUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    Full_Name = models.CharField(max_length=100)
    bank_details = models.JSONField(blank=True, null=True)
    agent_details = models.JSONField(blank=True, null=True)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.user.username

