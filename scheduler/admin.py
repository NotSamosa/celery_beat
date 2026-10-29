from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ScheduledEmail, EmailCampaign, PeriodicTaskLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Scheduling & Preferences', {
            'fields': ('timezone', 'birthday', 'anniversary', 'email_notifications', 'preferred_email_time')
        }),
    )
    list_display = ('username', 'email', 'timezone', 'birthday', 'anniversary', 'email_notifications', 'is_staff')


@admin.register(ScheduledEmail)
class ScheduledEmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'recipient_email', 'category', 'scheduled_time', 'status', 'task_id', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('subject', 'recipient_email', 'task_id')


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'scheduled_time', 'status', 'total_recipients', 'sent_count', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'subject')


@admin.register(PeriodicTaskLog)
class PeriodicTaskLogAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'executed_at', 'status')
    list_filter = ('task_name', 'status')
    readonly_fields = ('task_name', 'executed_at', 'status', 'details')
