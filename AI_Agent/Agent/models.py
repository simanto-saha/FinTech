from django.db import models
from django.contrib.auth.models import User 



class AgentUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    Full_Name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.user.username

