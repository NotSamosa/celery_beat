from datetime import datetime
from django.shortcuts import render
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_celery_beat.models import PeriodicTask
from django_celery_results.models import TaskResult

from .models import ScheduledEmail, PeriodicTaskLog, User
from .serializers import (
    ScheduleTaskSerializer,
    ScheduleEmailSerializer,
    PeriodicTaskListSerializer,
    TaskHistorySerializer,
    ScheduledEmailSerializer
)
from .services import create_dynamic_task, delete_dynamic_task
from .tasks import email_scheduler_task
from .timezone_utils import local_datetime_to_utc


class ScheduleTaskAPIView(APIView):
    def post(self, request):
        serializer = ScheduleTaskSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            periodic_task = create_dynamic_task(
                task_name=data['task_name'],
                schedule_time=data.get('schedule_time'),
                args=data.get('args', []),
                kwargs=data.get('kwargs', {}),
                schedule_type=data['schedule_type'],
                interval_every=data.get('interval_every'),
                interval_period=data.get('interval_period', 'seconds'),
                crontab_expr=data.get('crontab_expr'),
                timezone_str=data.get('timezone', 'UTC'),
                custom_name=data.get('custom_name')
            )
            return Response({
                'message': 'Task scheduled successfully.',
                'task': {
                    'id': periodic_task.id,
                    'name': periodic_task.name,
                    'task': periodic_task.task,
                    'enabled': periodic_task.enabled,
                    'one_off': periodic_task.one_off,
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ScheduleEmailAPIView(APIView):
    def post(self, request):
        serializer = ScheduleEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        recipient_email = data['recipient_email']
        subject = data['subject']
        body = data['body']
        schedule_time = data.get('schedule_time')
        tz_str = data.get('timezone', 'UTC')
        category = data.get('category', 'CUSTOM')

        now_utc = timezone.now()
        target_utc = None

        if schedule_time:
            target_utc = local_datetime_to_utc(schedule_time, tz_str)

        scheduled_email = ScheduledEmail.objects.create(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            category=category,
            scheduled_time=target_utc or now_utc,
            status='PENDING'
        )

        email_payload = {
            'scheduled_email_id': scheduled_email.id,
            'recipient_email': recipient_email,
            'subject': subject,
            'body': body,
        }

        if target_utc and target_utc > now_utc:
            periodic_task = create_dynamic_task(
                task_name='scheduler.tasks.email_scheduler_task',
                schedule_time=target_utc,
                kwargs={
                    'email_data': email_payload,
                    'schedule_time': target_utc.isoformat()
                },
                schedule_type='one_time',
                timezone_str='UTC',
                custom_name=f"email_{scheduled_email.id}_{scheduled_email.recipient_email}"
            )
            scheduled_email.periodic_task_id = periodic_task.id
            scheduled_email.save(update_fields=['periodic_task_id'])
            task_identifier = f"beat_task:{periodic_task.id}"
        else:
            async_result = email_scheduler_task.delay(
                email_data=email_payload,
                schedule_time=now_utc.isoformat()
            )
            scheduled_email.task_id = async_result.id
            scheduled_email.save(update_fields=['task_id'])
            task_identifier = async_result.id

        return Response({
            'message': 'Email scheduled successfully.',
            'email': ScheduledEmailSerializer(scheduled_email).data,
            'task_identifier': task_identifier
        }, status=status.HTTP_201_CREATED)


class ScheduledTasksAPIView(APIView):
    def get(self, request):
        tasks = PeriodicTask.objects.all().order_by('-id')
        serializer = PeriodicTaskListSerializer(tasks, many=True)
        return Response({
            'count': tasks.count(),
            'tasks': serializer.data
        }, status=status.HTTP_200_OK)


class CancelTaskAPIView(APIView):
    def post(self, request, task_id):
        return self._cancel(task_id)

    def delete(self, request, task_id):
        return self._cancel(task_id)

    def _cancel(self, task_id):
        deleted = False
        task_name = None
        if str(task_id).isdigit():
            deleted, task_name = delete_dynamic_task(int(task_id))
            ScheduledEmail.objects.filter(periodic_task_id=int(task_id)).update(status='CANCELLED')

        if not deleted:
            p_task = PeriodicTask.objects.filter(name=str(task_id)).first()
            if p_task:
                task_name = p_task.name
                p_task.delete()
                deleted = True

        if not deleted:
            email_qs = ScheduledEmail.objects.filter(task_id=str(task_id), status='PENDING')
            if not email_qs.exists() and str(task_id).isdigit():
                email_qs = ScheduledEmail.objects.filter(id=int(task_id), status='PENDING')
            if email_qs.exists():
                email_qs.update(status='CANCELLED')
                deleted = True
                task_name = f"ScheduledEmail:{task_id}"

        if deleted:
            return Response({
                'message': f"Task '{task_name or task_id}' successfully cancelled/deleted.",
                'cancelled': True
            }, status=status.HTTP_200_OK)

        return Response({
            'error': f"Task with ID/name '{task_id}' not found.",
            'cancelled': False
        }, status=status.HTTP_404_NOT_FOUND)


class TaskHistoryAPIView(APIView):
    def get(self, request):
        results = TaskResult.objects.all().order_by('-date_done')[:50]
        results_data = TaskHistorySerializer(results, many=True).data

        logs = PeriodicTaskLog.objects.all().order_by('-executed_at')[:50]
        logs_data = [
            {
                'id': log.id,
                'task_name': log.task_name,
                'executed_at': log.executed_at.isoformat(),
                'status': log.status,
                'details': log.details
            }
            for log in logs
        ]

        return Response({
            'celery_results_count': results.count(),
            'celery_results': results_data,
            'periodic_task_logs_count': logs.count(),
            'periodic_task_logs': logs_data
        }, status=status.HTTP_200_OK)


def dashboard_view(request):
    periodic_tasks = PeriodicTask.objects.all().order_by('-id')
    scheduled_emails = ScheduledEmail.objects.all().order_by('-created_at')[:20]
    recent_results = TaskResult.objects.all().order_by('-date_done')[:15]
    recent_logs = PeriodicTaskLog.objects.all().order_by('-executed_at')[:15]
    total_users = User.objects.count()

    context = {
        'periodic_tasks': periodic_tasks,
        'scheduled_emails': scheduled_emails,
        'recent_results': recent_results,
        'recent_logs': recent_logs,
        'total_periodic_tasks': periodic_tasks.count(),
        'enabled_tasks_count': periodic_tasks.filter(enabled=True).count(),
        'total_emails': ScheduledEmail.objects.count(),
        'sent_emails': ScheduledEmail.objects.filter(status='SENT').count(),
        'pending_emails': ScheduledEmail.objects.filter(status='PENDING').count(),
        'total_users': total_users,
        'current_time_utc': timezone.now(),
    }
    return render(request, 'scheduler/dashboard.html', context)
