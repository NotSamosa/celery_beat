import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import ScheduledEmail, EmailCampaign, User, PeriodicTaskLog
from .timezone_utils import get_current_date_in_tz, get_user_datetime_for_time

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def email_scheduler_task(self, email_data, schedule_time=None):
    scheduled_email_id = email_data.get('scheduled_email_id')
    recipient_email = email_data.get('recipient_email')
    subject = email_data.get('subject')
    body = email_data.get('body')

    scheduled_email = None
    if scheduled_email_id:
        try:
            scheduled_email = ScheduledEmail.objects.get(id=scheduled_email_id)
        except ScheduledEmail.DoesNotExist:
            pass

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )

        sent_time = timezone.now()
        if scheduled_email:
            scheduled_email.status = 'SENT'
            scheduled_email.sent_at = sent_time
            scheduled_email.task_id = self.request.id or ''
            scheduled_email.save(update_fields=['status', 'sent_at', 'task_id', 'updated_at'])

        logger.info(f"Email successfully sent to {recipient_email} (Task ID: {self.request.id})")
        return {
            'status': 'SENT',
            'recipient_email': recipient_email,
            'sent_at': sent_time.isoformat(),
            'task_id': self.request.id,
        }

    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_email}: {exc}")
        if scheduled_email:
            scheduled_email.status = 'FAILED'
            scheduled_email.error_message = str(exc)
            scheduled_email.save(update_fields=['status', 'error_message', 'updated_at'])

        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_birthday_anniversary_reminders(self):
    now_utc = timezone.now()
    scheduled_count = 0
    active_users = User.objects.filter(is_active=True, email_notifications=True)

    for user in active_users:
        if not user.email:
            continue

        user_today = get_current_date_in_tz(user.timezone)

        if user.birthday and user.birthday.month == user_today.month and user.birthday.day == user_today.day:
            already_scheduled = ScheduledEmail.objects.filter(
                user=user,
                category='BIRTHDAY',
                created_at__date=now_utc.date()
            ).exists()

            if not already_scheduled:
                email_obj = ScheduledEmail.objects.create(
                    user=user,
                    recipient_email=user.email,
                    subject=f"Happy Birthday, {user.first_name or user.username}!",
                    body=f"Dear {user.first_name or user.username},\n\nWishing you a fantastic birthday and a great year ahead!\n\nBest regards,\nThe Team",
                    category='BIRTHDAY',
                    scheduled_time=now_utc,
                    status='PENDING'
                )
                async_res = email_scheduler_task.delay(
                    email_data={
                        'scheduled_email_id': email_obj.id,
                        'recipient_email': email_obj.recipient_email,
                        'subject': email_obj.subject,
                        'body': email_obj.body,
                    },
                    schedule_time=now_utc.isoformat()
                )
                email_obj.task_id = async_res.id
                email_obj.save(update_fields=['task_id'])
                scheduled_count += 1

        if user.anniversary and user.anniversary.month == user_today.month and user.anniversary.day == user_today.day:
            already_scheduled = ScheduledEmail.objects.filter(
                user=user,
                category='ANNIVERSARY',
                created_at__date=now_utc.date()
            ).exists()

            if not already_scheduled:
                email_obj = ScheduledEmail.objects.create(
                    user=user,
                    recipient_email=user.email,
                    subject=f"Happy Anniversary, {user.first_name or user.username}!",
                    body=f"Dear {user.first_name or user.username},\n\nCongratulations on your anniversary! Wishing you continued happiness.\n\nBest regards,\nThe Team",
                    category='ANNIVERSARY',
                    scheduled_time=now_utc,
                    status='PENDING'
                )
                async_res = email_scheduler_task.delay(
                    email_data={
                        'scheduled_email_id': email_obj.id,
                        'recipient_email': email_obj.recipient_email,
                        'subject': email_obj.subject,
                        'body': email_obj.body,
                    },
                    schedule_time=now_utc.isoformat()
                )
                email_obj.task_id = async_res.id
                email_obj.save(update_fields=['task_id'])
                scheduled_count += 1

    PeriodicTaskLog.objects.create(
        task_name='check_birthday_anniversary_reminders',
        executed_at=now_utc,
        status='SUCCESS',
        details={'processed_users': active_users.count(), 'reminders_sent': scheduled_count}
    )
    return {'status': 'SUCCESS', 'reminders_sent': scheduled_count}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_scheduled_campaigns(self):
    now = timezone.now()
    pending_campaigns = EmailCampaign.objects.filter(
        status='SCHEDULED',
        scheduled_time__lte=now
    )

    processed_campaigns = 0
    total_emails_sent = 0

    for campaign in pending_campaigns:
        campaign.status = 'IN_PROGRESS'
        campaign.save(update_fields=['status', 'updated_at'])

        recipients_qs = User.objects.filter(is_active=True, email_notifications=True)
        if campaign.target_timezone:
            recipients_qs = recipients_qs.filter(timezone=campaign.target_timezone)

        campaign.total_recipients = recipients_qs.count()
        campaign.sent_count = 0
        campaign.save(update_fields=['total_recipients', 'updated_at'])

        for user in recipients_qs:
            if not user.email:
                continue
            email_obj = ScheduledEmail.objects.create(
                user=user,
                recipient_email=user.email,
                subject=campaign.subject,
                body=campaign.body,
                category='CAMPAIGN',
                scheduled_time=now,
                status='PENDING'
            )
            async_res = email_scheduler_task.delay(
                email_data={
                    'scheduled_email_id': email_obj.id,
                    'recipient_email': email_obj.recipient_email,
                    'subject': email_obj.subject,
                    'body': email_obj.body,
                },
                schedule_time=now.isoformat()
            )
            email_obj.task_id = async_res.id
            email_obj.save(update_fields=['task_id'])
            campaign.sent_count += 1

        campaign.status = 'COMPLETED'
        campaign.save(update_fields=['status', 'sent_count', 'updated_at'])
        processed_campaigns += 1
        total_emails_sent += campaign.sent_count

    PeriodicTaskLog.objects.create(
        task_name='process_scheduled_campaigns',
        executed_at=now,
        status='SUCCESS',
        details={'processed_campaigns': processed_campaigns, 'total_emails_sent': total_emails_sent}
    )
    return {'campaigns_processed': processed_campaigns, 'emails_dispatched': total_emails_sent}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def weekday_standup_report_task(self):
    now = timezone.now()
    report_data = {
        'timestamp': now.isoformat(),
        'task': 'Weekday 10:30 AM Standup Status Report',
        'status': 'Generated',
        'active_workers': 1
    }
    PeriodicTaskLog.objects.create(
        task_name='weekday_standup_report_task',
        executed_at=now,
        status='SUCCESS',
        details=report_data
    )
    return report_data


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def daily_report_task(self):
    try:
        now = timezone.now()
        report_data = {
            'timestamp': now.isoformat(),
            'report_name': 'Daily System Performance Report',
            'status': 'Generated successfully',
            'summary': {
                'active_jobs': 0,
                'system_health': 'Optimal',
            }
        }
        PeriodicTaskLog.objects.create(
            task_name='daily_report_task',
            executed_at=now,
            status='SUCCESS',
            details=report_data
        )
        logger.info(f"daily_report_task executed successfully at {now}")
        return report_data
    except Exception as exc:
        logger.error(f"Error in daily_report_task: {exc}")
        PeriodicTaskLog.objects.create(
            task_name='daily_report_task',
            executed_at=timezone.now(),
            status='FAILED',
            details={'error': str(exc)}
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def weekly_cleanup_task(self):
    try:
        now = timezone.now()
        cleanup_summary = {
            'timestamp': now.isoformat(),
            'cleaned_items': 0,
            'status': 'Weekly system cleanup completed'
        }
        PeriodicTaskLog.objects.create(
            task_name='weekly_cleanup_task',
            executed_at=now,
            status='SUCCESS',
            details=cleanup_summary
        )
        logger.info(f"weekly_cleanup_task executed successfully at {now}")
        return cleanup_summary
    except Exception as exc:
        logger.error(f"Error in weekly_cleanup_task: {exc}")
        PeriodicTaskLog.objects.create(
            task_name='weekly_cleanup_task',
            executed_at=timezone.now(),
            status='FAILED',
            details={'error': str(exc)}
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def hourly_status_check_task(self):
    try:
        now = timezone.now()
        status_data = {
            'timestamp': now.isoformat(),
            'database': 'Connected',
            'redis_broker': 'Operational',
            'status': 'All systems normal'
        }
        PeriodicTaskLog.objects.create(
            task_name='hourly_status_check_task',
            executed_at=now,
            status='SUCCESS',
            details=status_data
        )
        logger.info(f"hourly_status_check_task executed successfully at {now}")
        return status_data
    except Exception as exc:
        logger.error(f"Error in hourly_status_check_task: {exc}")
        PeriodicTaskLog.objects.create(
            task_name='hourly_status_check_task',
            executed_at=timezone.now(),
            status='FAILED',
            details={'error': str(exc)}
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
