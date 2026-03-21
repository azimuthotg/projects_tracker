from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('budget/', views.budget_report, name='budget_report'),
    path('budget/print/', views.budget_report_print, name='budget_report_print'),
    path('budget/excel/', views.budget_report_excel, name='budget_report_excel'),
    path('budget/pdf/', views.budget_report_pdf, name='budget_report_pdf'),
    path('expenses/', views.expense_report, name='expense_report'),
    path('expenses/excel/', views.expense_report_excel, name='expense_report_excel'),
    path('project/<int:pk>/', views.project_report, name='project_report'),
    path('project/<int:pk>/pdf/', views.project_report_pdf, name='project_report_pdf'),
]
