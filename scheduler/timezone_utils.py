from datetime import datetime, date, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.utils import timezone


def get_zoneinfo(tz_name):
    if not tz_name:
        return ZoneInfo('UTC')
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo('UTC')


def get_current_date_in_tz(tz_name):
    tz = get_zoneinfo(tz_name)
    return timezone.now().astimezone(tz).date()


def local_datetime_to_utc(local_dt, tz_name):
    tz = get_zoneinfo(tz_name)
    if timezone.is_naive(local_dt):
        local_dt = local_dt.replace(tzinfo=tz)
    else:
        local_dt = local_dt.astimezone(tz)
    return local_dt.astimezone(ZoneInfo('UTC'))


def utc_to_local(utc_dt, tz_name):
    tz = get_zoneinfo(tz_name)
    if timezone.is_naive(utc_dt):
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo('UTC'))
    return utc_dt.astimezone(tz)


def get_user_datetime_for_time(user, target_time, target_date=None):
    user_tz = get_zoneinfo(user.timezone)
    if target_date is None:
        target_date = timezone.now().astimezone(user_tz).date()
    local_dt = datetime.combine(target_date, target_time, tzinfo=user_tz)
    return local_dt.astimezone(ZoneInfo('UTC'))

