from django.urls import path

from .views import executive, index, my_tasks

app_name = 'dashboard'

urlpatterns = [
    path('', index, name='index'),
    path('my-tasks/', my_tasks, name='my_tasks'),
    path('executive/', executive, name='executive'),
]
