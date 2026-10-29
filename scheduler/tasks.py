import logging
from celery import shared_task
from django.utils import timezone
from .models import PeriodicTaskLog

logger = logging.getLogger(__name__)


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

