from django.urls import path

from .views import (
    CustomLoginView,
    CustomLogoutView,
    department_create,
    department_delete,
    department_edit,
    department_list,
    fiscalyear_create,
    fiscalyear_delete,
    fiscalyear_edit,
    fiscalyear_list,
    fiscalyear_toggle,
    manage_dashboard,
    my_profile,
    user_create,
    user_edit,
    user_list,
    user_toggle_active,
)

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('profile/', my_profile, name='my_profile'),

    # Admin management
    path('manage/', manage_dashboard, name='manage_dashboard'),

    # User management
    path('manage/users/', user_list, name='user_list'),
    path('manage/users/create/', user_create, name='user_create'),
    path('manage/users/<int:pk>/edit/', user_edit, name='user_edit'),
    path('manage/users/<int:pk>/toggle/', user_toggle_active, name='user_toggle_active'),

    # Department management
    path('manage/departments/', department_list, name='department_list'),
    path('manage/departments/create/', department_create, name='department_create'),
    path('manage/departments/<int:pk>/edit/', department_edit, name='department_edit'),
    path('manage/departments/<int:pk>/delete/', department_delete, name='department_delete'),

    # Fiscal year management
    path('manage/fiscal-years/', fiscalyear_list, name='fiscalyear_list'),
    path('manage/fiscal-years/create/', fiscalyear_create, name='fiscalyear_create'),
    path('manage/fiscal-years/<int:pk>/edit/', fiscalyear_edit, name='fiscalyear_edit'),
    path('manage/fiscal-years/<int:pk>/toggle/', fiscalyear_toggle, name='fiscalyear_toggle'),
    path('manage/fiscal-years/<int:pk>/delete/', fiscalyear_delete, name='fiscalyear_delete'),
]
