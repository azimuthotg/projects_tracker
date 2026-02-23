from django.urls import path

from . import views

app_name = 'budget'

urlpatterns = [
    path('', views.expense_list, name='expense_list'),
    path('create/', views.expense_create, name='expense_create'),
    path('create/<int:activity_pk>/', views.expense_create, name='expense_create_for_activity'),
    path('<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('approvals/', views.approval_list, name='approval_list'),
    path('<int:pk>/approve/', views.expense_approve, name='expense_approve'),
    path('<int:pk>/link-report/', views.expense_link_report, name='expense_link_report'),
    path('<int:pk>/delete/', views.expense_delete, name='expense_delete'),
]
