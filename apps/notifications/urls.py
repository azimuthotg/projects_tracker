from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('send/project/<int:pk>/', views.send_project_notify, name='send_project_notify'),
    path('send/activity/<int:project_pk>/<int:pk>/', views.send_activity_notify, name='send_activity_notify'),
]
