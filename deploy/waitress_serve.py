"""
Waitress entry point สำหรับ Windows production
รันด้วย: python deploy/waitress_serve.py
หรือให้ NSSM เรียกไฟล์นี้
"""
import os
import sys
from pathlib import Path

# เพิ่ม project root เข้า Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

from waitress import serve
from django.core.wsgi import get_wsgi_application

# เมื่อใช้ IIS เป็น reverse proxy: listen แค่ localhost (ไม่ expose ออกนอก)
# IIS รับ HTTPS แล้วส่งต่อมาที่ 127.0.0.1:8000
HOST    = os.environ.get('WAITRESS_HOST',    '127.0.0.1')
PORT    = int(os.environ.get('WAITRESS_PORT',    '8000'))
THREADS = int(os.environ.get('WAITRESS_THREADS', '8'))

application = get_wsgi_application()

if __name__ == '__main__':
    print(f'Starting Waitress on {HOST}:{PORT} with {THREADS} threads...')
    serve(
        application,
        host=HOST,
        port=PORT,
        threads=THREADS,
        channel_timeout=120,
        cleanup_interval=30,
        connection_limit=1000,
        url_scheme='http',  # IIS จัดการ HTTPS ให้แล้ว — Waitress รับแค่ HTTP ภายใน
    )
