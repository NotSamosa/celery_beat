from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    timezone = models.CharField(max_length=63, default='UTC')
    birthday = models.DateField(null=True, blank=True)
    anniversary = models.DateField(null=True, blank=True)
    email_notifications = models.BooleanField(default=True)
    preferred_email_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        return self.username


class ScheduledEmail(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    CATEGORY_CHOICES = [
        ('CUSTOM', 'Custom'),
        ('BIRTHDAY', 'Birthday Reminder'),
        ('ANNIVERSARY', 'Anniversary Reminder'),
        ('CAMPAIGN', 'Email Campaign'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='scheduled_emails')
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='CUSTOM')
    scheduled_time = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True, default='')
    task_id = models.CharField(max_length=255, blank=True, default='')
    periodic_task_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject} to {self.recipient_email} ({self.status})"


class EmailCampaign(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    target_timezone = models.CharField(max_length=63, blank=True, default='')
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.status})"


class PeriodicTaskLog(models.Model):
    task_name = models.CharField(max_length=255)
    executed_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=32, default='SUCCESS')
    details = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.task_name} at {self.executed_at}"
