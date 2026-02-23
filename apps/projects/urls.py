from django.urls import path

from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('create/', views.project_create, name='project_create'),
    path('<int:pk>/', views.project_detail, name='project_detail'),
    path('<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('<int:pk>/status/', views.project_status_change, name='project_status_change'),
    path('<int:pk>/delete-request/', views.project_delete_request, name='project_delete_request'),
    path('delete-requests/', views.delete_request_list, name='delete_request_list'),
    path('delete-requests/<int:pk>/review/', views.delete_request_review, name='delete_request_review'),
    path('<int:project_pk>/activities/create/', views.activity_create, name='activity_create'),
    path('<int:project_pk>/activities/<int:pk>/', views.activity_detail, name='activity_detail'),
    path('<int:project_pk>/activities/<int:pk>/edit/', views.activity_edit, name='activity_edit'),
    path('activities/<int:activity_pk>/reports/create/', views.activity_report_create, name='activity_report_create'),
    path('activities/reports/<int:pk>/edit/', views.activity_report_edit, name='activity_report_edit'),
    path('activities/reports/<int:pk>/delete/', views.activity_report_delete, name='activity_report_delete'),
]
