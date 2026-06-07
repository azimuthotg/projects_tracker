import time

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from django.views.static import serve as media_serve


# Health endpoint สำหรับ NMS Agent monitoring — เช็ก DB ด้วย SELECT 1 (public)
def health(request):
    t0 = time.monotonic()
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        db_status = 'ok'
    except Exception as e:
        db_status = f'error: {e}'
    db_ms = round((time.monotonic() - t0) * 1000)
    status = 'ok' if db_status == 'ok' else 'degraded'
    return JsonResponse(
        {'status': status, 'db': db_status, 'db_ms': db_ms},
        status=200 if status == 'ok' else 503,
    )


urlpatterns = [
    path('health/', health, name='nms_health'),  # NMS monitoring
    path('admin/', admin.site.urls),
    path('', include('apps.dashboard.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('projects/', include('apps.projects.urls')),
    path('budget/', include('apps.budget.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('reports/', include('apps.reports.urls')),
    # Serve media files (IIS strips SCRIPT_NAME prefix ก่อนส่งมา Django)
    path('media/<path:path>', media_serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
