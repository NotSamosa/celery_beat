from rest_framework import serializers
from django_celery_beat.models import PeriodicTask
from django_celery_results.models import TaskResult
from .models import ScheduledEmail, PeriodicTaskLog


class ScheduleTaskSerializer(serializers.Serializer):
    task_name = serializers.CharField(max_length=255, default='scheduler.tasks.execute_dynamic_task')
    schedule_type = serializers.ChoiceField(choices=['one_time', 'interval', 'crontab'], default='one_time')
    schedule_time = serializers.DateTimeField(required=False, allow_null=True)
    crontab_expr = serializers.CharField(max_length=100, required=False, allow_blank=True)
    interval_every = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    interval_period = serializers.ChoiceField(
        choices=['seconds', 'minutes', 'hours', 'days', 'microseconds'],
        default='seconds',
        required=False
    )
    args = serializers.ListField(child=serializers.JSONField(), required=False, default=list)
    kwargs = serializers.DictField(required=False, default=dict)
    timezone = serializers.CharField(max_length=63, default='UTC')
    custom_name = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, data):
        stype = data.get('schedule_type')
        if stype == 'one_time' and not data.get('schedule_time'):
            raise serializers.ValidationError({"schedule_time": "Required when schedule_type is 'one_time'."})
        if stype == 'interval' and not data.get('interval_every'):
            raise serializers.ValidationError({"interval_every": "Required when schedule_type is 'interval'."})
        if stype == 'crontab' and not data.get('crontab_expr'):
            raise serializers.ValidationError({"crontab_expr": "Required when schedule_type is 'crontab'."})
        return data


class ScheduleEmailSerializer(serializers.Serializer):
    recipient_email = serializers.EmailField()
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()
    schedule_time = serializers.DateTimeField(required=False, allow_null=True)
    timezone = serializers.CharField(max_length=63, default='UTC')
    category = serializers.ChoiceField(
        choices=['CUSTOM', 'BIRTHDAY', 'ANNIVERSARY', 'CAMPAIGN'],
        default='CUSTOM'
    )


class PeriodicTaskListSerializer(serializers.ModelSerializer):
    schedule_description = serializers.SerializerMethodField()

    class Meta:
        model = PeriodicTask
        fields = [
            'id', 'name', 'task', 'enabled', 'one_off',
            'schedule_description', 'last_run_at', 'total_run_count', 'date_changed'
        ]

    def get_schedule_description(self, obj):
        if obj.clocked:
            return f"Clocked: {obj.clocked.clocked_time.isoformat()} (One-off)"
        elif obj.crontab:
            return f"Crontab: {obj.crontab.minute} {obj.crontab.hour} {obj.crontab.day_of_month} {obj.crontab.month_of_year} {obj.crontab.day_of_week} ({obj.crontab.timezone})"
        elif obj.interval:
            return f"Interval: every {obj.interval.every} {obj.interval.period}"
        return "Manual / None"


class TaskHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskResult
        fields = [
            'id', 'task_id', 'task_name', 'status',
            'result', 'date_created', 'date_done', 'traceback'
        ]


class ScheduledEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledEmail
        fields = '__all__'

