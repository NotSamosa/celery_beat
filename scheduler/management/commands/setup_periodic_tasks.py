from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule


class Command(BaseCommand):
    help = 'Setup default crontab periodic tasks in django-celery-beat'

    def handle(self, *args, **options):
        # 1. daily_report_task: Every day at 9 AM
        daily_cron, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='9',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            timezone='UTC'
        )
        p_daily, created = PeriodicTask.objects.update_or_create(
            name='Daily Report Task (9 AM)',
            defaults={
                'task': 'scheduler.tasks.daily_report_task',
                'crontab': daily_cron,
                'enabled': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} periodic task: {p_daily.name}"))

        # 2. weekly_cleanup_task: Every Monday at 2 AM
        weekly_cron, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='2',
            day_of_week='1',
            day_of_month='*',
            month_of_year='*',
            timezone='UTC'
        )
        p_weekly, created = PeriodicTask.objects.update_or_create(
            name='Weekly Cleanup Task (Mon 2 AM)',
            defaults={
                'task': 'scheduler.tasks.weekly_cleanup_task',
                'crontab': weekly_cron,
                'enabled': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} periodic task: {p_weekly.name}"))

        # 3. hourly_status_check_task: Every hour (at minute 0)
        hourly_cron, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='*',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            timezone='UTC'
        )
        p_hourly, created = PeriodicTask.objects.update_or_create(
            name='Hourly Status Check Task',
            defaults={
                'task': 'scheduler.tasks.hourly_status_check_task',
                'crontab': hourly_cron,
                'enabled': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} periodic task: {p_hourly.name}"))

