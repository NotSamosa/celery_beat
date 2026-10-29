from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('api/schedule-task/', views.ScheduleTaskAPIView.as_view(), name='api-schedule-task'),
    path('api/schedule-email/', views.ScheduleEmailAPIView.as_view(), name='api-schedule-email'),
    path('api/scheduled-tasks/', views.ScheduledTasksAPIView.as_view(), name='api-scheduled-tasks'),
    path('api/cancel-task/<str:task_id>/', views.CancelTaskAPIView.as_view(), name='api-cancel-task'),
    path('api/task-history/', views.TaskHistoryAPIView.as_view(), name='api-task-history'),
]

