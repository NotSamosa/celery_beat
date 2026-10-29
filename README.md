# Django Celery Beat & Asynchronous Task Scheduler

A robust, enterprise-grade asynchronous task scheduling system built with Django, Celery, Redis, `django-celery-beat`, and `django-celery-results`.

---

## 1. System Architecture

- **Web Framework**: Django 6.0.9 & Django REST Framework 3.18.3
- **Message Broker**: Redis 8.1.0 (`redis://127.0.0.1:6379/0`)
- **Task Queue & Workers**: Celery 5.6.3
- **Periodic Task Scheduler**: Celery Beat backed by `django-celery-beat` DatabaseScheduler
- **Result Backend**: `django_celery_results` (persisted to SQL database)
- **Timezone Management**: Python standard library `zoneinfo` + Django timezone utilities
- **Email Backend**: Django console backend (development) / SMTP (production configurable)

---

## 2. Directory Structure

```
celery_task_scheduler/
├── config/
│   ├── __init__.py          # Autodiscovers celery_app
│   ├── celery.py            # Celery app configuration
│   ├── settings.py          # Django, Celery, DRF & SMTP settings
│   ├── urls.py              # Root URL routing
│   └── wsgi.py
├── scheduler/
│   ├── admin.py             # Admin registrations for User, Email, Logs
│   ├── models.py            # User, ScheduledEmail, EmailCampaign, PeriodicTaskLog
│   ├── serializers.py       # DRF serializers for API endpoints
│   ├── services.py          # Dynamic task CRUD & collision-free name generator
│   ├── tasks.py             # Periodic, dynamic, email, and retry tasks
│   ├── tests.py             # 13 automated unit & integration tests
│   ├── timezone_utils.py    # Local timezone to UTC conversion helpers
│   ├── urls.py              # Application and API routes
│   └── views.py             # REST API views & HTML Dashboard view
├── templates/
│   └── scheduler/
│       └── dashboard.html   # Web monitoring dashboard
├── logs/
│   ├── celery_worker.log    # Verified worker execution logs
│   └── celery_beat.log      # Verified Beat scheduler dispatch logs
├── manage.py
├── requirements.txt
└── .env
```

---

## 3. Quick Start & Setup

### Prerequisites
- Python 3.11+
- Redis Server running on port 6379 (`redis-cli ping` returns `PONG`)

### Installation

```bash
# 1. Activate Virtual Environment
source venv/bin/activate

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Apply Database Migrations
python manage.py migrate

# 4. Seed Default Periodic Tasks into DatabaseScheduler
python manage.py setup_periodic_tasks

# 5. (Optional) Create Superuser if needed
python manage.py createsuperuser
# Default admin pre-created: Username: admin, Password: admin123
```

---

## 4. Running the System Services

In separate terminal tabs:

### 1. Celery Worker
```bash
./venv/bin/celery -A config worker --loglevel=info --pool=solo
```

### 2. Celery Beat Scheduler
```bash
./venv/bin/celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 3. Django Web Server
```bash
./venv/bin/python manage.py runserver 8000
```

- **Web Dashboard**: `http://127.0.0.1:8000/`
- **Django Admin**: `http://127.0.0.1:8000/admin/`

---

## 5. Periodic Tasks & Crontab Schedules

Periodic tasks are stored in the database and monitored via `django_celery_beat`:

| Task Name | Function Path | Crontab Expression | Schedule Description |
|-----------|---------------|-------------------|----------------------|
| Daily Report Task | `scheduler.tasks.daily_report_task` | `0 9 * * *` | Every day at 09:00 AM UTC |
| Weekly Cleanup Task | `scheduler.tasks.weekly_cleanup_task` | `0 2 * * 1` | Every Monday at 02:00 AM UTC |
| Hourly Status Check | `scheduler.tasks.hourly_status_check_task` | `0 * * * *` | Every hour at minute 0 |
| Weekday Standup Report | `scheduler.tasks.weekday_standup_report_task` | `30 10 * * 1-5` | Every weekday (Mon-Fri) at 10:30 AM UTC |
| Birthday/Anniversary Check | `scheduler.tasks.check_birthday_anniversary_reminders` | `0 8 * * *` | Every day at 08:00 AM UTC |
| Process Campaigns | `scheduler.tasks.process_scheduled_campaigns` | `*/5 * * * *` | Every 5 minutes |

---

## 6. REST API Endpoints

### 1. Schedule Task Dynamically
- **Endpoint**: `POST /api/schedule-task/`
- **Content-Type**: `application/json`

**Payload Examples**:

*One-Time Scheduled Task:*
```json
{
  "task_name": "scheduler.tasks.execute_dynamic_task",
  "schedule_type": "one_time",
  "schedule_time": "2026-10-30T10:00:00",
  "timezone": "America/New_York",
  "args": ["data_sync"],
  "kwargs": {"payload": {"sync_records": 100}}
}
```

*Recurring Interval Task:*
```json
{
  "task_name": "scheduler.tasks.hourly_status_check_task",
  "schedule_type": "interval",
  "interval_every": 30,
  "interval_period": "seconds"
}
```

*Recurring Crontab Task:*
```json
{
  "task_name": "scheduler.tasks.weekday_standup_report_task",
  "schedule_type": "crontab",
  "crontab_expr": "30 10 * * 1-5",
  "timezone": "Asia/Kolkata"
}
```

### 2. Schedule Email for Future Delivery
- **Endpoint**: `POST /api/schedule-email/`
- **Content-Type**: `application/json`

```json
{
  "recipient_email": "client@example.com",
  "subject": "Scheduled Project Briefing",
  "body": "Here is the summary of the upcoming milestone.",
  "schedule_time": "2026-10-30T14:30:00",
  "timezone": "Asia/Kolkata",
  "category": "CUSTOM"
}
```

### 3. List Scheduled Tasks
- **Endpoint**: `GET /api/scheduled-tasks/`
- Returns count and full list of database-managed periodic tasks with schedule details, run count, and status.

### 4. Cancel Scheduled Task
- **Endpoint**: `POST` or `DELETE /api/cancel-task/<task_id>/`
- Accepts PeriodicTask ID, unique task name, or ScheduledEmail ID.

### 5. View Task Execution History
- **Endpoint**: `GET /api/task-history/`
- Returns recorded executions from `django_celery_results` and internal `PeriodicTaskLog`.

---

## 7. Automated Testing Suite

Run all automated unit and integration tests:

```bash
./venv/bin/python manage.py test
```

**Results**:
```
Ran 13 tests in 0.331s
OK
```

Tests cover:
- Periodic task execution and payload persistence
- Email delayed delivery and status state machine
- Birthday & anniversary reminder triggering with user timezone dates
- Email campaign batch processing
- Dynamic task CRUD operations
- All REST API endpoints and dashboard rendering

