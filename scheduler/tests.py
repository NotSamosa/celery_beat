import json
from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from scheduler.models import User, ScheduledEmail, PeriodicTaskLog, EmailCampaign
from scheduler.services import create_dynamic_task, modify_dynamic_task, delete_dynamic_task
from scheduler.tasks import (
    daily_report_task,
    weekly_cleanup_task,
    hourly_status_check_task,
    email_scheduler_task,
    check_birthday_anniversary_reminders,
    process_scheduled_campaigns,
    execute_dynamic_task
)
from scheduler.timezone_utils import get_current_date_in_tz, local_datetime_to_utc


class SchedulerPeriodicTasksTests(TestCase):
    def test_daily_report_task(self):
        result = daily_report_task.apply()
        self.assertEqual(result.status, 'SUCCESS')
        self.assertIn('report_name', result.result)
        self.assertTrue(PeriodicTaskLog.objects.filter(task_name='daily_report_task').exists())

    def test_weekly_cleanup_task(self):
        result = weekly_cleanup_task.apply()
        self.assertEqual(result.status, 'SUCCESS')
        self.assertTrue(PeriodicTaskLog.objects.filter(task_name='weekly_cleanup_task').exists())

    def test_hourly_status_check_task(self):
        result = hourly_status_check_task.apply()
        self.assertEqual(result.status, 'SUCCESS')
        self.assertEqual(result.result.get('redis_broker'), 'Operational')


class SchedulerEmailAndRemindersTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='johndoe',
            email='john@example.com',
            password='testpassword',
            timezone='America/New_York',
            birthday=get_current_date_in_tz('America/New_York'),
            anniversary=get_current_date_in_tz('America/New_York'),
            email_notifications=True
        )

    def test_email_scheduler_task_direct(self):
        email_obj = ScheduledEmail.objects.create(
            recipient_email='receiver@example.com',
            subject='Test Subject',
            body='Test Body',
            scheduled_time=timezone.now(),
            status='PENDING'
        )
        res = email_scheduler_task.apply(
            args=[{
                'scheduled_email_id': email_obj.id,
                'recipient_email': email_obj.recipient_email,
                'subject': email_obj.subject,
                'body': email_obj.body
            }],
            kwargs={'schedule_time': timezone.now().isoformat()}
        )
        self.assertEqual(res.status, 'SUCCESS')
        email_obj.refresh_from_db()
        self.assertEqual(email_obj.status, 'SENT')
        self.assertIsNotNone(email_obj.sent_at)

    def test_birthday_and_anniversary_reminders(self):
        res = check_birthday_anniversary_reminders.apply()
        self.assertEqual(res.status, 'SUCCESS')
        self.assertEqual(res.result.get('reminders_sent'), 2)
        self.assertEqual(ScheduledEmail.objects.filter(user=self.user).count(), 2)

    def test_email_campaign_processing(self):
        campaign = EmailCampaign.objects.create(
            name='Q4 Promo',
            subject='Promo Update',
            body='Enjoy our end of year offers!',
            scheduled_time=timezone.now() - timedelta(minutes=5),
            status='SCHEDULED'
        )
        res = process_scheduled_campaigns.apply()
        self.assertEqual(res.status, 'SUCCESS')
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'COMPLETED')
        self.assertGreaterEqual(campaign.sent_count, 1)


class DynamicTaskServiceTests(TestCase):
    def test_dynamic_task_crud(self):
        future_dt = timezone.now() + timedelta(hours=1)
        task = create_dynamic_task(
            task_name='scheduler.tasks.execute_dynamic_task',
            schedule_time=future_dt,
            args=['test_action'],
            kwargs={'payload': {'key': 'val'}},
            schedule_type='one_time',
            timezone_str='UTC'
        )
        self.assertTrue(task.one_off)
        self.assertIsNotNone(task.clocked)

        mod = modify_dynamic_task(task.id, enabled=False)
        self.assertFalse(mod.enabled)

        deleted, _ = delete_dynamic_task(task.id)
        self.assertTrue(deleted)
        self.assertFalse(PeriodicTask.objects.filter(id=task.id).exists())


class SchedulerAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_dashboard_view(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Celery Beat')

    def test_api_schedule_task(self):
        payload = {
            'task_name': 'scheduler.tasks.hourly_status_check_task',
            'schedule_type': 'interval',
            'interval_every': 10,
            'interval_period': 'minutes'
        }
        res = self.client.post('/api/schedule-task/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        self.assertIn('task', res.json())

    def test_api_schedule_email(self):
        payload = {
            'recipient_email': 'lead@business.com',
            'subject': 'Demo Booking Confirmation',
            'body': 'Your demo is booked.',
            'timezone': 'UTC'
        }
        res = self.client.post('/api/schedule-email/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['email']['recipient_email'], 'lead@business.com')

    def test_api_scheduled_tasks_list(self):
        res = self.client.get('/api/scheduled-tasks/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('tasks', res.json())

    def test_api_cancel_task(self):
        task = create_dynamic_task(
            task_name='scheduler.tasks.hourly_status_check_task',
            schedule_type='interval',
            interval_every=5,
            interval_period='seconds'
        )
        res = self.client.delete(f'/api/cancel-task/{task.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['cancelled'])

    def test_api_task_history(self):
        res = self.client.get('/api/task-history/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('celery_results', res.json())
        self.assertIn('periodic_task_logs', res.json())
