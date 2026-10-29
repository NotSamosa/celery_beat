import json
import uuid
import logging
from datetime import datetime
from django.utils import timezone
from zoneinfo import ZoneInfo
from django_celery_beat.models import PeriodicTask, ClockedSchedule, IntervalSchedule, CrontabSchedule
from .timezone_utils import local_datetime_to_utc, get_zoneinfo

logger = logging.getLogger(__name__)


def generate_unique_task_name(base_name):
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = uuid.uuid4().hex[:6]
    clean_base = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
    return f"{clean_base}_{timestamp}_{random_suffix}"


def parse_crontab_expression(crontab_expr, tz_str='UTC'):
    parts = crontab_expr.strip().split()
    if len(parts) != 5:
        raise ValueError("Crontab expression must have exactly 5 parts: 'minute hour day_of_month month day_of_week'")
    minute, hour, dom, month, dow = parts
    crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=minute,
        hour=hour,
        day_of_month=dom,
        month_of_year=month,
        day_of_week=dow,
        timezone=tz_str
    )
    return crontab_schedule


def create_dynamic_task(
    task_name,
    schedule_time=None,
    args=None,
    kwargs=None,
    schedule_type='one_time',
    interval_every=None,
    interval_period='seconds',
    crontab_expr=None,
    timezone_str='UTC',
    custom_name=None
):
    unique_name = custom_name if custom_name else generate_unique_task_name(task_name)
    args_json = json.dumps(args or [])
    kwargs_json = json.dumps(kwargs or {})

    periodic_task_kwargs = {
        'name': unique_name,
        'task': task_name,
        'args': args_json,
        'kwargs': kwargs_json,
        'enabled': True,
    }

    if schedule_type == 'one_time':
        if not schedule_time:
            raise ValueError("schedule_time is required for one-time scheduled tasks.")
        
        if isinstance(schedule_time, str):
            parsed_time = datetime.fromisoformat(schedule_time)
        else:
            parsed_time = schedule_time

        utc_time = local_datetime_to_utc(parsed_time, timezone_str)
        clocked, _ = ClockedSchedule.objects.get_or_create(clocked_time=utc_time)
        periodic_task_kwargs['clocked'] = clocked
        periodic_task_kwargs['one_off'] = True

    elif schedule_type == 'interval':
        if not interval_every:
            raise ValueError("interval_every is required for interval tasks.")
        
        valid_periods = [p[0] for p in IntervalSchedule.PERIOD_CHOICES]
        if interval_period not in valid_periods:
            raise ValueError(f"interval_period must be one of: {valid_periods}")

        interval, _ = IntervalSchedule.objects.get_or_create(
            every=int(interval_every),
            period=interval_period
        )
        periodic_task_kwargs['interval'] = interval

    elif schedule_type == 'crontab':
        if not crontab_expr:
            raise ValueError("crontab_expr is required for crontab scheduled tasks.")
        
        crontab = parse_crontab_expression(crontab_expr, tz_str=timezone_str)
        periodic_task_kwargs['crontab'] = crontab

    else:
        raise ValueError(f"Unsupported schedule_type: {schedule_type}")

    periodic_task = PeriodicTask.objects.create(**periodic_task_kwargs)
    logger.info(f"Dynamically created periodic task '{unique_name}' (ID: {periodic_task.id})")
    return periodic_task


def modify_dynamic_task(task_id, schedule_time=None, args=None, kwargs=None, enabled=None, crontab_expr=None, interval_every=None, interval_period=None, timezone_str='UTC'):
    periodic_task = PeriodicTask.objects.get(id=task_id)

    if args is not None:
        periodic_task.args = json.dumps(args)
    if kwargs is not None:
        periodic_task.kwargs = json.dumps(kwargs)
    if enabled is not None:
        periodic_task.enabled = enabled

    if schedule_time:
        if isinstance(schedule_time, str):
            parsed_time = datetime.fromisoformat(schedule_time)
        else:
            parsed_time = schedule_time
        utc_time = local_datetime_to_utc(parsed_time, timezone_str)
        clocked, _ = ClockedSchedule.objects.get_or_create(clocked_time=utc_time)
        periodic_task.clocked = clocked
        periodic_task.interval = None
        periodic_task.crontab = None
        periodic_task.one_off = True

    elif crontab_expr:
        crontab = parse_crontab_expression(crontab_expr, tz_str=timezone_str)
        periodic_task.crontab = crontab
        periodic_task.interval = None
        periodic_task.clocked = None
        periodic_task.one_off = False

    elif interval_every and interval_period:
        interval, _ = IntervalSchedule.objects.get_or_create(
            every=int(interval_every),
            period=interval_period
        )
        periodic_task.interval = interval
        periodic_task.clocked = None
        periodic_task.crontab = None
        periodic_task.one_off = False

    periodic_task.save()
    logger.info(f"Modified periodic task (ID: {periodic_task.id})")
    return periodic_task


def delete_dynamic_task(task_id):
    try:
        task = PeriodicTask.objects.get(id=task_id)
        task_name = task.name
        task.delete()
        logger.info(f"Deleted periodic task '{task_name}' (ID: {task_id})")
        return True, task_name
    except PeriodicTask.DoesNotExist:
        return False, None

